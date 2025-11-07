"""
Kernel Email Daemon - Persistent resource manager and rendering service

Handles:
- Persistent database connections
- IMAP/SMTP connection pooling
- Rendering tasks for kernel operations
- Resource management with selective cache invalidation
- Secure socket management
"""

import asyncio
import json
import os
import secrets
import signal
import sys
import time
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from rich.console import Console

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from security.key_store import KeyStore
from src.core.email.imap.client import IMAPClient
from src.core.email.smtp.client import SMTPClient
from src.utils.config import ConfigManager
from src.utils.errors import (
    DatabaseError,
    FileSystemError,
    KernelError,
    safe_execute,
)
from src.utils.logging import get_logger, log_event
from src.utils.paths import DAEMON_PID_PATH, DAEMON_SOCKET_PATH, DAEMON_TOKEN_PATH

logger = get_logger(__name__)


## Connection Pools - Unified with Template Method Pattern

@dataclass
class ConnectionPool:
    """Base connection pool with timeout and keepalive."""
    
    timeout: int
    client: Optional[Any] = None
    last_used: Optional[float] = None
    
    def is_expired(self, current_time: float) -> bool:
        """Check if connection has expired."""

        if not self.client or not self.last_used:
            return True
        
        return (current_time - self.last_used) > self.timeout
    
    def update_usage(self) -> None:
        """Update last used timestamp."""

        self.last_used = time.time()
    
    def close(self, client_type: str) -> None:
        """Close and cleanup connection."""

        if self.client:
            try:
                if hasattr(self.client, "close"):
                    self.client.close()
                elif hasattr(self.client, "logout"):
                    self.client.logout()
                logger.debug(f"{client_type} connection closed")

            except Exception as e:
                logger.debug(f"Error closing {client_type} client: {e}")

            finally:
                self.client = None
                self.last_used = None


class EmailConnectionPool:
    """Base email connection pool using template method pattern."""
    
    def __init__(self, config: ConfigManager, keystore: KeyStore, timeout: int):
        self.config = config
        self.keystore = keystore
        self.pool = ConnectionPool(timeout=timeout)
        self._client_type = self._get_client_type()
    
    def get_client(self) -> Any:
        """Get or create email client (template method)."""

        current_time = time.time()
        
        if self.pool.is_expired(current_time):
            if self.pool.client:
                logger.info(f"{self._client_type} connection expired, reconnecting...")
                self.pool.close(self._client_type)
            
            # Create new client (delegated to subclass)
            account_config = self._get_account_config()
            self.pool.client = self._create_client(account_config)
            logger.info(f"{self._client_type} client connected")
            log_event(f"{self._client_type.lower()}_connected", {"timeout": self.pool.timeout})
        
        self.pool.update_usage()
        return self.pool.client
    
    def _get_account_config(self) -> Dict[str, Any]:
        """Retrieve account configuration with credentials."""

        config = self.config.account.model_dump()
        
        username = config.get("username")
        if username:
            credential_key = f"{self._get_credential_prefix()}_{username}"
            password = self.keystore.retrieve(credential_key)
            if password:
                config["password"] = password
        
        return config
    
    def close(self) -> None:
        """Close connection."""
        self.pool.close(self._client_type)
    

    ## Abstract methods for subclasses

    def _create_client(self, config: Dict[str, Any]) -> Any:
        """Create client instance. Must be implemented by subclass."""
        raise NotImplementedError
    
    def _get_client_type(self) -> str:
        """Get client type name. Must be implemented by subclass."""
        raise NotImplementedError
    
    def _get_credential_prefix(self) -> str:
        """Get credential key prefix. Must be implemented by subclass."""
        raise NotImplementedError


