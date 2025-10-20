"""Flag command - flag or unflag emails"""
from rich.console import Console
from ...core import storage_api
from ...ui import search_viewer
from ...utils.logger import get_logger
from .command_utils import log_error, log_success, print_status, get_email_with_validation

console = Console()
logger = get_logger()


async def handle_flagged(args, cfg):
    """List flagged emails"""
    print_status("Loading flagged emails...")
    
    try:
        emails = storage_api.search_emails_by_flag_status(True, limit=args.limit)
        search_viewer.display_search_results("inbox", emails, "flagged emails")
        log_success(f"Retrieved {len(emails)} flagged email(s).")

    except Exception as e:
        log_error(f"Failed to retrieve flagged emails: {e}")


async def handle_unflagged(args, cfg):
    """List unflagged emails"""
    print_status("Loading unflagged emails...")
    
    try:
        emails = storage_api.search_emails_by_flag_status(False, limit=args.limit)
        search_viewer.display_search_results("inbox", emails, "unflagged emails")
        log_success(f"Retrieved {len(emails)} unflagged email(s).")

    except Exception as e:
        log_error(f"Failed to retrieve unflagged emails: {e}")


async def handle_flag(args, cfg):
    """Flag or unflag a specific email"""
    if args.flag == args.unflag:
        log_error("Please specify either --flag or --unflag.")
        return

    email_data = get_email_with_validation("inbox", args.id)
    if not email_data:
        return
        
    try:
        flag_status = True if args.flag else False
        storage_api.mark_email_flagged(args.id, flag_status)
        action = "Flagged" if args.flag else "Unflagged"
        log_success(f"{action} email ID {args.id} successfully.")

    except Exception as e:
        log_error(f"Failed to update flag status: {e}")
