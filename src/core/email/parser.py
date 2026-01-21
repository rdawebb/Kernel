"""Email parsing module

Parse RFC822 email messages into structured data using the builtin Python email library. Provides two parsing modes:

- Lenient (default): Returns None for malformed emails, logs errors
    Use for batch processing where some malformed emails are acceptable.

- Strict: Raises ValidationError for any malformed emails
    Use for scenarios where email integrity is critical.

Features
--------
- Handles malformed emails gracefully based on parsing mode
- Provides sensible defaults for missing fields
- Extracts: subject, sender, recipient, date/time, body, attachments
- Supports bytes and email.message.Message inputs
- Logs detailed error information for debugging

Usage Examples
--------------

Lenient parsing (for sync operations):
    >>> raw_bytes = fetch_email_from_server()
    >>> email_dict = EmailParser.parse_from_bytes(raw_bytes, uid="12345")
    >>>
    >>> if email_dict is None:
    ...     print("Malformed email, skipping")
    ... else:
    ...     save_to_database(email_dict)

Strict parsing (for critical operations):
    >>> email_dict = EmailParser.parse_from_bytes(
    ...     raw_bytes, uid="12345", strict=True)
    ... ) # Raises ValidationError if malformed
"""

import email
from datetime import datetime
from email.utils import getaddresses, parsedate_to_datetime
from typing import Optional

from src.core.models.email import Attachment, Email, EmailAddress, EmailId, FolderName
from src.utils.errors import (
    KernelError,
    ValidationError,
)
from src.utils.logging import get_logger

logger = get_logger(__name__)


class EmailParser:
    """Parse MIME email messages into structured data

    Parsing modes:
    - Lenient (default): Returns None for malformed emails, logs errors
    - Strict: Raises ValidationError for any malformed emails
    """

    @staticmethod
    def parse_from_bytes(
        raw_email: bytes, uid: str, strict: bool = False
    ) -> Optional[Email]:
        """Parse raw email bytes into structured dictionary

        Args:
            raw_email: Raw email bytes (RFC822 format)
            uid: Unique identifier for the email
            strict: If True, raises ValidationError on parsing errors,
                    otherwise returns None

        Returns:
            Parsed email dictionary or None if parsing fails (lenient mode)

        Raises:
            ValidationError: If parsing fails (strict mode)
            KernelError: If there is a low-level error (e.g. memory error)
        """
        try:
            msg = email.message_from_bytes(raw_email)

            sender = _extract_sender(msg)
            if sender is None:
                error_msg = f"Missing or invalid sender in email UID {uid}"
                logger.error(error_msg, extra={"uid": uid})
                if strict:
                    raise ValidationError(error_msg)
                return None

            recipients = _extract_recipients(msg)

            subject = msg.get("Subject", "").strip() or ""

            received_at = _extract_datetime(msg)

            body, attachments = _extract_body_and_attachments(msg)

            return Email(
                id=EmailId(uid),
                sender=sender,
                recipients=recipients if recipients else [sender],
                subject=subject,
                body=body,
                received_at=received_at,
                attachments=attachments,
                folder=FolderName.INBOX,
            )

        except KernelError:
            raise

        except Exception as e:
            error_msg = f"Failed to parse email UID {uid}: {str(e)}"
            logger.error(
                error_msg,
                extra={
                    "uid": uid,
                    "email_size": len(raw_email),
                    "error_type": type(e).__name__,
                },
            )

            if strict:
                raise ValidationError(error_msg) from e

            return None

    @staticmethod
    def parse_from_message(
        message: email.message.Message, uid: str, strict: bool = False
    ) -> Optional[Email]:
        """Parse email.message.Message into Email object

        Args:
            message: email.message.Message object
            uid: Unique identifier for the email
            strict: If True, raises ValidationError on parsing errors,
                    otherwise returns None

        Returns:
            Parsed Email object or None if parsing fails (lenient mode)

        Raises:
            ValidationError: If parsing fails (strict mode)
        """
        try:
            raw_bytes = message.as_bytes()
            return EmailParser.parse_from_bytes(raw_bytes, uid, strict=strict)

        except KernelError:
            raise

        except Exception as e:
            error_msg = f"Failed to parse email UID {uid}: {str(e)}"
            logger.error(
                error_msg,
                extra={
                    "uid": uid,
                    "error_type": type(e).__name__,
                },
            )

            if strict:
                raise ValidationError(error_msg) from e

            return None


