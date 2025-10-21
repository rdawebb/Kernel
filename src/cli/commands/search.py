"""Search command - search emails by keyword"""
from rich.console import Console
from ...core import storage_api
from ...ui import search_viewer
from ...utils.log_manager import get_logger, async_log_call
from .command_utils import print_error, print_status

console = Console()
logger = get_logger(__name__)


@async_log_call
async def handle_search(args, cfg_manager):
    """Search emails by keyword in specified table or all tables"""
    try:
        if not args.all and not args.table_name:
            logger.error("Must specify either table_name or --all flag")
            print_error("Error: Must specify either table_name or --all flag")
            return
        
        if args.all:
            print_status(f"Searching all emails for '{args.keyword}'...")
            search_results = storage_api.search_all_emails(args.keyword)
            search_viewer.display_search_results("all emails", search_results, args.keyword)

        else:
            print_status(f"Searching {args.table_name} for '{args.keyword}'...")
            search_results = storage_api.search_emails(args.table_name, args.keyword)
            search_viewer.display_search_results(args.table_name, search_results, args.keyword)

    except Exception as e:
        logger.error(f"Failed to search emails: {e}")
        print_error(f"Failed to search emails: {e}")
