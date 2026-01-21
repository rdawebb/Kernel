"""CLI client for daemon communication via Unix socket.

Handles daemon lifecycle and command execution with resilience patterns:
- DaemonClient: Start, stop, and communicate with the daemon
- CircuitBreaker: Prevent cascading failures when daemon is unavailable
- DaemonStatus: Cache availability checks to reduce overhead

Features
--------
- Automatic daemon startup when not running
- Circuit breaker opens after 3 consecutive failures
- Recovery attempts after 30-second timeout
- Cached availability status (5-second TTL)
- Graceful fallback when daemon unavailable

Usage Examples
--------------

Send a command to the daemon:
    >>> client = DaemonClient()
    >>> result = await client.send_command("inbox", {"limit": 10})
    >>> print(result["data"])

Check daemon status:
    >>> if await client.is_running():
    ...     print("Daemon is running")
    ... else:
    ...     await client.start()

Circuit breaker status:
    >>> if client.circuit_breaker.can_attempt():
    ...     result = await client.send_command("search", {"query": "test"})
"""

import asyncio
import json
import os
import pprint
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional

from src.utils.errors import (
    FileSystemError,
    KernelError,
    NetworkError,
    NetworkTimeoutError,
)
from src.utils.logging import get_logger, log_event
from src.utils.paths import DAEMON_PID_PATH, DAEMON_SOCKET_PATH

logger = get_logger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failures detected, daemon unavailable
    HALF_OPEN = "half_open"  # Testing if daemon recovered


