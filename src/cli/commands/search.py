"""Search command implementation."""

from typing import Any, Dict

from src.features.search import search_emails

from .base import BaseCommand


class SearchCommand(BaseCommand):
    """Command for searching emails by keyword."""

    @property
    def name(self) -> str:
        """Command name.

        Returns:
            str: Command name
        """
        return "search"

    @property
    def description(self) -> str:
        """Command description.

        Returns:
            str: Command description
        """
        return "Search emails by keyword"

    def add_arguments(self, parser) -> None:
        """Add search-specific arguments.

        Args:
            parser: ArgumentParser to configure
        """
        parser.add_argument("keyword", help="Keyword to search for")
        parser.add_argument(
            "--in",
            dest="folder",
            default="inbox",
            choices=["inbox", "sent", "drafts", "trash"],
            help="Folder to search in (default: inbox)",
        )
        parser.add_argument("--all", action="store_true", help="Search in all folders")
        self.add_limit_argument(parser, default=50)
        self.add_filter_arguments(parser)

    async def execute_impl(self, args: Dict[str, Any]) -> bool:
        """Execute search command.

        Args:
            args: Parsed arguments containing:
                - keyword: Search term (required)
                - folder: Folder to search in (default: inbox)
                - all: Search all folders flag
                - limit: Max results
                - Filter flags: flagged, unread, etc.

        Returns:
            True if successful

        Raises:
            ValueError: If keyword is missing
        """
        keyword = args.get("keyword")
        if not keyword:
            raise ValueError("Search keyword is required")

        folder = args.get("folder", "inbox")
        limit = args.get("limit", 50)
        search_all = args.get("all", False)

        return await search_emails(
            keyword=keyword,
            folder=folder,
            limit=limit,
            search_all=search_all,
            console=self.console,
        )
