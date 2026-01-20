"""View workflow orchestration."""

from typing import Optional
from rich.console import Console

from src.core.database import EngineManager, EmailRepository
from src.utils.paths import DATABASE_PATH
from src.utils.errors import EmailNotFoundError, KernelError
from src.utils.logging import async_log_call, get_logger

from .display import ViewDisplay
from .filters import EmailFilters

logger = get_logger(__name__)


class ViewWorkflow:
    """Orchestrates email viewing operations."""

    def __init__(self, repository: EmailRepository, console: Optional[Console] = None):
        self.repo = repository
        self.display = ViewDisplay(console)

    @async_log_call
    async def view_single(
        self, email_id: str, folder: str = "inbox", mark_read: bool = True
    ) -> bool:
        """View a single email by ID.

        Args:
            email_id: Email UID
            folder: Folder name
            mark_read: Whether to mark as read

        Returns:
            True if displayed successfully
        """
        try:
            from src.core.models.email import EmailId, FolderName

            folder_name = FolderName(folder)
            email_obj_id = EmailId(email_id)

            email = await self.repo.find_by_id(email_obj_id, folder_name)

            if not email:
                raise EmailNotFoundError(
                    f"Email not found in {folder}",
                    details={"email_id": email_id, "folder": folder},
                )

            # Convert Email object to dictionary for display
            email_dict = email.to_dict()
            self.display.display_single(email_dict)

            # Note: mark_read feature needs to be implemented in the repository
            # if mark_read and not email.is_read:
            #     await self.repo.mark_read(email_obj_id, folder_name)

            return True

        except EmailNotFoundError as e:
            logger.error(f"Email not found: {e.details}")
            self.display.show_error(str(e))
            return False

        except KernelError as e:
            logger.error(f"Kernel error viewing email {email_id}: {e.message}")
            self.display.show_error(e.user_message)
            return False

        except Exception as e:
            logger.error(f"Failed to view email {email_id}: {e}")
            self.display.show_error("Failed to display email")
            return False

    @async_log_call
    async def view_list(
        self,
        folder: str = "inbox",
        limit: int = 50,
        filters: Optional[EmailFilters] = None,
    ) -> bool:
        """View list of emails in a folder.

        Args:
            folder: Folder name
            limit: Maximum emails to display
            filters: Optional filters

        Returns:
            True if displayed successfully
        """
        try:
            from src.core.models.email import FolderName

            folder_name = FolderName(folder)

            # Fetch emails from repository
            emails = await self.repo.find_all(
                context=folder_name,
                limit=limit,
                offset=0,
            )

            # Convert Email objects to dictionaries for display
            email_dicts = [email.to_dict() for email in emails]

            show_flagged = folder == "inbox"

            self.display.display_list(
                emails=email_dicts, folder=folder, show_flagged=show_flagged
            )

            return True

        except KernelError as e:
            logger.error(f"Failed to view {folder}: {e.message}")
            self.display.show_error(e.user_message)
            return False

        except Exception as e:
            logger.error(f"Failed to view {folder}: {e}")
            self.display.show_error(f"Failed to display {folder}")
            return False


## Factory functions


async def view_email(
    email_id: str, folder: str = "inbox", console: Optional[Console] = None
) -> bool:
    """View a single email."""
    engine_mgr = EngineManager(DATABASE_PATH)
    try:
        repo = EmailRepository(engine_mgr)
        workflow = ViewWorkflow(repo, console)
        return await workflow.view_single(email_id, folder)
    finally:
        await engine_mgr.close()


async def view_inbox(
    limit: int = 50,
    filters: Optional[EmailFilters] = None,
    console: Optional[Console] = None,
) -> bool:
    """View inbox."""
    engine_mgr = EngineManager(DATABASE_PATH)
    try:
        repo = EmailRepository(engine_mgr)
        workflow = ViewWorkflow(repo, console)
        return await workflow.view_list("inbox", limit, filters)
    finally:
        await engine_mgr.close()


async def view_folder(
    folder: str,
    limit: int = 50,
    filters: Optional[EmailFilters] = None,
    console: Optional[Console] = None,
) -> bool:
    """View any folder."""
    engine_mgr = EngineManager(DATABASE_PATH)
    try:
        repo = EmailRepository(engine_mgr)
        workflow = ViewWorkflow(repo, console)
        return await workflow.view_list(folder, limit, filters)
    finally:
        await engine_mgr.close()
