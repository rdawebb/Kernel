"""Main CLI entrypoint - routes commands to their handlers"""

import asyncio
from rich.console import Console
from ..utils.config_manager import ConfigManager
from ..utils.log_manager import get_logger, log_call, async_log_call
from .cli_parser import setup_argument_parser
from .cli_utils import initialize_database, handle_downloads_list, handle_open_attachment
from .commands import (
    list as cmd_list,
    refresh as cmd_refresh,
    view as cmd_view,
    search as cmd_search,
    flag as cmd_flag,
    attachments as cmd_attachments,
    download as cmd_download,
    compose as cmd_compose,
    move as cmd_move,
    backup as cmd_backup,
    delete_db as cmd_delete_db,
    export as cmd_export,
    delete as cmd_delete,
)
import time

console = Console()
logger = get_logger(__name__)


@async_log_call
async def dispatch_command(args, cfg_manager):
    """Route parsed command to its handler."""
    handlers = {
        "list": cmd_list.handle_list,
        "refresh": cmd_refresh.handle_refresh,
        "view": cmd_view.handle_view,
        "search": cmd_search.handle_search,
        "flagged": cmd_flag.handle_flagged,
        "unflagged": cmd_flag.handle_unflagged,
        "flag": cmd_flag.handle_flag,
        "attachments": cmd_attachments.handle_attachments,
        "attachments-list": cmd_attachments.handle_attachments_list,
        "download": cmd_download.handle_download,
        "downloads-list": handle_downloads_list,
        "open": handle_open_attachment,
        "delete": cmd_delete.handle_delete,
        "compose": cmd_compose.handle_compose,
        "move": cmd_move.handle_move,
        "backup": cmd_backup.handle_backup,
        "delete-db": cmd_delete_db.handle_delete_db,
        "export": cmd_export.handle_export,
    }

    handler = handlers.get(args.command)
    if handler:
        await handler(args, cfg_manager)
    else:
        logger.error(f"Unknown command: {args.command}")
        console.print(f"[red]Unknown command: {args.command}[/]")

@log_call
def main():
    """Main CLI entry point"""
    total_start = time.time()
    db_start = time.time()
    initialize_database()
    db_end = time.time()
    print(f"Database initialization time: {db_end - db_start:.4f} seconds")

    parse_start = time.time()
    parser = setup_argument_parser()
    args = parser.parse_args()
    parse_end = time.time()
    print(f"Argument parsing time: {parse_end - parse_start:.4f} seconds")

    try:
        config_start = time.time()
        cfg_manager = ConfigManager()
        config_end = time.time()
        print(f"Configuration loading time: {config_end - config_start:.4f} seconds")

    except Exception as e:
        logger.error(f"Configuration error: {e}")
        console.print(f"[red]Configuration error: {e}[/]")
        return

    dispatch_start = time.time()
    asyncio.run(dispatch_command(args, cfg_manager))
    dispatch_end = time.time()
    print(f"Command dispatch time: {dispatch_end - dispatch_start:.4f} seconds")

    total_end = time.time()
    print(f"Total execution time: {total_end - total_start:.4f} seconds")

if __name__ == "__main__":
    main()
