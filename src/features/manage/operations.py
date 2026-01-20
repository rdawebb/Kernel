"""Email management operations (business logic)."""

from src.core.database import EmailRepository
from src.core.models.email import EmailId, FolderName
from src.utils.logging import async_log_call, get_logger

logger = get_logger(__name__)


class EmailOperations:
    """Encapsulates email management operations."""

    def __init__(self, repository: EmailRepository):
        self.repo = repository

    @async_log_call
    async def delete_permanent(self, folder: str, email_id: str) -> None:
        """Permanently delete an email."""
        await self.repo.delete(EmailId(email_id), FolderName(folder))
        logger.info(f"Permanently deleted {email_id} from {folder}")

    @async_log_call
    async def move_to_trash(self, folder: str, email_id: str) -> None:
        """Move email to trash."""
        await self.repo.move(
            EmailId(email_id),
            FolderName(folder),
            FolderName("trash"),
        )
        logger.info(f"Moved {email_id} to trash from {folder}")

    @async_log_call
    async def move(self, from_folder: str, to_folder: str, email_id: str) -> None:
        """Move email between folders."""
        await self.repo.move(
            EmailId(email_id),
            FolderName(from_folder),
            FolderName(to_folder),
        )
        logger.info(f"Moved {email_id} from {from_folder} to {to_folder}")

    @async_log_call
    async def set_flag(self, email_id: str, folder: str, flagged: bool) -> None:
        """Set email flag status."""
        await self.repo.flag(EmailId(email_id), FolderName(folder), flagged)
        logger.info(f"{'Flagged' if flagged else 'Unflagged'} {email_id} in {folder}")

    @async_log_call
    async def mark_read(self, folder: str, email_id: str, read: bool = True) -> None:
        """Mark email as read/unread."""
        # TODO: Implement read/unread status update in repository
        logger.info(f"Marked {email_id} as {'read' if read else 'unread'}")
