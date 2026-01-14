"""Email domain models"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List


class EmailId:
    """Value object for email identifiers."""

    def __init__(self, value: str):
        if not value or not value.strip():
            raise ValueError("Email ID cannot be empty")
        self._value = value.strip()

    @property
    def value(self) -> str:
        return self._value

    def __str__(self) -> str:
        return self._value

    def __eq__(self, other) -> bool:
        if not isinstance(other, EmailId):
            return False
        return self._value == other._value

    def __hash__(self) -> int:
        return hash(self._value)


class EmailAddress:
    """Value object for email addresses."""

    def __init__(self, address: str):
        from src.core.validation.email import EmailValidator

        if not EmailValidator.is_valid_email(address):
            raise ValueError(f"Invalid email address: {address}")

        self._address = address.lower().strip()

    @property
    def address(self) -> str:
        return self._address

    @property
    def local_part(self) -> str:
        return self._address.split("@")[0]

    @property
    def domain(self) -> str:
        return self._address.split("@")[1]

    def __str__(self) -> str:
        return self._address

    def __eq__(self, other) -> bool:
        if not isinstance(other, EmailAddress):
            return False
        return self._address == other._address


class FolderName(Enum):
    """Valid email folder names."""

    INBOX = "inbox"
    SENT = "sent"
    DRAFTS = "drafts"
    TRASH = "trash"

    @classmethod
    def from_string(cls, value: str) -> "FolderName":
        """Create FolderName from string.

        Args:
            value (str): The folder name as a string.

        Returns:
            FolderName: The corresponding FolderName enum value.

        Raises:
            ValueError: If the folder name is invalid.
        """
        try:
            return cls(value.lower())

        except ValueError:
            raise ValueError(f"Invalid folder name: {value}")


@dataclass
class Attachment:
    """Email attachment."""

    filename: str
    content_type: str
    size_bytes: int

    def __post_init__(self):
        from src.utils.security import PathSecurity

        self.filename = PathSecurity.sanitise_filename(self.filename)


@dataclass
class Email:
    """Email domain entity with rich behavior."""

    id: EmailId
    subject: str
    sender: EmailAddress
    recipients: List[EmailAddress]
    body: str
    received_at: datetime
    attachments: List[Attachment] = field(default_factory=list)
    is_read: bool = False
    is_flagged: bool = False
    folder: FolderName = FolderName.INBOX

    def mark_as_read(self) -> None:
        """Mark email as read."""
        self.is_read = True

    def mark_as_unread(self) -> None:
        """Mark email as unread."""
        self.is_read = False

    def flag(self) -> None:
        """Flag email for follow-up."""
        self.is_flagged = True

    def unflag(self) -> None:
        """Remove flag from email."""
        self.is_flagged = False

    def move_to(self, folder: FolderName) -> None:
        """Move email to different folder."""
        self.folder = folder

    def has_attachments(self) -> bool:
        """Check if email has attachments."""
        return len(self.attachments) > 0

    def get_attachment_count(self) -> int:
        """Get number of attachments."""
        return len(self.attachments)

    def get_preview(self, max_length: int = 100) -> str:
        """Get preview of email body."""
        if not self.body:
            return ""

        # Remove HTML tags if present
        import re

        text = re.sub(r"<[^>]+>", "", self.body)

        if len(text) <= max_length:
            return text

        return text[: max_length - 3] + "..."

    @classmethod
    def from_dict(cls, data: dict) -> "Email":
        """Create Email from dictionary (database row)."""
        return cls(
            id=EmailId(data["uid"]),
            subject=data.get("subject", ""),
            sender=EmailAddress(data["from"]),
            recipients=[
                EmailAddress(addr.strip())
                for addr in data.get("to", "").split(",")
                if addr.strip()
            ],
            body=data.get("body", ""),
            received_at=datetime.fromisoformat(data["date"] + " " + data["time"]),
            attachments=[],  # Parse from data['attachments']
            is_read=bool(data.get("is_read", False)),
            is_flagged=bool(data.get("flagged", False)),
            folder=FolderName.from_string(data.get("folder", "inbox")),
        )

    def to_dict(self) -> dict:
        """Convert Email to dictionary for database storage.

        Returns:
            dict: The dictionary representation of the Email.
        """
        return {
            "uid": self.id.value,
            "subject": self.subject,
            "from": str(self.sender),
            "to": ", ".join(str(r) for r in self.recipients),
            "date": self.received_at.strftime("%Y-%m-%d"),
            "time": self.received_at.strftime("%H:%M:%S"),
            "body": self.body,
            "attachments": ", ".join(a.filename for a in self.attachments),
            "is_read": self.is_read,
            "flagged": self.is_flagged,
            "folder": self.folder.value,
        }
