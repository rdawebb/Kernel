"""Email handling - IMAP fetching, SMTP sending, and parsing.

This module provides service-layer APIs for email operations:
- EmailFetchService: Fetch emails from IMAP with retry and persistence
- EmailSendService: Send emails via SMTP with retry logic
- EmailParser: Parse RFC822 messages into structured data

All services use automatic connection management, retry logic,
and persistence.

Recommended Imports (for internal code)
---------------------------------------
Import services directly from their modules for clarity:

    >>> from src.core.email.services.fetch import EmailFetchServiceFactory, SyncMode
    >>> from src.core.email.services.send import EmailSendServiceFactory
    >>> from src.core.email.parser import EmailParser

This makes the architecture explicit and improves IDE support.

Quick Start Examples
--------------------

Fetch emails:
    >>> from src.core.email.services.fetch import EmailFetchServiceFactory, SyncMode
    >>> from src.core.models.email import FolderName
    >>>
    >>> async with EmailFetchServiceFactory.create() as service:
    ...     stats = await service.fetch_new_emails(
    ...         folder=FolderName.INBOX,
    ...         sync_mode=SyncMode.INCREMENTAL
    ...     )
    ...     print(f"Fetched {stats.saved_count} new emails")

Send emails:
    >>> from src.core.email.services.send import EmailSendServiceFactory
    >>>
    >>> async with EmailSendServiceFactory.create() as service:
    ...     stats = await service.send_email(
    ...         to_email="user@example.com",
    ...         subject="Test Email",
    ...         body="Hello from the service layer!"
    ...     )
    ...     print(f"Sent: {stats.success}")

Parse email:
    >>> from src.core.email.parser import EmailParser
    >>>
    >>> email = EmailParser.parse_from_bytes(raw_bytes, uid="123")
    >>> print(email.subject)

Direct Access to Components
----------------------------
For advanced usage or testing, you can access lower-level components:

    >>> from src.core.email.imap import IMAPClient, IMAPProtocol, IMAPConnection
    >>> from src.core.email.smtp import SMTPClient, SMTPProtocol, SMTPConnection

Convenience Re-exports
----------------------
This module re-exports common components for external packages.
Internal code should prefer direct imports from service modules.

Architecture
------------
```
Services Layer (High-level - USE THIS)
├── EmailFetchService (fetch emails + persistence)
├── EmailSendService (send emails + retry + persistence)
└── Factories (resource management)

Protocol Layer (Low-level - for advanced use)
├── IMAP (IMAPClient, IMAPProtocol, IMAPConnection)
├── SMTP (SMTPClient, SMTPProtocol, SMTPConnection)
└── Parser (EmailParser)
```

See Also
--------
- EmailFetchService: Full fetch service documentation
- EmailSendService: Full send service documentation
- EmailParser: Full parser documentation
"""

# Service layer - RECOMMENDED
from .services.fetch import (
    EmailFetchService,
    FetchStats,
    SyncMode,
)
from .services.fetch_factory import EmailFetchServiceFactory
from .services.send import EmailSendService, SendStats
from .services.send_factory import EmailSendServiceFactory

# Parser
from .parser import EmailParser

# Low-level components - for advanced usage
from .imap import IMAPClient, IMAPProtocol, IMAPConnection
from .smtp import SMTPClient, SMTPProtocol, SMTPConnection

__all__ = [
    # ===== Service Layer (Recommended) =====
    # Fetch service
    "EmailFetchService",
    "EmailFetchServiceFactory",
    "FetchStats",
    "SyncMode",
    # Send service
    "EmailSendService",
    "EmailSendServiceFactory",
    "SendStats",
    # ===== Parser =====
    "EmailParser",
    # ===== Low-level Components =====
    # IMAP
    "IMAPClient",
    "IMAPProtocol",
    "IMAPConnection",
    # SMTP
    "SMTPClient",
    "SMTPProtocol",
    "SMTPConnection",
]
