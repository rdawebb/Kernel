"""Maintenance display coordinator (uses shared UI components)."""

from typing import List, Optional
from pathlib import Path
from rich.console import Console

from src.ui.components import StatusMessage, StatusPanel, ConfirmPrompt


class MaintenanceDisplay:
    """Display for maintenance operations."""

    def __init__(self, console: Optional[Console] = None):
        self.message = StatusMessage(console)
        self.panel = StatusPanel(console)
        self.prompt = ConfirmPrompt(console)
        self.console = console or self.message.console

    def show_backing_up(self) -> None:
        """Show backup status."""
        self.message.status("Creating database backup...")

    def show_backed_up(self, path: Path) -> None:
        """Show backup success."""
        self.panel.show_success(
            f"Database backed up to:\n{path}", title="Backup Complete"
        )

    def show_exporting(self) -> None:
        """Show export status."""
        self.message.status("Exporting emails to CSV...")

    def show_exported(self, files: List[Path], export_dir: Path) -> None:
        """Show export success."""
        self.panel.show_success(
            f"Exported {len(files)} file(s) to:\n{export_dir}", title="Export Complete"
        )
        for file in files:
            self.console.print(f"  • {file.name}")

    async def confirm_delete(self) -> bool:
        """Confirm database deletion."""
        return self.prompt.ask(
            "[bold red]Delete database?[/bold red]\n"
            "[yellow]This will delete all local email data![/yellow]"
        )

    async def confirm_backup_before_delete(self) -> bool:
        """Ask if user wants backup before deletion."""
        return self.prompt.ask("Create backup before deletion?", default=True)

    async def confirm_delete_final(self) -> bool:
        """Final confirmation before deletion."""
        return self.prompt.ask(
            "[bold red]This is your last chance. Proceed with deletion?[/bold red]"
        )

    def show_deleted(self, path: Path) -> None:
        """Show deletion success."""
        self.panel.show_warning(f"Database deleted: {path}", title="Database Deleted")

    def show_cancelled(self) -> None:
        """Show cancellation."""
        self.message.info("Operation cancelled")

    def show_error(self, message: str) -> None:
        """Show error message."""
        self.message.error(message)
