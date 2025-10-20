"""Backup command - backup the database"""
from rich.console import Console
from ...core import storage_api
from ...utils.logger import get_logger
from .command_utils import log_error, log_success, print_status

console = Console()
logger = get_logger()


async def handle_backup(args, cfg):
    """Backup the database"""
    try:
        print_status("Starting database backup...")
        backup_path = storage_api.backup_db(args.path)
        log_success(f"Database backed up successfully to: {backup_path}")
    
    except Exception as e:
        log_error(f"Failed to backup database: {e}")
