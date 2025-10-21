"""Main CLI entrypoint - routes commands to their handlers"""
import asyncio
from rich.console import Console
from ..core.config_manager import ConfigManager
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
    initialize_database()
    
    parser = setup_argument_parser()
    args = parser.parse_args()

    try:
        cfg_manager = ConfigManager()

    except Exception as e:
        logger.error(f"Configuration error: {e}")
        console.print(f"[red]Configuration error: {e}[/]")
        return

    asyncio.run(dispatch_command(args, cfg_manager))

if __name__ == "__main__":
    main()
