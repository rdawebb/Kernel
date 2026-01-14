"""Daemon entry point and main event loop.

Initialises and runs the email daemon as a background process:
- Sets up secure Unix socket for client communication
- Registers signal handlers for graceful shutdown (SIGINT, SIGTERM)
- Starts background tasks (keepalive, idle checker)
- Manages PID file for process tracking

Lifecycle
---------
1. Initialise EmailDaemon and database connection
2. Verify socket location security
3. Start Unix socket server
4. Rotate authentication token
5. Launch background keepalive and idle checker tasks
6. Serve client connections until shutdown signal

Usage
-----

Run directly:
    $ python -m src.daemon.daemon

Or programmatically:
    >>> from src.daemon import run_daemon
    >>> await run_daemon()
"""

import asyncio
import os
import signal
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.daemon.auth import DaemonAuth, SocketSecurity
from src.daemon.lifecycle import EmailDaemon
from src.utils.errors import KernelError
from src.utils.logging import get_logger, log_event
from src.utils.paths import DAEMON_PID_PATH

logger = get_logger(__name__)


async def run_daemon() -> None:
    """Main daemon event loop with socket setup"""
    daemon = None
    server = None
    keepalive_task = None
    idle_checker_task = None

    try:
        init_start = time.time()

        daemon = EmailDaemon()
        logger.info("Initialising database...")
        if daemon.db is not None and hasattr(daemon.db, "_initialise"):
            await daemon.db._initialise()
            logger.info("Database initialised")
        else:
            logger.error("daemon.db is None or missing _initialise method")
            raise AttributeError("daemon.db is None or missing _initialise method")

        init_duration = time.time() - init_start
        logger.info(f"Daemon initialisation took {init_duration:.2f}s")

        loop = asyncio.get_running_loop()

        def signal_handler(signum, frame):
            if daemon and not daemon._shutting_down:
                logger.info(f"Received signal {signum}, initiating shutdown...")
                loop.call_soon_threadsafe(
                    lambda: asyncio.create_task(daemon.shutdown())
                )

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        socket_path = SocketSecurity.get_socket_path()
        await SocketSecurity.verify_socket_location(socket_path)

        if socket_path.exists():
            logger.warning(f"Removing stale socket file: {socket_path}")
            await asyncio.to_thread(socket_path.unlink, missing_ok=True)

        server = await asyncio.start_unix_server(
            daemon.handle_client, path=str(socket_path)
        )

        await SocketSecurity.verify_socket_permissions(socket_path)

        pid_file = DAEMON_PID_PATH
        pid_file.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(pid_file.write_text, str(os.getpid()))

        await DaemonAuth.rotate_token()

        keepalive_task = asyncio.create_task(daemon.connections.keepalive_loop())
        idle_checker_task = asyncio.create_task(daemon.idle_checker())

        logger.info(f"Daemon started (PID: {os.getpid()})")
        log_event(
            "daemon_start",
            {
                "pid": os.getpid(),
                "socket": str(socket_path),
                "max_concurrent_clients": daemon._max_concurrent_clients,
                "init_duration_seconds": init_duration,
            },
        )

        async with server:
            await server.serve_forever()

    except KernelError as e:
        logger.error(f"Daemon error: {e.message}")
        sys.exit(1)

    except KeyboardInterrupt:
        logger.info("Daemon interrupted by user")

    except Exception as e:
        logger.exception(f"Daemon encountered an unexpected error: {e}")
        sys.exit(1)

    finally:
        for task in [keepalive_task, idle_checker_task]:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        if server:
            server.close()
            await server.wait_closed()

        if daemon and not daemon._shutting_down:
            try:
                await daemon.shutdown()
            except Exception as e:
                logger.exception(f"Error during daemon shutdown: {e}")


if __name__ == "__main__":
    try:
        asyncio.run(run_daemon())
    except KeyboardInterrupt:
        logger.info("Daemon terminated by user")
    except Exception as e:
        logger.exception(f"Daemon error on startup: {e}", exc_info=True)
        sys.exit(1)
