"""IMAP constants and configuration values."""

from dataclasses import dataclass


class IMAPResponse:
    """Standard IMAP response codes."""

    OK = "OK"
    NO = "NO"
    BAD = "BAD"


class Timeouts:
    """Timeout values for IMAP operations (in seconds)."""

    IMAP_CONNECT = 30.0  # Initial connection timeout
    IMAP_LOGIN = 30.0  # Login operation timeout
    IMAP_SELECT = 10.0  # SELECT folder timeout
    IMAP_SEARCH = 30.0  # SEARCH operation timeout
    IMAP_FETCH = 30.0  # FETCH operation timeout (per batch)
    IMAP_STORE = 10.0  # STORE operation timeout
    IMAP_COPY = 10.0  # COPY operation timeout
    IMAP_EXPUNGE = 10.0  # EXPUNGE operation timeout
    IMAP_LIST = 10.0  # LIST operation timeout
    IMAP_STATUS = 10.0  # STATUS operation timeout
    IMAP_NOOP = 5.0  # NOOP (keep-alive) timeout


@dataclass
class BatchConfig:
    """Configuration for batch operations."""

    FETCH_BATCH_SIZE: int = 50  # Number of emails to fetch per batch
    FETCH_DELAY: float = 0.0  # Delay between batches (seconds)
    SAVE_BATCH_SIZE: int = 100  # Number of emails to save per batch


class IMAPFolders:
    """Standard IMAP folder names."""

    INBOX = "INBOX"
    SENT = "Sent"
    DRAFTS = "Drafts"
    TRASH = "Trash"
    SPAM = "Spam"
    ARCHIVE = "Archive"

    # Gmail-specific folders
    GMAIL_ALL_MAIL = "[Gmail]/All Mail"
    GMAIL_SENT = "[Gmail]/Sent Mail"
    GMAIL_DRAFTS = "[Gmail]/Drafts"
    GMAIL_TRASH = "[Gmail]/Trash"
    GMAIL_SPAM = "[Gmail]/Spam"
    GMAIL_STARRED = "[Gmail]/Starred"
    GMAIL_IMPORTANT = "[Gmail]/Important"


class IMAPFlags:
    """Standard IMAP flags."""

    SEEN = "\\Seen"  # Read/unread status
    FLAGGED = "\\Flagged"  # Starred/flagged
    DELETED = "\\Deleted"  # Marked for deletion
    ANSWERED = "\\Answered"  # Has been replied to
    DRAFT = "\\Draft"  # Is a draft
    RECENT = "\\Recent"  # Recently arrived
