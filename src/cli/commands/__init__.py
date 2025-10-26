"""Command handlers for the Kernel CLI

This module provides:
1. Individual command handlers (list, view, search, etc.) - loaded on demand
2. Command registry for daemon command routing
3. Utilities for command discovery

Command handlers are organized by function:
- Each command has its own module (list.py, view.py, search.py, etc.)
- Each module exports both CLI and daemon-compatible handlers
- The command_registry module maps command names to daemon handlers via lazy loading
"""

# Import only the registry and utilities - handlers are lazy-loaded on demand
from .command_registry import (
    command_registry,
    get_command_handler,
    list_commands,
)

__all__ = [
    # Registry and utilities
    'command_registry',
    'get_command_handler',
    'list_commands',
]

