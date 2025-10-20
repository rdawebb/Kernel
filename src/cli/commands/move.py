"""Move command - move emails between folders"""
from rich.console import Console
from ...core import storage_api
from ...utils.logger import get_logger
from .command_utils import log_error, log_success, validate_required_args, get_email_with_validation

console = Console()
logger = get_logger()

# Valid table names for email storage
VALID_TABLES = ["inbox", "sent_emails", "drafts", "deleted_emails"]


async def handle_move(args, cfg):
    """Move email to another folder"""
    if not validate_required_args(source=args.source, target=args.target):
        return

    if args.source not in VALID_TABLES or args.target not in VALID_TABLES:
        log_error(f"Invalid source or target folder. Valid options: {', '.join(VALID_TABLES)}")
        return
    
    if args.source == args.target:
        log_error("Source and target folders must be different.")
        return

    email_data = get_email_with_validation(args.source, args.id)
    if not email_data:
        return
    
    try:
        storage_api.move_email_between_tables(args.source, args.target, args.id)
        log_success(f"Moved email ID {args.id} from '{args.source}' to '{args.target}' successfully.")
    
    except Exception as e:
        log_error(f"Failed to move email: {e}")
