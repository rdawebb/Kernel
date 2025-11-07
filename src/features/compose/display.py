"""Compose display coordinator (uses shared UI components)."""

from typing import Any, Dict, Optional
from rich.console import Console

from src.ui.components import PreviewPanel, StatusPanel


class ComposeDisplay:
    """Coordinates display for compose feature."""
    
    def __init__(self, console: Optional[Console] = None):
        self.preview = PreviewPanel(console)
        self.panel = StatusPanel(console)
        self.console = console or self.preview.console
    
    def show_header(self) -> None:
        """Display composition header."""
        self.console.print("\n[bold cyan]Email Composition[/bold cyan]\n")
    
    def show_preview(self, email_data: Dict[str, Any]) -> None:
        """Show email preview (delegates to PreviewPanel)."""
        self.preview.display(email_data)
    
    def show_sending(self) -> None:
        """Show sending status."""
        self.console.print("\n[cyan]Sending email...[/cyan]")
    
    def show_success(self, recipient: str) -> None:
        """Show success (delegates to StatusPanel)."""
        self.panel.show_success(f"Email sent to {recipient}")
    
    def show_scheduled(self, send_time: str) -> None:
        """Show scheduled confirmation (delegates to StatusPanel)."""
        self.panel.show_info(f"Email scheduled for {send_time}")
    
    def show_draft_saved(self) -> None:
        """Show draft saved."""
        self.panel.show_info("Draft saved")

    def show_cancelled(self) -> None:
        """Show cancellation."""
        self.console.print("\n[yellow]Composition cancelled[/yellow]")
    
    def show_error(self, message: str, show_details: bool = False) -> None:
        """Show error (delegates to StatusPanel)."""
        self.panel.show_error(message)