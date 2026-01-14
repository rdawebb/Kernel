"""Email filtering logic."""

from dataclasses import dataclass
from typing import Optional, Dict, Any


@dataclass
class EmailFilters:
    """Email filtering criteria."""

    flagged: Optional[bool] = None
    unread: Optional[bool] = None
    has_attachments: bool = False
    from_address: Optional[str] = None
    subject_contains: Optional[str] = None

    @classmethod
    def from_args(cls, args) -> "EmailFilters":
        """Create filters from CLI arguments."""
        flagged = None
        if getattr(args, "flagged", False):
            flagged = True
        elif getattr(args, "unflagged", False):
            flagged = False

        unread = None
        if getattr(args, "unread", False):
            unread = True
        elif getattr(args, "read", False):
            unread = False

        return cls(
            flagged=flagged,
            unread=unread,
            has_attachments=getattr(args, "has_attachments", False),
            from_address=getattr(args, "from_address", None),
            subject_contains=getattr(args, "subject", None),
        )

    def has_filters(self) -> bool:
        """Check if any filters are active."""
        return any(
            [
                self.flagged is not None,
                self.unread is not None,
                self.has_attachments,
                self.from_address,
                self.subject_contains,
            ]
        )

    def to_query(self) -> Dict[str, Any]:
        """Convert to database query filters."""
        query = {}

        if self.flagged is not None:
            query["is_flagged"] = self.flagged
        if self.unread is not None:
            query["is_read"] = not self.unread
        if self.has_attachments:
            query["has_attachments"] = True
        if self.from_address:
            query["sender"] = f"%{self.from_address}%"
        if self.subject_contains:
            query["subject"] = f"%{self.subject_contains}%"

        return query
