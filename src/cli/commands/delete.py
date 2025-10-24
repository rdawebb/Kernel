"""Delete command - delete emails"""
from datetime import datetime
from rich.console import Console
from ...core.imap_client import IMAPClient
from ...core import storage_api
from ...utils.log_manager import get_logger, log_call, async_log_call, log_event
from ...utils.ui_helpers import confirm_action
from .command_utils import print_error, print_success

console = Console()
logger = get_logger(__name__)

# Constants
DELETE_CANCELLED_MSG = "[yellow]Deletion cancelled.[/]"
PERM_DELETE_CANCELLED_MSG = "[yellow]Permanent deletion cancelled.[/]"


@log_call
def _delete_from_local_database(email_id: int, email_data: dict) -> bool:
    """Delete email from local database only."""
    try:
        email_data["deleted_at"] = datetime.now().isoformat()
        storage_api.save_deleted_email(email_data)
        storage_api.delete_email(email_id)
        message = f"Deleted email ID {email_id} from local database."
        logger.info(message)
        print_success(message)
        log_event("email_deleted_local", message, email_id=email_id)
        return True
    except Exception as e:
        logger.error(f"Failed to delete email from local database: {e}")
        print_error(f"Failed to delete email from local database: {e}")
        return False

@log_call
def _delete_from_local_and_server(account_config, email_id: int, email_data: dict) -> bool:
    """Delete email from both local database and server."""
    try:
        client = IMAPClient(account_config)
        email_data["deleted_at"] = datetime.now().isoformat()
        storage_api.save_deleted_email(email_data)
        storage_api.delete_email(email_id)
        client.delete_email(email_id)
        message = f"Deleted email ID {email_id} from local database and server."
        logger.info(message)
        print_success(message)
        log_event("email_deleted_server", message, email_id=email_id)
        return True
    except Exception as e:
        logger.error(f"Failed to delete email: {e}")
        print_error(f"Failed to delete email: {e}")
        return False

@log_call
def _permanently_delete_email(email_id: int) -> bool:
    """Permanently delete email from the deleted_emails table."""
    try:
        storage_api.delete_email_from_table("deleted_emails", email_id)
        message = f"Permanently deleted email ID {email_id} from 'deleted' table."
        logger.info(message)
        print_success(message)
        log_event("email_permanently_deleted", message, email_id=email_id)
        return True
    except Exception as e:
        logger.error(f"Failed to permanently delete email: {e}")
        print_error(f"Failed to permanently delete email: {e}")
        return False

@async_log_call
async def handle_delete(args, cfg_manager) -> None:
    """Delete email from local database or server.
    
    Handles two deletion scenarios:
    1. Soft delete: Move email to deleted_emails table (from inbox)
    2. Hard delete: Permanently remove from deleted_emails table
    """
    # Early return if email ID is not provided
    if args.id is None:
        logger.error("Email ID is required for deletion.")
        print_error("Email ID is required for deletion.")
        return

    # Get account config
    account_config = cfg_manager.get_account_config()

    # Check if email is in deleted_emails table (hard delete scenario)
    if storage_api.email_exists("deleted_emails", args.id):
        _handle_permanent_deletion(args.id)
        return

    # Soft delete scenario - email in inbox
    _handle_soft_deletion(account_config, args)

@log_call
def _handle_soft_deletion(account_config, args) -> None:
    """Handle soft deletion of email (move to deleted_emails table)."""
    if not confirm_action(f"Are you sure you want to delete email ID {args.id}?"):
        logger.info("Email deletion cancelled by user.")
        console.print(DELETE_CANCELLED_MSG)
        return

    email_data = storage_api.get_email_from_table("inbox", args.id)
    if not email_data:
        logger.error(f"Email with ID {args.id} not found in inbox.")
        print_error(f"Email with ID {args.id} not found in inbox.")
        return

    # Determine deletion scope based on --all flag
    if args.all:
        _delete_from_local_and_server(account_config, args.id, email_data)
    else:
        _delete_from_local_database(args.id, email_data)

@log_call
def _handle_permanent_deletion(email_id: int) -> None:
    """Handle permanent deletion of email from deleted_emails table."""
    if not confirm_action("Are you sure you want to permanently delete this email? This action cannot be undone."):
        logger.info("Permanent deletion cancelled by user.")
        console.print(PERM_DELETE_CANCELLED_MSG)
        return

    _permanently_delete_email(email_id)
