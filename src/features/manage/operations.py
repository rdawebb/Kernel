"""Email management operations (business logic)."""

from datetime import datetime

from src.core.database import Database
from src.utils.logging import async_log_call, get_logger

logger = get_logger(__name__)


class EmailOperations:
    """Encapsulates email management operations."""
    
    def __init__(self, database: Database):
        self.db = database
    
    @async_log_call
    async def delete_permanent(self, folder: str, email_id: str) -> None:
        """Permanently delete an email."""
        await self.db.delete_email(folder, email_id)
        logger.info(f"Permanently deleted {email_id} from {folder}")
    
    @async_log_call
    async def move_to_trash(self, folder: str, email_id: str) -> None:
        """Move email to trash."""
        await self.db.move_email(
            folder,
            "trash",
            email_id,
            deleted_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
        logger.info(f"Moved {email_id} to trash from {folder}")
    
    @async_log_call
    async def move(self, from_folder: str, to_folder: str, email_id: str) -> None:
        """Move email between folders."""
        await self.db.move_email(from_folder, to_folder, email_id)
        logger.info(f"Moved {email_id} from {from_folder} to {to_folder}")
    
    @async_log_call
    async def set_flag(self, folder: str, email_id: str, flagged: bool) -> None:
        """Set email flag status."""
        await self.db.update_field(folder, email_id, "flagged", 1 if flagged else 0)
        logger.info(f"{'Flagged' if flagged else 'Unflagged'} {email_id} in {folder}")
    
    @async_log_call
    async def mark_read(self, folder: str, email_id: str, read: bool = True) -> None:
        """Mark email as read/unread."""
        await self.db.update_field(folder, email_id, "is_read", read)
        logger.info(f"Marked {email_id} as {'read' if read else 'unread'}")