"""Attachment workflow orchestration."""

from typing import Optional
from rich.console import Console

from src.core.attachments import AttachmentManager
from src.core.database import Database, get_database
from src.utils.config import ConfigManager
from src.utils.logging import async_log_call, get_logger

from .display import AttachmentDisplay

logger = get_logger(__name__)


class AttachmentWorkflow:
    """Orchestrates attachment operations."""
    
    def __init__(
        self,
        database: Database,
        attachment_manager: AttachmentManager,
        console: Optional[Console] = None
    ):
        self.db = database
        self.manager = attachment_manager
        self.display = AttachmentDisplay(console)
    
    @async_log_call
    async def list_email_attachments(
        self,
        email_id: str,
        folder: str = "inbox"
    ) -> bool:
        """List attachments for a specific email.
        
        Args:
            email_id: Email UID
            folder: Folder name
            
        Returns:
            True if displayed successfully
        """
        try:
            # Get email
            email = await self.db.get_email(folder, email_id, include_body=True)
            if not email:
                self.display.show_error(f"Email {email_id} not found")
                return False
            
            # Get attachments
            attachments = self.manager.get_attachment_list_from_email(
                email.get('raw_email') if 'raw_email' in email else None
            )
            
            if not attachments:
                self.display.show_no_attachments(email_id)
                return True
            
            # Display
            self.display.display_list(attachments, email_id)
            return True
            
        except Exception as e:
            logger.error(f"Failed to list attachments for {email_id}: {e}")
            self.display.show_error("Failed to list attachments")
            return False
    
    @async_log_call
    async def download(
        self,
        email_id: str,
        folder: str = "inbox",
        index: Optional[int] = None
    ) -> bool:
        """Download attachment(s) from email.
        
        Args:
            email_id: Email UID
            folder: Folder name
            index: Specific attachment index (None = all)
            
        Returns:
            True if downloaded successfully
        """
        try:
            # Get email
            email = await self.db.get_email(folder, email_id, include_body=True)
            if not email:
                self.display.show_error(f"Email {email_id} not found")
                return False
            
            # Download
            self.display.show_downloading()
            
            downloaded = self.manager.download_from_email_data(
                email,
                attachment_index=index
            )
            
            if not downloaded:
                self.display.show_error("No attachments to download")
                return False
            
            # Display success
            self.display.show_downloaded(downloaded)
            return True
            
        except Exception as e:
            logger.error(f"Failed to download attachments from {email_id}: {e}")
            self.display.show_error("Failed to download attachments")
            return False
    
    @async_log_call
    async def list_all_downloads(self) -> bool:
        """List all downloaded attachments.
        
        Returns:
            True if displayed successfully
        """
        try:
            downloads = self.manager.list_downloaded_attachments()
            
            if not downloads:
                self.display.show_no_downloads()
                return True
            
            self.display.display_downloads(downloads)
            return True
            
        except Exception as e:
            logger.error(f"Failed to list downloads: {e}")
            self.display.show_error("Failed to list downloads")
            return False
    
    @async_log_call
    async def open(self, filename: str) -> bool:
        """Open a downloaded attachment.
        
        Args:
            filename: Filename to open
            
        Returns:
            True if opened successfully
        """
        try:
            self.manager.open_attachment(filename)
            self.display.show_opened(filename)
            return True
            
        except Exception as e:
            logger.error(f"Failed to open {filename}: {e}")
            self.display.show_error(f"Failed to open {filename}")
            return False


# Factory functions
async def list_attachments(
    email_id: str,
    folder: str = "inbox",
    console: Optional[Console] = None
) -> bool:
    """List attachments in an email."""
    config = ConfigManager()
    db = get_database(config)
    manager = AttachmentManager(config)
    workflow = AttachmentWorkflow(db, manager, console)
    return await workflow.list_email_attachments(email_id, folder)


async def download_attachment(
    email_id: str,
    index: int,
    folder: str = "inbox",
    console: Optional[Console] = None
) -> bool:
    """Download specific attachment."""
    config = ConfigManager()
    db = get_database(config)
    manager = AttachmentManager(config)
    workflow = AttachmentWorkflow(db, manager, console)
    return await workflow.download(email_id, folder, index)


async def download_all_attachments(
    email_id: str,
    folder: str = "inbox",
    console: Optional[Console] = None
) -> bool:
    """Download all attachments from email."""
    config = ConfigManager()
    db = get_database(config)
    manager = AttachmentManager(config)
    workflow = AttachmentWorkflow(db, manager, console)
    return await workflow.download(email_id, folder, None)


async def list_downloads(console: Optional[Console] = None) -> bool:
    """List all downloaded attachments."""
    config = ConfigManager()
    db = get_database(config)
    manager = AttachmentManager(config)
    workflow = AttachmentWorkflow(db, manager, console)
    return await workflow.list_all_downloads()


async def open_attachment(filename: str, console: Optional[Console] = None) -> bool:
    """Open a downloaded attachment."""
    config = ConfigManager()
    db = get_database(config)
    manager = AttachmentManager(config)
    workflow = AttachmentWorkflow(db, manager, console)
    return await workflow.open(filename)