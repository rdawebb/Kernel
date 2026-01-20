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
            result = EmailParser._to_dict(parsed_email, uid)

            # If sender or recipient is empty, try to extract from raw email using email module
            if not result.get("sender") or not result.get("recipient"):
                logger.debug(
                    f"Attempting to extract missing headers from raw email for UID {uid}"
                )
                backup_result = EmailParser._parse_raw_headers(raw_email, uid)
                if backup_result:
                    if not result.get("sender") and backup_result.get("sender"):
                        result["sender"] = backup_result["sender"]
                    if not result.get("recipient") and backup_result.get("recipient"):
                        result["recipient"] = backup_result["recipient"]

            return result

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
    def _parse_raw_headers(raw_email: bytes, uid: str) -> Optional[Dict[str, str]]:
        """Extract headers from raw email bytes using email module as fallback.

        Args:
            raw_email: Raw email bytes (RFC822 format)
            uid: Unique identifier for the email

        Returns:
            Dictionary with 'sender' and 'recipient' keys, or None if parsing fails
        """
        try:
            msg = email.message_from_bytes(raw_email)

            sender = msg.get("From", "").strip()
            recipient = msg.get("To", "").strip()

            if sender or recipient:
                logger.debug(
                    f"Extracted from raw headers for UID {uid}: from='{sender}', to='{recipient}'"
                )
                return {"sender": sender, "recipient": recipient}

            return None
        except Exception as e:
            logger.debug(f"Failed to extract raw headers for UID {uid}: {e}")
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
        # Extract email addresses from headers
        # fast_mail_parser stores headers in a dict with capitalized keys (From, To, etc)
        headers = EmailParser._extract_headers(parsed_email)

        # Try various header key formats (case-insensitive lookup)
        sender = ""
        for key in headers:
            if key.lower() == "from":
                sender = EmailParser._extract_address_field(headers[key])
                break

        recipient = ""
        for key in headers:
            if key.lower() == "to":
                recipient = EmailParser._extract_address_field(headers[key])
                break

        attachments = EmailParser._extract_attachments(parsed_email.attachments)

        # Use date from parsed_email, fall back to headers if empty
        date_obj = parsed_email.date
        if not date_obj:
            for key in headers:
                if key.lower() == "date":
                    date_obj = headers[key]
                    break

        received_at = EmailParser._extract_datetime(date_obj)
        body = EmailParser._extract_body(parsed_email)

        # Debug: log if sender is empty
        if not sender:
            logger.warning(f"UID {uid}: No sender extracted. Headers: {headers}")

        return {
            "uid": uid,
            "subject": parsed_email.subject or "",
            "sender": sender,
            "recipient": recipient,
            "received_at": received_at,
            "body": body,
            "attachments": attachments,
        }

    @staticmethod
    def _extract_headers(parsed_email: Any) -> Dict[str, str]:
        """Safely extract headers from parsed email

        Args:
            parsed_email: Parsed email object from fast_mail_parser

        Returns:
            Dictionary of headers with lowercase keys for From/To/Subject
        """
        try:
            if hasattr(parsed_email, "headers") and parsed_email.headers:
                headers = parsed_email.headers
                # Normalise keys to lowercase
                return {k.lower(): v for k, v in headers.items()}
            return {}
        except Exception as e:
            logger.warning(f"Failed to extract headers: {e}")
            return {}

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
    def _extract_datetime(date_obj: Any) -> datetime:
        """Safely extract datetime object from date object

        Args:
            date_obj: Parsed date object (can be string or datetime)

        Returns:
            datetime object, or current time if parsing fails
        """
        try:
            # If it's a non-empty string, try to parse it as an email date
            if isinstance(date_obj, str) and date_obj.strip():
                from email.utils import parsedate_to_datetime

                return parsedate_to_datetime(date_obj)

            if hasattr(date_obj, "year") and hasattr(date_obj, "month"):
                # Already a datetime-like object
                return date_obj

        except Exception as e:
            logger.debug(f"Failed to parse date object: {e}")

        # Fallback to current time
        return datetime.now()

    @staticmethod
    def _extract_body(parsed_email: Any) -> str:
        """Safely extract email body text

        Args:
            parsed_email: Parsed email object from fast_mail_parser

        Returns:
            Email body as text, or empty string if not available
        """
        try:
            if hasattr(parsed_email, "text_plain") and parsed_email.text_plain:
                # Join all text_plain parts
                return "".join(parsed_email.text_plain)

            if hasattr(parsed_email, "text_html") and parsed_email.text_html:
                # Join all text_html parts as fallback
                return "".join(parsed_email.text_html)

            return ""

        except Exception as e:
            logger.warning(f"Failed to extract email body: {e}")
            return ""
