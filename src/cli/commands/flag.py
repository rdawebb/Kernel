"""Flag command - flag or unflag emails"""
from rich.console import Console
from ...core import storage_api
from ...ui import search_viewer
from ...utils.log_manager import get_logger, async_log_call
from .command_utils import print_error, print_success, print_status, get_email_with_validation

console = Console()
logger = get_logger(__name__)


@async_log_call
async def handle_flagged(args, cfg_manager):
    """List flagged emails"""
    print_status("Loading flagged emails...")
    
    try:
        emails = storage_api.search_emails_by_flag_status(True, limit=args.limit)
        search_viewer.display_search_results("inbox", emails, "flagged emails")
        message = f"Retrieved {len(emails)} flagged email(s)."
        logger.info(message)
        print_success(message)

    except Exception as e:
        logger.error(f"Failed to retrieve flagged emails: {e}")
        print_error(f"Failed to retrieve flagged emails: {e}")

@async_log_call
async def handle_unflagged(args, cfg_manager):
    """List unflagged emails"""
    print_status("Loading unflagged emails...")
    
    try:
        emails = storage_api.search_emails_by_flag_status(False, limit=args.limit)
        search_viewer.display_search_results("inbox", emails, "unflagged emails")
        message = f"Retrieved {len(emails)} unflagged email(s)."
        logger.info(message)
        print_success(message)

    except Exception as e:
        logger.error(f"Failed to retrieve unflagged emails: {e}")
        print_error(f"Failed to retrieve unflagged emails: {e}")

@async_log_call
async def handle_flag(args, cfg_manager):
    """Flag or unflag a specific email"""
    if args.flag == args.unflag:
        logger.error("Please specify either --flag or --unflag.")
        print_error("Please specify either --flag or --unflag.")
        return

    email_data = get_email_with_validation("inbox", args.id)
    if not email_data:
        return
        
    try:
        flag_status = True if args.flag else False
        storage_api.mark_email_flagged(args.id, flag_status)
        action = "Flagged" if args.flag else "Unflagged"
        message = f"{action} email ID {args.id} successfully."
        logger.info(message)
        print_success(message)

    except Exception as e:
        logger.error(f"Failed to update flag status: {e}")
        print_error(f"Failed to update flag status: {e}")
