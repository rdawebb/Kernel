"""Sync display coordinator (uses shared UI components)."""

from typing import Optional
from rich.console import Console

from src.core.email.services.fetch import SyncMode
from src.ui.components import StatusMessage, StatusPanel


class SyncDisplay:
    """Display for sync operations."""

    def __init__(self, console: Optional[Console] = None):
        self.message = StatusMessage(console)
        self.panel = StatusPanel(console)

    def show_syncing(self, mode: SyncMode) -> None:
        """Show syncing status."""
        mode_str = "full" if mode == SyncMode.FULL else "incremental"
        self.message.status(f"Syncing emails ({mode_str})...")

    def show_synced(self, count: int) -> None:
        """Show sync success."""
        self.panel.show_success(f"Fetched {count} new email(s)", title="Sync Complete")

    def show_no_new_emails(self) -> None:
        """Show no new emails message."""
        self.panel.show_info("No new emails")

    def show_error(self, message: str) -> None:
        """Show error message."""
        self.panel.show_error(message)

    def show_stats(self, stats: dict) -> None:
        """Show folder statistics."""
        self.panel.show_info("Folder Statistics")
        for folder, info in stats.items():
            if "error" in info:
                self.panel.show_error(f"{folder}: Error - {info['error']}")
            else:
                self.panel.show_info(
                    f"  {folder}: {info.get('local_total', 0)} local, "
                    f"{info.get('server_total', 0)} server, "
                    f"{info.get('sync_needed', 0)} to sync"
                )
