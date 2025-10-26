"""
Kernel Renderer Daemon - Persistent resource manager and rendering service

Manages:
- Database connections and query caching
- IMAP/SMTP connection pooling  
- Configuration management (hot-reload capable)
- Credential management via KeyStore
- Email table rendering with Rich
- Render result caching (LRU with TTL)
- Auto-shutdown on idle timeout

The daemon runs once in the background, avoiding expensive imports and 
initialization on every CLI command execution.

Communication Protocol:
- Request: JSON with {command: str, args: dict}
- Response: JSON with {success: bool, data: any, error: str, cached: bool}
"""

import asyncio
import json
import os
import signal
import sys
import time
from pathlib import Path
from typing import Optional, Dict, Any
from collections import OrderedDict

# Rich imports (loaded once at daemon startup)
from rich.console import Console

# Your app imports - loaded at daemon startup, not at each CLI invocation
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from src.utils.config_manager import ConfigManager
from src.utils.log_manager import get_logger
from src.core.db_manager import DatabaseManager
from src.core.imap_client import IMAPClient
from src.core.smtp_client import SMTPClient
from security.key_store import KeyStore


logger = get_logger(__name__)


class RendererDaemon:
    """
    Central daemon managing email app resources and command execution.
    
    Provides:
    - Persistent IMAP/SMTP connections (connection pooling)
    - Configuration caching with hot-reload
    - Credential management via KeyStore
    - Database query result caching
    - Email table rendering with configurable columns
    - LRU render cache with TTL
    - Automatic idle shutdown (30 minutes)
    """
    
    def __init__(self):
        """Initialize daemon with all persistent resources."""
        self.logger = get_logger(__name__)
        self.console = Console()
        
        # Initialize managers (loaded once)
        self.config_manager = ConfigManager()
        self.db_manager = DatabaseManager()
        self.keystore = KeyStore()
        
        # Connection pools
        self.imap_client = None
        self.smtp_client = None
        self.imap_last_used = None
        self.smtp_last_used = None
        self.imap_timeout = 300  # 5 minutes
        self.smtp_timeout = 60   # 1 minute
        
        # UID cache for fetch optimization
        self._highest_uid_cache = None
        
        # Render cache (LRU with TTL)
        self._render_cache = OrderedDict()
        self._max_cache_entries = 50
        self._cache_ttl = 60  # 30 seconds
        
        # Activity tracking
        self.last_activity = time.time()
        self.idle_timeout = 1800  # 30 minutes
        
        self.logger.info("RendererDaemon initialized")
    
    # ========================================================================
    # CONFIG & CREDENTIALS
    # ========================================================================
    
    def get_config(self) -> Dict[str, Any]:
        """Get current configuration (hot-reload if changed)."""
        return self.config_manager.load_config()
    
    def get_password(self, service: str, username: str) -> str:
        """Get password from KeyStore."""
        return self.keystore.get_password(service, username)
    
    # ========================================================================
    # CONNECTION POOLING
    # ========================================================================
    
    def get_imap_client(self) -> IMAPClient:
        """Get IMAP client, creating connection if needed."""
        if self.imap_client is None:
            config = self.get_config()
            account_config = config.get('account', {})
            
            password = self.get_password('imap', account_config['username'])
            
            self.imap_client = IMAPClient(
                host=account_config['imap_server'],
                port=account_config['imap_port'],
                username=account_config['username'],
                password=password,
                use_tls=account_config.get('use_tls', True)
            )
            self.imap_last_used = time.time()
            self.logger.info("IMAP client connected")
        
        return self.imap_client
    
    def get_smtp_client(self) -> SMTPClient:
        """Get SMTP client, creating connection if needed."""
        if self.smtp_client is None:
            config = self.get_config()
            account_config = config.get('account', {})
            
            password = self.get_password('smtp', account_config['username'])
            
            self.smtp_client = SMTPClient(
                host=account_config['smtp_server'],
                port=account_config['smtp_port'],
                username=account_config['username'],
                password=password,
                use_tls=account_config.get('use_tls', True)
            )
            self.smtp_last_used = time.time()
            self.logger.info("SMTP client connected")
        
        return self.smtp_client
    
    # ========================================================================
    # DATABASE QUERIES
    # ========================================================================
    
    def query_emails(self, query: str, params: tuple = ()) -> list:
        """Execute database query and return results."""
        return self.db_manager.execute_query(query, params)
    
    def get_highest_uid_cached(self) -> int:
        """Get highest UID from cache or database."""
        if self._highest_uid_cache is None:
            result = self.query_emails("SELECT MAX(uid) as max_uid FROM emails")
            self._highest_uid_cache = result[0]['max_uid'] if result and result[0]['max_uid'] else 0
            self.logger.debug(f"Highest UID cache initialized: {self._highest_uid_cache}")
        
        return self._highest_uid_cache
    
    def invalidate_uid_cache(self):
        """Invalidate UID cache after fetch."""
        self._highest_uid_cache = None
    
    # ========================================================================
    # RENDER CACHING
    # ========================================================================
    
    def _get_cache_key(self, command: str, args: Dict) -> str:
        """Generate deterministic cache key from command and args."""
        # Create cache key from command and relevant args
        key_data = {
            'command': command,
            'folder': args.get('folder', 'inbox'),
            'limit': args.get('limit', 50),
            'show_source': args.get('show_source', False),
            'show_flagged': args.get('show_flagged', False),
        }
        return json.dumps(key_data, sort_keys=True)
    
    def get_from_cache(self, cache_key: str) -> Optional[Dict]:
        """Get rendered output from cache if fresh."""
        if cache_key not in self._render_cache:
            return None
        
        output, timestamp = self._render_cache[cache_key]
        age = time.time() - timestamp
        
        if age > self._cache_ttl:
            del self._render_cache[cache_key]
            self.logger.debug(f"Cache expired: {cache_key}")
            return None
        
        # Move to end (LRU)
        self._render_cache.move_to_end(cache_key)
        self.logger.debug(f"Cache hit: {cache_key} (age={age:.1f}s)")
        return {'output': output, 'age': age}
    
    def add_to_cache(self, cache_key: str, output: str):
        """Add rendered output to cache with LRU eviction."""
        # Evict oldest if at capacity
        if len(self._render_cache) >= self._max_cache_entries:
            oldest_key = next(iter(self._render_cache))
            del self._render_cache[oldest_key]
            self.logger.debug(f"Cache evicted oldest: {oldest_key}")
        
        self._render_cache[cache_key] = (output, time.time())
        self.logger.debug(f"Cache stored: {cache_key}")
    
    def invalidate_cache(self, pattern: Optional[str] = None):
        """Invalidate caches (called after data modifications)."""
        if pattern is None:
            count = len(self._render_cache)
            self._render_cache.clear()
            self.logger.debug(f"Cache cleared all ({count} entries)")
        else:
            to_remove = [k for k in self._render_cache if k.startswith(pattern)]
            for k in to_remove:
                del self._render_cache[k]
            self.logger.debug(f"Cache cleared pattern {pattern} ({len(to_remove)} entries)")
    
    # ========================================================================
    # COMMAND EXECUTION
    # ========================================================================
    
    async def execute_command(self, command: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a command and return structured response.
        
        Response format:
        {
            'success': bool,
            'data': any,          # Command result
            'error': str|None,    # Error message if failed
            'cached': bool,       # Whether result was cached
            'metadata': {}        # Additional info
        }
        """
        self.last_activity = time.time()
        
        try:
            # Import command handlers dynamically (built in step 3)
            from src.cli.commands import command_registry
            
            if command not in command_registry:
                return {
                    'success': False,
                    'data': None,
                    'error': f'Unknown command: {command}',
                    'cached': False,
                    'metadata': {}
                }
            
            # Get handler function
            handler = command_registry[command]
            
            # Check cache for read-only commands
            if command in {'list', 'view', 'search', 'attachments', 'attachments-list'}:
                cache_key = self._get_cache_key(command, args)
                cached = self.get_from_cache(cache_key)
                
                if cached:
                    return {
                        'success': True,
                        'data': cached['output'],
                        'error': None,
                        'cached': True,
                        'metadata': {'cache_age_seconds': cached['age']}
                    }
            else:
                cache_key = None
            
            # Execute command
            result = await handler(self, args)
            
            # Cache result if applicable
            if cache_key and result.get('success'):
                self.add_to_cache(cache_key, result['data'])
            
            # Invalidate caches for write commands
            if command in {'move', 'delete', 'flag', 'unflagged', 'send', 'refresh'}:
                self.invalidate_cache()
            
            return {
                'success': result.get('success', True),
                'data': result.get('data'),
                'error': result.get('error'),
                'cached': False,
                'metadata': result.get('metadata', {})
            }
        
        except Exception as e:
            self.logger.exception(f"Error executing {command}")
            return {
                'success': False,
                'data': None,
                'error': str(e),
                'cached': False,
                'metadata': {}
            }
    
    # ========================================================================
    # CLIENT HANDLER (Unix Socket)
    # ========================================================================
    
    async def handle_client(self, reader: asyncio.StreamReader, 
                           writer: asyncio.StreamWriter):
        """Handle incoming command request from CLI client."""
        try:
            # Read request line (JSON terminated with newline)
            line = await asyncio.wait_for(reader.readline(), timeout=5.0)
            if not line:
                return
            
            request = json.loads(line.decode().strip())
            
            command = request.get('command')
            args = request.get('args', {})
            
            # Execute command
            response = await self.execute_command(command, args)
            
            # Send response as JSON followed by newline
            response_json = json.dumps(response)
            writer.write(response_json.encode() + b'\n')
            await writer.drain()
        
        except asyncio.TimeoutError:
            self.logger.warning("Timeout reading client request")
            response = {
                'success': False,
                'data': None,
                'error': 'Request timeout',
                'cached': False,
                'metadata': {}
            }
            writer.write(json.dumps(response).encode() + b'\n')
            await writer.drain()
        
        except Exception as e:
            self.logger.exception("Error handling client request")
            response = {
                'success': False,
                'data': None,
                'error': str(e),
                'cached': False,
                'metadata': {}
            }
            writer.write(json.dumps(response).encode() + b'\n')
            await writer.drain()
        
        finally:
            writer.close()
            await writer.wait_closed()
    
    # ========================================================================
    # BACKGROUND TASKS
    # ========================================================================
    
    async def connection_keepalive(self):
        """Keep connections alive or close stale ones."""
        while True:
            await asyncio.sleep(60)  # Check every minute
            now = time.time()
            
            # IMAP keepalive
            if self.imap_client:
                idle_time = now - (self.imap_last_used or 0)
                if idle_time > self.imap_timeout:
                    self.imap_client.logout()
                    self.imap_client = None
                    self.logger.info("IMAP connection closed (idle timeout)")
            
            # SMTP keepalive (shorter timeout)
            if self.smtp_client:
                idle_time = now - (self.smtp_last_used or 0)
                if idle_time > self.smtp_timeout:
                    try:
                        self.smtp_client.quit()
                    except Exception:
                        pass
                    self.smtp_client = None
                    self.logger.info("SMTP connection closed (idle timeout)")
    
    async def idle_checker(self):
        """Shutdown daemon after idle timeout."""
        while True:
            await asyncio.sleep(60)  # Check every minute
            
            idle_time = time.time() - self.last_activity
            if idle_time > self.idle_timeout:
                self.logger.info(f"Daemon idle for {idle_time:.0f}s, shutting down")
                self.shutdown()
                break
    
    # ========================================================================
    # CLEANUP
    # ========================================================================
    
    def shutdown(self):
        """Clean up all resources and shutdown."""
        self.logger.info("Shutting down daemon")
        
        # Close connections
        if self.imap_client:
            try:
                self.imap_client.logout()
            except Exception as e:
                self.logger.warning(f"Error closing IMAP: {e}")
        
        if self.smtp_client:
            try:
                self.smtp_client.close()
            except Exception as e:
                self.logger.warning(f"Error closing SMTP: {e}")
        
        # Clear caches
        self._render_cache.clear()
        
        # Remove PID file
        pid_file = _get_pid_file()
        if pid_file.exists():
            pid_file.unlink()
        
        # Remove socket file
        socket_path = _get_socket_path()
        if socket_path.exists():
            socket_path.unlink()
        
        self.logger.info("Daemon shutdown complete")
        sys.exit(0)


# ==============================================================================
# DAEMON LIFECYCLE
# ==============================================================================

def _get_socket_path() -> Path:
    """Get Unix socket path."""
    return Path.home() / '.kernel' / 'daemon.sock'


def _get_pid_file() -> Path:
    """Get PID file path."""
    return Path.home() / '.kernel' / 'daemon.pid'


async def run_daemon():
    """Main daemon event loop."""
    daemon = RendererDaemon()
    
    # Signal handlers
    def signal_handler(signum, frame):
        daemon.shutdown()
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    # Start Unix socket server
    socket_path = _get_socket_path()
    socket_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Remove stale socket
    if socket_path.exists():
        socket_path.unlink()
    
    server = await asyncio.start_unix_server(
        daemon.handle_client,
        path=str(socket_path)
    )
    
    # Set socket permissions (user only)
    os.chmod(socket_path, 0o600)
    
    # Write PID file
    pid_file = _get_pid_file()
    pid_file.write_text(str(os.getpid()))
    
    # Start background tasks
    asyncio.create_task(daemon.connection_keepalive())
    asyncio.create_task(daemon.idle_checker())
    
    daemon.logger.info(f"Daemon started (PID: {os.getpid()})")
    
    # Serve forever
    async with server:
        await server.serve_forever()


if __name__ == '__main__':
    try:
        asyncio.run(run_daemon())
    except KeyboardInterrupt:
        logger.info("Daemon interrupted")
    except Exception as e:
        logger.error(f"Daemon error: {e}", exc_info=True)
        sys.exit(1)
