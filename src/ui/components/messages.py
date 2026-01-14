"""Simple status messages (no panels)."""

from typing import Optional

from rich.console import Console

from src.utils.console import get_console


class StatusMessage:
    """Simple status messages without panels.

    Used by: features that need quick inline feedback.
    """

    def __init__(self, console: Optional[Console] = None):
        self.console = console or get_console()

    def success(self, message: str) -> None:
        """Print success message."""
        self.console.print(f"[green]✓ {message}[/green]")

    def error(self, message: str) -> None:
        """Print error message."""
        self.console.print(f"[red]✗ {message}[/red]")

    def warning(self, message: str) -> None:
        """Print warning message."""
        self.console.print(f"[yellow]⚠ {message}[/yellow]")

    def info(self, message: str) -> None:
        """Print info message."""
        self.console.print(f"[cyan]ℹ {message}[/cyan]")

    def status(self, message: str) -> None:
        """Print status message."""
        self.console.print(f"[dim]{message}[/dim]")
