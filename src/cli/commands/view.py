"""View command - display a specific email"""
from typing import Dict, Any
from io import StringIO
from rich.console import Console
from ...core import storage_api
from ...ui import email_viewer
from ...utils.log_manager import get_logger, async_log_call
from .command_utils import print_error, print_status, get_email_with_validation, clean_ansi_output

logger = get_logger(__name__)


@async_log_call
async def handle_view(args, cfg_manager):
    """View a specific email by ID"""
    print_status(f"Fetching email {args.id} from {args.table}...")
    
    email_data = get_email_with_validation(args.table, args.id)
    if not email_data:
        return

    try:
        email_viewer.display_email(email_data)
    except Exception as e:
        logger.error(f"Failed to display email: {e}")
        print_error(f"Failed to display email: {e}")


async def handle_view_daemon(daemon, args: Dict[str, Any]) -> Dict[str, Any]:
    """View command - daemon compatible wrapper."""
    try:
        email_data = storage_api.get_email(args.get('table', 'inbox'), args.get('id'))
        
        if not email_data:
            return {
                'success': False,
                'data': None,
                'error': 'Email not found',
                'metadata': {}
            }
        
        buffer = StringIO()
        buffer_console = Console(
            file=buffer,
            force_terminal=True,  # Enable terminal mode for proper Rich rendering
            width=120,
            legacy_windows=False
        )
        
        # Capture email_viewer output
        email_viewer.display_email(email_data, console_obj=buffer_console)
        
        # Get the rendered output with ANSI codes
        output = buffer.getvalue()
        output = clean_ansi_output(output)
        
        return {
            'success': True,
            'data': output,
            'error': None,
            'metadata': {'email_id': email_data.get('uid')}
        }
    except Exception as e:
        logger.exception("Error in handle_view_daemon")
        return {
            'success': False,
            'data': None,
            'error': str(e),
            'metadata': {}
        }