class IMAPConnectionPool(EmailConnectionPool):
    """IMAP connection pool."""

    CLIENT_CLASS = IMAPClient
    CLIENT_TYPE = "IMAP"
    CREDENTIAL_PREFIX = "imap"
    DEFAULT_TIMEOUT = 300  # seconds

    def __init__(self, config: ConfigManager, keystore: KeyStore, timeout: int = None):
        super().__init__(config, keystore, timeout or self.DEFAULT_TIMEOUT)
    
    def _create_client(self, config: Dict[str, Any]) -> IMAPClient:
        """Create IMAP client."""

        return self.CLIENT_CLASS(config)
    
    def _get_client_type(self) -> str:
        """Get client type name."""

        return self.CLIENT_TYPE
    
    def _get_credential_prefix(self) -> str:
        """Get credential key prefix."""

        return self.CREDENTIAL_PREFIX

    async def keepalive(self) -> None:
        """Send NOOP to keep connection alive."""

        if self.pool.client and not self.pool.is_expired(time.time()):
            try:
               self.pool.client._connection.noop()
               logger.debug(f"{self.CLIENT_TYPE} keepalive sent")

            except Exception as e:
                logger.warning(f"{self.CLIENT_TYPE} keepalive failed: {e}")
                self.pool.close(self.CLIENT_TYPE)


class SMTPConnectionPool(EmailConnectionPool):
    """SMTP connection pool."""

    CLIENT_CLASS = SMTPClient
    CLIENT_TYPE = "SMTP"
    CREDENTIAL_PREFIX = "smtp"
    DEFAULT_TIMEOUT = 60  # seconds

    def __init__(self, config: ConfigManager, keystore: KeyStore, timeout: int = None):
        super().__init__(config, keystore, timeout or self.DEFAULT_TIMEOUT)

    def _create_client(self, config: Dict[str, Any]) -> SMTPClient:
        """Create SMTP client."""

        return self.CLIENT_CLASS(
            host=config["smtp_host"],
            port=config["smtp_port"],
            username=config["username"],
            password=config["password"],
            use_tls=config.get("use_tls", True)
        )
    
    def _get_client_type(self) -> str:
        """Get client type name."""

        return self.CLIENT_TYPE

    def _get_credential_prefix(self) -> str:
        """Get credential key prefix."""

        return self.CREDENTIAL_PREFIX


class ConnectionManager:
    """Manages all connection pools with unified keepalive."""
    
    def __init__(self, config: ConfigManager, keystore: KeyStore):
        self.imap_pool = IMAPConnectionPool(config, keystore, timeout=300)
        self.smtp_pool = SMTPConnectionPool(config, keystore, timeout=60)
    
    def get_imap_client(self) -> IMAPClient:
        """Get IMAP client from pool."""

        return self.imap_pool.get_client()
    
    def get_smtp_client(self) -> SMTPClient:
        """Get SMTP client from pool."""

        return self.smtp_pool.get_client()
    
    def close_all(self) -> None:
        """Close all connections."""

        self.imap_pool.close()
        self.smtp_pool.close()
        logger.info("All connections closed")
    
    async def keepalive_loop(self) -> None:
        """Background task to keep connections alive."""

        while True:
            await asyncio.sleep(60)
            
            # Keepalive for IMAP
            await safe_execute(
                self.imap_pool.keepalive,
                default=None,
                context="imap_keepalive"
            )


## Cache Manager with Selective Invalidation

