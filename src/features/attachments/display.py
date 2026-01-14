"""Attachments display coordinator (uses shared UI components)."""

from typing import List, Tuple, Optional
from pathlib import Path
from rich.console import Console

from src.ui.components import StatusMessage, StatusPanel


class AttachmentDisplay:
    """Display for attachment operations."""

    def __init__(self, console: Optional[Console] = None):
        self.message = StatusMessage(console)
        self.panel = StatusPanel(console)
        self.console = console or self.message.console

    def display_list(self, attachments: List[str], email_id: str) -> None:
        """Display list of attachments in email."""
        self.console.print(
            f"\n[bold cyan]Attachments in email {email_id}:[/bold cyan]\n"
        )
        for idx, filename in enumerate(attachments):
            self.console.print(f"  [cyan]{idx}[/cyan]: {filename}")

    def display_downloads(self, downloads: List[Tuple[Path, int]]) -> None:
        """Display list of downloaded files."""
        self.console.print(
            f"\n[bold cyan]Downloaded attachments ({len(downloads)}):[/bold cyan]\n"
        )
        for file_path, size in downloads:
            size_str = self._format_size(size)
            self.console.print(f"  • {file_path.name} ([dim]{size_str}[/dim])")

    def show_no_attachments(self, email_id: str) -> None:
        """Show message when no attachments found."""
        self.message.info(f"No attachments in email {email_id}")

    def show_no_downloads(self) -> None:
        """Show message when no downloads found."""
        self.message.info("No downloaded attachments found")

    def show_downloading(self) -> None:
        """Show downloading status."""
        self.message.status("Downloading attachments...")

    def show_downloaded(self, files: List[Path]) -> None:
        """Show successful download."""
        self.panel.show_success(
            f"Downloaded {len(files)} attachment(s)", title="Success"
        )
        for path in files:
            self.console.print(f"  • {path}")

    def show_opened(self, filename: str) -> None:
        """Show opened confirmation."""
        self.message.success(f"Opened {filename}")

    def show_error(self, message: str) -> None:
        """Show error message."""
        self.message.error(message)

    @staticmethod
    def _format_size(size: int) -> str:
        """Format file size human-readable."""
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"
