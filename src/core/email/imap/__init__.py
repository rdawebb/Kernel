"""IMAP protocol implementation.

Low-level IMAP components for building services:
- IMAPProtocol: IMAP protocol operations
- IMAPConnection: Connection lifecycle management
- IMAPClient: High-level IMAP operations

For email fetching, use EmailFetchService from services layer.

Architecture
------------
- IMAPConnection: Connection management (health checks, TTL, reconnections)
- IMAPProtocol: Low-level IMAP commands (SELECT, SEARCH, FETCH, etc.)
- IMAPClient: High-level operations (delete, move, flag, etc.)

Direct Usage (Advanced)
-----------------------
Most users should use EmailFetchService instead. Direct usage:

    >>> from src.core.email.imap import IMAPConnection, IMAPProtocol, IMAPClient
    >>> from src.utils.config import ConfigManager
    >>>
    >>> config = ConfigManager()
    >>> connection = IMAPConnection(config)
    >>> protocol = IMAPProtocol(connection)
    >>> client = IMAPClient(protocol)
    >>>
    >>> # Use client for operations
    >>> await client.delete_email("12345")
    >>>
    >>> # Clean up
    >>> await connection.close_connection()

Recommended Usage
-----------------
Use the service layer for complete workflows:

    >>> from src.core.email.services.fetch import EmailFetchServiceFactory
    >>>
    >>> async with EmailFetchServiceFactory.create() as fetch_service:
    ...     stats = await fetch_service.fetch_new_emails()
    ...     print(f"Fetched {stats.saved_count} emails")
"""

from .client import IMAPClient
from .connection import IMAPConnection
from .protocol import IMAPProtocol

__all__ = [
    "IMAPClient",
    "IMAPConnection",
    "IMAPProtocol",
]
