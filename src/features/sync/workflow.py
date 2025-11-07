"""Sync workflow orchestration."""

from typing import Optional
from rich.console import Console

from src.core.email.imap.client import IMAPClient, SyncMode
from src.core.database import Database, get_database
from src.utils.config import ConfigManager
from src.utils.logging import async_log_call, get_logger

from .display import SyncDisplay

logger = get_logger(__name__)


class SyncWorkflow:
    """Orchestrates email synchronization."""
    
    def __init__(
        self,
        database: Database,
        imap_client: IMAPClient,
        console: Optional[Console] = None
    ):
        self.db = database
        self.imap = imap_client
        self.display = SyncDisplay(console)
    
    @async_log_call
    async def sync(
        self,
        mode: SyncMode = SyncMode.INCREMENTAL
    ) -> bool:
        """Sync emails from server.
        
        Args:
            mode: Sync mode (INCREMENTAL or FULL)
            
        Returns:
            True if synced successfully
        """
        try:
            self.display.show_syncing(mode)
            
            # Fetch emails
            count = await self.imap.fetch_new_emails(mode)
            
            # Display result
            if count > 0:
                self.display.show_synced(count)
            else:
                self.display.show_no_new_emails()
            
            return True
            
        except Exception as e:
            logger.error(f"Sync failed: {e}")
            self.display.show_error("Sync failed")
            return False


# Factory functions
async def sync_emails(
    full: bool = False,
    console: Optional[Console] = None
) -> bool:
    """Sync emails from server."""
    config = ConfigManager()
    db = get_database(config)
    imap = IMAPClient(config)
    workflow = SyncWorkflow(db, imap, console)
    
    mode = SyncMode.FULL if full else SyncMode.INCREMENTAL
    return await workflow.sync(mode)


async def refresh_folder(
    folder: str = "inbox",
    console: Optional[Console] = None
) -> bool:
    """Refresh specific folder (alias for sync)."""
    return await sync_emails(full=False, console=console)