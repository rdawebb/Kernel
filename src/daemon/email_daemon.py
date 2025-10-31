"""
Kernel Renderer Daemon - Persistent resource manager and rendering service

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
from src.core.database import Database
from src.core.imap_client import IMAPClient
from src.core.smtp_client import SMTPClient
from src.utils.config_manager import ConfigManager
from src.utils.error_handling import (
    DatabaseError,
    FileSystemError,
    KernelError,
    safe_execute,
)
from src.utils.log_manager import get_logger, log_event
from src.utils.paths import DAEMON_PID_PATH, DAEMON_SOCKET_PATH

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
                logger.warning(f"Error closing {client_type} client: {e}")

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
    
    def __init__(self, config: ConfigManager, keystore: KeyStore, timeout: int = 300):
        super().__init__(config, keystore, timeout)
    
    def _create_client(self, config: Dict[str, Any]) -> IMAPClient:
        """Create IMAP client."""

        return IMAPClient(config)
    
    def _get_client_type(self) -> str:
        """Get client type name."""

        return "IMAP"
    
    def _get_credential_prefix(self) -> str:
        """Get credential key prefix."""

        return "imap"
    
    async def keepalive(self) -> None:
        """Send NOOP to keep connection alive."""

        if self.pool.client and not self.pool.is_expired(time.time()):
            try:
                if hasattr(self.pool.client, 'noop'):
                    self.pool.client.noop()
                    logger.debug("IMAP keepalive sent")

            except Exception as e:
                logger.warning(f"IMAP keepalive failed: {e}")
                self.pool.close("IMAP")


class SMTPConnectionPool(EmailConnectionPool):
    """SMTP connection pool."""
    
    def __init__(self, config: ConfigManager, keystore: KeyStore, timeout: int = 60):
        super().__init__(config, keystore, timeout)
    
    def _create_client(self, config: Dict[str, Any]) -> SMTPClient:
        """Create SMTP client."""

        return SMTPClient(
            host=config["smtp_host"],
            port=config["smtp_port"],
            username=config["username"],
            password=config["password"],
            use_tls=config.get("use_tls", True)
        )
    
    def _get_client_type(self) -> str:
        """Get client type name."""

        return "SMTP"
    
    def _get_credential_prefix(self) -> str:
        """Get credential key prefix."""

        return "smtp"


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
    
    def get_cache_key(self, command: str, args: Dict) -> str:
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
    
    def get(self, cache_key: str) -> Optional[Tuple[str, float]]:
        """Retrieve cached output if valid."""

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
    
    def set(self, cache_key: str, output: str) -> None:
        """Add to cache with LRU eviction."""

        if len(self._cache) >= self.max_entries:
            oldest = next(iter(self._cache))
            del self._cache[oldest]
            logger.debug("Evicted oldest cache entry")
        
        self._cache[cache_key] = (output, time.time())
        logger.debug(f"Cache set ({len(self._cache)}/{self.max_entries} entries)")
    
    def invalidate_all(self) -> None:
        """Invalidate all cache entries."""

        count = len(self._cache)
        self._cache.clear()
        logger.info(f"Cache cleared: {count} entries removed")
        log_event("cache_cleared", {"entries_removed": count})
    
    def invalidate_by_pattern(self, pattern: str) -> int:
        """Invalidate cache entries matching pattern."""

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
    
    def invalidate_table(self, table: str) -> int:
        """Invalidate all entries for a specific table."""

        pattern = f'"table":"{table}"'
        return self.invalidate_by_pattern(pattern)
    
    def invalidate_email(self, email_id: str, table: Optional[str] = None) -> int:
        """Invalidate entries related to a specific email."""

        pattern = f'"id":"{email_id}"'
        count = self.invalidate_by_pattern(pattern)
        
        # Also invalidate list views for the table
        if table:
            count += self.invalidate_table(table)
        
        return count
    
    def invalidate_search(self, keyword: str) -> int:
        """Invalidate search results containing keyword."""

        pattern = f'"keyword":"{keyword}"'
        return self.invalidate_by_pattern(pattern)
    
    def invalidate_command(self, command: str) -> int:
        """Invalidate all entries for a specific command."""

        pattern = f'"command":"{command}"'
        return self.invalidate_by_pattern(pattern)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""

        return {
            "entries": len(self._cache),
            "max_entries": self.max_entries,
            "ttl_seconds": self.ttl_seconds,
            "usage_percent": (len(self._cache) / self.max_entries * 100)
        }


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
    
    def __init__(self):
        """Initialize daemon with configuration, database, connections, and cache."""

        self.logger = get_logger(__name__)
        self.console = Console()
        
        try:
            self.config = ConfigManager()
            self.keystore = KeyStore()
            
            self.db = Database(self.config)
            self.db._initialize()
            self.logger.info("Database initialized with persistent connection")
            
            self.connections = ConnectionManager(self.config, self.keystore)
            self.cache = CacheManager(max_entries=50, ttl_seconds=60)
            
            self.last_activity = time.time()
            self.idle_timeout = 1800  # 30 minutes
            
            self.logger.info("Email Daemon initialized")
            log_event("daemon_initialized", {
                "cache_max_entries": 50,
                "cache_ttl": 60,
                "idle_timeout": self.idle_timeout
            })
        
        except (DatabaseError, KernelError):
            raise

        except Exception as e:
            raise DatabaseError("Failed to initialize Email Daemon") from e
    

    ## Command Execution
    
    async def execute_command(self, command: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute command with selective cache management."""

        self.last_activity = time.time()
        
        try:
            from src.cli.commands import _registry
            
            if not _registry.exists(command):
                return self._error_response(f"Unknown command: {command}")
            
            # Try cache for cacheable commands
            cache_key = None
            if command in self.CACHEABLE_COMMANDS:
                cache_key = self.cache.get_cache_key(command, args)
                cached = self.cache.get(cache_key)
                
                if cached:
                    output, age = cached
                    return {
                        "success": True,
                        "data": output,
                        "error": None,
                        "cached": True,
                        "metadata": {"cache_age_seconds": age}
                    }
            
            # Execute command
            handler = _registry.get_handler(command)
            result = await handler(self, args)
            
            # Cache successful results
            if cache_key and result.get("success"):
                self.cache.set(cache_key, result["data"])
            
            # Selective cache invalidation for write commands
            if command in self.WRITE_COMMANDS:
                self._invalidate_cache_selective(command, args)
            
            return {
                "success": result.get("success", True),
                "data": result.get("data"),
                "error": result.get("error"),
                "cached": False,
                "metadata": result.get("metadata", {})
            }
        
        except KernelError as e:
            self.logger.error(f"Error executing command '{command}': {e.message}")
            return self._error_response(e.message)
        
        except Exception as e:
            self.logger.exception(f"Error executing command '{command}': {e}")
            return self._error_response(str(e))
    
    def _invalidate_cache_selective(self, command: str, args: Dict[str, Any]) -> None:
        """Selectively invalidate cache based on command and arguments."""

        strategy = self.INVALIDATION_STRATEGY.get(command)
        
        if strategy == "all":
            self.cache.invalidate_all()
        
        elif strategy == "source_and_dest_tables":
            # Move command - invalidate both tables
            source_table = args.get("source", args.get("table", "inbox"))
            dest_table = args.get("destination", args.get("dest"))
            
            count = self.cache.invalidate_table(source_table)
            if dest_table:
                count += self.cache.invalidate_table(dest_table)
            
            logger.debug(f"Invalidated {count} entries for move operation")
        
        elif strategy == "email_and_table":
            # Delete - invalidate email and table
            email_id = args.get("id")
            table = args.get("table", "inbox")
            
            if email_id:
                count = self.cache.invalidate_email(str(email_id), table)
                logger.debug(f"Invalidated {count} entries for email {email_id}")
        
        elif strategy == "email_and_flagged_cache":
            # Flag/unflag - invalidate email and flagged lists
            email_id = args.get("id")
            table = args.get("table", "inbox")
            
            if email_id:
                count = self.cache.invalidate_email(str(email_id), table)
                count += self.cache.invalidate_command("flagged")
                count += self.cache.invalidate_command("unflagged")
                logger.debug(f"Invalidated {count} entries for flag operation")
        
        elif strategy == "sent_table":
            # Send - invalidate sent folder
            count = self.cache.invalidate_table("sent")
            logger.debug(f"Invalidated {count} entries for sent folder")
        
        elif strategy == "drafts_table":
            # Compose - invalidate drafts folder
            count = self.cache.invalidate_table("drafts")
            logger.debug(f"Invalidated {count} entries for drafts folder")
        
        else:
            # Unknown command - invalidate all to be safe
            logger.warning(f"Unknown invalidation strategy for '{command}', clearing all cache")
            self.cache.invalidate_all()
    
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
        """Handle incoming commands from CLI."""

        try:
            line = await asyncio.wait_for(reader.readline(), timeout=5.0)
            if not line:
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
    

    ## Background Tasks
    
    async def idle_checker(self) -> None:
        """Background task to check for idle timeout and shutdown."""

        while True:
            try:
                await asyncio.sleep(60)
                
                idle_time = time.time() - self.last_activity
                if idle_time > self.idle_timeout:
                    self.logger.info(f"Daemon idle for {idle_time:.0f}s, shutting down")
                    self.shutdown()
                    break
            
            except (KernelError, Exception) as e:
                self.logger.exception(f"Error in idle checker: {e}")
                raise


    ## Cleanup and Shutdown
    
    def shutdown(self) -> None:
        """Shutdown daemon and clean up resources."""

        self.logger.info("Shutting down daemon...")
        
        try:
            self.connections.close_all()
            self.db = None
            self.cache.invalidate_all()
            
            # Clean up files
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
    try:
        daemon = EmailDaemon()
        
        def signal_handler(signum, frame):
            daemon.shutdown()
        
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
        
        # Verify socket security
        socket_path = SocketSecurity.get_socket_path()
        SocketSecurity.verify_socket_location(socket_path)
        
        # Remove old socket if exists
        socket_path.unlink(missing_ok=True)
        
        # Start server
        server = await asyncio.start_unix_server(
            daemon.handle_client,
            path=str(socket_path)
        )
        
        # Set secure permissions
        SocketSecurity.secure_socket_permissions(socket_path)
        
        # Write PID file
        pid_file = DAEMON_PID_PATH
        pid_file.write_text(str(os.getpid()))
        
        # Start background tasks
        asyncio.create_task(daemon.connections.keepalive_loop())
        asyncio.create_task(daemon.idle_checker())
        
        daemon.logger.info(f"Daemon started (PID: {os.getpid()})")
        log_event("daemon_started", {
            "pid": os.getpid(),
            "socket": str(socket_path)
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


if __name__ == "__main__":
    try:
        asyncio.run(run_daemon())
    except KeyboardInterrupt:
        logger.info("Daemon interrupted by user")
    except Exception as e:
        logger.error(f"Daemon error: {e}", exc_info=True)
        sys.exit(1)
