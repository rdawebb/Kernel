"""Command registry for the Kernel CLI

This module provides:
1. Command registry mapping command names to handlers (lazy-loaded to avoid import-time Console instantiation)
2. Utility functions for command lookup and discovery
"""

from typing import Callable, Dict, Optional

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


COMMAND_HANDLERS: Dict[str, Callable] = {
    "attachments": handle_attachments_daemon,
    "attachments-list": handle_attachments_list_daemon,
    "backup": handle_backup_daemon,
    "compose": handle_compose_daemon,
    "delete": handle_delete_command_daemon,
    "delete-db": handle_delete_db_daemon,
    "download": handle_download_daemon,
    "export": handle_export_daemon,
    "flag": handle_flag_command_daemon,
    "unflag": handle_flag_command_daemon,
    "flagged": handle_list_flagged_daemon,
    "list": handle_list_command_daemon,
    "move": handle_move_daemon,
    "refresh": handle_refresh_command_daemon,
    "search": handle_search_command_daemon,
    "view": handle_view_command_daemon,
}


def get_command_handler(command: str) -> Optional[Callable]:
    """Retrieve the handler function for a given command name."""

    return COMMAND_HANDLERS.get(command)


def list_commands() -> list:
    """List all available command names."""

    return sorted(COMMAND_HANDLERS.keys())


def command_exists(command: str) -> bool:
    """Check if a command exists in the registry."""

    return command in COMMAND_HANDLERS