class CacheManager:
    """LRU cache with TTL and selective invalidation."""
    
    def __init__(self, max_entries: int = 50, ttl_seconds: int = 60):
        self.max_entries = max_entries
        self.ttl_seconds = ttl_seconds
        self._cache = OrderedDict()
        self._lock = asyncio.Lock()
    
    async def get_cache_key(self, command: str, args: Dict) -> str:
        """Generate cache key from command and arguments."""

        key_data = {
            "command": command,
            "table": args.get("table", "inbox"),
            "limit": args.get("limit", 50),
            "keyword": args.get("keyword", ""),
            "id": args.get("id", ""),
            "flagged": args.get("flagged", None)
        }

        return json.dumps(key_data, sort_keys=True)
    
    async def get(self, cache_key: str) -> Optional[Tuple[str, float]]:
        """Retrieve cached output if valid."""

        async with self._lock:
            if cache_key not in self._cache:
                return None

            output, timestamp = self._cache[cache_key]
            age = time.time() - timestamp
        
            if age > self.ttl_seconds:
                del self._cache[cache_key]
                logger.debug(f"Cache entry expired: {cache_key[:50]}...")
                return None
        
            self._cache.move_to_end(cache_key)
            logger.debug(f"Cache hit (age: {age:.1f}s)")
            return output, age
    
    async def set(self, cache_key: str, output: str) -> None:
        """Add to cache with LRU eviction."""

        async with self._lock:
            if len(self._cache) >= self.max_entries:
                oldest = next(iter(self._cache))
                del self._cache[oldest]
                logger.debug("Evicted oldest cache entry")

            self._cache[cache_key] = (output, time.time())
            logger.debug(f"Cache set ({len(self._cache)}/{self.max_entries} entries)")
    
    async def invalidate_all(self) -> None:
        """Invalidate all cache entries."""

        async with self._lock:
            count = len(self._cache)
            self._cache.clear()
            logger.info(f"Cache cleared: {count} entries removed")
            log_event("cache_cleared", {"entries_removed": count})

    async def invalidate_by_pattern(self, pattern: str) -> int:
        """Invalidate cache entries matching pattern."""

        async with self._lock:
            to_remove = [key for key in self._cache if pattern in key]
            for key in to_remove:
                del self._cache[key]
        
            if to_remove:
                logger.info(f"Cache invalidated by pattern '{pattern}': {len(to_remove)} entries")
                log_event("cache_invalidated_pattern", {
                    "pattern": pattern,
                    "entries_removed": len(to_remove)
                })
        
            return len(to_remove)

    async def invalidate_table(self, table: str) -> int:
        """Invalidate all entries for a specific table."""

        pattern = f'"table":"{table}"'
        return await self.invalidate_by_pattern(pattern)

    async def invalidate_email(self, email_id: str, table: Optional[str] = None) -> int:
        """Invalidate entries related to a specific email."""

        pattern = f'"id":"{email_id}"'
        count = await self.invalidate_by_pattern(pattern)

        # Also invalidate list views for the table
        if table:
            count += await self.invalidate_table(table)

        return count

    async def invalidate_search(self, keyword: str) -> int:
        """Invalidate search results containing keyword."""

        pattern = f'"keyword":"{keyword}"'
        return await self.invalidate_by_pattern(pattern)

    async def invalidate_command(self, command: str) -> int:
        """Invalidate all entries for a specific command."""

        pattern = f'"command":"{command}"'
        return await self.invalidate_by_pattern(pattern)

    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""

        async with self._lock:
            return {
                "entries": len(self._cache),
                "max_entries": self.max_entries,
                "ttl_seconds": self.ttl_seconds,
                "usage_percent": (len(self._cache) / self.max_entries * 100)
            }


## Socket Authentication

