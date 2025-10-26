"""Refresh command - fetch new emails from server"""
from typing import Dict, Any
from ...core.imap_client import IMAPClient, SyncMode
from ...core import storage_api
from ...ui import inbox_viewer
from ...utils.log_manager import get_logger, async_log_call, log_event
from ...utils.ui_helpers import confirm_action
from .command_utils import print_error, print_success, print_status

logger = get_logger(__name__)


@async_log_call
async def handle_refresh(args, cfg_manager):
    """Fetch new emails from the server"""
    try:
        # Load account config inside the function so prompts can happen
        from ...core.imap_connection import get_account_info
        
        account_config = get_account_info()
        client = IMAPClient(account_config)
        
        if args.all:
            print_status("Warning: Fetching all emails can be slow and may hit server limits.", color="yellow")
            if not confirm_action("Are you sure you want to fetch all emails?"):
                logger.info("Fetch cancelled by user.")
                print_status("Fetch cancelled.", color="yellow")
                return
            print_status("Fetching all emails from server...")
            fetched_count = client.fetch_new_emails(SyncMode.FULL)

        else:
            print_status("Fetching new emails from server...")
            fetched_count = client.fetch_new_emails(SyncMode.INCREMENTAL)

        message = f"Fetched {fetched_count} new email(s) from the server."
        logger.info(message)
        print_success(message)
        log_event("emails_fetched", message, count=fetched_count)
        
        print_status("Loading emails...")
        emails = storage_api.get_inbox(limit=args.limit)
        inbox_viewer.display_inbox("inbox", emails)

    except Exception as e:
        logger.error(f"Failed to fetch or load emails: {e}")
        print_error(f"Failed to fetch or load emails: {e}")


async def handle_refresh_daemon(daemon, args: Dict[str, Any]) -> Dict[str, Any]:
    """Refresh command - daemon compatible wrapper."""
    try:
        from ...core.imap_connection import get_account_info
        
        account_config = get_account_info()
        client = IMAPClient(account_config)
        
        if args.get('all'):
            count = client.fetch_new_emails(SyncMode.FULL)
        else:
            count = client.fetch_new_emails(SyncMode.INCREMENTAL)
        
        return {
            'success': True,
            'data': f'Refreshed {count} emails',
            'error': None,
            'metadata': {'email_count': count}
        }
    except Exception as e:
        logger.exception("Error in handle_refresh_daemon")
        return {
            'success': False,
            'data': None,
            'error': str(e),
            'metadata': {}
        }
