"""Folder viewing commands (inbox, sent, drafts, trash)."""

from typing import Any, Dict, Optional

from rich.console import Console

from src.features.view import EmailFilters, view_folder

from .base import BaseCommand


class FolderViewCommand(BaseCommand):
    """Command for viewing emails in a specific folder."""

    def __init__(
        self,
        folder_name: str,
        console: Optional[Console] = None,
    ):
        """Initialise folder view command.

        Args:
            folder_name: Default folder to view (inbox/sent/drafts/trash)
            console: Rich Console instance
        """
        super().__init__(console)
        self._folder_name = folder_name

    @property
    def name(self) -> str:
        """Command name matches folder.

        Returns:
            str: The name of the command.
        """
        return self._folder_name

    @property
    def description(self) -> str:
        """Description varies by folder.

        Returns:
            str: The description of the command.
        """
        descriptions = {
            "inbox": "View emails in the inbox",
            "sent": "View sent emails",
            "drafts": "View draft emails",
            "trash": "View deleted emails",
        }

        return descriptions.get(self._folder_name, f"View {self._folder_name} folder")

    def add_arguments(self, parser) -> None:
        """Add folder-specific arguments.

        Args:
            parser: ArgumentParser to configure
        """
        self.add_limit_argument(parser, default=10)
        self.add_filter_arguments(parser)

    async def execute_impl(self, args: Dict[str, Any]) -> bool:
        """Execute folder view.

        Args:
            args: Parsed arguments containing:
                - limit: Number of emails to show
                - Filter flags: flagged, unread, has_attachments, etc.

        Returns:
            True if successful
        """
        limit = args.get("limit", 10)
        filters = self._build_filters(args)

        return await view_folder(
            folder=self._folder_name,
            limit=limit,
            filters=filters,
            console=self.console,
        )

    @staticmethod
    def _build_filters(args: Dict[str, Any]) -> Optional[EmailFilters]:
        """Build EmailFilters from arguments.

        Args:
            args: Parsed command arguments

        Returns:
            EmailFilters instance or None if no filters active
        """
        flagged = None
        if args.get("flagged"):
            flagged = True
        elif args.get("unflagged"):
            flagged = False

        unread = None
        if args.get("unread"):
            unread = True
        elif args.get("read"):
            unread = False

        filters = EmailFilters(
            flagged=flagged,
            unread=unread,
            has_attachments=args.get("has_attachments", False),
            from_address=args.get("from_address"),
            subject_contains=args.get("subject_contains"),
        )

        return filters if filters.has_filters() else None


def create_folder_commands(console: Optional[Console] = None) -> list[BaseCommand]:
    """Factory function to create all folder view commands.

    Args:
        console: Shared Console instance

    Returns:
        List of FolderViewCommand instances for each folder
    """
    folders = ["inbox", "sent", "drafts", "trash"]

    return [FolderViewCommand(folder, console) for folder in folders]
