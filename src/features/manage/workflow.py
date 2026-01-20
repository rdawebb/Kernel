"""Email management workflow orchestration."""

from typing import Optional
from rich.console import Console

from src.core.database import EngineManager, EmailRepository
from src.utils.paths import DATABASE_PATH
from src.utils.logging import async_log_call, get_logger

from .display import ManageDisplay
from .operations import EmailOperations

logger = get_logger(__name__)


class ManageWorkflow:
    """Orchestrates email management operations."""

    def __init__(self, repository: EmailRepository, console: Optional[Console] = None):
        self.repo = repository
        self.ops = EmailOperations(repository)
        self.display = ManageDisplay(console)

    @async_log_call
    async def delete(
        self,
        email_id: str,
        folder: str = "inbox",
        permanent: bool = False,
        confirm: bool = True,
    ) -> bool:
        """Delete an email.

        Args:
            email_id: Email UID
            folder: Source folder
            permanent: If True, permanently delete; else move to trash
            confirm: If True, ask for confirmation

        Returns:
            True if deleted successfully
        """
        try:
            from src.core.models.email import EmailId, FolderName

            # Check if email exists
            email_obj_id = EmailId(email_id)
            folder_name = FolderName(folder)

            if not await self.repo.exists(email_obj_id, folder_name):
                self.display.show_error(f"Email {email_id} not found")
                return False

            # Get email info for confirmation
            email = await self.repo.find_by_id(email_obj_id, folder_name)
            if confirm and email:
                if not await self.display.confirm_delete(email.to_dict(), permanent):
                    self.display.show_cancelled()
                    return False

            # Execute delete
            if permanent or folder == "trash":
                await self.ops.delete_permanent(email_id, folder)
                self.display.show_deleted(email_id, permanent=True)
            else:
                await self.ops.move_to_trash(email_id, folder)
                self.display.show_deleted(email_id, permanent=False)

            return True

        except Exception as e:
            logger.error(f"Failed to delete email {email_id}: {e}")
            self.display.show_error("Failed to delete email")
            return False

    @async_log_call
    async def move(
        self, email_id: str, from_folder: str, to_folder: str, confirm: bool = True
    ) -> bool:
        """Move an email between folders.

        Args:
            email_id: Email UID
            from_folder: Source folder
            to_folder: Destination folder
            confirm: If True, ask for confirmation

        Returns:
            True if moved successfully
        """
        try:
            from src.core.models.email import EmailId, FolderName

            # Validation
            if from_folder == to_folder:
                self.display.show_error("Source and destination must be different")
                return False

            # Check if email exists
            email_obj_id = EmailId(email_id)
            from_folder_name = FolderName(from_folder)

            email = await self.repo.find_by_id(email_obj_id, from_folder_name)
            if not email:
                self.display.show_error(f"Email {email_id} not found in {from_folder}")
                return False

            # Confirm if requested
            if confirm:
                if not await self.display.confirm_move(
                    email.to_dict(), from_folder, to_folder
                ):
                    self.display.show_cancelled()
                    return False

            # Execute move
            await self.ops.move(email_id, from_folder, to_folder)
            self.display.show_moved(email_id, from_folder, to_folder)

            return True

        except Exception as e:
            logger.error(f"Failed to move email {email_id}: {e}")
            self.display.show_error("Failed to move email")
            return False

    @async_log_call
    async def flag(
        self, email_id: str, folder: str = "inbox", flagged: bool = True
    ) -> bool:
        """Flag or unflag an email.

        Args:
            email_id: Email UID
            folder: Folder name
            flagged: True to flag, False to unflag

        Returns:
            True if updated successfully
        """
        try:
            from src.core.models.email import EmailId, FolderName

            # Check email exists
            email_obj_id = EmailId(email_id)
            folder_name = FolderName(folder)

            if not await self.repo.exists(email_obj_id, folder_name):
                self.display.show_error(f"Email {email_id} not found")
                return False

            # Update flag
            await self.ops.set_flag(email_id, folder, flagged)
            self.display.show_flagged(email_id, flagged)

            return True

        except Exception as e:
            logger.error(f"Failed to flag email {email_id}: {e}")
            self.display.show_error("Failed to update flag")
            return False


# Factory functions
async def delete_email(
    email_id: str,
    folder: str = "inbox",
    permanent: bool = False,
    console: Optional[Console] = None,
) -> bool:
    """Delete an email."""
    engine_mgr = EngineManager(DATABASE_PATH)
    try:
        repo = EmailRepository(engine_mgr)
        workflow = ManageWorkflow(repo, console)
        return await workflow.delete(email_id, folder, permanent)
    finally:
        await engine_mgr.close()


async def move_email(
    email_id: str, from_folder: str, to_folder: str, console: Optional[Console] = None
) -> bool:
    """Move an email."""
    engine_mgr = EngineManager(DATABASE_PATH)
    try:
        repo = EmailRepository(engine_mgr)
        workflow = ManageWorkflow(repo, console)
        return await workflow.move(email_id, from_folder, to_folder)
    finally:
        await engine_mgr.close()


async def flag_email(
    email_id: str, folder: str = "inbox", console: Optional[Console] = None
) -> bool:
    """Flag an email."""
    engine_mgr = EngineManager(DATABASE_PATH)
    try:
        repo = EmailRepository(engine_mgr)
        workflow = ManageWorkflow(repo, console)
        return await workflow.flag(email_id, folder, True)
    finally:
        await engine_mgr.close()


async def unflag_email(
    email_id: str, folder: str = "inbox", console: Optional[Console] = None
) -> bool:
    """Unflag an email."""
    engine_mgr = EngineManager(DATABASE_PATH)
    try:
        repo = EmailRepository(engine_mgr)
        workflow = ManageWorkflow(repo, console)
        return await workflow.flag(email_id, folder, False)
    finally:
        await engine_mgr.close()
