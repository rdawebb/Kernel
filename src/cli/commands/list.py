"""List command - display recent emails"""
from rich.console import Console
from ...core import storage_api
from ...ui import inbox_viewer
from ...utils.log_manager import get_logger, async_log_call
from .command_utils import print_error, print_status

console = Console()
logger = get_logger(__name__)


@async_log_call
async def handle_list(args, cfg_manager):
    """List recent emails from inbox"""
    print_status("Loading emails...")
    try:
        emails = storage_api.get_inbox(limit=args.limit)
        inbox_viewer.display_inbox("inbox", emails)

    except Exception as e:
        logger.error(f"Failed to load emails: {e}")
        print_error(f"Failed to load emails: {e}")
