"""Centralised console management module"""

from typing import Optional
from rich.console import Console

_console: Optional[Console] = None


def get_console() -> Console:
    """Get the shared Console instance"""
    
    global _console
    
    if _console is None:
        _console = Console()

    return _console

def get_buffer_console(width: int = 120) -> Console:
    """Get a Console for capturing output to a buffer (Daemon use)"""

    from io import StringIO

    buffer = StringIO()

    return Console(
        file=buffer,
        force_terminal=True,
        width=width,
        legacy_windows=False
    ), buffer


## Convenience Print Functions

def print_success(message: str) -> None:
    """Print a success message to the console"""
    
    get_console().print(f"[green]{message}[/]")

def print_error(message: str) -> None:
    """Print an error message to the console"""
    
    get_console().print(f"[red]{message}[/]")

def print_warning(message: str) -> None:
    """Print a warning message to the console"""
    
    get_console().print(f"[yellow]{message}[/]")

def print_status(message: str) -> None:
    """Print a status message to the console"""
    
    get_console().print(f"[cyan]{message}[/]")

def print_info(message: str) -> None:
    """Print an info message to the console"""
    
    get_console().print(message)
    