"""Main CLI entrypoint - routes commands via daemon with fallback"""

import asyncio
from typing import Any, Dict

from src.daemon.daemon_client import execute_via_daemon
from src.utils.config_manager import ConfigManager
from src.utils.log_manager import async_log_call, get_logger, log_call
from .cli_parser import setup_argument_parser

logger = get_logger(__name__)


def _args_to_dict(args) -> Dict[str, Any]:
    """Convert argparse Namespace to dictionary for daemon."""

    result = {}
    for key, value in vars(args).items():
        if key != 'command' and value is not None:
            result[key] = value

    return result


@async_log_call
async def dispatch_command(args, cfg_manager):
    """Route parsed command via daemon (with fallback) or local handlers."""

    from rich.console import Console
    
    console = Console()
    command = args.command
    
    try:
        args_dict = _args_to_dict(args)
        result = await execute_via_daemon(command, args_dict)

        if result['success']:
            if result.get('data'):
                print(result['data'])

            via_daemon = " (via daemon)" if result.get('via_daemon') else " (direct)"
            logger.debug(f"Command {command} executed{via_daemon}")
        else:
            logger.error(f"Command {command} failed: {result.get('error')}")
            console.print(f"[red]Error: {result.get('error')}[/]")

    except ValueError as ve:
        logger.error(f"Unrecognized command: {ve}")
        console.print(f"[red]{ve}[/]")

    except Exception as e:
        logger.error(f"Error executing command {command}: {e}")
        console.print(f"[red]Error: {e}[/]")

@log_call
def main():
    """Main CLI entry point"""
    
    from rich.console import Console
    
    console = Console()

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
