"""Sync workflow orchestration - CLI entry point for email synchronization."""

from typing import Optional

from rich.console import Console

from src.core.email.services.fetch import SyncMode
from src.core.email.services.fetch_factory import EmailFetchServiceFactory
from src.core.models.email import FolderName
from src.utils.logging import async_log_call, get_logger

from .display import SyncDisplay

logger = get_logger(__name__)


class SyncWorkflow:
    """Class to manage the email sync workflow."""

    def __init__(
        self, full: bool, folder: str, console: Optional[Console] = None
    ) -> None:
        """Initialise the sync workflow."""
        self.full = full
        self.folder = folder
        self.console = console

    @async_log_call
    async def sync(
        self,
        full: bool = False,
        folder: str = "inbox",
    ) -> bool:
        """Sync emails from server (primary CLI entry point).

        Args:
            full: If True, perform full sync; otherwise incremental
            folder: Folder to sync (default: "inbox")

        Returns:
            True if sync succeeded, False otherwise
        """
        display = SyncDisplay(self.console)
        mode = SyncMode.FULL if full else SyncMode.INCREMENTAL

        try:
            folder_enum = FolderName.from_string(folder)
        except ValueError:
            logger.error(f"Invalid folder name: {folder}")
            display.show_error(f"Invalid folder: {folder}")
            return False

        try:
            async with EmailFetchServiceFactory.create() as service:
                display.show_syncing(mode)

                stats = await service.fetch_new_emails(folder_enum, mode)

                if stats.saved_count > 0:
                    display.show_synced(stats.saved_count)
                else:
                    display.show_no_new_emails()

                return True

        except Exception as e:
            logger.error(f"Sync failed: {e}")
            display.show_error(f"Sync failed: {str(e)}")
            return False

    @async_log_call
    async def sync_all_folders(
        self,
        full: bool = False,
    ) -> bool:
        """Sync all folders.

        Args:
            full: If True, perform full sync; otherwise incremental

        Returns:
            True if all syncs succeeded, False if any failed
        """
        display = SyncDisplay(self.console)
        mode = SyncMode.FULL if full else SyncMode.INCREMENTAL
        all_success = True

        try:
            async with EmailFetchServiceFactory.create() as service:
                for folder in FolderName:
                    try:
                        logger.info(f"Syncing folder: {folder.value}")
                        display.show_syncing(mode)

                        stats = await service.fetch_new_emails(folder, mode)

                        if stats.saved_count > 0:
                            display.show_synced(stats.saved_count)
                        else:
                            display.show_no_new_emails()

                    except Exception as e:
                        logger.error(f"Error syncing folder {folder.value}: {e}")
                        display.show_error(f"Failed to sync {folder.value}")
                        all_success = False

            return all_success

        except Exception as e:
            logger.error(f"Sync all folders failed: {e}")
            display.show_error(f"Sync failed: {str(e)}")
            return False

    @async_log_call
    async def get_sync_status(
        self,
    ) -> dict:
        """Get sync status for all folders.

        Args:
            console: Optional Rich console for display

        Returns:
            Dictionary mapping folder names to status info
        """
        display = SyncDisplay(self.console)

        try:
            async with EmailFetchServiceFactory.create() as service:
                status = {}

                for folder in FolderName:
                    try:
                        info = await service.get_folder_stats(folder)
                        status[folder.value] = info

                    except Exception as e:
                        logger.error(f"Failed to get status for {folder.value}: {e}")
                        status[folder.value] = {"error": str(e)}

                if self.console:
                    display.show_stats(status)

                return status

        except Exception as e:
            logger.error(f"Failed to get sync status: {e}")
            display.show_error(f"Failed to get status: {str(e)}")
            return {}


# Factory function
async def sync_emails(full: bool = False, console: Optional[Console] = None) -> bool:
    """Sync emails with the server.

    Args:
        full: If True, perform full sync; otherwise incremental
        console: Optional Rich console for display

    Returns:
        True if sync succeeded, False otherwise
    """
    try:
        workflow = SyncWorkflow(full=full, folder="inbox", console=console)
        return await workflow.sync(full=full)

    except Exception as e:
        logger.error(f"Sync failed: {e}")
        return False
