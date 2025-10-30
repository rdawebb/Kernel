"""Refresh command - fetch new emails from server"""

from typing import Any, Dict
from src.core.database import get_database
from src.ui import inbox_viewer
from src.utils.log_manager import get_logger, async_log_call
from .command_utils import (
    print_error, 
    print_success, 
    print_status
)

logger = get_logger(__name__)


@async_log_call
async def handle_refresh_command(args, config_manager):
    """Fetch new emails from the server (CLI version)"""

    try:
        from src.core.imap_client import SyncMode
        from src.utils.ui_helpers import confirm_action

        db = get_database(config_manager)

        from src.core.imap_connection import get_account_info
        account_config = get_account_info(config_manager)

        if not account_config:
            print_error("No account configuration found. Please set up your email account first.")
            return
        
        from src.core.imap_client import IMAPClient
        imap_client = IMAPClient(config_manager)

        if args.all:
            print_status("Warning: Fetching all emails can be slow")
            if not confirm_action("Continue? (y/n): "):
                print_status("Refresh cancelled", color="yellow")
                return
            sync_mode = SyncMode.FULL
        else:
            sync_mode = SyncMode.INCREMENTAL

        print_status("Fetching emails from server...")

        fetched_count = await imap_client.fetch_new_emails(sync_mode)
        print_success(f"Fetched {fetched_count} new email(s).")

        print_status("Loading emails...")
        emails = await db.get_emails("inbox", limit=args.limit)
        inbox_viewer.display_inbox("inbox", emails)

    except Exception as e:
        logger.error(f"Failed to refresh emails: {e}")
        print_error(f"Failed to refresh emails: {e}")


async def handle_refresh_command_daemon(daemon, args: Dict[str, Any]) -> Dict[str, Any]:
    """Fetch new emails from the server (Daemon version)"""

    try:
        from src.core.imap_client import SyncMode

        imap_client = daemon.get_imap_client()

        if not imap_client:
            return {
                "success": False,
                "data": None,
                "error": "IMAP connection failed",
                "metadata": {}
            }
        
        sync_mode = SyncMode.FULL if args.get("all", False) else SyncMode.INCREMENTAL
        fetched_count = await imap_client.fetch_new_emails(sync_mode)

        return {
            "success": True,
            "data": f"Fetched {fetched_count} new email(s).",
            "error": None,
            "metadata": {"fetched_count": fetched_count}
        }
    
    except Exception as e:
        logger.exception(f"Error in handle_refresh_command_daemon: {e}")

        return {
            "success": False,
            "data": None,
            "error": str(e),
            "metadata": {}
        }
        