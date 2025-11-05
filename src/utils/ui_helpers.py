"""UI helper functions for Kernel - confirmation prompts, input handling, etc."""

## TODO: move more UI helper functions here to reduce duplication?

from typing import Optional

from rich.console import Console

from src.utils.console import get_console
from src.utils.log_manager import get_logger

logger = get_logger(__name__)

async def confirm_action(message: str, console: Optional[Console] = None) -> bool:
    """Ask user for confirmation with y/n prompt"""
    output_console = console or get_console()

    try:
        response = output_console.input(f"{message} (y/n): ").strip().lower()
        return response in ["y", "yes"]
    
    except (KeyboardInterrupt, EOFError):
        output_console.print("\n[Yellow]Action cancelled by user.[/]")
        return False
    
    except Exception as e:
        logger.error(f"Error during confirmation prompt: {e}")
        return False

