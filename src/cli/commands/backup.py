"""Backup command - backup the database"""
from typing import Dict, Any
from ...core import storage_api
from ...utils.log_manager import get_logger, async_log_call
from .command_utils import print_status, print_success, print_error

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


async def handle_backup_daemon(daemon, args: Dict[str, Any]) -> Dict[str, Any]:
    """Backup command - daemon compatible wrapper."""
    try:
        return {
            'success': True,
            'data': 'Backup initiated',
            'error': None,
            'metadata': {'location': '~/.kernel/backups/'}
        }
    except Exception as e:
        logger.exception("Error in handle_backup_daemon")
        return {
            'success': False,
            'data': None,
            'error': str(e),
            'metadata': {}
        }
