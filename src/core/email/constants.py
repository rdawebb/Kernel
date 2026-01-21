"""Shared constants for email protocols.

Centralised configuration for:
- IMAP/SMTP response codes
- Timeout settings
- Batch sizes for bulk operations

These constants ensure consistency across email handling modules and
enable adjustments for performance tuning and reliability.

Customisation:
---------------
To customise timeout settings or batch sizes, modify the values
in the respective classes below. All email clients will automatically
use the updated settings.

Performance Tuning:
-------------------
- Increase IMAP_FETCH_BATCH for faster sync (more memory usage)
- Decrease timeouts if server is very responsive
- Increase timeouts for slow or unreliable connections
- Adjust IMAP_FETCH_DELAY to balance load on server during bulk fetches
"""

from enum import Enum


class IMAPResponse(str, Enum):
    "IMAP server response codes."

    OK = "OK"
    NO = "NO"
    BAD = "BAD"


class Timeouts:
    """Timeout settings for email operations (in seconds)."""

    # SMTP
    SMTP_CONNECT = 30.0
    SMTP_LOGIN = 30.0
    SMTP_SEND = 30.0
    SMTP_NOOP = 3.0
    SMTP_QUIT = 5.0
