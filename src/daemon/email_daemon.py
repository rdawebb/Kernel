"""
Kernel Renderer Daemon - Persistent resource manager and rendering service

Handles:
- Persistent database connections
- IMAP/SMTP connection pooling
- Rendering tasks for kernel operations
- Resource management
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
from src.utils.config_manager import ConfigManager
from src.utils.log_manager import get_logger
from src.core.database import Database
from src.core.imap_client import IMAPClient
from src.core.smtp_client import SMTPClient
from security.key_store import KeyStore

logger = get_logger(__name__)


## Connection Manager

@dataclass
class ConnectionConfig:
    """Configuration for connection pooling."""

    timeout: int
    client: Optional[Any] = None
    last_used: Optional[float] = None


class ConnectionManager:
    """ Manages IMAP/SMTP connection pooling with auto-reconnection logic."""

    def __init__(self, config: ConfigManager, keystore: KeyStore):
        """Initialize connection manager with configuration and keystore."""

        self.config = config
        self.keystore = keystore

        self.imap = ConnectionConfig(timeout=300) # Add to config for customisation
        self.smtp = ConnectionConfig(timeout=60) # Add to config for customisation

        def get_imap_client(self) -> Optional[IMAPClient]:
            """Get or create an IMAP client connection."""

            return self._get_client(
                pool=self.imap,
                client_type="IMAP",
                create= self._create_imap_client
            )
        
        def get_smtp_client(self) -> Optional[SMTPClient]:
            """Get or create an SMTP client connection."""

            return self._get_client(
                pool=self.smtp,
                client_type="SMTP",
                create= self._create_smtp_client
            )
        
        def _get_client(self, pool: ConnectionConfig, client_type: str, create):
            """Get or create a client connection from the pool."""

            current_time = time.time()

            if pool.client and pool.last_used:
                idle_time = current_time - pool.last_used
                if idle_time > pool.timeout:
                    logger.info(f"{client_type} connection idle for {idle_time:.2f}s, reconnecting...")
                    self._close_client(pool, client_type)

            if pool.client is None:
                try:
                    pool.client = create()
                    pool.last_used = current_time
                    logger.info(f"{client_type} client connected.")
                except Exception as e:
                    logger.error(f"Failed to create {client_type} client: {e}")
                    return None
            
            pool.last_used = current_time

            return pool.client
        

        def _create_imap_client(self) -> IMAPClient:
            """Create and return a new IMAP client."""

            account_config = self._get_account_config()

            return IMAPClient(account_config)

        
        def _create_smtp_client(self) -> SMTPClient:
            """Create and return a new SMTP client."""

            account_config = self._get_account_config()

            return SMTPClient(
                host=account_config["smtp_host"],
                port=account_config["smtp_port"],
                username=account_config["username"],
                password=account_config["password"],
                use_tls=account_config["use_tls", True]
            )
        
        def _get_account_config(self) -> Dict[str, Any]:
            """Retrieve account configuration with credentials."""

            config = self.config.get("account", {})

            username = config.get("username")
            if username:
                password = self.keystore.get_password("kernel_imap", username)
                if password:
                    config["password"] = password
            
            return config


        def _close_client(self, pool: ConnectionConfig, client_type: str):
            """Close and clean up a client connection."""

            if pool.client:
                try:
                    if hasattr(pool.client, "close"):
                        pool.client.close()
                    elif hasattr(pool.client, "logout"):
                        pool.client.logout()
                except Exception as e:
                    logger.warning(f"Error closing {client_type} client: {e}")
                finally:
                    pool.client = None

        
        def close_all(self):
            """Close all managed connections."""

            self._close_client(self.imap, "IMAP")
            self._close_client(self.smtp, "SMTP")

        
        async def keepalive_loop(self):
            """Background task to keep connections alive."""

            while True:
                await asyncio.sleep(60)
                current_time = time.time()

                for pool, client_type in [(self.imap, "IMAP"), (self.smtp, "SMTP")]:
                    if pool.client and pool.last_used:
                        idle_time = current_time - pool.last_used
                        if idle_time > pool.timeout:
                            self._close_client(pool, client_type)


## Cache Manager

class CacheManager:
    """LRU cache with TTL for rendered outputs."""

    def __init__(self, max_entries: int = 50, ttl_seconds: int = 60):
        """Initialize cache with max entries and TTL."""

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
            "id": args.get("id", "")
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
            logger.debug(f"Cache entry expired for key: {cache_key}")
            return None
        
        self._cache.move_to_end(cache_key)
        logger.debug(f"Cache hit for key: {cache_key}")

        return output, age
    

    def set(self, cache_key: str, output: str):
        """Add to cache with LRU eviction."""

        count = len(self._cache)

        if count >= self.max_entries:
            oldest = next(iter(self._cache))
            del self._cache[oldest]
            logger.debug(f"Evicted oldest cache entry for key: {oldest}")

        self._cache[cache_key] = (output, time.time())
        logger.debug(f"Cache set for key: {cache_key} - Total entries: {count + 1}")

    
    def invalidate(self, pattern: Optional[str] = None):
        """Invalidate cache entries matching pattern or all if None."""

        if pattern is None:
            count = len(self._cache)
            self._cache.clear()
            logger.debug(f"Cleared cache, removed {count} entries.")
        else:
            to_remove = [key for key in self._cache if pattern in key]
            for key in to_remove:
                del self._cache[key]
            logger.debug(f"Invalidated {len(to_remove)} cache entries matching pattern: {pattern}")


## Email Daemon

class EmailDaemon:
    """Main daemon for managing email resources and command execution."""

    WRITE_COMMANDS = {"move", "delete", "flag", "unflag", "send", "refresh", "compose"}

    CACHEABLE_COMMANDS = {"list", "view", "search", "attachments", "attachments_list", 
                          "flagged", "unflagged"}
    
    def __init__(self):
        """Initialize daemon with configuration, database, connection and cache managers."""

        self.logger = get_logger(__name__)
        self.console = Console()

        self.config = ConfigManager()
        self.keystore = KeyStore()

        self.db = Database(self.config)
        self.db.initialize()
        self.logger.info("Database initialised with persistent connection.")

        self.connections = ConnectionManager(self.config, self.keystore)

        self.cache = CacheManager(max_entries=50, ttl_seconds=60)

        self.last_activity = time.time()
        self.idle_timeout = 1800 # Add to config for customisation

        self.logger.info("Email Daemon initialized.")

    
    ## Command Execution

    async def execute_command(self, command: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a command with given arguments, managing cache and connections."""

        self.last_activity = time.time()

        try:
            from src.cli.commands import command_registry

            if command not in command_registry:
                return self._error_response(f"Unknown command: {command}")
            
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

            handler = command_registry[command]
            result = await handler(self, args)

            if cache_key and result.get("success"):
                self.cache.set(cache_key, result["data"])

            if command in self.WRITE_COMMANDS:
                self.cache.invalidate()

            return {
                "success": result.get("success", True),
                "data": result.get("data"),
                "error": result.get("error"),
                "cached": False,
                "metadata": result.get("metadata", {})
            }
        
        except Exception as e:
            self.logger.exception(f"Error executing command '{command}': {e}")
            return self._error_response(str(e))

        
    def _error_response(self, error: str) -> Dict[str, Any]:
        """Create error response"""

        return {
            "success": False,
            "data": None,
            "error": error,
            "cached": False,
            "metadata": {}
        }
    

    ## Client Handler

    async def handle_client(self, reader: asyncio.StreamReader, 
                            writer: asyncio.StreamWriter):
        """Handle incoming commands from CLI"""

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
            self.logger.warning("Client request timeout.")
            error_response = self._error_response("Request timeout.")
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

    async def idle_checker(self):
        """Background task to check for idle timeout and shutdown."""

        while True:
            await asyncio.sleep(60)
            
            idle_time = time.time() - self.last_activity
            if idle_time > self.idle_timeout:
                self.logger.info(f"Daemon idle for {idle_time:.0f}s, shutting down.")
                self.shutdown()
                break

    
    ## Cleanup and Shutdown

    def shutdown(self):
        """Shutdown daemon and clean up resources."""

        self.logger.info("Shutting down daemon...")

        self.connections.close_all()
        self.db = None
        self.cache.invalidate()

        _get_pid_file().unlink(missing_ok=True)
        _get_socket_path().unlink(missing_ok=True)

        self.logger.info("Daemon shutdown complete.")
        sys.exit(0)


