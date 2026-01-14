"""Search workflow orchestration."""

from typing import Optional
from rich.console import Console

from src.core.database import Database, get_database
from src.utils.config import ConfigManager
from src.utils.logging import async_log_call, get_logger

from .query import SearchQuery
from .display import SearchDisplay

logger = get_logger(__name__)


class SearchWorkflow:
    """Orchestrates email search operations."""

    def __init__(self, database: Database, console: Optional[Console] = None):
        self.db = database
        self.display = SearchDisplay.display_results(console)

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
            # Execute search
            if query.search_all_folders:
                results = await self.db.search_all_tables(query.keyword, limit=limit)
            else:
                results = await self.db.search(
                    query.folder, query.keyword, limit=limit, fields=query.fields
                )

            # Display results
            self.display.display(
                results=results, query=query, show_source=query.search_all_folders
            )

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
    db = get_database(ConfigManager())
    workflow = SearchWorkflow(db, console)

    query = SearchQuery(keyword=keyword, folder=folder, search_all_folders=search_all)

    return await workflow.search(query, limit)
