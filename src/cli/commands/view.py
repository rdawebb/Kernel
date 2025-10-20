"""View command - display a specific email"""
from rich.console import Console
from ...ui import email_viewer
from ...utils.logger import get_logger
from .command_utils import log_error, print_status, get_email_with_validation

console = Console()
logger = get_logger()


async def handle_view(args, cfg):
    """View a specific email by ID"""
    print_status(f"Fetching email {args.id} from {args.table}...")
    
    email_data = get_email_with_validation(args.table, args.id)
    if not email_data:
        return

    try:
        email_viewer.display_email(email_data)
    except Exception as e:
        log_error(f"Failed to display email: {e}")
