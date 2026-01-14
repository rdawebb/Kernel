"""Search display coordinator (uses shared UI components)."""

from typing import Any, Dict, List, Optional
from rich.console import Console

from src.ui.components import EmailTable, StatusMessage
from .query import SearchQuery


class SearchDisplay:
    """Coordinates display for search feature."""

    def __init__(self, console: Optional[Console] = None):
        self.table = EmailTable(console)
        self.message = StatusMessage(console)

    def display_results(
        self, results: List[Dict[str, Any]], query: SearchQuery
    ) -> None:
        """Display search results (delegates to EmailTable with custom title)."""
        scope = "all folders" if query.search_all_folders else query.folder
        title = f"Search: '{query.keyword}' in {scope}"

        self.table.display(
            emails=results,
            title=title,
            show_source=query.search_all_folders,
            show_flagged=False,
        )

        # Add result count message
        if results:
            self.message.success(f"Found {len(results)} result(s)")
        else:
            self.message.info(f"No results for '{query.keyword}'")

    def show_error(self, message: str) -> None:
        """Show error (delegates to StatusMessage)."""
        self.message.error(message)
