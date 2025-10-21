"""Backup command - backup the database"""
from rich.console import Console
from ...core import storage_api
from ...utils.log_manager import get_logger, async_log_call
from .command_utils import print_status, print_success, print_error

console = Console()
logger = get_logger(__name__)


@async_log_call
async def handle_backup(args, cfg_manager):
    """Backup the database"""
    try:
        print_status("Starting database backup...")
        backup_path = storage_api.backup_db(args.path)
        message = f"Database backed up successfully to: {backup_path}"
        logger.info(message)
        print_success(message)
    
    except Exception as e:
        logger.error(f"Failed to backup database: {e}")
        print_error(f"Failed to backup database: {e}")
