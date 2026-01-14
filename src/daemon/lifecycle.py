"""Core daemon logic for command routing, caching, and resource management.

Provides the EmailDaemon class which orchestrates all daemon operations:
- Command routing to appropriate feature handlers
- Result caching with intelligent invalidation
- Connection pool management for IMAP/SMTP
- Client connection limiting and graceful shutdown

Features
--------
- Semaphore-based client limiting (max 10 concurrent)
- Command timeout enforcement (30 seconds)
- Write command cache invalidation strategies
- Idle timeout for automatic shutdown (30 minutes)
- Metrics collection for observability

Usage Examples
--------------

The EmailDaemon is typically instantiated by run_daemon():
    >>> daemon = EmailDaemon()
    >>> await daemon.db._initialise()
    >>> result = await daemon.execute_command("inbox", {"limit": 10})

Execute with caching:
    >>> # Cacheable commands are automatically cached
    >>> result = await daemon.execute_command("view", {"id": "12345"})
    >>> # result.cached indicates if served from cache

Graceful shutdown:
    >>> await daemon.shutdown()  # Closes connections, clears cache
"""

import asyncio
import json
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Optional

from rich.console import Console

from security.key_store import KeyStore
from src.core.database import EngineManager, get_config
from src.daemon.auth import DaemonAuth, get_auth_metrics
from src.daemon.cache import CacheManager
from src.daemon.pools import ConnectionPoolManager, get_pool_metrics
from src.utils.config import ConfigManager
from src.utils.errors import DatabaseError, KernelError
from src.utils.logging import get_logger, log_event
from src.utils.paths import DATABASE_PATH

logger = get_logger(__name__)


