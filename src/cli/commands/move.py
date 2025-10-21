"""Move command - move emails between folders"""
from rich.console import Console
from ...core import storage_api
from ...utils.log_manager import get_logger, async_log_call
from .command_utils import print_error, print_success, validate_required_args, get_email_with_validation

console = Console()
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
