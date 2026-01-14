"""Maintenance workflow orchestration."""

from typing import Optional
from pathlib import Path
from rich.console import Console

from src.core.database import Database, get_database
from src.utils.config import ConfigManager
from src.utils.logging import async_log_call, get_logger

from .display import MaintenanceDisplay

logger = get_logger(__name__)


class MaintenanceWorkflow:
    """Orchestrates database maintenance operations."""

    def __init__(self, database: Database, console: Optional[Console] = None):
        self.db = database
        self.display = MaintenanceDisplay(console)

    @async_log_call
    async def backup(self, backup_path: Optional[Path] = None) -> bool:
        """Backup database.

        Args:
            backup_path: Optional custom backup path

        Returns:
            True if backed up successfully
        """
        try:
            self.display.show_backing_up()

            path = await self.db.backup(backup_path)

            self.display.show_backed_up(path)
            return True

        except Exception as e:
            logger.error(f"Backup failed: {e}")
            self.display.show_error("Backup failed")
            return False

    @async_log_call
    async def export(
        self, folder: Optional[str] = None, export_path: Optional[Path] = None
    ) -> bool:
        """Export emails to CSV.

        Args:
            folder: Specific folder to export (None = all)
            export_path: Export directory path

        Returns:
            True if exported successfully
        """
        try:
            self.display.show_exporting()

            tables = [folder] if folder else None
            export_dir = export_path or Path("./exports")

            files = await self.db.export_to_csv(export_dir, tables=tables)

            self.display.show_exported(files, export_dir)
            return True

        except Exception as e:
            logger.error(f"Export failed: {e}")
            self.display.show_error("Export failed")
            return False

    @async_log_call
    async def delete(self, confirm: bool = False) -> bool:
        """Delete database.

        Args:
            confirm: If True, skip confirmation prompt

        Returns:
            True if deleted successfully
        """
        try:
            # Double confirmation for safety
            if not confirm:
                if not await self.display.confirm_delete():
                    self.display.show_cancelled()
                    return False

            # Offer backup first
            if await self.display.confirm_backup_before_delete():
                await self.backup()

            # Final confirmation
            if not await self.display.confirm_delete_final():
                self.display.show_cancelled()
                return False

            # Delete
            db_path = self.db.get_db_path()
            await self.db.delete_database()

            self.display.show_deleted(db_path)
            return True

        except Exception as e:
            logger.error(f"Delete failed: {e}")
            self.display.show_error("Delete failed")
            return False


# Factory functions
async def backup_database(
    path: Optional[Path] = None, console: Optional[Console] = None
) -> bool:
    """Backup database."""
    db = get_database(ConfigManager())
    workflow = MaintenanceWorkflow(db, console)
    return await workflow.backup(path)


async def export_emails(
    folder: Optional[str] = None,
    path: Optional[Path] = None,
    console: Optional[Console] = None,
) -> bool:
    """Export emails to CSV."""
    db = get_database(ConfigManager())
    workflow = MaintenanceWorkflow(db, console)
    return await workflow.export(folder, path)


async def delete_database(
    confirm: bool = False, console: Optional[Console] = None
) -> bool:
    """Delete database."""
    db = get_database(ConfigManager())
    workflow = MaintenanceWorkflow(db, console)
    return await workflow.delete(confirm)
