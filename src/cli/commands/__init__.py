"""Command handlers for the Kernel CLI

This module provides:
1. Individual command handlers (list, view, search, etc.) - loaded on demand
2. Command registry for daemon command routing with metadata support
3. Utilities for command discovery and categorization

Command handlers are organized by function:
- Each command has its own module (list.py, view.py, search.py, etc.)
- Each module exports both CLI and daemon-compatible handlers
- The command_registry module maps command names to daemon handlers with metadata
"""

# Import registry and metadata
from .command_registry import (
    CommandMetadata,
    _registry,
    get_categories,
    get_command_metadata,
    get_commands_grouped_by_category,
)

__all__ = [
    # Registry instance
    '_registry',
    # CLI Commands
    'inbox_cli',
    'search_cli',
    'view_cli',
    'database_cli',
    # Metadata API
    'CommandMetadata',
    'get_command_metadata',
    'get_categories',
    'get_commands_grouped_by_category',
]
