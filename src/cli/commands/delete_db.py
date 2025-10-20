"""Delete DB command - delete the local database"""
import os
from rich.console import Console
from ...core import storage_api
from ...utils.logger import get_logger
from ...utils.ui_helpers import confirm_action
from .command_utils import log_error, log_success

console = Console()
logger = get_logger()


async def handle_delete_db(args, cfg):
    """Delete the local database"""
    try:
        db_path = args.path if args.path else storage_api.get_db_path()
        if not os.path.exists(db_path):
            log_error(f"Database file '{db_path}' does not exist.")
            return
        
        if not args.confirm:
            log_error("Deletion requires --confirm flag to proceed.")
            return
        
        if confirm_action("Would you like to back up the database before deletion?"):
            try:
                backup_path = storage_api.backup_db()
                log_success(f"Database backed up successfully to: {backup_path}")
            except Exception as e:
                log_error(f"Failed to backup database: {e}")
                return
        
        if not confirm_action(f"Are you sure you want to delete the database file at '{db_path}'? This action cannot be undone."):
            logger.info("Database deletion cancelled.")
            console.print("[yellow]Database deletion cancelled.[/]")
            return

        # Second confirmation for extra safety
        if not confirm_action("This is your last chance to cancel. Proceed with deletion?"):
            logger.info("Database deletion cancelled.")
            console.print("[yellow]Database deletion cancelled.[/]")
            return

        storage_api.delete_db()
        log_success(f"Database file '{db_path}' deleted successfully.")
    
    except Exception as e:
        log_error(f"Failed to delete database: {e}")
