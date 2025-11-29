"""Email parsing module

Parse RFC822 email messages into structured data using fast-mail-parser
library. Provides two parsing modes:

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
from typing import Any, Dict, Optional

from fast_mail_parser import parse_email

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
    ) -> Optional[Dict[str, Any]]:
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
        """
        try:
            if not raw_email or len(raw_email) == 0:
                error_msg = f"Empty email data for UID {uid}"
                if strict:
                    raise ValidationError(error_msg)

                logger.warning(error_msg)
                return None

            parsed_email = parse_email(raw_email)
            return EmailParser._to_dict(parsed_email, uid)

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
    ) -> Optional[Dict[str, Any]]:
        """Parse email.message.Message into structured dictionary

        Args:
            message: email.message.Message object
            uid: Unique identifier for the email
            strict: If True, raises ValidationError on parsing errors,
                    otherwise returns None

        Returns:
            Parsed email dictionary or None if parsing fails (lenient mode)

        Raises:
            ValidationError: If parsing fails (strict mode)
        """
        try:
            raw_bytes = message.as_bytes()
            return EmailParser.parse_from_bytes(raw_bytes, uid, strict=strict)

        except KernelError:
            raise

        except Exception as e:
            error_msg = f"Failed to convert message to bytes for UID {uid}: {str(e)}"
            logger.error(error_msg, extra={"uid": uid})

            if strict:
                raise ValidationError(error_msg) from e

            return None

    @staticmethod
    def _to_dict(parsed_email: Any, uid: str) -> Dict[str, Any]:
        """Convert fast-mail-parser result to dictionary format

        Args:
            parsed_email: Result from fast_mail_parser
            uid: Unique identifier for the email

        Returns:
            Dictionary with structured email data
        """
        sender = EmailParser._extract_address_field(parsed_email.from_)
        recipient = EmailParser._extract_address_field(parsed_email.to)
        attachments = EmailParser._extract_attachments(parsed_email.attachments)
        date_str, time_str = EmailParser._extract_datetime(parsed_email.date)
        body = EmailParser._extract_body(parsed_email)

        return {
            "uid": uid,
            "subject": parsed_email.subject or "",
            "sender": sender,
            "recipient": recipient,
            "date": date_str,
            "time": time_str,
            "body": body,
            "attachments": attachments,
            "flagged": 0,
        }

    @staticmethod
    def _extract_address_field(field: Any) -> str:
        """Safely extract email address (to/from/cc/bcc)

        Args:
            field: Parsed email address field

        Returns:
            Comma-separated email addresses as string
        """
        if field is None:
            return ""

        if isinstance(field, list):
            if not field:
                return ""

            valid_addresses = [str(addr) for addr in field if addr is not None]
            return ", ".join(valid_addresses)

        return str(field)

    @staticmethod
    def _extract_attachments(attachments: Any) -> str:
        """Safely extract attachment filenames

        Args:
            attachments: Parsed attachments list

        Returns:
            Comma-separated attachment filenames as string
        """
        if not attachments:
            return ""

        try:
            filenames = [
                att.filename
                for att in attachments
                if hasattr(att, "filename") and att.filename
            ]

            return ", ".join(filenames)

        except Exception as e:
            logger.warning(f"Failed to extract attachments: {e}")
            return ""

    @staticmethod
    def _extract_datetime(date_obj: Any) -> tuple[str, str]:
        """Safely extract date and time strings from date object

        Args:
            date_obj: Parsed date object

        Returns:
            Tuple of (date_str, time_str) in format ("YYYY-MM-DD", "HH:MM")
        """
        if date_obj and hasattr(date_obj, "strftime"):
            try:
                return (date_obj.strftime("%Y-%m-%d"), date_obj.strftime("%H:%M"))

            except Exception as e:
                logger.warning(f"Failed to format date object: {e}")

        now = datetime.now()
        return (now.strftime("%Y-%m-%d"), now.strftime("%H:%M"))

    @staticmethod
    def _extract_body(parsed_email: Any) -> str:
        """Safely extract email body text

        Args:
            parsed_email: Parsed email object

        Returns:
            Email body as text, or empty string if not available
        """
        try:
            if hasattr(parsed_email, "text") and parsed_email.text:
                return parsed_email.text

            if hasattr(parsed_email, "html") and parsed_email.html:
                return parsed_email.html

            return ""

        except Exception as e:
            logger.warning(f"Failed to extract email body: {e}")
            return ""
