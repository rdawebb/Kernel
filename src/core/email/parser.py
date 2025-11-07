"""Email parsing and composition."""

import email
from typing import Any, Dict

from fast_mail_parser import parse_email

from src.utils.errors import (
    KernelError,
    ValidationError,
)
from src.utils.logging import get_logger

logger = get_logger(__name__)


class EmailParser:
    """Parse MIME email messages into structured data"""

    @staticmethod
    def parse_from_bytes(raw_email: bytes, uid: str) -> Dict[str, Any]:
        """Parse raw email bytes into structured dictionary"""
        try:
            parsed_email = parse_email(raw_email)
            return EmailParser._to_dict(parsed_email, uid)

        except KernelError:
            raise
        
        except Exception as e:
            raise ValidationError("Failed to parse email bytes") from e
        
    @staticmethod
    def parse_from_message(message: email.message.Message, uid: str) -> Dict[str, Any]:
        """Parse email.message.Message into structured dictionary"""
        try:
            raw_bytes = message.as_bytes()
            parsed_email = parse_email(raw_bytes)
            return EmailParser._to_dict(parsed_email, uid)
        
        except KernelError:
            raise
        
        except Exception as e:
            raise ValidationError("Failed to parse email message") from e
        
    @staticmethod
    def _to_dict(parsed_email: Any, uid: str) -> Dict[str, Any]:
        """Convert fast-mail-parser result to dictionary format"""
        sender = ", ".join(parsed_email.from_) if isinstance(parsed_email.from_, list) else (parsed_email.from_ or "")
        recipient = ", ".join(parsed_email.to) if isinstance(parsed_email.to, list) else (parsed_email.to or "")
        attachments = ", ".join(att.filename for att in parsed_email.attachments) if parsed_email.attachments else ""
        date_str = parsed_email.date.strftime("%Y-%m-%d") if parsed_email.date else ""
        time_str = parsed_email.date.strftime("%H:%M") if parsed_email.date else ""
        body = parsed_email.text or parsed_email.html or ""

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