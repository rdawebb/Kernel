"""Refresh command - fetch new emails from server"""
from rich.console import Console
from ...core import imap_client, storage_api
from ...ui import inbox_viewer
from ...utils.logger import get_logger
from ...utils.ui_helpers import confirm_action
from .command_utils import log_error, log_success, print_status

console = Console()
logger = get_logger()


async def handle_refresh(args, cfg):
    """Fetch new emails from the server"""
    try:
        if args.all:
            console.print("[yellow]Warning: Fetching all emails can be slow and may hit server limits.[/]")
            if not confirm_action("Are you sure you want to fetch all emails?"):
                console.print("[yellow]Fetch cancelled.[/]")
                return
            print_status("Fetching all emails from server...")
            fetched_count = imap_client.fetch_new_emails(cfg, fetch_all=True)
            
        else:
            print_status("Fetching new emails from server...")
            fetched_count = imap_client.fetch_new_emails(cfg, fetch_all=False)

        log_success(f"Fetched {fetched_count} new email(s) from server.")
        
        print_status("Loading emails...")
        emails = storage_api.get_inbox(limit=args.limit)
        inbox_viewer.display_inbox("inbox", emails)

    except Exception as e:
        log_error(f"Failed to fetch or load emails: {e}")
