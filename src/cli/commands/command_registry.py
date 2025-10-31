"""Command registry for the Kernel CLI

This module provides a registry pattern for command handlers with metadata.
Commands can be registered with additional metadata like description, category, etc.
"""

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

from .attachments import handle_attachments_daemon, handle_attachments_list_daemon
from .backup import handle_backup_daemon
from .compose import handle_compose_daemon
from .delete import handle_delete_command_daemon
from .delete_db import handle_delete_db_daemon
from .download import handle_download_daemon
from .export import handle_export_daemon
from .flag import handle_flag_command_daemon
from .list import handle_list_command_daemon
from .move import handle_move_daemon
from .refresh import handle_refresh_command_daemon
from .search import handle_search_command_daemon
from .view import handle_view_command_daemon


@dataclass
class CommandMetadata:
    """Metadata for a registered command."""
    
    name: str
    handler: Callable
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
        handler: Callable,
        description: str = "",
        category: str = "general",
        aliases: Optional[List[str]] = None,
        requires_daemon: bool = True
    ) -> None:
        """Register a command with metadata."""

        metadata = CommandMetadata(
            name=name,
            handler=handler,
            description=description,
            category=category,
            aliases=aliases or [],
            requires_daemon=requires_daemon
        )
        
        # Register primary name
        self._commands[name] = metadata
        
        # Register aliases
        for alias in metadata.aliases:
            self._commands[alias] = metadata
    
    def get_handler(self, command: str) -> Optional[Callable]:
        """Get handler function for a command."""

        metadata = self._commands.get(command)
        return metadata.handler if metadata else None
    
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


# Create global registry instance
_registry = CommandRegistry()


# Register all commands with metadata
def _initialize_registry():
    """Initialize the command registry with all available commands."""
    
    # Email management commands
    _registry.register(
        "list",
        handle_list_command_daemon,
        description="List emails from inbox",
        category="email"
    )
    
    _registry.register(
        "view",
        handle_view_command_daemon,
        description="View email details",
        category="email"
    )
    
    _registry.register(
        "search",
        handle_search_command_daemon,
        description="Search emails by keyword",
        category="email"
    )
    
    _registry.register(
        "compose",
        handle_compose_daemon,
        description="Compose and send email",
        category="email"
    )
    
    # Email actions
    _registry.register(
        "flag",
        handle_flag_command_daemon,
        description="Flag an email",
        category="email_actions"
    )
    
    _registry.register(
        "unflag",
        handle_flag_command_daemon,
        description="Unflag an email",
        category="email_actions",
        aliases=[]
    )
    
    _registry.register(
        "move",
        handle_move_daemon,
        description="Move email to another folder",
        category="email_actions"
    )
    
    _registry.register(
        "delete",
        handle_delete_command_daemon,
        description="Delete an email",
        category="email_actions"
    )
    
    # Attachment commands
    _registry.register(
        "attachments",
        handle_attachments_daemon,
        description="List emails with attachments",
        category="attachments"
    )
    
    _registry.register(
        "attachments-list",
        handle_attachments_list_daemon,
        description="List attachments for an email",
        category="attachments"
    )
    
    _registry.register(
        "download",
        handle_download_daemon,
        description="Download email attachments",
        category="attachments"
    )
    
    # Database commands
    _registry.register(
        "refresh",
        handle_refresh_command_daemon,
        description="Refresh emails from server",
        category="database"
    )
    
    _registry.register(
        "backup",
        handle_backup_daemon,
        description="Backup the database",
        category="database"
    )
    
    _registry.register(
        "export",
        handle_export_daemon,
        description="Export emails to CSV",
        category="database"
    )
    
    _registry.register(
        "delete-db",
        handle_delete_db_daemon,
        description="Delete the local database",
        category="database"
    )


# Initialize registry on module import
_initialize_registry()


# Public API - direct access to registry methods
def get_command_metadata(command: str) -> Optional[CommandMetadata]:
    """Get full metadata for a command."""

    return _registry.get_metadata(command)

def get_categories() -> List[str]:
    """Get all command categories."""

    return _registry.list_categories()

def get_commands_grouped_by_category() -> Dict[str, List[str]]:
    """Get commands organized by category."""
    
    return _registry.get_commands_by_category()