## Daemon Lifecycle

def _get_pid_file() -> Path:
    """Get path to daemon PID file."""
    return Path.home() / ".kernel" / "daemon.pid"


def _get_socket_path() -> Path:
    """Get path to daemon socket file."""
    return Path.home() / ".kernel" / "daemon.sock"


async def run_daemon():
    """Main daemon event loop."""

    daemon = EmailDaemon()

    def signal_handler(signum, frame):
        daemon.shutdown()

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    socket_path = _get_socket_path()
    socket_path.parent.mkdir(parents=True, exist_ok=True)

    socket_path.unlink(missing_ok=True)

    server = await asyncio.start_unix_server(
        daemon.handle_client,
        path=str(socket_path)
    )

    os.chmod(socket_path, 0o600)

    _get_pid_file().write_text(str(os.getpid()))

    asyncio.create_task(daemon.connections.keepalive_loop())
    asyncio.create_task(daemon.idle_checker())

    daemon.logger.info(f"Daemon started and listening for commands: {os.getpid()}")

    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    try:
        asyncio.run(run_daemon())
    except KeyboardInterrupt:
        logger.info("Daemon interrupted by user, shutting down.")
    except Exception as e:
        logger.error(f"Daemon encountered an error: {e}", exc_info=True)
        sys.exit(1)
        