@dataclass
class CircuitBreaker:
    """Circuit breaker for daemon connection failures."""

    failure_threshold: int = 3
    recovery_timeout: int = 30  # seconds
    half_open_timeout: int = 10  # seconds

    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    last_failure_time: Optional[datetime] = None
    last_state_change: Optional[datetime] = None

    def record_success(self) -> None:
        """Record successful daemon communication."""

        if self.state != CircuitState.CLOSED:
            logger.info("Circuit breaker: daemon recovered, closing circuit")
            log_event("circuit_breaker_closed", {"previous_state": self.state.value})

        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = None
        self.last_state_change = datetime.now()

    def record_failure(self) -> None:
        """Record daemon communication failure."""

        self.failure_count += 1
        self.last_failure_time = datetime.now()

        if (
            self.state == CircuitState.CLOSED
            and self.failure_count >= self.failure_threshold
        ):
            logger.warning(
                f"Circuit breaker: opening after {self.failure_count} failures"
            )
            self.state = CircuitState.OPEN
            self.last_state_change = datetime.now()
            log_event("circuit_breaker_opened", {"failure_count": self.failure_count})

        elif self.state == CircuitState.HALF_OPEN:
            logger.warning("Circuit breaker: test failed, reopening circuit")
            self.state = CircuitState.OPEN
            self.last_state_change = datetime.now()
            log_event("circuit_breaker_reopened", {"failure_count": self.failure_count})

    def can_attempt(self) -> bool:
        """Check if we can attempt daemon connection."""

        now = datetime.now()

        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            if self.last_state_change:
                time_since_open = (now - self.last_state_change).total_seconds()
                if time_since_open >= self.recovery_timeout:
                    logger.info("Circuit breaker: entering half-open state for testing")
                    self.state = CircuitState.HALF_OPEN
                    self.last_state_change = now
                    log_event(
                        "circuit_breaker_half_open",
                        {"time_since_open": time_since_open},
                    )
                    return True
            return False

        # HALF_OPEN - allow one attempt
        if self.state == CircuitState.HALF_OPEN:
            return True

        return False

    def reset(self) -> None:
        """Reset circuit breaker to initial state."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = None
        self.last_state_change = None


@dataclass
class DaemonStatus:
    """Cached daemon availability status."""

    is_available: bool = False
    last_check: Optional[datetime] = None
    cache_duration: int = 5  # seconds

    def is_valid(self) -> bool:
        """Check if cached status is still valid."""
        if self.last_check is None:
            return False

        age = (datetime.now() - self.last_check).total_seconds()
        return age < self.cache_duration

    def update(self, available: bool) -> None:
        """Update cached status."""
        self.is_available = available
        self.last_check = datetime.now()

    def invalidate(self) -> None:
        """Invalidate cached status."""
        self.last_check = None


class DaemonExecutionStrategy:
    """Execute commands via daemon."""

    def __init__(self, client: "DaemonClient"):
        self.client = client

    async def execute(self, command: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute command via daemon."""

        if not self.client.circuit_breaker.can_attempt():
            logger.debug("Circuit breaker open, skipping daemon attempt")
            raise NetworkError("Daemon unavailable (circuit breaker open)")

        if not self.client.daemon_status.is_valid():
            is_running = self.client._check_daemon_running()
            self.client.daemon_status.update(is_running)

        if not self.client.daemon_status.is_available:
            if not await self.client._start_daemon():
                self.client.circuit_breaker.record_failure()
                raise NetworkError("Failed to start daemon")

        try:
            result = await self._execute_via_socket(command, args)

            self.client.circuit_breaker.record_success()
            self.client.daemon_status.update(True)

            result["via_daemon"] = True
            return result

        except Exception:
            self.client.circuit_breaker.record_failure()
            self.client.daemon_status.update(False)
            raise

    async def _execute_via_socket(
        self, command: str, args: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute command via Unix socket."""

        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_unix_connection(path=str(self.client.SOCKET_PATH)),
                timeout=self.client.CONNECT_TIMEOUT,
            )

        except asyncio.TimeoutError as e:
            raise NetworkTimeoutError("Failed to connect to daemon (timeout)") from e

        except OSError as e:
            raise NetworkError(f"Failed to connect to daemon socket: {str(e)}") from e

        try:
            # Send authentication token first
            from src.utils.paths import DAEMON_TOKEN_PATH

            try:
                token = DAEMON_TOKEN_PATH.read_text().strip()
                auth_request = json.dumps({"token": token})
                writer.write(auth_request.encode() + b"\n")
                await writer.drain()
            except FileNotFoundError:
                raise NetworkError("Daemon token not found - daemon may not be running")

            # Send command
            request = json.dumps({"command": command, "args": args})

            writer.write(request.encode() + b"\n")
            await writer.drain()

            try:
                line = await asyncio.wait_for(
                    reader.readline(), timeout=self.client.COMMAND_TIMEOUT
                )
            except asyncio.TimeoutError as e:
                raise NetworkTimeoutError("Daemon command timeout") from e

            if not line:
                raise NetworkError("Daemon sent empty response")

            response = json.loads(line.decode().strip())
            return response

        finally:
            try:
                writer.close()
                await writer.wait_closed()

            except Exception:
                pass


class FallbackExecutionStrategy:
    """Execute commands directly without daemon."""

    def __init__(self, client: "DaemonClient"):
        self.client = client
        self.router = None

    def get_router(self):
        """Lazy load CLI CommandRouter."""
        if self.router is None:
            from src.cli.router import CommandRouter

            self.router = CommandRouter()

        return self.router

    async def execute(self, command: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute command directly."""

        logger.debug(f"Fallback: executing command '{command}' directly")

        try:
            router = self.get_router()
            success = await router.route(command, args)

            return {
                "success": success,
                "data": None,
                "error": None,
                "cached": False,
                "metadata": {},
                "via_daemon": False,
            }

        except ValueError as e:
            logger.exception(f"Unknown command error: {str(e)}")
            return {
                "success": False,
                "data": None,
                "error": str(e),
                "cached": False,
                "metadata": {},
                "via_daemon": False,
            }

        except KernelError as e:
            logger.exception(f"Direct execution error: {e.message}")
            return {
                "success": False,
                "data": None,
                "error": e.message,
                "cached": False,
                "metadata": {},
                "via_daemon": False,
            }
        except Exception as e:
            logger.exception(f"Direct execution error: {e}")
            return {
                "success": False,
                "data": None,
                "error": str(e),
                "cached": False,
                "metadata": {},
                "via_daemon": False,
            }


class DaemonClient:
    """Client for communicating with EmailDaemon with authentication"""

    SOCKET_PATH = DAEMON_SOCKET_PATH
    PID_FILE = DAEMON_PID_PATH
    DAEMON_SCRIPT = Path(__file__).parent / "daemon.py"

    # Timeouts
    CONNECT_TIMEOUT = 5
    COMMAND_TIMEOUT = 10
    DAEMON_START_TIMEOUT = 5

    def __init__(self, fallback_mode: bool = True, disable_daemon: bool = False):
        """initialise daemon client."""

        self.fallback_mode = fallback_mode
        self.disable_daemon = disable_daemon

        self.circuit_breaker = CircuitBreaker(
            failure_threshold=3, recovery_timeout=30, half_open_timeout=10
        )

        self.daemon_status = DaemonStatus(cache_duration=5)

        self._daemon_strategy = DaemonExecutionStrategy(self)
        self._fallback_strategy = FallbackExecutionStrategy(self)

    ## Daemon Lifecycle

    def is_daemon_running(self) -> bool:
        """Check if daemon process is running."""

        if self.daemon_status.is_valid():
            return self.daemon_status.is_available

        is_running = self._check_daemon_running()
        self.daemon_status.update(is_running)
        return is_running

    def _check_daemon_running(self) -> bool:
        """Actually check if daemon is running (no cache)."""
        if not self.PID_FILE.exists():
            return False

        try:
            pid = int(self.PID_FILE.read_text().strip())
            os.kill(pid, 0)
            return True

        except (ValueError, OSError, ProcessLookupError):
            try:
                self.PID_FILE.unlink(missing_ok=True)

            except Exception:
                pass

            return False

    async def start_daemon(self) -> bool:
        """Start daemon in background."""

        result = await self._start_daemon()

        if result:
            self.daemon_status.update(True)
            self.circuit_breaker.reset()
        else:
            self.daemon_status.update(False)
            self.circuit_breaker.record_failure()

        return result

    async def _start_daemon(self) -> bool:
        """Internal daemon startup logic."""

        if self._check_daemon_running():
            logger.debug("Daemon already running")
            return True

        logger.info("Starting daemon...")

        try:
            python_exe = self._find_python_executable()

            try:
                # Capture stderr to a temp file for debugging
                import tempfile

                stderr_file = tempfile.NamedTemporaryFile(
                    mode="w+", delete=False, suffix=".log"
                )
                stderr_path = stderr_file.name
                stderr_file.close()

                process = subprocess.Popen(
                    [python_exe, str(self.DAEMON_SCRIPT)],
                    stdout=subprocess.DEVNULL,
                    stderr=open(stderr_path, "w"),
                    start_new_session=True,
                )
            except FileNotFoundError as e:
                raise FileSystemError(
                    f"Python executable not found: {python_exe}"
                ) from e

            except Exception as e:
                raise NetworkError(f"Failed to spawn daemon process: {str(e)}") from e

            start_time = time.time()
            while time.time() - start_time < self.DAEMON_START_TIMEOUT:
                if self.SOCKET_PATH.exists() and self._check_daemon_running():
                    logger.info(f"Daemon started (PID: {process.pid})")
                    log_event("daemon_started", {"pid": process.pid})
                    return True
                await asyncio.sleep(0.1)

            # Timeout - try to read stderr for debugging
            logger.error("Daemon failed to start (timeout)")
            try:
                if stderr_path and Path(stderr_path).exists():
                    with open(stderr_path, "r") as f:
                        stderr_content = f.read()
                        if stderr_content:
                            logger.error(f"Daemon stderr:\n{stderr_content}")
                        Path(stderr_path).unlink()  # Clean up
            except Exception as e:
                logger.debug(f"Could not read daemon stderr: {e}")

            return False

        except KernelError:
            raise

        except Exception as e:
            logger.error(f"Failed to start daemon: {str(e)}")
            return False

    async def stop_daemon(self) -> None:
        """Stop running daemon."""

        if not self._check_daemon_running():
            logger.debug("Daemon not running")
            return

        try:
            pid = int(self.PID_FILE.read_text().strip())
            try:
                os.kill(pid, 15)  # SIGTERM
                logger.info("Daemon stopped")
                log_event("daemon_stopped", {"pid": pid})

                self.daemon_status.update(False)
                self.circuit_breaker.reset()

            except ProcessLookupError as e:
                raise NetworkError(f"Failed to stop daemon process {pid}") from e

            except Exception as e:
                raise NetworkError(f"Error stopping daemon: {str(e)}") from e

        except KernelError:
            raise

        except Exception as e:
            raise FileSystemError(f"Failed to read PID file: {str(e)}") from e

    def _find_python_executable(self) -> str:
        """Find appropriate Python executable."""

        venv_path = os.environ.get("VIRTUAL_ENV")

        if not venv_path:
            project_root = Path(__file__).parent.parent.parent
            for venv_name in ["venv", ".venv", "env"]:
                candidate = project_root / venv_name
                if candidate.exists():
                    venv_path = str(candidate)
                    break

        if venv_path:
            venv_python = Path(venv_path) / "bin" / "python"
            if venv_python.exists():
                logger.debug(f"Using venv Python: {venv_python}")
                return str(venv_python)

        return sys.executable

    ## Command Execution

    async def execute_command(
        self, command: str, args: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute command using appropriate strategy."""

        if self.disable_daemon:
            return await self._fallback_strategy.execute(command, args)

        if not self.circuit_breaker.can_attempt() and self.fallback_mode:
            logger.debug("Using fallback due to open circuit breaker")
            return await self._fallback_strategy.execute(command, args)

        try:
            return await self._daemon_strategy.execute(command, args)

        except (NetworkError, NetworkTimeoutError) as e:
            if self.fallback_mode:
                logger.warning(
                    f"Daemon execution failed, using fallback: {e.message if isinstance(e, KernelError) else str(e)}"
                )
                return await self._fallback_strategy.execute(command, args)
            else:
                return {
                    "success": False,
                    "data": None,
                    "error": "Daemon unavailable and fallback disabled",
                    "cached": False,
                    "metadata": {},
                    "via_daemon": False,
                }

        except Exception as e:
            logger.exception(f"Unexpected error during command execution: {e}")

            if self.fallback_mode:
                return await self._fallback_strategy.execute(command, args)
            else:
                return {
                    "success": False,
                    "data": None,
                    "error": str(e),
                    "cached": False,
                    "metadata": {},
                    "via_daemon": False,
                }

    async def get_daemon_status(self) -> Dict[str, Any]:
        """Check and return daemon availability status."""
        try:
            result = await self.execute_command("status", {})

            if result["success"] and result["data"]:
                status_data = json.loads(result["data"])
                return status_data
            else:
                logger.warning(f"Failed to get daemon status: {result.get('error')}")
                return {"error": result.get("error")}

        except Exception as e:
            logger.error(f"Error getting daemon status: {e}")
            return {"error": str(e)}

    def format_status(self, status_data: Dict[str, Any]) -> str:
        """Format daemon status for display."""
        return pprint.pformat(status_data, indent=2, width=100)

    ## Status & Debug

    def get_status(self) -> Dict[str, Any]:
        """Get current daemon client status."""

        return {
            "daemon_running": self.is_daemon_running(),
            "circuit_breaker": {
                "state": self.circuit_breaker.state.value,
                "failure_count": self.circuit_breaker.failure_count,
                "can_attempt": self.circuit_breaker.can_attempt(),
            },
            "cache": {
                "is_valid": self.daemon_status.is_valid(),
                "is_available": self.daemon_status.is_available,
                "age_seconds": (
                    (datetime.now() - self.daemon_status.last_check).total_seconds()
                    if self.daemon_status.last_check
                    else None
                ),
            },
            "settings": {
                "fallback_mode": self.fallback_mode,
                "disable_daemon": self.disable_daemon,
            },
        }

    def reset_circuit_breaker(self) -> None:
        """Manually reset circuit breaker (for debugging/recovery)."""
        logger.info("Manually resetting circuit breaker")
        self.circuit_breaker.reset()
        self.daemon_status.invalidate()


## Convenience Functions

_client = None


def get_daemon_client() -> DaemonClient:
    """Get or create singleton daemon client."""
    global _client
    if _client is None:
        _client = DaemonClient(fallback_mode=True)

    return _client


async def execute_via_daemon(command: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """Execute command via daemon (convenience function)."""
    client = get_daemon_client()

    return await client.execute_command(command, args)


async def ensure_daemon_started() -> None:
    """Ensure daemon is running."""
    client = get_daemon_client()
    if not client.is_daemon_running():
        try:
            await client.start_daemon()

        except KernelError as e:
            logger.error(f"Failed to start daemon: {e.message}")
            raise

        except Exception as e:
            logger.error(f"Failed to start daemon: {e}")
            raise
