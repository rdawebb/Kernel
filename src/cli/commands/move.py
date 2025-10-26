"""Move command - move emails between folders"""
from typing import Dict, Any
from ...core import storage_api
from ...utils.log_manager import get_logger, async_log_call
from .command_utils import print_error, print_success, validate_required_args, get_email_with_validation

logger = get_logger(__name__)

# Valid table names for email storage
VALID_TABLES = ["inbox", "sent_emails", "drafts", "deleted_emails"]


@async_log_call
async def handle_move(args, cfg_manager):
    """Move email to another folder"""
    if not validate_required_args(source=args.source, target=args.target):
        return

    if args.source not in VALID_TABLES or args.target not in VALID_TABLES:
        logger.error(f"Invalid source or target folder. Valid options: {', '.join(VALID_TABLES)}")
        print_error(f"Invalid source or target folder. Valid options: {', '.join(VALID_TABLES)}")
        return
    
    if args.source == args.target:
        logger.error("Source and target folders must be different.")
        print_error("Source and target folders must be different.")
        return

    email_data = get_email_with_validation(args.source, args.id)
    if not email_data:
        return
    
    try:
        storage_api.move_email_between_tables(args.source, args.target, args.id)
        message = f"Moved email ID {args.id} from '{args.source}' to '{args.target}' successfully."
        logger.info(message)
        print_success(message)
    
    except Exception as e:
        logger.error(f"Failed to move email: {e}")
        print_error(f"Failed to move email: {e}")


async def handle_move_daemon(daemon, args: Dict[str, Any]) -> Dict[str, Any]:
    """Move command - daemon compatible wrapper."""
    try:
        table = args.get('table', 'inbox')
        email_id = args.get('id')
        destination = args.get('destination', 'trash')
        
        storage_api.move_email(table, email_id, destination)
        
        return {
            'success': True,
            'data': f'Email {email_id} moved to {destination}',
            'error': None,
            'metadata': {}
        }
    except Exception as e:
        logger.exception("Error in handle_move_daemon")
        return {
            'success': False,
            'data': None,
            'error': str(e),
            'metadata': {}
        }
