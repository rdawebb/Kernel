"""Routes daemon commands to feature modules."""

from typing import Any, Dict

from src.features.compose import compose_email
from src.features.view import view_email, view_folder, EmailFilters
from src.features.search import search_emails
from src.features.manage import delete_email, move_email, flag_email, unflag_email
from src.features.attachments import (
    list_attachments,
    download_attachment,
    download_all_attachments,
    list_downloads
)
from src.features.sync import sync_emails
from src.features.maintenance import backup_database, export_emails
from src.utils.console import get_buffer_console
from src.utils.logging import async_log_call, get_logger

logger = get_logger(__name__)


class DaemonCommandRouter:
    """Routes daemon commands to features with output capture."""
    
    @async_log_call
    async def route(self, command: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Route command and capture output.
        
        Args:
            command: Command name
            args: Command arguments
            
        Returns:
            Response dictionary with:
                - success: bool
                - data: str (captured output)
                - error: Optional[str]
                - metadata: Dict[str, Any]
        """
        # Create buffer console to capture output
        console, buffer = get_buffer_console()
        
        try:
            # Use CLI router logic but with buffer console
            from src.cli.router import CommandRouter
            
            router = CommandRouter(console)
            success = await router.route(command, args)
            
            # Get captured output
            output = buffer.getvalue()
            
            return {
                'success': success,
                'data': output,
                'error': None,
                'metadata': {'via_daemon': True}
            }
            
        except ValueError as e:
            # Invalid command
            return {
                'success': False,
                'data': None,
                'error': str(e),
                'metadata': {}
            }
        
        except Exception as e:
            # Unexpected error
            logger.error(f"Daemon command failed: {e}")
            return {
                'success': False,
                'data': None,
                'error': f"Command failed: {str(e)}",
                'metadata': {}
            }