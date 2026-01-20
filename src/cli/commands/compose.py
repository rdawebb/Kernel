"""Compose command implementation."""

from typing import Any, Dict

from src.features.compose import compose_email

from .base import BaseCommand


class ComposeCommand(BaseCommand):
    """Command for composing and sending new emails."""

    @property
    def name(self) -> str:
        """Command name.

        Returns:
            str: Command name
        """
        return "compose"

    @property
    def description(self) -> str:
        """Command description.

        Returns:
            str: Command description
        """
        return "Compose a new email"

    def add_arguments(self, parser) -> None:
        """Add compose-specific arguments.

        Args:
            parser: ArgumentParser to configure
        """
        # Optional direct composition arguments
        parser.add_argument("--to", help="Recipient email addresses (comma-separated)")
        parser.add_argument("--subject", help="Email subject")
        parser.add_argument("--body", help="Email body content")
        parser.add_argument(
            "--cc",
            action="append",
            help="CC recipient email addresses (comma-separated)",
        )
        parser.add_argument(
            "--bcc",
            action="append",
            help="BCC recipient email addresses (comma-separated)",
        )

    async def execute_impl(self, args: Dict[str, Any]) -> bool:
        """Execute compose command.

        Args:
            args: Parsed arguments containing optional:
                - to: Recipient addresses
                - subject: Email subject
                - body: Email body
                - cc: CC addresses
                - bcc: BCC addresses

                Note: compose_email feature handles interactive flow
                if arguments are not provided.

        Returns:
            True if successful
        """
        return await compose_email(console=self.console)
