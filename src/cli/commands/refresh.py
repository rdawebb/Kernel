"""Refresh/sync command implementation."""

from typing import Any, Dict

from src.features.sync import sync_emails

from .base import BaseCommand


class RefreshCommand(BaseCommand):
    """Command for fetching new emails from server."""

    @property
    def name(self) -> str:
        """Command name.

        Returns:
            str: Command name
        """
        return "refresh"

    @property
    def description(self) -> str:
        """Command description.

        Returns:
            str: Command description
        """
        return "Fetch new emails from server"

    def add_arguments(self, parser) -> None:
        """Add refresh-specific arguments.

        Args:
            parser: ArgumentParser to configure
        """
        parser.add_argument(
            "--all",
            action="store_true",
            help="Fetch all emails, not just new ones",
        )
        self.add_limit_argument(parser, default=50)

    async def execute_impl(self, args: Dict[str, Any]) -> bool:
        """Execute refresh command.

        Args:
            args: Parsed arguments containing:
                - all: Fetch all emails flag (vs just new)
                - limit: Max emails to fetch

        Returns:
            True if successful
        """
        full = args.get("all", False)

        return await sync_emails(full=full, console=self.console)
