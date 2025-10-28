"""
Daemon Client - CLI interface to communicate with RendererDaemon

Handles:
- Daemon lifecycle (start/stop/check)
- Command communication via Unix socket
- Fallback to direct execution if daemon unavailable
- Response parsing and error handling
"""

import asyncio
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Any, Optional
from src.utils.log_manager import get_logger


logger = get_logger(__name__)


class DaemonClient:
    """Client for communicating with RendererDaemon."""
    
    # Paths
    SOCKET_PATH = Path.home() / '.kernel' / 'daemon.sock'
    PID_FILE = Path.home() / '.kernel' / 'daemon.pid'
    DAEMON_SCRIPT = Path(__file__).parent / 'renderer_daemon.py'
    
    # Timeouts - add to config for customisation
    CONNECT_TIMEOUT = 5
    COMMAND_TIMEOUT = 10
    DAEMON_START_TIMEOUT = 5
    
    def __init__(self, fallback_mode: bool = True, disable_daemon: bool = False):
        """Initialize daemon client."""

        self.fallback_mode = fallback_mode
        self.disable_daemon = disable_daemon
    
    
    ## Daemon Lifecycle
    
    def is_daemon_running(self) -> bool:
        """Check if daemon process is running."""

        if not self.PID_FILE.exists():
            return False
        
        try:
            pid = int(self.PID_FILE.read_text().strip())
            # Check if process exists
            os.kill(pid, 0)  # Signal 0 doesn't kill, just checks
            return True
        except (ValueError, OSError, ProcessLookupError):
            return False
    

    async def start_daemon(self) -> bool:
        """Start daemon in background."""

        if self.is_daemon_running():
            logger.debug("Daemon already running")
            return True
        
        logger.info("Starting daemon...")
        
        try:
            # Determine which Python executable to use
            python_exe = sys.executable
            
            # Try to find venv from VIRTUAL_ENV environment variable
            venv_path = os.environ.get('VIRTUAL_ENV')
            
            if not venv_path:
                project_root = Path(__file__).parent.parent.parent
                venv_candidates = [
                    project_root / '.venv',
                    project_root / 'venv',
                    project_root / '.env',
                ]
                for candidate in venv_candidates:
                    if candidate.exists():
                        venv_path = str(candidate)
                        break
   
            if venv_path:
                venv_python = Path(venv_path) / 'bin' / 'python'
                if venv_python.exists():
                    python_exe = str(venv_python)
                    logger.debug(f"Using venv Python: {python_exe}")
            
            process = subprocess.Popen(
                [python_exe, str(self.DAEMON_SCRIPT)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            
            start_time = time.time()
            while time.time() - start_time < self.DAEMON_START_TIMEOUT:
                if self.SOCKET_PATH.exists() and self.is_daemon_running():
                    logger.info(f"Daemon started (PID: {process.pid})")
                    return True
                await asyncio.sleep(0.1)
            
            logger.error("Daemon failed to start (timeout)")
            return False
        
        except Exception as e:
            logger.error(f"Failed to start daemon: {e}")
            return False
    

    async def stop_daemon(self):
        """Stop running daemon."""

        if not self.is_daemon_running():
            logger.debug("Daemon not running")
            return
        
        try:
            pid = int(self.PID_FILE.read_text().strip())
            os.kill(pid, 15)  # SIGTERM
            logger.info("Daemon stopped")    
        except Exception as e:
            logger.warning(f"Error stopping daemon: {e}")
    

    ## Command Execution
    
    async def execute_command(self, command: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute command via daemon, with fallback to direct execution."""
        
        if self.disable_daemon:
            if self.fallback_mode:
                logger.debug(f"Daemon disabled, using direct execution: {command}")
                result = await self._execute_direct(command, args)
                result['via_daemon'] = False
                return result
            else:
                return {
                    'success': False,
                    'data': None,
                    'error': 'Daemon disabled and fallback disabled',
                    'cached': False,
                    'metadata': {},
                    'via_daemon': False
                }
        
        try:
            result = await self._execute_via_daemon(command, args)
            if result is not None:
                result['via_daemon'] = True
                return result
        except Exception as e:
            logger.warning(f"Daemon execution failed: {e}")
        
        if self.fallback_mode:
            logger.info(f"Falling back to direct execution: {command}")
            result = await self._execute_direct(command, args)
            result['via_daemon'] = False
            return result
        
        return {
            'success': False,
            'data': None,
            'error': 'Daemon unavailable and fallback disabled',
            'cached': False,
            'metadata': {},
            'via_daemon': False
        }
    

    async def _execute_via_daemon(self, command: str, args: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Execute command via Unix socket to daemon."""

        if not self.is_daemon_running():
            if not await self.start_daemon():
                return None
        
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_unix_connection(path=str(self.SOCKET_PATH)),
                timeout=self.CONNECT_TIMEOUT
            )
            
            request = json.dumps({
                'command': command,
                'args': args
            })

            writer.write(request.encode() + b'\n')
            await writer.drain()
            
            line = await asyncio.wait_for(
                reader.readline(),
                timeout=self.COMMAND_TIMEOUT
            )
            
            if not line:
                logger.warning("Daemon sent empty response")
                return None
            
            response = json.loads(line.decode().strip())
            writer.close()
            await writer.wait_closed()
            
            return response
        
        except asyncio.TimeoutError:
            logger.error("Daemon command timeout")
            return None
        except Exception as e:
            logger.warning(f"Daemon socket error: {e}")
            return None
    

    async def _execute_direct(self, command: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback: Execute command directly without daemon."""

        try:
            from src.cli.commands import command_registry
            
            if command not in command_registry:
                return {
                    'success': False,
                    'data': None,
                    'error': f'Unknown command: {command}',
                    'cached': False,
                    'metadata': {}
                }
            
            handler = command_registry[command]
            
            result = await handler(None, args)
            
            return {
                'success': result.get('success', True),
                'data': result.get('data'),
                'error': result.get('error'),
                'cached': False,
                'metadata': result.get('metadata', {})
            }
        
        except Exception as e:
            logger.exception(f"Direct execution error: {e}")
            return {
                'success': False,
                'data': None,
                'error': str(e),
                'cached': False,
                'metadata': {}
            }


## Convienience Functions

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


async def ensure_daemon_started():
    """Ensure daemon is running."""
    client = get_daemon_client()
    if not client.is_daemon_running():
        if not await client.start_daemon():
            logger.warning("Failed to start daemon")


async def stop_daemon():
    """Stop daemon."""
    client = get_daemon_client()
    await client.stop_daemon()
