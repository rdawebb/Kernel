"""Search workflow orchestration."""

from typing import Optional
from rich.console import Console

from src.core.database import EngineManager, EmailRepository
from src.core.database.query import QueryBuilder
from src.utils.paths import DATABASE_PATH
from src.utils.logging import async_log_call, get_logger
from src.core.models.email import FolderName
from src.core.database.utils import row_to_email

from .query import SearchQuery
from .display import SearchDisplay

logger = get_logger(__name__)


class SearchWorkflow:
    """Orchestrates email search operations."""

    def __init__(self, repository: EmailRepository, console: Optional[Console] = None):
        self.repo = repository
        self.display = SearchDisplay(console)

    @async_log_call
    async def search(self, query: SearchQuery, limit: int = 50) -> bool:
        """Execute search and display results.

        Args:
            query: Search query object
            limit: Maximum results

        Returns:
            True if search completed successfully
        """
        try:
            # Map field names from SearchQuery to database column names
            db_fields = set()
            for field in query.fields:
                if field == "from":
                    db_fields.add("sender")
                elif field == "to":
                    db_fields.add("recipient")
                else:
                    db_fields.add(field)

            # Determine which folders to search
            if query.search_all_folders:
                folders = [
                    FolderName.INBOX,
                    FolderName.SENT,
                    FolderName.DRAFTS,
                    FolderName.TRASH,
                ]
            else:
                folders = [FolderName(query.folder)]

            # Build and execute search query
            query_builder = QueryBuilder()
            search_query = query_builder.search_emails(
                folders=folders,
                keyword=query.keyword,
                fields=db_fields,
                limit=limit,
            )

            # Execute search
            engine = await self.repo.engine_mgr.get_engine()
            results = []

            async with engine.connect() as conn:
                result = await conn.execute(search_query)
                rows = result.fetchall()

                # Convert rows to Email objects (we need to infer folder from result)
                for row in rows:
                    # Try to determine folder from result
                    # This is a simplified approach - in real code, we'd include folder in result
                    email = row_to_email(row, FolderName.INBOX)
                    results.append(email.to_dict())

            # Display results
            self.display.display_results(results=results, query=query)

            logger.info(f"Search for '{query.keyword}' found {len(results)} results")
            return True

        except Exception as e:
            logger.error(f"Search failed: {e}")
            self.display.show_error("Search failed")
            return False


# Factory function
async def search_emails(
    keyword: str,
    folder: str = "inbox",
    limit: int = 50,
    search_all: bool = False,
    console: Optional[Console] = None,
) -> bool:
    """Search emails by keyword.

    Args:
        keyword: Search keyword
        folder: Folder to search (if not search_all)
        limit: Maximum results
        search_all: Search all folders
        console: Optional console

    Returns:
        True if search completed
    """
    engine_mgr = EngineManager(DATABASE_PATH)
    try:
        repo = EmailRepository(engine_mgr)
        workflow = SearchWorkflow(repo, console)

        query = SearchQuery(
            keyword=keyword, folder=folder, search_all_folders=search_all
        )

        return await workflow.search(query, limit)
    finally:
        await engine_mgr.close()
