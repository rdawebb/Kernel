"""Email viewing feature.

Public API:
    view_email(email_id, folder) -> Display single email
    view_inbox(limit, filters) -> Display inbox list
    view_folder(folder, limit, filters) -> Display folder list
"""

from .workflow import view_email, view_inbox, view_folder, ViewWorkflow
from .filters import EmailFilters

__all__ = [
    "view_email",
    "view_inbox",
    "view_folder",
    "ViewWorkflow",
    "EmailFilters",
]
