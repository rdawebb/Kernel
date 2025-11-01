"""UI helper functions for Kernel - confirmation prompts, input handling, etc."""

## TODO: move more UI helper functions here to reduce duplication?

from src.utils.console import get_console
from src.utils.log_manager import get_logger, log_call

logger = get_logger(__name__)

@log_call
def confirm_action(message):
    """Ask user for confirmation with y/n prompt"""
    response = get_console().input(f"{message} (y/n): ").strip().lower()
    return response in ['y', 'yes']

