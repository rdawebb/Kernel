"""List command - display recent emails"""

from io import StringIO
from rich.console import Console
from typing import Any, Dict
from src.core.database import get_database
from src.utils.log_manager import get_logger, async_log_call
from .command_utils import (
    print_error, 
    print_status,
    clean_ansi_output
)

logger = get_logger(__name__)


@async_log_call
async def handle_list_command(args, config_manager):
    """List recent emails in the inbox (CLI version)"""
    
    print_status("Loading emails...")

    try:
        db = get_database(config_manager)

        emails = await db.get_emails("inbox", limit=args.limit, include_body=False)

        from src.ui import inbox_viewer

        inbox_viewer.display_inbox("inbox", emails)

    except Exception as e:
        logger.error(f"Failed to load emails: {e}")
        print_error(f"Failed to load emails: {e}")


async def handle_list_command_daemon(daemon, args: Dict[str, Any]) -> Dict[str, Any]:
    """List recent emails in the inbox (Daemon version)"""
    
    try:
        emails = await daemon.db.get_emails("inbox", limit=args.get("limit", 50))

        buffer = StringIO()
        buffer_console = Console(
            file=buffer,
            force_terminal=True,
            width=120,
            legacy_windows=False,
        )

        from src.ui import table_viewer
        
        table_viewer.display_email_table(
            emails,
            title="Inbox",
            console_obj=buffer_console
        )

        output = buffer.getvalue()
        output = clean_ansi_output(output)

        return {
            "success": True,
            "data": output,
            "error": None,
            "metadata": {"count": len(emails)}
        }
    
    except Exception as e:
        logger.exception(f"Error in handle_list_command_daemon: {e}")

        return {
            "success": False,
            "data": None,
            "error": str(e),
            "metadata": {}
        }
    