"""UI helper functions for Kernel - confirmation prompts, input handling, etc."""

## TODO: move more UI helper functions here to reduce duplication?

from rich.console import Console

console = Console()

def confirm_action(message):
    """Ask user for confirmation with y/n prompt"""
    response = console.input(f"{message} (y/n): ").strip().lower()
    return response in ['y', 'yes']
