"""Email synchronization feature.

Public API:
    sync_emails(mode) -> Sync with IMAP server
    refresh_folder(folder) -> Refresh specific folder
"""

from .workflow import sync_emails, refresh_folder, SyncWorkflow

__all__ = ['sync_emails', 'refresh_folder', 'SyncWorkflow']