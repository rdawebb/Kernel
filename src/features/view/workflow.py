"""View workflow orchestration."""

from typing import Optional
from rich.console import Console

from src.core.database import Database, get_database
from src.utils.errors import EmailNotFoundError, KernelError
from src.utils.config import ConfigManager
from src.utils.logging import async_log_call, get_logger

from .display import EmailDisplay, EmailTableDisplay
from .filters import EmailFilters

logger = get_logger(__name__)


class ViewWorkflow:
    """Orchestrates email viewing operations."""
    
    def __init__(
        self,
        database: Database,
        console: Optional[Console] = None
    ):
        self.db = database
        self.email_display = EmailDisplay(console)
        self.table_display = EmailTableDisplay(console)
    
    @async_log_call
    async def view_single(
        self,
        email_id: str,
        folder: str = "inbox",
        mark_read: bool = True
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
            email = await self.db.get_email(folder, email_id, include_body=True)
            
            if not email:
                raise EmailNotFoundError(
                    user_message=f"Email not found in {folder}",
                    details={"email_id": email_id, "folder": folder}
                )
            
            self.email_display.display(email)
            
            if mark_read and not email.get('is_read'):
                await self.db.update_field(folder, email_id, 'is_read', True)
            
            return True
            
        except EmailNotFoundError as e:
            logger.error(f"Email not found: {e.details}")
            self.email_display.show_error(e.user_message)
            return False

        except KernelError as e:
            logger.error(f"Kernel error viewing email {email_id}: {e.message}")
            self.email_display.show_error(e.user_message)
            return False

        except Exception as e:
            logger.error(f"Failed to view email {email_id}: {e}")
            self.email_display.show_error("Failed to display email")
            return False
    
    @async_log_call
    async def view_list(
        self,
        folder: str = "inbox",
        limit: int = 50,
        filters: Optional[EmailFilters] = None
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
            query_filters = filters.to_query() if filters else {}
            if query_filters:
                emails = await self.db.get_emails(
                    folder,
                    limit=limit,
                    include_body=False,
                    **query_filters
                )
            else:
                emails = await self.db.get_emails(
                    folder,
                    limit=limit,
                    include_body=False
                )
            
            show_flagged = (folder == "inbox")
            
            self.table_display.display(
                emails=emails,
                title=folder.title(),
                show_flagged=show_flagged
            )
            
            return True
            
        except KernelError as e:
            logger.error(f"Failed to view {folder}: {e.message}")
            self.email_display.show_error(e.user_message)
            return False

        except Exception as e:
            logger.error(f"Failed to view {folder}: {e}")
            self.email_display.show_error(f"Failed to display {folder}")
            return False


## Factory functions

async def view_email(
    email_id: str,
    folder: str = "inbox",
    console: Optional[Console] = None
) -> bool:
    """View a single email."""
    db = get_database(ConfigManager())
    workflow = ViewWorkflow(db, console)
    return await workflow.view_single(email_id, folder)

async def view_inbox(
    limit: int = 50,
    filters: Optional[EmailFilters] = None,
    console: Optional[Console] = None
) -> bool:
    """View inbox."""
    db = get_database(ConfigManager())
    workflow = ViewWorkflow(db, console)
    return await workflow.view_list("inbox", limit, filters)

async def view_folder(
    folder: str,
    limit: int = 50,
    filters: Optional[EmailFilters] = None,
    console: Optional[Console] = None
) -> bool:
    """View any folder."""
    db = get_database(ConfigManager())
    workflow = ViewWorkflow(db, console)
    return await workflow.view_list(folder, limit, filters)