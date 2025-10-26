"""Flag command - flag or unflag emails"""
from typing import Dict, Any
from io import StringIO
from rich.console import Console
from ...core import storage_api
from ...ui import search_viewer
from ...utils.log_manager import get_logger, async_log_call
from .command_utils import print_error, print_success, print_status, get_email_with_validation, clean_ansi_output

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


async def handle_flag_daemon(daemon, args: Dict[str, Any]) -> Dict[str, Any]:
    """Flag command - daemon compatible wrapper."""
    try:
        table = args.get('table', 'inbox')
        email_id = args.get('id')
        
        storage_api.flag_email(table, email_id)
        
        return {
            'success': True,
            'data': f'Email {email_id} flagged',
            'error': None,
            'metadata': {}
        }
    except Exception as e:
        logger.exception("Error in handle_flag_daemon")
        return {
            'success': False,
            'data': None,
            'error': str(e),
            'metadata': {}
        }


async def handle_unflagged_daemon(daemon, args: Dict[str, Any]) -> Dict[str, Any]:
    """Unflag command - daemon compatible wrapper."""
    try:
        table = args.get('table', 'inbox')
        email_id = args.get('id')
        
        storage_api.unflag_email(table, email_id)
        
        return {
            'success': True,
            'data': f'Email {email_id} unflagged',
            'error': None,
            'metadata': {}
        }
    except Exception as e:
        logger.exception("Error in handle_unflagged_daemon")
        return {
            'success': False,
            'data': None,
            'error': str(e),
            'metadata': {}
        }


async def handle_flagged_daemon(daemon, args: Dict[str, Any]) -> Dict[str, Any]:
    """Flagged command - daemon compatible wrapper."""
    try:
        emails = storage_api.search_emails_by_flag_status(True, limit=args.get('limit', 50))
        
        buffer = StringIO()
        buffer_console = Console(
            file=buffer,
            force_terminal=True,  # Enable terminal mode for proper Rich rendering
            width=120,
            legacy_windows=False
        )
        search_viewer.display_search_results("inbox", emails, "flagged emails", console_obj=buffer_console)
        
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
        logger.exception("Error in handle_flagged_daemon")
        return {
            'success': False,
            'data': None,
            'error': str(e),
            'metadata': {}
        }
