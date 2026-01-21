"""SMTP protocol implementation.

Low-level SMTP components for building services:
- SMTPProtocol: SMTP protocol operations
- SMTPConnection: Connection lifecycle management
- SMTPClient: High-level SMTP operations

For email sending, use EmailSendService from services layer.

Architecture
------------
- SMTPConnection: Connection management (health checks, TTL, reconnections)
- SMTPProtocol: Low-level SMTP commands (send, verify, noop)
- SMTPClient: High-level operations (send text/HTML, attachments)

Direct Usage (Advanced)
-----------------------
Most users should use EmailSendService instead. Direct usage:

    >>> from src.core.email.smtp import SMTPConnection, SMTPProtocol, SMTPClient
    >>> from src.utils.config import ConfigManager
    >>>
    >>> config = ConfigManager()
    >>> connection = SMTPConnection(config)
    >>> protocol = SMTPProtocol(connection)
    >>> client = SMTPClient(protocol, "sender@example.com")
    >>>
    >>> # Send email
    >>> await client.send_text_email(
    ...     to_email="recipient@example.com",
    ...     subject="Test",
    ...     body="Hello"
    ... )
    >>>
    >>> # Clean up
    >>> await connection.close_connection()

Recommended Usage
-----------------
Use the service layer for complete workflows:

    >>> from src.core.email.services.send import EmailSendServiceFactory
    >>>
    >>> async with EmailSendServiceFactory.create() as send_service:
    ...     stats = await send_service.send_email(
    ...         to_email="recipient@example.com",
    ...         subject="Test",
    ...         body="Hello"
    ...     )
    ...     print(f"Success: {stats.success}")
"""

from .client import SMTPClient
from .connection import SMTPConnection
from .protocol import SMTPProtocol

__all__ = [
    "SMTPClient",
    "SMTPConnection",
    "SMTPProtocol",
]
