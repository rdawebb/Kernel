"""Centralised console management module"""

from io import StringIO
from typing import Optional

from rich.console import Console

_console: Optional[Console] = None


def get_console() -> Console:
    """Get the shared Console instance"""
    global _console
    
    if _console is None:
        _console = Console()

    return _console

def get_buffer_console(width: int = 120) -> tuple[Console, StringIO]:
    """Get a Console for capturing output to a buffer (Daemon use)"""
    buffer = StringIO()

    console = Console(
        file=buffer,
        force_terminal=True,
        width=width,
        legacy_windows=False,
        record=True
    )

    return console, buffer

def reset_console() -> None:
    """Reset the shared Console instance (for testing purposes)"""
    global _console
    _console = None


## Convenience Print Functions

async def print_success(message: str, console: Optional[Console] = None) -> None:
    """Print a success message to the console"""
    output_console = console or get_console()
    output_console.print(f"[green]{message}[/]")

async def print_error(message: str, console: Optional[Console] = None) -> None:
    """Print an error message to the console"""
    output_console = console or get_console()
    output_console.print(f"[red]{message}[/]")

async def print_warning(message: str, console: Optional[Console] = None) -> None:
    """Print a warning message to the console"""
    output_console = console or get_console()
    output_console.print(f"[yellow]{message}[/]")

async def print_status(message: str, console: Optional[Console] = None) -> None:
    """Print a status message to the console"""
    output_console = console or get_console()
    output_console.print(f"[cyan]{message}[/]")

async def print_info(message: str, console: Optional[Console] = None) -> None:
    """Print an info message to the console"""
    output_console = console or get_console()
    output_console.print(message)
