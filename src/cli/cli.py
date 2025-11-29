"""Main CLI entry point - simplified to use router."""

import asyncio
from typing import Any, Dict

from rich.console import Console

from src.utils.config import ConfigManager
from src.utils.logging import async_log_call, get_logger

from .cli_parser import setup_argument_parser
from .router import CommandRouter

logger = get_logger(__name__)


def _args_to_dict(args) -> Dict[str, Any]:
    """Convert argparse Namespace to dictionary."""
    result = {}
    for key, value in vars(args).items():
        if key != "command" and value is not None:
            result[key] = value
    return result


@async_log_call
async def dispatch_command(args, console: Console) -> int:
    """Dispatch command via router.

    Args:
        args: Parsed arguments
        console: Rich console

    Returns:
        Exit code (0 = success, 1 = error)
    """
    command = args.command

    try:
        router = CommandRouter(console)
        args_dict = _args_to_dict(args)
        success = await router.route(command, args_dict)

        return 0 if success else 1

    except ValueError as e:
        logger.error(f"Invalid command: {e}")
        console.print(f"[red]Error: {e}[/red]")
        return 1

    except Exception as e:
        logger.error(f"Command failed: {e}")
        console.print(f"[red]Unexpected error: {e}[/red]")
        return 1


def main() -> int:
    """Main CLI entry point.

    Returns:
        Exit code
    """
    console = Console()

    try:
        parser = setup_argument_parser()
        args = parser.parse_args()

        try:
            ConfigManager()
        except Exception as e:
            logger.error(f"Configuration error: {e}")
            console.print(f"[red]Configuration error: {e}[/red]")
            return 1

        return asyncio.run(dispatch_command(args, console))

    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
        return 130  # Standard SIGINT exit code

    except Exception as e:
        logger.error(f"Fatal error: {e}")
        console.print(f"[red]Fatal error: {e}[/red]")
        return 1


if __name__ == "__main__":
    exit(main())
