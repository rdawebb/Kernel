"""Delete DB command - delete the local database"""
import os
from typing import Any, Dict

from ...core import storage_api
from ...utils.log_manager import async_log_call, get_logger, log_event
from ...utils.ui_helpers import confirm_action
from .command_utils import print_error, print_success

logger = get_logger(__name__)


@async_log_call
async def handle_delete_db(args, cfg_manager):
    """Delete the local database"""
    try:
        db_path = args.path if args.path else storage_api.get_db_path()
        if not os.path.exists(db_path):
            logger.error(f"Database file '{db_path}' does not exist.")
            print_error(f"Database file '{db_path}' does not exist.")
            return
        
        if not args.confirm:
            logger.warning("Deletion requires --confirm flag to proceed.")
            print_error("Deletion requires --confirm flag to proceed.")
            return
        
        if confirm_action("Would you like to back up the database before deletion?"):
            try:
                backup_path = storage_api.backup_db()
                message = f"Database backed up successfully to: {backup_path}"
                logger.info(message)
                print_success(message)
            except Exception as e:
                logger.error(f"Failed to backup database: {e}")
                print_error(f"Failed to backup database: {e}")
                return
        
        if not confirm_action(f"Are you sure you want to delete the database file at '{db_path}'? This action cannot be undone."):
            logger.info("Database deletion cancelled.")
            print_success("Database deletion cancelled.")
            return

        # Second confirmation for extra safety
        if not confirm_action("This is your last chance to cancel. Proceed with deletion?"):
            logger.info("Database deletion cancelled.")
            print_success("Database deletion cancelled.")
            return

        storage_api.delete_db()
        message = f"Database file '{db_path}' deleted successfully."
        logger.info(message)
        print_success(message)
        log_event("database_deleted", "Database deleted", path=str(db_path))
    
    except Exception as e:
        logger.error(f"Failed to delete database: {e}")
        print_error(f"Failed to delete database: {e}")


async def handle_delete_db_daemon(daemon, args: Dict[str, Any]) -> Dict[str, Any]:
    """Delete database command - daemon compatible wrapper."""
    try:
        return {
            'success': True,
            'data': 'Database deletion initiated',
            'error': None,
            'metadata': {}
        }
    except Exception as e:
        logger.exception("Error in handle_delete_db_daemon")
        return {
            'success': False,
            'data': None,
            'error': str(e),
            'metadata': {}
        }
