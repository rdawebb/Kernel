"""Delete command - delete emails"""

from datetime import datetime
from typing import Any, Dict
from src.core.database import get_database
from src.utils.log_manager import get_logger, async_log_call, log_event
from .command_utils import (
    print_error, 
    print_success, 
    print_status
)

logger = get_logger(__name__)


@async_log_call
async def handle_delete_command(args, config_manager):
    """Delete emails by ID from specified table (CLI version)"""

    if args.id is None:
        print_error("Please specify at least one email ID to delete using --id.")
        return
    
    try:
        from src.utils.ui_helpers import confirm_action

        db = get_database(config_manager)

        if db.email_exists("trash", args.id):

            if not confirm_action("Permanently delete the email(s) from 'trash'? This action cannot be undone - (y/n): "):
                print_status("Deletion cancelled", color="yellow")
                return
            
            db.delete_email("trash", args.id)
            print_success(f"Permanently deleted email(s) with ID(s) {args.id} from 'trash'.")
            log_event("email_deleted", {"id": args.id, "table": "trash"})

        if not db.email_exists("inbox", args.id):
            print_error(f"Email(s) with ID(s) {args.id} not found in 'inbox'.")
            return
        
        from datetime import datetime

        if not confirm_action(f"Delete email(s) {args.id} from 'inbox'? - (y/n): "):
            print_status("Deletion cancelled", color="yellow")
            return

        db.move_email("inbox", "trash", args.id, deleted_at=datetime.now())
        print_success(f"Deleted email {args.id}")
        log_event("email_deleted", {"id": args.id, "table": "inbox"})

    except Exception as e:
        logger.error(f"Failed to delete email(s): {e}")
        print_error(f"Failed to delete email(s): {e}")


async def handle_delete_command_daemon(daemon, args: Dict[str, Any]) -> Dict[str, Any]:
    """Delete emails by ID from specified table (Daemon version)"""

    try:
        email_id = args.get("id")
        table = args.get("table", "inbox")

        if not daemon.db.email_exists(table, email_id):
            return {
                "success": False,
                "data": None,
                "error": f"Email with ID {email_id} not found in '{table}'",
                "metadata": {}
            }
        
        if table == "trash":
            daemon.db.delete_email("trash", email_id)
            message = f"Permanently deleted email with ID {email_id} from 'trash'."
        else:
            daemon.db.move_email(table, "trash", email_id, deleted_at=datetime.now())
            message = f"Deleted email with ID {email_id} from '{table}'."
            log_event("email_deleted", {"id": email_id, "table": table})

        return {
            "success": True,
            "data": message,
            "error": None,
            "metadata": {"email_id": email_id}
        }
    
    except Exception as e:
        logger.exception(f"Error in handle_delete_command_daemon: {e}")

        return {
            "success": False,
            "data": None,
            "error": str(e),
            "metadata": {}
        }

