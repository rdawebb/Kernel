"""Email operations command implementation."""

from typing import Any, Dict

from src.features.manage import delete_email, flag_email, move_email, unflag_email
from src.features.view import view_email

from .base import BaseCommand


class EmailOperationsCommand(BaseCommand):
    """Command for email operations (view, delete, flag, unflag, move).

    Handles subcommands that operate on individual emails by ID.
    """

    @property
    def name(self) -> str:
        """Command name.

        Returns:
            str: Command name
        """
        return "email"

    @property
    def description(self) -> str:
        """Command description.

        Returns:
            str: Command description
        """
        return "Email operations (view, delete, flag, etc)"

    def add_arguments(self, parser) -> None:
        """Add email operations subcommands.

        Args:
            parser: ArgumentParser to configure
        """
        # Create subparsers for email operations
        subparsers = parser.add_subparsers(
            dest="email_command",
            required=True,
            help="Email operation to perform",
        )

        # View subcommand
        view_parser = subparsers.add_parser(
            "view",
            help="View email details",
        )
        view_parser.add_argument("id", help="Email ID")
        self.add_folder_argument(view_parser, required=False)

        # Delete subcommand
        delete_parser = subparsers.add_parser(
            "delete",
            help="Delete an email",
        )
        delete_parser.add_argument("id", help="Email ID")
        delete_parser.add_argument(
            "--permanent",
            action="store_true",
            help="Permanently delete email (if in trash)",
        )
        self.add_folder_argument(delete_parser, required=False)

        # Flag subcommand
        flag_parser = subparsers.add_parser(
            "flag",
            help="Flag an email",
        )
        flag_parser.add_argument("id", help="Email ID")
        self.add_folder_argument(flag_parser, required=False)

        # Unflag subcommand
        unflag_parser = subparsers.add_parser(
            "unflag",
            help="Unflag an email",
        )
        unflag_parser.add_argument("id", help="Email ID")
        self.add_folder_argument(unflag_parser, required=False)

        # Move subcommand
        move_parser = subparsers.add_parser(
            "move",
            help="Move an email to another folder",
        )
        move_parser.add_argument("id", help="Email ID")
        move_parser.add_argument(
            "--to",
            dest="destination",
            required=True,
            choices=["inbox", "sent", "drafts", "trash"],
            help="Destination folder",
        )
        move_parser.add_argument(
            "--from",
            dest="source",
            default="inbox",
            choices=["inbox", "sent", "drafts", "trash"],
            help="Source folder (default: inbox)",
        )

    async def execute_impl(self, args: Dict[str, Any]) -> bool:
        """Execute email operation based on subcommand.

        Args:
            args: Parsed arguments containing:
                - email_command: Subcommand (view/delete/flag/unflag/move)
                - id: Email ID
                - folder: Folder name (for most operations)
                - permanent: Permanent delete flag (delete only)
                - destination: Target folder (move only)
                - source: Source folder (move only)

        Returns:
            True if successful

        Raises:
            ValueError: If subcommand is unknown or required args missing
        """
        email_command = args.get("email_command")

        if not email_command:
            raise ValueError("Email subcommand is required")

        # Route to appropriate handler
        if email_command == "view":
            return await self._handle_view(args)
        elif email_command == "delete":
            return await self._handle_delete(args)
        elif email_command == "flag":
            return await self._handle_flag(args)
        elif email_command == "unflag":
            return await self._handle_unflag(args)
        elif email_command == "move":
            return await self._handle_move(args)
        else:
            raise ValueError(f"Unknown email operation: {email_command}")

    async def _handle_view(self, args: Dict[str, Any]) -> bool:
        """Handle view email operation.

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

        return await view_email(email_id, folder, console=self.console)

    async def _handle_delete(self, args: Dict[str, Any]) -> bool:
        """Handle delete email operation.

        Args:
            args: Parsed arguments with id, folder, and permanent flag

        Returns:
            True if successful

        Raises:
            ValueError: If email_id is missing
        """
        email_id = args.get("id")
        folder = args.get("folder", "inbox")
        permanent = args.get("permanent", False)

        if not email_id:
            raise ValueError("Email ID is required")

        return await delete_email(
            email_id=email_id,
            folder=folder,
            permanent=permanent,
            console=self.console,
        )

    async def _handle_flag(self, args: Dict[str, Any]) -> bool:
        """Handle flag email operation.

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

        return await flag_email(email_id=email_id, folder=folder, console=self.console)

    async def _handle_unflag(self, args: Dict[str, Any]) -> bool:
        """Handle unflag email operation.

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

        return await unflag_email(
            email_id=email_id, folder=folder, console=self.console
        )

    async def _handle_move(self, args: Dict[str, Any]) -> bool:
        """Handle move email operation.

        Args:
            args: Parsed arguments with id, source, and destination

        Returns:
            True if successful

        Raises:
            ValueError: If email_id or destination is missing
        """
        email_id = args.get("id")
        from_folder = args.get("source", "inbox")
        to_folder = args.get("destination")

        if not email_id or not to_folder:
            raise ValueError("Email ID and destination folder are required")

        return await move_email(
            email_id=email_id,
            from_folder=from_folder,
            to_folder=to_folder,
            console=self.console,
        )
