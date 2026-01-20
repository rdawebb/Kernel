"""Attachments command implementation."""

from typing import Any, Dict

from src.features.attachments import (
    download_all_attachments,
    download_attachment,
    list_attachments,
    list_downloads,
    open_attachment,
)

from .base import BaseCommand


class AttachmentsCommand(BaseCommand):
    """Command for attachment operations (list, download, downloads, open)."""

    @property
    def name(self) -> str:
        """Command name.

        Returns:
            str: Command name
        """
        return "attachments"

    @property
    def description(self) -> str:
        """Command description.

        Returns:
            str: Command description
        """
        return "Attachment operations"

    def add_arguments(self, parser) -> None:
        """Add attachments subcommands.

        Args:
            parser: ArgumentParser to configure
        """
        # Create subparsers for attachment operations
        subparsers = parser.add_subparsers(
            dest="attachment_command",
            required=True,
            help="Attachment operation to perform",
        )

        # List subcommand
        list_parser = subparsers.add_parser(
            "list",
            help="List attachments in an email",
        )
        list_parser.add_argument("id", help="Email ID")
        self.add_folder_argument(list_parser, required=False)

        # Download subcommand
        download_parser = subparsers.add_parser(
            "download",
            help="Download attachments from an email",
        )
        download_parser.add_argument("id", help="Email ID")
        download_parser.add_argument(
            "--all", action="store_true", help="Download all attachments"
        )
        download_parser.add_argument(
            "--index", type=int, help="Download attachment by index (0-based)"
        )
        self.add_folder_argument(download_parser, required=False)

        # Downloads subcommand (list downloaded files)
        downloads_parser = subparsers.add_parser(
            "downloads", help="List all downloaded attachments"
        )

        # Open subcommand
        open_parser = subparsers.add_parser("open", help="Open a downloaded attachment")
        open_parser.add_argument("filename", help="Filename to open")

    async def execute_impl(self, args: Dict[str, Any]) -> bool:
        """Execute attachment operation based on subcommand.

        Args:
            args: Parsed arguments containing:
                - attachment_command: Subcommand (list/download/downloads/open)
                - id: Email ID (for list/download)
                - folder: Folder name (for list/download)
                - all: Download all flag (download only)
                - index: Attachment index (download only)
                - filename: Filename to open (open only)

        Returns:
            True if successful

        Raises:
            ValueError: If subcommand is unknown or required args missing
        """
        attachment_command = args.get("attachment_command")

        if not attachment_command:
            raise ValueError("Attachment subcommand is required")

        # Route to appropriate handler
        if attachment_command == "list":
            return await self._handle_list(args)
        elif attachment_command == "download":
            return await self._handle_download(args)
        elif attachment_command == "downloads":
            return await self._handle_downloads(args)
        elif attachment_command == "open":
            return await self._handle_open(args)
        else:
            raise ValueError(f"Unknown attachment operation: {attachment_command}")

    async def _handle_list(self, args: Dict[str, Any]) -> bool:
        """Handle list attachments operation.

        Args:
            args: Parsed arguments with id and folder

        Returns:
            True if successful

        Raises:
            ValueError: If email_id is missing
        """
        email_id = args.get("id")
        folder = args.get("folder", "inbox")

        if not email_id:
            raise ValueError("Email ID is required")

        return await list_attachments(email_id, folder, console=self.console)

    async def _handle_download(self, args: Dict[str, Any]) -> bool:
        """Handle download attachments operation.

        Args:
            args: Parsed arguments with id, folder, all flag, and index

        Returns:
            True if successful

        Raises:
            ValueError: If email_id is missing
        """
        email_id = args.get("id")
        folder = args.get("folder", "inbox")
        index = args.get("index")
        download_all = args.get("all", False)

        if not email_id:
            raise ValueError("Email ID is required")

        # Download all or specific attachment
        if download_all or index is None:
            return await download_all_attachments(
                email_id, folder, console=self.console
            )
        else:
            return await download_attachment(
                email_id, index, folder, console=self.console
            )

    async def _handle_downloads(self, args: Dict[str, Any]) -> bool:
        """Handle list downloads operation.

        Args:
            args: Parsed arguments (no args needed)

        Returns:
            True if successful
        """
        return await list_downloads(console=self.console)

    async def _handle_open(self, args: Dict[str, Any]) -> bool:
        """Handle open attachment operation.

        Args:
            args: Parsed arguments with filename

        Returns:
            True if successful

        Raises:
            ValueError: If filename is missing
        """
        filename = args.get("filename")

        if not filename:
            raise ValueError("Filename is required")

        return await open_attachment(filename, console=self.console)
