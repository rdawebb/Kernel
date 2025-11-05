"""Command registry for the Kernel CLI

This module provides a registry pattern for command handlers with metadata.
Commands can be registered with additional metadata like description, category, etc.
"""

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

from .attachments import AttachmentsCommandHandler
from .base import create_command_handlers
from .compose import ComposeCommandHandler
from .database import DatabaseCommandHandler
from .email import EmailCommandHandler
from .refresh import RefreshCommandHandler
from .search import SearchCommandHandler
from .viewing import ViewingCommandHandler


@dataclass
class CommandMetadata:
    """Metadata for a registered command."""
    
    name: str
    cli_handler: Callable
    daemon_handler: Callable
    description: str = ""
    category: str = "general"
    aliases: List[str] = None
    requires_daemon: bool = True
    
    def __post_init__(self):
        """Initialize default values."""
        if self.aliases is None:
            self.aliases = []


class CommandRegistry:
    """Registry for CLI command handlers with metadata."""
    
    def __init__(self):
        self._commands: Dict[str, CommandMetadata] = {}
    
    def register(
        self,
        name: str,
        cli_handler: Callable,
        daemon_handler: Callable,
        description: str = "",
        category: str = "general",
        aliases: Optional[List[str]] = None,
        requires_daemon: bool = True
    ) -> None:
        """Register a command with metadata."""
        metadata = CommandMetadata(
            name=name,
            cli_handler=cli_handler,
            daemon_handler=daemon_handler,
            description=description,
            category=category,
            aliases=aliases or [],
            requires_daemon=requires_daemon
        )
        
        self._commands[name] = metadata
        for alias in metadata.aliases:
            self._commands[alias] = metadata
    
    def get_handler(self, command: str, daemon: bool = False) -> Optional[Callable]:
        """Get handler function for a command. Returns daemon_handler if daemon=True, else cli_handler."""
        metadata = self._commands.get(command)
        if not metadata:
            return None
        return metadata.daemon_handler if daemon else metadata.cli_handler
    
    def get_metadata(self, command: str) -> Optional[CommandMetadata]:
        """Get full metadata for a command."""
        return self._commands.get(command)
    
    def exists(self, command: str) -> bool:
        """Check if a command exists."""
        return command in self._commands
    
    def list_commands(self, category: Optional[str] = None) -> List[str]:
        """List all command names, optionally filtered by category."""

        # Get unique commands (filter out aliases)
        seen = set()
        commands = []
        
        for name, metadata in self._commands.items():
            if metadata.name not in seen:
                if category is None or metadata.category == category:
                    commands.append(metadata.name)
                    seen.add(metadata.name)
        
        return sorted(commands)
    
    def list_categories(self) -> List[str]:
        """List all command categories."""
        categories = {meta.category for meta in self._commands.values()}
        return sorted(categories)
    
    def get_commands_by_category(self) -> Dict[str, List[str]]:
        """Get commands grouped by category."""
        result: Dict[str, List[str]] = {}
        
        for metadata in self._commands.values():
            if metadata.name not in result.get(metadata.category, []):
                if metadata.category not in result:
                    result[metadata.category] = []
                result[metadata.category].append(metadata.name)
        
        # Sort commands within each category
        for category in result:
            result[category].sort()
        
        return result


## Global Registry Instance

_registry = CommandRegistry()


## Registration Helper

def register_command_with_base(
        registry: CommandRegistry,
        name: str,
        handler_class: type,
        description: str,
        category: str = "general",
        aliases: List[str] = None,
):
    """Helper function to register commands using BaseCommandHandler"""
    from .base import create_command_handlers

    cli_handler, daemon_handler = create_command_handlers(handler_class)

    registry.register(
        name=name,
        handler=daemon_handler,
        description=description,
        category=category,
        aliases=aliases or []
    )

    return cli_handler


## Initialize Registry with Commands

def _initialize_registry():
    """Initialize the command registry with all available commands."""
    
    # Viewing commands (inbox, sent, drafts, trash)

    viewing_cli, viewing_daemon = create_command_handlers(ViewingCommandHandler)
    
    _registry.register(
        "inbox",
        cli_handler=viewing_cli,
        daemon_handler=viewing_daemon,
        description="View inbox emails",
        category="viewing"
    )
    
    _registry.register(
        "sent",
        cli_handler=viewing_cli,
        daemon_handler=viewing_daemon,
        description="View sent emails",
        category="viewing"
    )
    
    _registry.register(
        "drafts",
        cli_handler=viewing_cli,
        daemon_handler=viewing_daemon,
        description="View draft emails",
        category="viewing"
    )
    
    _registry.register(
        "trash",
        cli_handler=viewing_cli,
        daemon_handler=viewing_daemon,
        description="View deleted emails",
        category="viewing"
    )

    # Email operations command

    email_cli, email_daemon = create_command_handlers(EmailCommandHandler)
    _registry.register(
        "email",
        cli_handler=email_cli,
        daemon_handler=email_daemon,
        description="Email operations (view, delete, flag, unflag, move)",
        category="email"
    )
    
    # Search and compose commands
    
    search_cli, search_daemon = create_command_handlers(SearchCommandHandler)
    _registry.register(
        "search",
        cli_handler=search_cli,
        daemon_handler=search_daemon,
        description="Search emails by keyword",
        category="email"
    )
    
    compose_cli, compose_daemon = create_command_handlers(ComposeCommandHandler)
    _registry.register(
        "compose",
        cli_handler=compose_cli,
        daemon_handler=compose_daemon,
        description="Compose and send email",
        category="email"
    )

    # Attachment commands

    attachments_cli, attachments_daemon = create_command_handlers(AttachmentsCommandHandler)
    _registry.register(
        "attachments",
        cli_handler=attachments_cli,
        daemon_handler=attachments_daemon,
        description="Attachment operations (list, download, downloads, open)",
        category="attachments"
    )

    # Maintenance commands

    refresh_cli, refresh_daemon = create_command_handlers(RefreshCommandHandler)
    _registry.register(
        "refresh",
        cli_handler=refresh_cli,
        daemon_handler=refresh_daemon,
        description="Refresh emails from server",
        category="maintenance"
    )
    
    database_cli, database_daemon = create_command_handlers(DatabaseCommandHandler)
    _registry.register(
        "database",
        cli_handler=database_cli,
        daemon_handler=database_daemon,
        description="Database operations (backup, export, delete, info)",
        category="maintenance"
    )


## Initialize Registry at Import

_initialize_registry()


## Public API - direct access to registry methods

def get_command_metadata(command: str) -> Optional[CommandMetadata]:
    """Get full metadata for a command."""
    return _registry.get_metadata(command)

def get_categories() -> List[str]:
    """Get all command categories."""
    return _registry.list_categories()

def get_commands_grouped_by_category() -> Dict[str, List[str]]:
    """Get commands organized by category."""
    return _registry.get_commands_by_category()
