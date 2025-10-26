"""Command registry for the Kernel CLI

This module provides:
1. Command registry mapping command names to handlers (lazy-loaded to avoid import-time Console instantiation)
2. Utility functions for command lookup and discovery
"""

from typing import Dict, Optional, Callable


_handlers_cache: Dict[str, Callable] = {}
_handler_modules = {
    'list': ('list', 'handle_list_daemon'),
    'view': ('view', 'handle_view_daemon'),
    'search': ('search', 'handle_search_daemon'),
    'attachments': ('attachments', 'handle_attachments_daemon'),
    'attachments-list': ('attachments', 'handle_attachments_list_daemon'),
    'flagged': ('flag', 'handle_flagged_daemon'),
    'flag': ('flag', 'handle_flag_daemon'),
    'unflagged': ('flag', 'handle_unflagged_daemon'),
    'delete': ('delete', 'handle_delete_daemon'),
    'move': ('move', 'handle_move_daemon'),
    'download': ('download', 'handle_download_daemon'),
    'compose': ('compose', 'handle_compose_daemon'),
    'refresh': ('refresh', 'handle_refresh_daemon'),
    'backup': ('backup', 'handle_backup_daemon'),
    'export': ('export', 'handle_export_daemon'),
    'delete-db': ('delete_db', 'handle_delete_db_daemon'),
}


def _load_handler(command: str) -> Optional[Callable]:
    """Lazy-load a command handler on demand."""

    # Check cache first
    if command in _handlers_cache:
        return _handlers_cache[command]
    
    if command not in _handler_modules:
        return None
    
    # Load handler dynamically
    module_name, handler_name = _handler_modules[command]
    try:
        module = __import__(f'src.cli.commands.{module_name}', fromlist=[handler_name])
        handler = getattr(module, handler_name)
        _handlers_cache[command] = handler
        return handler
    except (ImportError, AttributeError):
        return None
    

class LazyCommandRegistry(dict):
    """Dict-like registry that lazy-loads command handlers on access."""
    
    def __init__(self):
        """Initialize with available command names."""
        super().__init__()
        for cmd in _handler_modules.keys():
            self[cmd] = None  # Placeholder
    
    def __getitem__(self, key: str) -> Callable:
        """Get handler, lazy-loading if needed."""
        handler = _load_handler(key)
        if handler is None:
            raise ValueError(f"Unrecognized command: '{key}'. Please check the command and try again.")
        return handler
    
    def get(self, key: str, default=None) -> Optional[Callable]:
        """Get handler with default, lazy-loading if needed."""
        try:
            return self[key]
        except KeyError:
            return default
    
    def __contains__(self, key: str) -> bool:
        """Check if command exists."""
        return key in _handler_modules
    
    def keys(self):
        """Get all command names."""
        return _handler_modules.keys()
    
    def values(self):
        """Get all handlers (loaded on access)."""
        return [_load_handler(cmd) for cmd in _handler_modules.keys()]
    
    def items(self):
        """Get all command/handler pairs (loaded on access)."""
        return [(cmd, _load_handler(cmd)) for cmd in _handler_modules.keys()]


command_registry = LazyCommandRegistry()


def get_command_handler(command: str) -> Optional[Callable]:
    """Get handler for a specific command."""
    return command_registry.get(command)


def list_commands() -> list:
    """List all available commands."""
    return sorted(command_registry.keys())
