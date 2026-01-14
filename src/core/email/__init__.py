"""Email protocol handling for IMAP, SMTP, and parsing.

This module provides clients for email operations:
- IMAP: Fetch, search, delete, move, flag emails
- SMTP: Send emails with retry logic
- Parser: Parse RFC822 email messages into structured data

All clients are asynchronous, use automatic reconnection,
and credential management.

Usage Examples
----------------

Fetch emails via IMAP:
    >>> from src.core.email.imap import get_imap_client, SyncMode
    >>>
    >>> imap = get_imap_client(config)
    >>> count = await imap.fetch_new_emails(SyncMode.INCREMENTAL)
    >>> print(f"Fetched {count} new emails")

Send email via SMTP:
    >>> from src.core.email.smtp import get_smtp_client
    >>>
    >>> smtp = get_smtp_client(config)
    >>> await smtp.send_email(
    ...     to_email="user@example.com",
    ...     subject="Test Email",
    ...     body="This is a test email."
    ... )

Parse email message:
    >>> from src.core.email.parser import EmailParser
    >>>
    >>> email_dict = EmailParser.parse_from_bytes(raw_bytes, uid="123")
    >>> print(email_dict['subject'])

Connection statistics:
    >>> imap_stats = imap.get_connection_stats()
    >>> print(f"Operations: {imap_stats['operations_count']}")
    >>> print(f"Reconnections: {imap_stats['reconnections']}")

Notes
-----
- All operations are asynchronous and require 'await'
- Connections are managed automatically (health checks, TTL, reconnections)
- Credentials are loaded from keystore via CredentialManager
- Malformed emails are logged and skipped
- All clients support structured logging for observability

See Also
--------
- IMAPClient: Full IMAP operations documentation
- SMTPClient: Full SMTP operations documentation
- EmailParser: Full email parsing documentation
- constants: Timeout and batch size configurations
"""

from .imap import IMAPClient
from .parser import EmailParser
from .smtp import SMTPClient

__all__ = [
    # Parser
    "EmailParser",
    # IMAP
    "IMAPClient",
    "SyncMode",
    "get_imap_client",
    # SMTP
    "SMTPClient",
    "get_smtp_client",
]