class DaemonAuth:
    """Generate and verify authentication tokens for daemon clients."""

    TOKEN_FILE = DAEMON_TOKEN_PATH
    TOKEN_LENGTH = 32  # bytes
    _lock = asyncio.Lock()

    @classmethod
    async def generate_token(cls) -> str:
        """Generate a new secure token and save to file."""

        async with cls._lock:
            token = secrets.token_hex(cls.TOKEN_LENGTH)

            cls.TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
            cls.TOKEN_FILE.write_text(token)
            cls.TOKEN_FILE.chmod(0o600)

            logger.info("Generated new daemon authentication token")
            log_event("daemon_token_generated", {"token": token})

            return token
    
    @classmethod
    async def get_token(cls) -> Optional[str]:
        """Retrieve the stored token from file."""

        async with cls._lock:
            if not cls.TOKEN_FILE.exists():
                token = secrets.token_hex(cls.TOKEN_LENGTH)
                cls.TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
                cls.TOKEN_FILE.write_text(token)
                cls.TOKEN_FILE.chmod(0o600)

                logger.info("Generated new daemon authentication token")
                log_event("daemon_token_generated", {"token": token})

                return token
            
            try:
                return cls.TOKEN_FILE.read_text().strip()

            except Exception as e:
                logger.error(f"Failed to read daemon token: {e}")
                return None
        
    @classmethod
    async def verify_token(cls, provided_token: str) -> bool:
        """Verify provided token against stored token."""

        if not provided_token:
            logger.warning("No token provided for verification")
            return False

        stored_token = await cls.get_token()
        if not stored_token:
            logger.error("No stored token available for verification")
            return False

        return secrets.compare_digest(provided_token, stored_token)
    
    @classmethod
    async def rotate_token(cls) -> str:
        """Rotate the authentication token (call when daemon restarts)."""

        async with cls._lock:
            if cls.TOKEN_FILE.exists():
                cls.TOKEN_FILE.unlink(missing_ok=True)

            token = secrets.token_hex(cls.TOKEN_LENGTH)
            cls.TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
            cls.TOKEN_FILE.write_text(token)
            cls.TOKEN_FILE.chmod(0o600)

            logger.info("Rotated daemon authentication token")
            log_event("daemon_token_rotated", {
                "timestamp": time.time(),
                "token_length": len(token)
            })

            return token


## Socket Security Verification

class SocketSecurity:
    """Verify socket file security."""
    
    @staticmethod
    def get_socket_path() -> Path:
        """Get path to daemon socket file."""

        return DAEMON_SOCKET_PATH
    
    @staticmethod
    def verify_socket_location(socket_path: Path) -> None:
        """Verify socket is in a secure location."""

        try:
            resolved_path = socket_path.resolve()
            home_dir = Path.home().resolve()
            
            # Check 1: Must be under home directory
            try:
                resolved_path.relative_to(home_dir)
            except ValueError:
                raise FileSystemError(
                    f"Socket must be in user home directory, not {resolved_path}",
                    details={"path": str(resolved_path), "home": str(home_dir)}
                )
            
            # Check 2: Must not be in /tmp
            tmp_dir = Path("/tmp").resolve()
            try:
                resolved_path.relative_to(tmp_dir)
                raise FileSystemError(
                    "Socket cannot be in /tmp (insecure location)",
                    details={"path": str(resolved_path)}
                )
            except ValueError:
                pass
            
            # Check 3: Parent directory must exist and be owned by user
            parent_dir = resolved_path.parent
            if not parent_dir.exists():
                parent_dir.mkdir(parents=True, exist_ok=True)
                parent_dir.chmod(0o700)  # Owner-only
                logger.info(f"Created secure socket directory: {parent_dir}")
            
            # Verify ownership
            stat_info = parent_dir.stat()
            if stat_info.st_uid != os.getuid():
                raise FileSystemError(
                    "Socket directory not owned by current user",
                    details={
                        "path": str(parent_dir),
                        "owner_uid": stat_info.st_uid,
                        "current_uid": os.getuid()
                    }
                )
            
            logger.info(f"Socket location verified as secure: {resolved_path}")
            log_event("socket_security_verified", {"path": str(resolved_path)})
        
        except FileSystemError:
            raise

        except Exception as e:
            raise FileSystemError(
                f"Failed to verify socket security: {str(e)}",
                details={"path": str(socket_path)}
            ) from e
    
    @staticmethod
    def secure_socket_permissions(socket_path: Path) -> None:
        """Set secure permissions on socket file."""

        if socket_path.exists():
            os.chmod(socket_path, 0o600)  # Owner read/write only
            logger.debug(f"Socket permissions set to 0600: {socket_path}")


## Email Daemon

