"""IMAP client module for email operations.

Provides asynchronous IMAP operations with:
- Automatic connection management (health checks, TTL, reconnections)
- Batch email fetching with configurable sizes and delays
- Email operations: delete, move, flag, mark as read/unread
- Folder management: list folders, get folder status
- Connection health statistics

Architecture
------------
- IMAPClient: High-level operations (fetch, delete, move, etc.)
- IMAPConnection: Low-level connection handling and lifecycle management
- Shared connection state

Usage Examples
----------------

Fetch new emails:
    >>> from src.core.email.imap import get_imap_client, SyncMode
    >>>
    >>> imap = get_imap_client(config)
    >>>
    >>> # Fetch new emails only (incremental sync)
    >>> count = await imap.fetch_new_emails(SyncMode.INCREMENTAL)
    >>>
    >>> # Fetch all emails (full sync)
    >>> count = await imap.fetch_new_emails(SyncMode.FULL)

Email operations:
    >>> # Delete email
    >>> success = await imap.delete_email(uid="12345")
    >>>
    >>> # Move email
    >>> success = await imap.move_email("12345", "Archive")
    >>>
    >>> # Mark as read
    >>> success = await imap.update_read_status("12345", read=True)
    >>>
    >>> # Flag email
    >>> success = await imap.update_flag_status("12345", flagged=True)

Connection statistics:
    >>> stats = imap.get_connection_stats()
    >>> print(stats)
    # {'connections_created': 2, 'reconnections': 1, 'operations_count': 150, ...}
"""

from .client import IMAPClient, SyncMode
from .connection import IMAPConnection

__all__ = ["IMAPClient", "SyncMode", "IMAPConnection"]


def get_imap_client(config) -> IMAPClient:
    """Factory function to create an IMAPClient instance.

    Args:
        config: Configuration object with IMAP settings

    Returns:
        IMAPClient instance

    Example:
        >>> from src.utils.config import ConfigManager
        >>> from src.core.email.imap import get_imap_client
        >>>
        >>> config = ConfigManager()
        >>> imap = get_imap_client(config)
        >>> count = await imap.fetch_new_emails()
    """
    return IMAPClient(config)
