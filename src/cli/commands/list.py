"""List command - display recent emails"""
from typing import Dict, Any
from io import StringIO
from rich.console import Console
from ...core import storage_api
from ...ui import inbox_viewer, table_viewer
from ...utils.log_manager import get_logger, async_log_call
from .command_utils import print_error, print_status, clean_ansi_output

logger = get_logger(__name__)



@async_log_call
async def handle_list(args, cfg_manager):
    """List recent emails from inbox"""
    print_status("Loading emails...")
    try:
        emails = storage_api.get_inbox(limit=args.limit)
        inbox_viewer.display_inbox("inbox", emails)

    except Exception as e:
        logger.error(f"Failed to load emails: {e}")
        print_error(f"Failed to load emails: {e}")


async def handle_list_daemon(daemon, args: Dict[str, Any]) -> Dict[str, Any]:
    """List command - daemon compatible wrapper."""
    try:
        emails = storage_api.get_inbox(limit=args.get('limit', 50))
        
        # Render table using Rich's terminal mode for proper formatting and colors
        buffer = StringIO()
        buffer_console = Console(
            file=buffer,
            force_terminal=True,  # Enable terminal mode for proper Rich rendering
            width=120,
            legacy_windows=False
        )
        table_viewer.display_email_table(
            emails,
            title="Inbox",
            show_source=args.get('show_source', False),
            show_flagged=args.get('show_flagged', False),
            console_obj=buffer_console
        )
        
        # Get the rendered output with ANSI codes
        output = buffer.getvalue()
        output = clean_ansi_output(output)
        
        return {
            'success': True,
            'data': output,
            'error': None,
            'metadata': {'count': len(emails)}
        }
    except Exception as e:
        logger.exception("Error in handle_list_daemon")
        return {
            'success': False,
            'data': None,
            'error': str(e),
            'metadata': {}
        }
