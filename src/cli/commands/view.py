"""View command - display a specific email"""
from rich.console import Console
from ...ui import email_viewer
from ...utils.log_manager import get_logger, async_log_call
from .command_utils import print_error, print_status, get_email_with_validation

console = Console()
logger = get_logger(__name__)


@async_log_call
async def handle_view(args, cfg_manager):
    """View a specific email by ID"""
    print_status(f"Fetching email {args.id} from {args.table}...")
    
    email_data = get_email_with_validation(args.table, args.id)
    if not email_data:
        return

    try:
        email_viewer.display_email(email_data)
    except Exception as e:
        logger.error(f"Failed to display email: {e}")
        print_error(f"Failed to display email: {e}")
