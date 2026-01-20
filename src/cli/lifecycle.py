"""Lifecycle management for Kernel CLI/Shell."""

import asyncio
import os
import threading
from typing import Optional

from src.core.database import EngineManager
from src.daemon.client import get_daemon_client
from src.utils.logging import get_logger

logger = get_logger(__name__)


class LifecycleManager:
    """Manages application lifecycle for CLI and shell modes."""

    def __init__(self, engine_manager: Optional[EngineManager] = None):
        """Initialise lifecycle manager.

        Args:
            engine_manager: Database engine manager instance (optional)
        """
        self.engine_manager = engine_manager

    async def cleanup(self) -> None:
        """Perform cleanup on application exit.

        Handles:
        - Stopping daemon
        - Closing database connections
        - Terminal state reset
        """
        # Stop daemon
        try:
            daemon_client = get_daemon_client()
            await daemon_client.stop_daemon()
        except Exception as e:
            logger.debug(f"Error stopping daemon: {e}")

        # Close database
        try:
            if self.engine_manager is not None:
                await self.engine_manager.close()
                await asyncio.sleep(0.1)  # Brief pause for cleanup
        except Exception as e:
            logger.debug(f"Error closing database: {e}")

        # Reset terminal state (Unix-like systems)
        try:
            os.system("stty sane 2>/dev/null")
        except Exception:
            pass

    def force_exit(self, exit_code: int = 0) -> None:
        """Force exit the application.

        Used when graceful shutdown fails or non-daemon threads exist.

        Args:
            exit_code: Exit code to return
        """
        # Kill any lingering daemon processes
        try:
            os.system('pkill -f "email_daemon.py" 2>/dev/null')
        except Exception:
            pass

        # Check for non-daemon threads
        active_threads = threading.enumerate()
        non_daemon_threads = [
            t
            for t in active_threads
            if not t.daemon and t != threading.current_thread()
        ]

        if non_daemon_threads:
            logger.debug(
                f"Force exiting due to {len(non_daemon_threads)} non-daemon threads"
            )
            os._exit(exit_code)
        else:
            # Normal exit
            raise SystemExit(exit_code)

    async def shutdown(self, exit_code: int = 0) -> int:
        """Perform graceful shutdown.

        Args:
            exit_code: Exit code to return

        Returns:
            Exit code
        """
        await self.cleanup()
        self.force_exit(exit_code)
        return exit_code  # Won't reach here if force_exit succeeds

    def handle_interrupt(self, exit_code: int = 130) -> int:
        """Handle keyboard interrupt (Ctrl-C).

        Args:
            exit_code: Exit code for interrupt (default: 130 = SIGINT)

        Returns:
            Exit code
        """
        logger.warning("Application interrupted by user")

        # Reset terminal and kill daemon
        try:
            os.system("stty sane 2>/dev/null")
            os.system('pkill -f "email_daemon.py" 2>/dev/null')
        except Exception:
            pass

        # Force exit
        os._exit(exit_code)

    def handle_error(self, error: Exception, exit_code: int = 1) -> int:
        """Handle fatal error.

        Args:
            error: Exception that occurred
            exit_code: Exit code to return (default: 1)

        Returns:
            Exit code
        """
        logger.error(f"Fatal error: {error}", exc_info=True)

        # Reset terminal and kill daemon
        try:
            os.system("stty sane 2>/dev/null")
            os.system('pkill -f "email_daemon.py" 2>/dev/null')
        except Exception:
            pass

        # Force exit
        os._exit(exit_code)
