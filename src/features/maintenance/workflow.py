"""Maintenance workflow orchestration."""

from typing import Optional
from pathlib import Path
from rich.console import Console

from src.core.database import EngineManager, EmailRepository
from src.utils.paths import DATABASE_PATH
from src.utils.logging import async_log_call, get_logger

from .display import MaintenanceDisplay

logger = get_logger(__name__)


class MaintenanceWorkflow:
    """Orchestrates database maintenance operations."""

    def __init__(self, repository: EmailRepository, console: Optional[Console] = None):
        self.repo = repository
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

            from src.core.database import BackupService

            # Create backup service and execute backup
            backup_service = BackupService(Path(DATABASE_PATH), self.repo)
            result = await backup_service.create_backup(
                backup_path=backup_path, compress=True
            )

            if result.success:
                self.display.show_backed_up(result.backup_path)
                return True
            else:
                self.display.show_error(f"Backup failed: {result.error}")
                return False

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

            from src.core.database import BackupService
            from src.core.models.email import FolderName

            export_service = BackupService(Path(DATABASE_PATH), self.repo)
            folders = [FolderName(folder)] if folder else None

            result = await export_service.export_to_csv(
                export_dir=export_path or Path("./exports"), folders=folders
            )

            if result.success:
                self.display.show_exported(
                    result.exported_files, export_path or Path("./exports")
                )
                return True
            else:
                error_msg = f"Export failed: {len(result.errors)} errors"
                self.display.show_error(error_msg)
                return False

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

            # Delete the database file
            db_path = Path(DATABASE_PATH)
            if db_path.exists():
                import os

                os.remove(db_path)
                self.display.show_deleted(db_path)
                logger.info(f"Database deleted: {db_path}")
            else:
                self.display.show_error("Database file not found")
                return False

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
    engine_mgr = EngineManager(DATABASE_PATH)
    try:
        repo = EmailRepository(engine_mgr)
        workflow = MaintenanceWorkflow(repo, console)
        return await workflow.backup(path)
    finally:
        await engine_mgr.close()


async def export_emails(
    folder: Optional[str] = None,
    path: Optional[Path] = None,
    console: Optional[Console] = None,
) -> bool:
    """Export emails to CSV."""
    engine_mgr = EngineManager(DATABASE_PATH)
    try:
        repo = EmailRepository(engine_mgr)
        workflow = MaintenanceWorkflow(repo, console)
        return await workflow.export(folder, path)
    finally:
        await engine_mgr.close()


async def delete_database(
    confirm: bool = False, console: Optional[Console] = None
) -> bool:
    """Delete database."""
    engine_mgr = EngineManager(DATABASE_PATH)
    try:
        repo = EmailRepository(engine_mgr)
        workflow = MaintenanceWorkflow(repo, console)
        return await workflow.delete(confirm)
    finally:
        await engine_mgr.close()
