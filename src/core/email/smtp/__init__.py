"""SMTP client for sending emails.

Provides asynchronous SMTP operations with:
- Automatic connection management (health checks, TTL)
- Retry logic for transient failures
- Multiple recipient support (To, CC, BCC)
- Connection health statistics and monitoring

Architecture
------------
- SMTPClient: High-level email sending operations
- SMTPConnection: Low-level SMTP connection handling and lifecycle management
- Shared connection state

Usage Examples
----------------

Send basic email:
    >>> from src.core.email.smtp import get_smtp_client
    >>>
    >>> smtp = get_smtp_client(config)
    >>>
    >>> await smtp.send_email(
    ...     to_email="recipient@example.com",
    ...     subject="Test Email",
    ...     body="This is a test email."
    ... )

Send email with CC and BCC:
    >>> await smtp.send_email(
    ...     to_email="recipient@example.com",
    ...     subject="Test Email",
    ...     body="This is a test email.",
    ...     cc=["recipient2@example.com"],
    ...     bcc=["recipient3@example.com"]
    ... )

Connection statistics:
    >>> stats = smtp.get_connection_stats()
    >>> print(stats)
    # {
    #   'connections_created': 1,
    #   'emails_sent': 15,
    #   'send_failures': 2,
    #   "avg_send_time": 1.35
    # }

Error Handling
--------------
Transient errors (e.g., network issues) are retried automatically with
exponential backoff. Non-transient errors (e.g., authentication failures)
raise SMTPError immediately.

All operations raise exceptions on failure:
- SMTPError: Send operation failed
- NetworkTimeoutError: Operation timeout occurred
- AuthenticationError: Invalid credentials
"""

from .client import SMTPClient, get_smtp_client
from .connection import SMTPConnection

__all__ = ["SMTPClient", "SMTPConnection", "get_smtp_client"]
