"""Database utilities."""

from datetime import datetime

from src.core.models.attachment import Attachment
from src.core.models.email import FolderName, Email, EmailAddress, EmailId


def row_to_email(row, folder: FolderName) -> Email:
    """Convert database row to Email domain object.

    Args:
        row: SQLAlchemy Row object
        folder: Folder the email belongs to

    Returns:
        Email domain object
    """
    # Parse datetime from date + time strings
    date_str = row.date
    time_str = row.time
    received_at = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S")

    # Parse email addresses - handle empty/invalid addresses gracefully
    sender_str = row.sender or ""
    sender = (
        EmailAddress(sender_str.strip())
        if sender_str.strip()
        else EmailAddress("unknown@unknown.local")
    )

    recipient_str = row.recipient or ""
    recipients = []
    if recipient_str.strip():
        for addr in recipient_str.split(","):
            addr = addr.strip()
            if addr:
                try:
                    recipients.append(EmailAddress(addr))
                except ValueError:
                    # Skip invalid addresses
                    pass

    # If no valid recipients, add a placeholder
    if not recipients:
        recipients = [EmailAddress("unknown@unknown.local")]

    # TODO: parse attachments (placeholder)
    attachments = []
    if row.attachments:
        for filename in row.attachments.split(","):
            if filename.strip():
                attachments.append(
                    Attachment(id=None, filename=filename.strip(), content=None)
                )

    email = Email(
        id=EmailId(row.uid),
        subject=row.subject,
        sender=sender,
        recipients=recipients,
        received_at=received_at,
        body=row.body or "",
        attachments=attachments,
        folder=folder,
        is_read=bool(row.is_read),
    )

    # Set folder-specific attributes
    if hasattr(row, "flagged"):
        email.is_flagged = bool(row.flagged)

    return email
