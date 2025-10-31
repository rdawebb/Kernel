"""Search command - search emails by keyword"""

from io import StringIO
from typing import Any, Dict

from rich.console import Console

from src.core.database import get_database
from src.ui import search_viewer
from src.utils.log_manager import async_log_call, get_logger

from .command_utils import clean_ansi_output, print_error, print_status

logger = get_logger(__name__)


@async_log_call
async def handle_search_command(args, config_manager):
    """Search emails by keyword in specified table or all tables (CLI version)"""

    try:
        db = get_database(config_manager)

        if args.all:
            print_status(f"Searching all tables for '{args.keyword}'...")
            results = await db.search_all_tables(args.keyword, limit=50)
            search_viewer.display_search_results("all emails", results, args.keyword)
        else:
            if not args.table:
                print_error("Please specify a table using --table or use --all to search all tables.")
                return

            print_status(f"Searching table '{args.table}' for '{args.keyword}'...")
            results = await db.search(args.table, args.keyword, limit=50)
            search_viewer.display_search_results(args.table, results, args.keyword)

    except Exception as e:
        logger.error(f"Failed to search emails: {e}")
        print_error(f"Failed to search emails: {e}")


async def handle_search_command_daemon(daemon, args: Dict[str, Any]) -> Dict[str, Any]:
    """Search emails by keyword in specified table or all tables (Daemon version)"""

    try:
        keyword = args.get("keyword", "")

        if args.get("all"):
            results = await daemon.db.search_all_tables(keyword, limit=50)
            title = "all emails"  
        else:
            table_name = args.get("table_name", "inbox")
            results = await daemon.db.search(table_name, keyword, limit=50)
            title = table_name
        
        buffer = StringIO()
        buffer_console = Console(
            file=buffer,
            force_terminal=True,
            width=120,
            legacy_windows=False,
        )

        search_viewer.display_search_results(title, results, keyword, console_obj=buffer_console)

        output = buffer.getvalue()
        output = clean_ansi_output(output)

        return {
            "success": True,
            "data": output,
            "error": None,
            "metadata": {}
        }
    
    except Exception as e:
        logger.error(f"Error in handle_search_command_daemon: {e}")
        return {
            "success": False,
            "data": None,
            "error": str(e),
            "metadata": {}
        }
