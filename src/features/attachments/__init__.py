"""Attachment management feature.

Public API:
    list_attachments(email_id, folder) -> List attachments in email
    download_attachment(email_id, index, folder) -> Download specific attachment
    list_downloads() -> List all downloaded attachments
"""

from .workflow import (
    list_attachments,
    download_attachment,
    download_all_attachments,
    list_downloads,
    open_attachment,
    AttachmentWorkflow,
)

__all__ = [
    "list_attachments",
    "download_attachment",
    "download_all_attachments",
    "list_downloads",
    "open_attachment",
    "AttachmentWorkflow",
]
