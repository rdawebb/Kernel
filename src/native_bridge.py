"""Bridge to communicate with native Go backend."""

import asyncio
import json
import os
import socket
import subprocess
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, Optional

from src.utils.logging import get_logger

logger = get_logger(__name__)


class NativeBridge:
    """Manages the native Go process and communication via Unix socket."""

    def __init__(self, socket_path: Optional[str] = None):
        """Initialise the native bridge.

        Args:
            socket_path: Path to Unix socket (auto-generated if None)
        """
        self.socket_path = socket_path or f"/tmp/kernel-{os.getpid()}.sock"
        self.process: Optional[subprocess.Popen] = None
        self._sock: Optional[socket.socket] = None
        self._lock = asyncio.Lock()
        self._connected = False

    async def start(self) -> None:
        """Start the native Go process."""
        if self._connected:
            return

        native_binary = self._find_native_binary()
        if not native_binary:
            raise FileNotFoundError(
                "Native binary not found. Run 'make build' in native/ directory"
            )

        logger.info(f"Starting native process: {native_binary}")

        # Start the Go process
        env = os.environ.copy()
        env["NATIVE_SOCKET_PATH"] = self.socket_path

        self.process = subprocess.Popen(
            [str(native_binary)],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Wait for socket to be ready (max 5 seconds)
        start_time = time.time()
        while time.time() - start_time < 5:
            if os.path.exists(self.socket_path):
                break
            await asyncio.sleep(0.1)
        else:
            self._kill_process()
            raise TimeoutError("Native process did not create socket in time")

        await self._connect_socket()
        self._connected = True
        logger.info("Native bridge connected")

    async def _connect_socket(self) -> None:
        """Connect to the Unix socket."""
        self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._sock.connect(self.socket_path)
        self._sock.settimeout(30.0)  # 30 second timeout

    def _find_native_binary(self) -> Optional[Path]:
        """Find the native binary."""
        current_file = Path(__file__)
        project_root = current_file.parent.parent

        possible_paths = [
            project_root / "native" / "build" / "kernel-native",
            project_root / "build" / "kernel-native",
            Path("/usr/local/bin/kernel-native"),
        ]

        for path in possible_paths:
            if path.exists() and path.is_file():
                return path

        return None

    async def call(
        self, module: str, action: str, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Call a native function.

        Args:
            module: Module name ("imap" or "smtp")
            action: Action name ("connect", "fetch", etc.)
            params: Action parameters

        Returns:
            Response data from native backend

        Raises:
            Exception: If the call fails
        """
        if not self._connected:
            await self.start()

        async with self._lock:
            request = {"module": module, "action": action, "params": params}

            request_json = json.dumps(request) + "\n"
            if self._sock is None:
                raise ConnectionError("Socket is not connected")
            self._sock.sendall(request_json.encode("utf-8"))

            response_data = b""
            while True:
                chunk = self._sock.recv(4096)
                if not chunk:
                    raise ConnectionError("Socket closed by server")

                response_data += chunk
                if b"\n" in chunk:
                    break

            response = json.loads(response_data.decode("utf-8"))

            if not response.get("success", False):
                error = response.get("error", "Unknown error")
                raise Exception(f"Native call failed: {error}")

            return response.get("data", {})

    async def stop(self) -> None:
        """Stop the native process and clean up."""
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None

        self._kill_process()

        if os.path.exists(self.socket_path):
            try:
                os.unlink(self.socket_path)
            except Exception:
                pass

        self._connected = False
        logger.info("Native bridge stopped")

    def _kill_process(self) -> None:
        """Kill the native process."""
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
            except Exception:
                pass
            finally:
                self.process = None

    async def __aenter__(self):
        """Enter async context manager."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context manager."""
        await self.stop()


# Global singleton instance
_bridge: Optional[NativeBridge] = None
_bridge_lock = asyncio.Lock()


async def get_bridge() -> NativeBridge:
    """Get the global native bridge instance.

    Returns:
        NativeBridge instance (starts it if not already running)
    """
    global _bridge

    async with _bridge_lock:
        if _bridge is None:
            _bridge = NativeBridge()
            await _bridge.start()

    return _bridge


@asynccontextmanager
async def native_bridge():
    """Context manager for native bridge lifecycle.

    Yields:
        NativeBridge instance

    Example:
        async with native_bridge() as bridge:
            result = await bridge.call("imap", "connect", {...})
    """
    bridge = await get_bridge()
    try:
        yield bridge
    finally:
        # Keep alive, will be stopped when process exits
        pass
