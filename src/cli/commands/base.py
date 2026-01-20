"""Base command interface and implementation for CLI."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Protocol

from rich.console import Console

from src.utils.logging import async_log_call, get_logger


class Command(Protocol):
    """Protocol for all CLI commands."""

    @property
    def name(self) -> str:
        """Command name used for routing (e.g., 'inbox', 'search')."""
        ...

    @property
    def description(self) -> str:
        """Short description shown in help text."""
        ...

    async def execute(self, args: Dict[str, Any]) -> bool:
        """Execute the command.

        Args:
            args: Parsed command arguments (from argparse)

        Returns:
            True if command succeeded, False otherwise

        Raises:
            ValueError: For invalid arguments
        """
        ...

    def add_arguments(self, parser) -> None:
        """Add command-specific arguments to argparse parser.

        Args:
            parser: ArgumentParser or subparser to configure
        """
        ...


class BaseCommand(ABC):
    """Base implementation for commands with common utilities."""

    def __init__(self, console: Optional[Console] = None):
        """Initialize base command.

        Args:
            console: Rich Console instance (creates new if None)
        """
        self.console = console or Console()
        self.logger = get_logger(self.__class__.__name__)

    @property
    @abstractmethod
    def name(self) -> str:
        """Command name - must be implemented by subclasses."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Command description - must be implemented by subclasses."""
        pass

    @async_log_call
    async def execute(self, args: Dict[str, Any]) -> bool:
        """Execute command with logging.

        Subclasses should override execute_impl instead.

        Args:
            args: Parsed arguments

        Returns:
            True if successful
        """
        return await self.execute_impl(args)

    @abstractmethod
    async def execute_impl(self, args: Dict[str, Any]) -> bool:
        """Implementation of command execution.

        Args:
            args: Parsed command arguments

        Returns:
            True if successful, False otherwise

        Raises:
            ValueError: For invalid arguments
        """
        pass

    @abstractmethod
    def add_arguments(self, parser) -> None:
        """Add command-specific arguments.

        Args:
            parser: ArgumentParser or subparser
        """
        pass

    # Common argument helpers

    @staticmethod
    def add_limit_argument(parser, default: int = 10) -> None:
        """Add --limit argument for pagination.

        Args:
            parser: ArgumentParser to configure
            default: Default limit value
        """
        parser.add_argument(
            "--limit",
            type=int,
            default=default,
            help=f"Number of items to display (default: {default})",
        )

    @staticmethod
    def add_folder_argument(parser, required: bool = False) -> None:
        """Add --folder argument for folder selection.

        Args:
            parser: ArgumentParser to configure
            required: Whether folder is required
        """
        parser.add_argument(
            "--folder",
            default="inbox" if not required else None,
            required=required,
            choices=["inbox", "sent", "drafts", "trash"],
            help="Email folder" + (" (default: inbox)" if not required else ""),
        )

    @staticmethod
    def add_filter_arguments(parser) -> None:
        """Add common email filter arguments.

        Args:
            parser: ArgumentParser to configure
        """
        filter_group = parser.add_argument_group("filters", "Filter displayed emails")

        filter_group.add_argument(
            "--flagged", action="store_true", help="Show only flagged emails"
        )
        filter_group.add_argument(
            "--unflagged", action="store_true", help="Show only unflagged emails"
        )
        filter_group.add_argument(
            "--unread", action="store_true", help="Show only unread emails"
        )
        filter_group.add_argument(
            "--read", action="store_true", help="Show only read emails"
        )
        filter_group.add_argument(
            "--with-attachments",
            action="store_true",
            dest="has_attachments",
            help="Show only emails with attachments",
        )
        filter_group.add_argument(
            "--from", dest="from_address", help="Filter by sender address"
        )
        filter_group.add_argument(
            "--subject", dest="subject_contains", help="Filter by subject keywords"
        )
