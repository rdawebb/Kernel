"""List command - display recent emails"""
from rich.console import Console
from ...core import storage_api
from ...ui import inbox_viewer
from ...utils.logger import get_logger
from .command_utils import log_error, print_status

console = Console()
logger = get_logger()


async def handle_list(args, cfg):
    """List recent emails from inbox"""
    print_status("Loading emails...")
    try:
        emails = storage_api.get_inbox(limit=args.limit)
        inbox_viewer.display_inbox("inbox", emails)

    except Exception as e:
        log_error(f"Failed to load emails: {e}")
