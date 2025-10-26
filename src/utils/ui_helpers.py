"""UI helper functions for Kernel - confirmation prompts, input handling, etc."""

## TODO: move more UI helper functions here to reduce duplication?

from .log_manager import get_logger, log_call

logger = get_logger(__name__)

def _get_console():
    """Get or create console instance."""
    from rich.console import Console
    return Console()

@log_call
def confirm_action(message):
    """Ask user for confirmation with y/n prompt"""
    response = _get_console().input(f"{message} (y/n): ").strip().lower()
    return response in ['y', 'yes']

