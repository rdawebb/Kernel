"""Routes CLI commands to feature modules."""

from typing import Any, Dict, Optional

from rich.console import Console

from src.utils.logging import async_log_call, get_logger

from .commands import (
    AttachmentsCommand,
    BaseCommand,
    ComposeCommand,
    ConfigCommand,
    DatabaseCommand,
    EmailOperationsCommand,
    RefreshCommand,
    SearchCommand,
    create_folder_commands,
)

logger = get_logger(__name__)


class CommandRouter:
    """Routes commands to appropriate feature workflows."""

    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()
        self._command_registry: Dict[str, BaseCommand] = {}

        self._register_commands()

    def _register_commands(self) -> None:
        """Register all command instances."""
        for command in create_folder_commands(self.console):
            self._command_registry[command.name] = command

        # Simple commands
        self._command_registry["search"] = SearchCommand(self.console)
        self._command_registry["compose"] = ComposeCommand(self.console)
        self._command_registry["refresh"] = RefreshCommand(self.console)

        # Commands with subcommands
        self._command_registry["email"] = EmailOperationsCommand(self.console)
        self._command_registry["attachments"] = AttachmentsCommand(self.console)
        self._command_registry["database"] = DatabaseCommand(self.console)
        self._command_registry["config"] = ConfigCommand(self.console)

    @async_log_call
    async def route(self, command: str, args: Optional[Dict[str, Any]] = None) -> bool:
        """Route command to feature.

        Args:
            command: Command name
            args: Parsed arguments dictionary

        Returns:
            True if command executed successfully

        Raises:
            ValueError: If command is unknown
        """
        if args is None:
            args = {}

        if not isinstance(command, str):
            raise TypeError("First argument to route() must be a command string")
        if not isinstance(args, dict):
            raise TypeError("Second argument to route() must be a dict")

        if command in self._command_registry:
            cmd = self._command_registry[command]
            try:
                return await cmd.execute(args)
            except Exception as e:
                logger.error(f"Command '{command}' failed: {e}")
                raise

        raise ValueError(f"Unknown command: {command}")

    def get_available_commands(self) -> Dict[str, str]:
        """Get all available commands and their descriptions.

        Returns:
            Dictionary mapping command names to descriptions
        """
        return {name: cmd.description for name, cmd in self._command_registry.items()}
