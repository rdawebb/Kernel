"""Email synchronization feature.

Public API:
    sync_emails(mode) -> Sync with IMAP server
    refresh_folder(folder) -> Refresh specific folder
"""

from .workflow import sync_emails

__all__ = ["sync_emails"]
