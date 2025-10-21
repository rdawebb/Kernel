"""Refresh command - fetch new emails from server"""
from rich.console import Console
from ...core import imap_client, storage_api
from ...ui import inbox_viewer
from ...utils.log_manager import get_logger, async_log_call, log_event
from ...utils.ui_helpers import confirm_action
from .command_utils import print_error, print_success, print_status

console = Console()
logger = get_logger(__name__)


@async_log_call
async def handle_refresh(args, cfg_manager):
    """Fetch new emails from the server"""
    try:
        if args.all:
            console.print("[yellow]Warning: Fetching all emails can be slow and may hit server limits.[/]")
            if not confirm_action("Are you sure you want to fetch all emails?"):
                logger.info("Fetch cancelled by user.")
                console.print("[yellow]Fetch cancelled.[/]")
                return
            print_status("Fetching all emails from server...")
            fetched_count = imap_client.fetch_new_emails(cfg_manager, fetch_all=True)
            
        else:
            print_status("Fetching new emails from server...")
            fetched_count = imap_client.fetch_new_emails(cfg_manager, fetch_all=False)

        message = f"Fetched {fetched_count} new email(s) from server."
        logger.info(message)
        print_success(message)
        log_event("emails_fetched", message, count=fetched_count)
        
        print_status("Loading emails...")
        emails = storage_api.get_inbox(limit=args.limit)
        inbox_viewer.display_inbox("inbox", emails)

    except Exception as e:
        logger.error(f"Failed to fetch or load emails: {e}")
        print_error(f"Failed to fetch or load emails: {e}")
