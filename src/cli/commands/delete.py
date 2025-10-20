"""Delete command - delete emails"""
from datetime import datetime
from rich.console import Console
from ...core import imap_client, storage_api
from ...utils.logger import get_logger
from ...utils.ui_helpers import confirm_action
from .command_utils import log_error, log_success

console = Console()
logger = get_logger()

# Constants
DELETE_CANCELLED_MSG = "[yellow]Deletion cancelled.[/]"
PERM_DELETE_CANCELLED_MSG = "[yellow]Permanent deletion cancelled.[/]"


def _delete_from_local_database(email_id: int, email_data: dict) -> bool:
    """Delete email from local database only.
    
    Args:
        email_id: The email ID to delete
        email_data: The email data to save to deleted_emails table
        
    Returns:
        True if deletion succeeded, False otherwise
    """
    try:
        email_data["deleted_at"] = datetime.now().isoformat()
        storage_api.save_deleted_email(email_data)
        storage_api.delete_email(email_id)
        log_success(f"Deleted email ID {email_id} from local database.")
        return True
    except Exception as e:
        log_error(f"Failed to delete email from local database: {e}")
        return False


def _delete_from_local_and_server(cfg, email_id: int, email_data: dict) -> bool:
    """Delete email from both local database and server.
    
    Args:
        cfg: Configuration object
        email_id: The email ID to delete
        email_data: The email data to save to deleted_emails table
        
    Returns:
        True if deletion succeeded, False otherwise
    """
    try:
        email_data["deleted_at"] = datetime.now().isoformat()
        storage_api.save_deleted_email(email_data)
        storage_api.delete_email(email_id)
        imap_client.delete_email(cfg, email_id)
        log_success(f"Deleted email ID {email_id} from local database and server.")
        return True
    except Exception as e:
        log_error(f"Failed to delete email: {e}")
        return False


def _permanently_delete_email(email_id: int) -> bool:
    """Permanently delete email from the deleted_emails table.
    
    Args:
        email_id: The email ID to permanently delete
        
    Returns:
        True if deletion succeeded, False otherwise
    """
    try:
        storage_api.delete_email_from_table("deleted_emails", email_id)
        log_success(f"Permanently deleted email ID {email_id} from 'deleted' table.")
        return True
    except Exception as e:
        log_error(f"Failed to permanently delete email: {e}")
        return False


async def handle_delete(args, cfg) -> None:
    """Delete email from local database or server.
    
    This function handles two deletion scenarios:
    1. Soft delete: Move email to deleted_emails table (from inbox)
    2. Hard delete: Permanently remove from deleted_emails table
    
    Args:
        args: Parsed command-line arguments containing:
            - id: Email ID to delete
            - all: If True, delete from both local DB and server
        cfg: Configuration object for IMAP operations
    """
    # Early return if email ID is not provided
    if args.id is None:
        log_error("Email ID is required for deletion.")
        return

    # Check if email is in deleted_emails table (hard delete scenario)
    if storage_api.email_exists("deleted_emails", args.id):
        _handle_permanent_deletion(args.id)
        return

    # Soft delete scenario - email in inbox
    _handle_soft_deletion(cfg, args)


def _handle_soft_deletion(cfg, args) -> None:
    """Handle soft deletion of email (move to deleted_emails table).
    
    Args:
        cfg: Configuration object
        args: Parsed command-line arguments
    """
    if not confirm_action(f"Are you sure you want to delete email ID {args.id}?"):
        logger.info("Email deletion cancelled by user.")
        console.print(DELETE_CANCELLED_MSG)
        return

    email_data = storage_api.get_email_from_table("inbox", args.id)
    if not email_data:
        log_error(f"Email with ID {args.id} not found in inbox.")
        return

    # Determine deletion scope based on --all flag
    if args.all:
        _delete_from_local_and_server(cfg, args.id, email_data)
    else:
        _delete_from_local_database(args.id, email_data)


def _handle_permanent_deletion(email_id: int) -> None:
    """Handle permanent deletion of email from deleted_emails table.
    
    Args:
        email_id: The email ID to permanently delete
    """
    if not confirm_action("Are you sure you want to permanently delete this email? This action cannot be undone."):
        logger.info("Permanent deletion cancelled by user.")
        console.print(PERM_DELETE_CANCELLED_MSG)
        return

    _permanently_delete_email(email_id)
