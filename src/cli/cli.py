"""Main CLI entrypoint - routes commands via daemon with fallback"""

import asyncio
import sys
from typing import Any, Dict

from src.cli.commands.command_registry import get_command_metadata
from src.daemon.daemon_client import execute_via_daemon
from src.utils.config_manager import ConfigManager
from src.utils.log_manager import async_log_call, get_logger, log_call
from .cli_parser import setup_argument_parser

logger = get_logger(__name__)


def _args_to_dict(args) -> Dict[str, Any]:
    """Convert argparse Namespace to dictionary for daemon."""

    result = {}
    for key, value in vars(args).items():
        if value is not None:
            result[key] = value

    return result


@async_log_call
async def dispatch_command(args, cfg_manager) -> None:
    """Route parsed command via daemon (with fallback) or local handlers."""
    from rich.console import Console

    console = Console()
    command = args.command
    
    try:
        args_dict = _args_to_dict(args)
        
        try:
            result = await execute_via_daemon(command, args_dict)
        
        except Exception as daemon_exc:
            logger.warning(f"Daemon unavailable or failed: {daemon_exc}")
            result = {"success": False, "error": str(daemon_exc), "via_daemon": False}

        if result['success']:
            if result.get('data'):
                console.print(result['data'])

            via_daemon = " (via daemon)" if result.get('via_daemon') else " (direct)"
            logger.debug(f"Command {command} executed{via_daemon}")
        else:
            logger.info(f"Falling back to local handler for command: {command}")
            meta = get_command_metadata(command)

            if meta and meta.cli_handler:
                await meta.cli_handler(args, cfg_manager)
            else:
                logger.error(f"No local handler found for command: {command}")
                console.print(f"[red]Error executing command: {result.get('error')}[/]")

    except ValueError as e:
        logger.error(f"Unrecognized command: {e}")
        console.print(f"[red]{e}[/]")

    except Exception as e:
        logger.error(f"Error executing command {command}: {e}")
        console.print(f"[red]Error: {e}[/]")
    
    finally:
        from src.core.database import close_database
        await close_database()

@log_call
def main() -> None:
    """Main CLI entry point"""
    from rich.console import Console
    
    console = Console()
    parser = setup_argument_parser()
    args = parser.parse_args()

    if not hasattr(args, 'command') or args.command is None:
        console.print("[yellow]No command provided. Showing help:[/]")
        parser.print_help()
        sys.exit(2)

    try:
        cfg_manager = ConfigManager()

    except Exception as e:
        logger.error(f"Configuration error: {e}")
        console.print(f"[red]Configuration error: {e}[/]")
        sys.exit(1)

    try:
        asyncio.run(dispatch_command(args, cfg_manager))

    except Exception as e:
        logger.error(f"Fatal error: {e}")
        console.print(f"[red]Fatal error: {e}[/]")
        sys.exit(1)

if __name__ == "__main__":
    main()
