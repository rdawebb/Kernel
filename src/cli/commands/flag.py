"""Flag command - flag or unflag emails"""

from typing import Any, Dict

from src.core.database import get_database
from src.utils.log_manager import async_log_call, get_logger, log_event

from .command_utils import print_error, print_success

logger = get_logger(__name__)


@async_log_call
async def handle_flag_command(args, config_manager):
    """Flag or unflag emails by ID (CLI version)"""

    if args.flag == args.unflag:
        print_error("Please specify either --flag or --unflag.")
        return
    
    try:
        db = get_database(config_manager)

        if not db.email_exists("inbox", args.id):
            print_error(f"Email with ID {args.id} not found in 'inbox'.")
            return
        
        flag_status = 1 if args.flag else 0
        db.update_field("inbox", args.id, "flagged", flag_status)

        action = "Flagged" if args.flag else "Unflagged"
        print_success(f"{action} email with ID {args.id}.")
        log_event(action, {"id": args.id, "table": "inbox"})

    except Exception as e:
        logger.error(f"Failed to update flag status: {e}")
        print_error(f"Failed to update flag status: {e}")


async def handle_flag_command_daemon(daemon, args: Dict[str, Any]) -> Dict[str, Any]:
    """Flag or unflag emails by ID (Daemon version)"""

    try:
        email_id = args.get("id")
        flag_status = args.get("flag", True)

        if not daemon.db.email_exists("inbox", email_id):
            return {
                "success": False,
                "data": None,
                "error": f"Email with ID {email_id} not found in 'inbox'",
                "metadata": {}
            }
        
        daemon.db.update_field("inbox", email_id, "flagged", 1 if flag_status else 0)

        action = "Flagged" if flag_status else "Unflagged"
        log_event(action, {"id": email_id, "table": "inbox"})
        return {
            "success": True,
            "data": f"{action} email with ID {email_id}.",
            "error": None,
            "metadata": {"email_id": email_id}
        }

    except Exception as e:
        logger.error(f"Error in handle_flag_command_daemon: {e}")
        return {
            "success": False,
            "data": None,
            "error": str(e),
            "metadata": {}
        }
    