class EmailDaemon:
    """Main daemon for managing email resources and command execution."""
    
    # Command categorization for cache management
    WRITE_COMMANDS = {"move", "delete", "flag", "unflag", "send", "refresh", "compose"}
    CACHEABLE_COMMANDS = {
        "list", "view", "search", "attachments", "attachments_list",
        "flagged", "unflagged"
    }
    
    # Cache invalidation strategy per command
    INVALIDATION_STRATEGY = {
        "move": "source_and_dest_tables",
        "delete": "email_and_table",
        "flag": "email_and_flagged_cache",
        "unflag": "email_and_flagged_cache",
        "send": "sent_table",
        "refresh": "all",
        "compose": "drafts_table"
    }

    # Resource limits
    RESOURCE_LIMITS = {
        "max_concurrent_clients": 10,
        "max_queue_size": 100,
        "max_cache_size": 1024 * 1024 * 100,  # 100 MB
    }

    def __init__(self):
        """Initialize daemon with configuration, database, connections, and cache."""

        self.logger = get_logger(__name__)
        self.console = Console()
        
        try:
            self.config = ConfigManager()
            self.keystore = KeyStore()
            
            from src.core.database import get_database
            self.db = get_database(self.config)
            
            self.connections = ConnectionManager(self.config, self.keystore)
            self.cache = CacheManager(max_entries=50, ttl_seconds=60)
            
            self.last_activity = time.time()
            self._activity_lock = asyncio.Lock()
            self.idle_timeout = 1800  # 30 minutes

            self._max_concurrent_clients = self.RESOURCE_LIMITS["max_concurrent_clients"]
            self._semaphore = asyncio.Semaphore(self._max_concurrent_clients)
            self._active_clients = 0
            self._client_lock = asyncio.Lock()
            self._shutting_down = False

            from src.cli.commands.command_registry import _ensure_initialized
            _ensure_initialized()
            self.logger.debug("Command registry initialized and cached")

            self.logger.info("Email Daemon initialized")
            log_event("daemon_initialized", {
                "cache_max_entries": 50,
                "cache_ttl": 60,
                "idle_timeout": self.idle_timeout,
                "max_concurrent_clients": self.RESOURCE_LIMITS["max_concurrent_clients"]
            })
        
        except (DatabaseError, KernelError):
            raise

        except Exception as e:
            raise DatabaseError("Failed to initialize Email Daemon") from e
    
    async def _acquire_client_slot(self) -> None:
        """Acquire a slot for a new client connection."""

        await self._semaphore.acquire()
        async with self._client_lock:
            self._active_clients += 1
            self.logger.debug(f"Client connected, active clients: {self._active_clients}/{self._max_concurrent_clients}")

    async def _release_client_slot(self) -> None:
        """Release a slot after client disconnects."""

        async with self._client_lock:
            self._active_clients -= 1
            self.logger.debug(f"Client disconnected, active clients: {self._active_clients}/{self._max_concurrent_clients}")
        self._semaphore.release()

    async def get_active_clients(self) -> int:
        """Get the number of active client connections."""

        async with self._client_lock:
            return self._active_clients
        

    ## Command Execution
    
    async def execute_command(self, command: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute command with selective cache management."""

        command_start = time.time()
        
        try:
            async with self._activity_lock:
                self.last_activity = time.time()

            from src.cli.commands.command_registry import _registry
            
            if not _registry.exists(command):
                return self._error_response(f"Unknown command: {command}")
            
            cache_key = None
            if command in self.CACHEABLE_COMMANDS:
                cache_key = await self.cache.get_cache_key(command, args)
                cached = await self.cache.get(cache_key)

                if cached:
                    output, age = cached
                    return {
                        "success": True,
                        "data": output,
                        "error": None,
                        "cached": True,
                        "metadata": {"cache_age_seconds": age}
                    }
            
            handler = _registry.get_handler(command, daemon=True)
            if not handler:
                return self._error_response(f"No daemon handler for command: {command}")

            args_with_command = {**args, "command": command}
            result = await handler(self, args_with_command)
            
            if cache_key and result.get("success"):
                await self.cache.set(cache_key, result["data"])

            if command in self.WRITE_COMMANDS:
                await self._invalidate_cache_selective(command, args)

            command_duration = time.time() - command_start

            return {
                "success": result.get("success", True),
                "data": result.get("data"),
                "error": result.get("error"),
                "cached": False,
                "metadata": {**result.get("metadata", {}), 
                             "execution_time_seconds": command_duration}
            }
        
        except KernelError as e:
            self.logger.error(f"Error executing command '{command}': {e.message}")
            return self._error_response(e.message)
        
        except Exception as e:
            self.logger.exception(f"Error executing command '{command}': {e}")
            return self._error_response(str(e))

    async def _invalidate_cache_selective(self, command: str, args: Dict[str, Any]) -> None:
        """Selectively invalidate cache based on command and arguments."""

        strategy = self.INVALIDATION_STRATEGY.get(command)
        
        if strategy == "all":
            await self.cache.invalidate_all()

        elif strategy == "source_and_dest_tables":
            source_table = args.get("source", args.get("table", "inbox"))
            dest_table = args.get("destination", args.get("dest"))
            
            count = await self.cache.invalidate_table(source_table)
            if dest_table:
                count += await self.cache.invalidate_table(dest_table)

            logger.debug(f"Invalidated {count} entries for move operation")
        
        elif strategy == "email_and_table":
            email_id = args.get("id")
            table = args.get("table", "inbox")
            
            if email_id:
                count = await self.cache.invalidate_email(str(email_id), table)
                logger.debug(f"Invalidated {count} entries for email {email_id}")
        
        elif strategy == "email_and_flagged_cache":
            email_id = args.get("id")
            table = args.get("table", "inbox")
            
            if email_id:
                count = await self.cache.invalidate_email(str(email_id), table)
                count += await self.cache.invalidate_command("flagged")
                count += await self.cache.invalidate_command("unflagged")
                logger.debug(f"Invalidated {count} entries for flag operation")
        
        elif strategy == "sent_table":
            count = await self.cache.invalidate_table("sent")
            logger.debug(f"Invalidated {count} entries for sent folder")
        
        elif strategy == "drafts_table":
            count = await self.cache.invalidate_table("drafts")
            logger.debug(f"Invalidated {count} entries for drafts folder")
        
        else:
            logger.warning(f"Unknown invalidation strategy for '{command}', clearing all cache")
            await self.cache.invalidate_all()

    def _error_response(self, error: str) -> Dict[str, Any]:
        """Create standardized error response."""

        return {
            "success": False,
            "data": None,
            "error": error,
            "cached": False,
            "metadata": {}
        }
    

    ## Client Handler
    
    async def handle_client(self, reader: asyncio.StreamReader,
                           writer: asyncio.StreamWriter) -> None:
        """Handle incoming commands from CLI with authentication"""

        await self._acquire_client_slot()
        self.logger.debug("Client connection accepted")

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
                error_response = self._error_response("Authentication required")
                writer.write(json.dumps(error_response).encode() + b"\n")
                await writer.drain()
                return

            if not await DaemonAuth.verify_token(provided_token):
                logger.warning("Invalid authentication token from client")
                error_response = self._error_response("Authentication failed")
                writer.write(json.dumps(error_response).encode() + b"\n")
                await writer.drain()
                return
            
            line = await asyncio.wait_for(reader.readline(), timeout=5.0)
            if not line:
                logger.warning("No command received from client")
                return

            request = json.loads(line.decode().strip())
            command = request.get("command")
            args = request.get("args", {})

            response = await self.execute_command(command, args)

            response_json = json.dumps(response)
            writer.write(response_json.encode() + b"\n")
            await writer.drain()

        except asyncio.TimeoutError:
            self.logger.warning("Client request timeout")
            error_response = self._error_response("Request timeout")
            writer.write(json.dumps(error_response).encode() + b"\n")
            await writer.drain()
        
        except KernelError as e:
            self.logger.error(f"Error handling request: {e.message}")
            error_response = self._error_response(e.message)
            writer.write(json.dumps(error_response).encode() + b"\n")
            await writer.drain()
        
        except Exception as e:
            self.logger.exception(f"Error handling request: {e}")
            error_response = self._error_response(str(e))
            writer.write(json.dumps(error_response).encode() + b"\n")
            await writer.drain()
        
        finally:
            writer.close()
            await writer.wait_closed()
            await self._release_client_slot()
            self.logger.debug("Client connection closed")


    ## Background Tasks
    
    async def idle_checker(self) -> None:
        """Background task to check for idle timeout and shutdown."""

        while True:
            try:
                await asyncio.sleep(60)

                async with self._activity_lock:
                    idle_time = time.time() - self.last_activity

                if idle_time > self.idle_timeout:
                    self.logger.info(f"Daemon idle for {idle_time:.0f}s, shutting down")
                    await self.shutdown()
                    break
            
            except (KernelError, Exception) as e:
                self.logger.exception(f"Error in idle checker: {e}")
                raise


    ## Cleanup and Shutdown

    async def shutdown(self) -> None:
        """Shutdown daemon and clean up resources."""

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
                    self.logger.warning(f"Timeout waiting for {active} clients, forcing shutdown")
                    break
                await asyncio.sleep(0.5)

            self.connections.close_all()
            if self.db and hasattr(self.db, 'connection_manager'):
                await self.db.connection_manager.close()
            self.db = None
            await self.cache.invalidate_all()
            
            pid_file = DAEMON_PID_PATH
            socket_path = SocketSecurity.get_socket_path()
            
            try:
                pid_file.unlink(missing_ok=True)
                socket_path.unlink(missing_ok=True)

            except Exception as e:
                raise FileSystemError("Failed to clean up daemon files") from e
            
            self.logger.info("Daemon shutdown complete")
            log_event("daemon_shutdown", {"reason": "idle_timeout"})
            sys.exit(0)
        
        except (KernelError, Exception) as e:
            self.logger.exception(f"Error during shutdown: {e}")
            raise


## Daemon Lifecycle

async def run_daemon() -> None:
    """Main daemon event loop with secure socket setup."""
    daemon = None
    try:
        daemon = EmailDaemon()

        logger.info("Initializing database...")
        await daemon.db._initialize()
        logger.info("Database initialized")

        def signal_handler(signum, frame):
            if daemon and not daemon._shutting_down:
                asyncio.create_task(daemon.shutdown())

        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
        
        socket_path = SocketSecurity.get_socket_path()
        SocketSecurity.verify_socket_location(socket_path)
        
        socket_path.unlink(missing_ok=True)

        server = await asyncio.start_unix_server(
            daemon.handle_client,
            path=str(socket_path)
        )
        
        SocketSecurity.secure_socket_permissions(socket_path)
        
        pid_file = DAEMON_PID_PATH
        pid_file.write_text(str(os.getpid()))

        await DaemonAuth.rotate_token()

        asyncio.create_task(daemon.connections.keepalive_loop())
        asyncio.create_task(daemon.idle_checker())
        
        daemon.logger.info(f"Daemon started (PID: {os.getpid()})")
        log_event("daemon_started", {
            "pid": os.getpid(),
            "socket": str(socket_path),
            "max_concurrent_clients": daemon._max_concurrent_clients
        })
        
        async with server:
            await server.serve_forever()
    
    except KernelError as e:
        logger.error(f"Daemon error: {e.message}")
        sys.exit(1)

    except KeyboardInterrupt:
        logger.info("Daemon interrupted by user")

    except Exception as e:
        logger.exception(f"Daemon encountered an error: {e}")
        sys.exit(1)

    finally:
        if daemon and not daemon._shutting_down:
            try:
                await daemon.shutdown()

            except Exception as e:
                logger.error(f"Error during final shutdown: {e}")

## Entry Point

if __name__ == "__main__":
    try:
        asyncio.run(run_daemon())
    except KeyboardInterrupt:
        logger.info("Daemon interrupted by user")
    except Exception as e:
        logger.error(f"Daemon error: {e}", exc_info=True)
        sys.exit(1)