def _extract_sender(msg: email.message.Message) -> Optional[EmailAddress]:
    """Extract sender email address with validation

    Args:
        msg: The email.message.Message object to extract the sender from.

    Returns:
        The EmailAddress object, or None if no valid sender is found.

    Raises:
        ValueError: If the sender email address is invalid.
    """
    from_header = msg.get("From", "").strip()
    if not from_header:
        logger.debug("No 'From' header found")
        return None

    parsed = getaddresses([from_header])
    if not parsed or not parsed[0][1]:
        logger.debug(f"Failed to parse sender from 'From' header: {from_header}")
        return None

    email_addresses = parsed[0][1]

    try:
        return EmailAddress(email_addresses)

    except ValueError as e:
        logger.warning(f"Invalid sender email address: {email_addresses} - {e}")
        return None


def _extract_recipients(msg: email.message.Message) -> list[EmailAddress]:
    """Extract recipient email addresses with validation

    Args:
        msg: The email.message.Message object to extract recipients from.

    Returns:
        A list of EmailAddress objects.

    Raises:
        ValueError: If no valid recipients are found.
    """
    recipients = []

    for header in ["To", "Cc"]:
        header_value = msg.get(header, "").strip()
        if not header_value:
            continue

        try:
            parsed = getaddresses([header_value])
            for _, email_addr in parsed:
                if email_addr:
                    try:
                        recipients.append(EmailAddress(email_addr))

                    except ValueError as e:
                        logger.debug(
                            f"Skipping invalid recipient email address: {email_addr} - {e}"
                        )
                        continue

        except Exception as e:
            logger.debug(f"Error parsing recipients from {header} header: {e}")
            continue

    return recipients


def _extract_datetime(msg: email.message.Message) -> datetime:
    """Extract message date and time with fallback to current time

    Args:
        msg: The email.message.Message object to extract the date from.

    Returns:
        The extracted datetime object, or the current time if extraction fails.

    Raises:
        ValueError: If the date string is invalid.
        TypeError: If the date string is not a string.
    """
    date_str = msg.get("Date", "").strip()
    if not date_str:
        logger.debug("No 'Date' header found, using current time")
        return datetime.now()

    try:
        return parsedate_to_datetime(date_str)

    except (TypeError, ValueError) as e:
        logger.debug(f"Failed to parse date: {date_str} - {e}, using current time")
        return datetime.now()


def _extract_body_and_attachments(
    msg: email.message.Message,
) -> tuple[str, list[Attachment]]:
    """Extract email body and attachments with metadata

    Args:
        msg: The email.message.Message object to extract body and attachments from.

    Returns:
        Tuple of (body_text, attachments_list)
    """
    body = ""
    attachments = []

    if not msg.is_multipart():
        return _extract_payload_as_text(msg), []

    text_parts = []
    html_parts = []

    for part in msg.walk():
        content_type = part.get_content_type()
        content_disposition = part.get_content_disposition()

        if content_type == "text/plain":
            text = _extract_payload_as_text(part)
            if text:
                text_parts.append(text)

        elif content_type == "text/html":
            html = _extract_payload_as_text(part)
            if html:
                html_parts.append(html)

        elif content_disposition == "attachment":
            filename = part.get_filename()
            if filename:
                try:
                    attachment = Attachment(
                        filename=filename,
                        content_type=content_type or "application/octet-stream",
                        size_bytes=len(part.get_payload(decode=True) or b""),
                    )
                    attachments.append(attachment)

                except Exception as e:
                    logger.debug(f"Failed to extract attachment {filename}: {e}")
                    continue

    if text_parts:
        body = "\n".join(text_parts)
    elif html_parts:
        body = "\n".join(html_parts)
        logger.debug("Using HTML fallback - no plain text found")

    return body, attachments


def _extract_payload_as_text(part: email.message.Message) -> str:
    """Extract the payload from a MIME part as text.

    Args:
        part: The email.message.Message object to extract the payload from.

    Returns:
        The extracted payload as text, or an empty string if extraction fails.
    """
    try:
        payload = part.get_payload(decode=True)

        if isinstance(payload, bytes):
            charset = part.get_content_charset() or "utf-8"
            try:
                return payload.decode(charset)

            except (LookupError, UnicodeDecodeError) as e:
                logger.debug(f"Failed to decode payload: {e}, falling back to utf-8")
                return payload.decode("utf-8", errors="ignore")

        elif isinstance(payload, str):
            return payload

        return ""

    except Exception as e:
        logger.debug(f"Error extracting payload from part: {e}")
        return ""
