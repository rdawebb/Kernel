"""View command - display a specific email"""

from io import StringIO
from typing import Any, Dict
from rich.console import Console
from src.core.database import get_database
from src.ui import email_viewer
from src.utils.log_manager import get_logger, async_log_call
from .command_utils import (
    print_error, 
    print_status, 
    clean_ansi_output
)

logger = get_logger(__name__)


@async_log_call
async def handle_view_command(args, config_manager):
    """View a specific email by ID (CLI version)"""

    print_status(f"Fetching email {args.id} from {args.table}...")
    
    try:
        db = get_database(config_manager)

        email_data = await db.get_email(args.table, args.id, include_body=True)

        if not email_data:
            logger.warning(f"Email with ID {args.id} not found in table {args.table}")
            print_error(f"Email with ID {args.id} not found in table {args.table}")
            return
        
        email_viewer.display_email(email_data)

    except Exception as e:
        logger.error(f"Failed to display email: {e}")
        print_error(f"Failed to display email: {e}")


async def handle_view_command_daemon(daemon, args: Dict[str, Any]) -> Dict[str, Any]:
    """View a specific email by ID (Daemon version)"""

    try:
        table = args.get("table")
        email_id = args.get("id")

        email_data = await daemon.db.get_email(table, email_id, include_body=True)

        if not email_data:
            return {
                "success": False,
                "data": None,
                "error": f"Email with ID {email_id} not found in table {table}",
                "metadata": {}
            }
        
        buffer = StringIO()
        buffer_console = Console(
            file=buffer,
            force_terminal=True,
            width=120,
            legacy_windows=False,
        )

        email_viewer.display_email(email_data, console_obj=buffer_console)

        output = buffer.getvalue()
        output = clean_ansi_output(output)

        return {
            "success": True,
            "data": output,
            "error": None,
            "metadata": {"email_id": email_data.get("uid")}
        }
    
    except Exception as e:
        logger.exception(f"Error in handle_view_command_daemon: {e}")

        return {
            "success": False,
            "data": None,
            "error": str(e),
            "metadata": {}
        }
            
