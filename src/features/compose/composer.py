"""Email composition domain logic."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid

from src.core.models.email import Email, EmailId, EmailAddress, FolderName
from src.core.validation import EmailValidator
from src.utils.errors import ValidationError
from src.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class EmailDraft:
    """Represents an email draft being composed."""

    recipient: str
    subject: str
    body: str
    cc: Optional[List[str]] = None
    bcc: Optional[List[str]] = None
    send_at: Optional[datetime] = None

    def to_email_dict(self, sender: str) -> Dict[str, Any]:
        """Convert draft to email data dictionary.

        Args:
            sender: Sender email address

        Returns:
            Email data dictionary
        """
        now = datetime.now()

        return {
            "uid": f"composed-{uuid.uuid4().hex[:12]}",
            "subject": self.subject,
            "sender": sender,
            "recipient": self.recipient,
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M"),
            "body": self.body,
            "attachments": "",
            "cc": ", ".join(self.cc) if self.cc else "",
            "bcc": ", ".join(self.bcc) if self.bcc else "",
            "send_at": self.send_at.isoformat() if self.send_at else None,
        }

    def to_email_entity(self, sender: str, folder: FolderName) -> Email:
        """Convert draft to Email domain entity.

        Args:
            sender: Sender email address
            folder: Target folder (DRAFTS or SENT)

        Returns:
            Email domain entity
        """
        uid = f"composed-{uuid.uuid4().hex[:12]}"

        sender_addr = EmailAddress(sender)
        recipients = [EmailAddress(self.recipient)]

        if self.cc:
            recipients.extend(EmailAddress(addr) for addr in self.cc)

        return Email(
            id=EmailId(uid),
            subject=self.subject,
            sender=sender_addr,
            recipients=recipients,
            body=self.body,
            received_at=datetime.now(),
            folder=folder,
            is_read=(folder == FolderName.SENT),
            is_flagged=False,
            attachments=[],
        )


class EmailComposer:
    """Handle email composition domain logic."""

    def __init__(self, sender_email: str):
        """Initialise composer with sender email.

        Args:
            sender_email: Sender email address
        """
        self.sender_email = sender_email

    def create_draft(
        self,
        recipient: str,
        subject: str,
        body: str,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        send_at: Optional[datetime] = None,
    ) -> EmailDraft:
        """Create an email draft from components.

        Args:
            recipient: Recipient email address
            subject: Email subject
            body: Email body text
            cc: Optional CC recipients
            bcc: Optional BCC recipients
            send_at: Optional scheduled send time

        Returns:
            EmailDraft instance
        """
        return EmailDraft(
            recipient=recipient,
            subject=subject,
            body=body,
            cc=cc,
            bcc=bcc,
            send_at=send_at,
        )

    def validate_draft(self, draft: EmailDraft) -> None:
        """Validate email draft.

        Args:
            draft: EmailDraft to validate

        Raises:
            ValidationError: If validation fails
        """
        if not EmailValidator.is_valid_email(draft.recipient):
            raise ValidationError(f"Invalid recipient: {draft.recipient}")

        if not EmailValidator.is_valid_email(self.sender_email):
            raise ValidationError(f"Invalid sender: {self.sender_email}")

        if draft.cc:
            for addr in draft.cc:
                if not EmailValidator.is_valid_email(addr):
                    raise ValidationError(f"Invalid CC address: {addr}")

        if draft.bcc:
            for addr in draft.bcc:
                if not EmailValidator.is_valid_email(addr):
                    raise ValidationError(f"Invalid BCC address: {addr}")

        if draft.send_at and draft.send_at < datetime.now():
            raise ValidationError("Scheduled send time must be in the future")

        logger.debug("Email draft validated successfully")

    def draft_to_email_dict(self, draft: EmailDraft) -> Dict[str, Any]:
        """Convert draft to email data dictionary.

        Args:
            draft: EmailDraft to convert

        Returns:
            Email data dictionary
        """
        return draft.to_email_dict(self.sender_email)

    def draft_to_entity(
        self,
        draft: EmailDraft,
        folder: FolderName = FolderName.DRAFTS,
    ) -> Email:
        """Convert draft to Email domain entity.

        Args:
            draft: EmailDraft to convert
            folder: Target folder

        Returns:
            Email domain entity
        """
        return draft.to_email_entity(self.sender_email, folder)