@dataclass
class CommandResult:
    """Result of a daemon command execution"""

    success: bool
    data: Optional[str] = None
    error: Optional[str] = None
    cached: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert CommandResult to dictionary"""
        return asdict(self)


class EmailDaemon:
    """Email Daemon for managing email resources and commands"""

    WRITE_COMMANDS = {"move", "delete", "flag", "unflag", "send", "refresh", "compose"}

    CACHEABLE_COMMANDS = {
        "inbox",
        "view",
        "search",
        "attachments",
        "flagged",
        "unflagged",
    }

    INVALIDATION_STRATEGY = {
        "move": "source_and_dest_tables",
        "delete": "email_and_table",
        "flag": "email_and_flagged_cache",
        "unflag": "email_and_flagged_cache",
        "send": "sent_table",
        "refresh": "all",
        "compose": "drafts_table",
    }

    RESOURCE_LIMITS = {
        "max_concurrent_clients": 10,
        "command_timeout_seconds": 30,
        "max_queue_size": 100,
    }

    def __init__(self) -> None:
        """Initialise the EmailDaemon with config, database, cache, and connection pool"""
        self.logger = get_logger(__name__)
        self.console = Console()

        try:
            self.config = ConfigManager()
            self.keystore = KeyStore()

            self.engine_manager = EngineManager(DATABASE_PATH, get_config())

            self.connections = ConnectionPoolManager(self.config, self.keystore)
            self.cache = CacheManager(max_entries=50, ttl_seconds=60)

            self.last_activity = time.time()
            self._activity_lock = asyncio.Lock()
            self.idle_timeout = 1800  # 30 minutes

            self._max_concurrent_clients = self.RESOURCE_LIMITS[
                "max_concurrent_clients"
            ]
            self._semaphore = asyncio.Semaphore(self._max_concurrent_clients)
            self._active_clients = 0
            self._client_lock = asyncio.Lock()
            self._shutting_down = False

            self._start_time = time.time()
            self._total_requests = 0
            self._failed_requests = 0

            from src.cli.router import CommandRouter

            self.router = CommandRouter(self.console)

            self.logger.info("EmailDaemon initialised successfully")
            log_event(
                "daemon_initialised",
                {
                    "cache_max_entries": 50,
                    "cache_ttl": 60,
                    "idle_timeout": self.idle_timeout,
                    "max_concurrent_clients": self._max_concurrent_clients,
                },
            )

        except (DatabaseError, KernelError):
            raise

        except Exception as e:
            raise DatabaseError("Failed to initialise EmailDaemon") from e

    async def _acquire_client_slot(self) -> bool:
        """Acquire a slot for a new client connection"""
        try:
            acquired = await asyncio.wait_for(self._semaphore.acquire(), timeout=5.0)

            if acquired:
                async with self._client_lock:
                    self._active_clients += 1
                    self.logger.debug(
                        f"Client connected, active clients: {self._active_clients}/{self._max_concurrent_clients}"
                    )
                return True

            return False

        except asyncio.TimeoutError:
            self.logger.warning("Client connection rejected (timeout)")
            return False

    async def _release_client_slot(self) -> None:
        """Release a slot after a client disconnects"""
        async with self._client_lock:
            self._active_clients -= 1
            self.logger.debug(
                f"Client disconnected, active clients: {self._active_clients}/{self._max_concurrent_clients}"
            )
        self._semaphore.release()

    async def get_active_clients(self) -> int:
        """Get the number of active client connections"""
        async with self._client_lock:
            return self._active_clients

    async def execute_command(
        self, command: str, args: Dict[str, Any]
    ) -> CommandResult:
        """Execute a command with caching and timeout logic"""
        command_start = time.time()
        self._total_requests += 1

        try:
            async with self._activity_lock:
                self.last_activity = time.time()

            if command == "status":
                return await self._handle_status_command()

            cache_key = None
            if command in self.CACHEABLE_COMMANDS:
                cache_key = self.cache.get_cache_key(command, args)
                cached = await self.cache.get(cache_key)

                if cached:
                    output, age = cached
                    return CommandResult(
                        success=True,
                        data=output,
                        cached=True,
                        metadata={"cache_age_seconds": age},
                    )

            try:
                success = await asyncio.wait_for(
                    self.router.route(command, args),
                    timeout=self.RESOURCE_LIMITS["command_timeout_seconds"],
                )

            except ValueError as e:
                # Unknown command
                self._failed_requests += 1
                return CommandResult(success=False, error=str(e))

            except asyncio.TimeoutError:
                self._failed_requests += 1
                return CommandResult(
                    success=False,
                    error=f"Command '{command}' timed out after {self.RESOURCE_LIMITS['command_timeout_seconds']}s",
                )

            if command in self.WRITE_COMMANDS:
                await self._invalidate_cache_selective(command, args)

            command_duration = time.time() - command_start

            return CommandResult(
                success=success,
                cached=False,
                metadata={"execution_time_seconds": command_duration},
            )

        except KernelError as e:
            self._failed_requests += 1
            self.logger.exception(f"Error executing command '{command}': {e.message}")
            return CommandResult(success=False, error=e.message)

        except Exception as e:
            self._failed_requests += 1
            self.logger.exception(
                f"Unexpected error executing command '{command}': {str(e)}"
            )
            return CommandResult(success=False, error=str(e))

    async def _handle_status_command(self) -> CommandResult:
        """Handle the 'status' command to return daemon metrics"""
        uptime_seconds = time.time() - self._start_time

        status_data = {
            "daemon": {
                "uptime_seconds": uptime_seconds,
                "uptime_human_readable": self._format_uptime(uptime_seconds),
                "active_clients": await self.get_active_clients(),
                "max_clients": self._max_concurrent_clients,
                "total_requests": self._total_requests,
                "failed_requests": self._failed_requests,
                "success_rate": (
                    (
                        (self._total_requests - self._failed_requests)
                        / self._total_requests
                        * 100
                    )
                    if self._total_requests > 0
                    else 100.0
                ),
            },
            "cache": await self.cache.get_stats(),
            "pools": {
                "health": await self.connections.health_check(),
                "metrics": get_pool_metrics(),
            },
            "auth": {"metrics": get_auth_metrics()},
        }

        status_json = json.dumps(status_data, indent=2)

        return CommandResult(
            success=True, data=status_json, metadata={"command": "status"}
        )

    def _format_uptime(self, seconds: float) -> str:
        """Format uptime in a human-readable format"""
        hours, remainder = divmod(int(seconds), 3600)
        minutes, seconds = divmod(remainder, 60)

        if hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"

    async def _invalidate_cache_selective(
        self, command: str, args: Dict[str, Any]
    ) -> None:
        """Invalidate cache entries based on the command and its invalidation strategy"""
        strategy = self.INVALIDATION_STRATEGY.get(command)

        if strategy == "all":
            await self.cache.invalidate_all()

        elif strategy == "source_and_dest_tables":
            source_table = args.get("source", args.get("table", "inbox"))
            dest_table = args.get("destination", args.get("dest"))

            count = await self.cache.invalidate_table(source_table)
            if dest_table and dest_table != source_table:
                count += await self.cache.invalidate_table(dest_table)

            logger.debug(f"Invalidated {count} cache entries for move operation")

        elif strategy == "email_and_table":
            email_id = args.get("id")
            table = args.get("table", "inbox")

            if email_id:
                count = await self.cache.invalidate_email(str(email_id), table)
                logger.debug(
                    f"Invalidated {count} cache entries for email ID {email_id}"
                )

        elif strategy == "email_and_flagged_cache":
            email_id = args.get("id")
            table = args.get("table", "inbox")

            if email_id:
                count = await self.cache.invalidate_email(str(email_id), table)
                count += await self.cache.invalidate_command("flagged")
                count += await self.cache.invalidate_command("unflagged")
                logger.debug(f"Invalidated {count} cache entries for flag operation")

        elif strategy == "sent_table":
            count = await self.cache.invalidate_table("sent")
            logger.debug(f"Invalidated {count} cache entries for sent folder")

        elif strategy == "drafts_table":
            count = await self.cache.invalidate_table("drafts")
            logger.debug(f"Invalidated {count} cache entries for drafts folder")

        else:
            logger.warning(
                f"No invalidation strategy defined for command '{command}', clearing all..."
            )
            await self.cache.invalidate_all()

    async def handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """Handle incoming CLI commands with authentication"""
        slot_acquired = await self._acquire_client_slot()

        if not slot_acquired:
            self.logger.warning(
                "Rejecting client connection due to max clients reached"
            )
            error_result = CommandResult(
                success=False,
                error="Maximum number of concurrent clients reached. Please try again later.",
            )
            writer.write(json.dumps(error_result.to_dict()).encode() + b"\n")
            await writer.drain()
            writer.close()
            await writer.wait_closed()
            return

        self.logger.debug("Client connected, starting authentication")

        try:
            auth_line = await asyncio.wait_for(reader.readline(), timeout=5.0)
            if not auth_line:
                logger.warning("No authentication token received from client")
                return

            try:
                auth_data = json.loads(auth_line.decode().strip())
                provided_token = auth_data.get("token", "")

            except (json.JSONDecodeError, KeyError):
                logger.warning("Invalid authentication data received from client")
                error_result = CommandResult(
                    success=False, error="Authentication required"
                )
                writer.write(json.dumps(error_result.to_dict()).encode() + b"\n")
                await writer.drain()
                return

            if not await DaemonAuth.verify_token(provided_token):
                logger.warning("Invalid authentication token from client")
                error_result = CommandResult(
                    success=False, error="Authentication failed"
                )
                writer.write(json.dumps(error_result.to_dict()).encode() + b"\n")
                await writer.drain()
                return

            line = await asyncio.wait_for(reader.readline(), timeout=5.0)
            if not line:
                logger.warning("No command received from client")
                return

            request = json.loads(line.decode().strip())
            command = request.get("command")
            args = request.get("args", {})

            result = await self.execute_command(command, args)

            response_json = json.dumps(result.to_dict())
            writer.write(response_json.encode() + b"\n")
            await writer.drain()

        except asyncio.TimeoutError:
            self.logger.warning("Client request timed out")
            error_result = CommandResult(success=False, error="Request timed out")
            writer.write(json.dumps(error_result.to_dict()).encode() + b"\n")
            await writer.drain()

        except KernelError as e:
            self.logger.error(f"Error handling client request: {e.message}")
            error_result = CommandResult(success=False, error=e.message)
            writer.write(json.dumps(error_result.to_dict()).encode() + b"\n")
            await writer.drain()

        except Exception as e:
            self.logger.exception(f"Unexpected error handling client request: {e}")
            error_result = CommandResult(success=False, error=str(e))
            writer.write(json.dumps(error_result.to_dict()).encode() + b"\n")
            await writer.drain()

        finally:
            writer.close()
            await writer.wait_closed()
            await self._release_client_slot()
            self.logger.debug("Client connection closed")

    async def idle_checker(self) -> None:
        """Background task to check for idle timeout and shutdown if necessary"""
        try:
            while True:
                try:
                    await asyncio.sleep(60)

                    async with self._activity_lock:
                        idle_time = time.time() - self.last_activity

                    if idle_time > self.idle_timeout:
                        self.logger.info(
                            f"Daemon idle for {idle_time:.0f}s, shutting down..."
                        )
                        await self.shutdown()
                        break

                except (KernelError, Exception) as e:
                    self.logger.exception(f"Error in idle checker: {e}")
                    raise

        except asyncio.CancelledError:
            logger.debug("Idle checker cancelled")
            raise

    async def shutdown(self) -> None:
        """Shutdown the daemon gracefully"""
        if self._shutting_down:
            self.logger.warning("Shutdown already in progress")
            return

        self._shutting_down = True
        self.logger.info("Shutting down daemon...")

        try:
            shutdown_start = time.time()
            while await self.get_active_clients() > 0:
                self.logger.info("Waiting for active clients to disconnect...")
                if time.time() - shutdown_start > 30:
                    active = await self.get_active_clients()
                    self.logger.warning(
                        f"Timeout waiting for {active} clients to disconnect, forcing shutdown..."
                    )
                    break
                await asyncio.sleep(0.5)

            await self.connections.close_all()

            if self.db and hasattr(self.db, "connection_manager"):
                await self.db.connection_manager.close()
            self.db = None

            await self.cache.invalidate_all()

            from src.utils.paths import DAEMON_PID_PATH, DAEMON_SOCKET_PATH

            await asyncio.to_thread(DAEMON_PID_PATH.unlink, missing_ok=True)
            await asyncio.to_thread(DAEMON_SOCKET_PATH.unlink, missing_ok=True)

            self.logger.info("Daemon shutdown complete")
            log_event(
                "daemon_shutdown",
                {"reason": "graceful", "uptime": time.time() - self._start_time},
            )

        except (KernelError, Exception) as e:
            self.logger.exception(f"Error during shutdown: {e}")
            raise
