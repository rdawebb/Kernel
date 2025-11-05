"""Unified email processing module"""

import email
import re
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from fast_mail_parser import parse_email

from src.utils.error_handling import (
    DatabaseError,
    InvalidEmailAddressError,
    KernelError,
    SMTPError,
    ValidationError,
)
from src.utils.log_manager import get_logger

logger = get_logger(__name__)


## Email Parsing

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
    

## Email Composition

class EmailComposer:
    """Handle email composition and sending"""

    def __init__(self, config=None, smtp_client=None):
        """Initialize EmailComposer with config and SMTP client"""

        self.config = config
        self.smtp_client = smtp_client

    def create_email_dict(self, recipient: str, subject: str, body: str,
                          sender: Optional[str] = None,
                          attachments: Optional[list] = None) -> Dict[str, Any]:
        """Create structured email dictionary for storage"""

        if sender is None and self.config:
            sender = self.config.get_account_config("email", "")

        now = datetime.now()

        return {
            "uid": self._generate_uid(),
            "subject": subject,
            "sender": sender or "",
            "recipient": recipient,
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M"),
            "body": body,
            "attachments": ",".join(attachments) if attachments else "",
        }

    def send_email(self, to_email: str, subject: str, body: str,
                   cc: Optional[list] = None, bcc: Optional[list] = None) -> Tuple[bool, Optional[str]]:
        """Send an email via SMTP client"""

        try:
            if self.smtp_client:
                smtp = self.smtp_client
            else:
                from src.core.smtp_client import SMTPClient

                if not self.config:
                    raise ValidationError("No configuration provided for SMTP client")
                
                config = self.config.get_account_config()

                smtp = SMTPClient(
                    host=config.get("smtp_server"),
                    port=config.get("smtp_port", 587),
                    username=config.get("username"),
                    password=config.get("password"),
                    use_tls=config.get("use_tls", True)
                )

            success = smtp.send_email(to_email, subject, body, cc, bcc)

            if success:
                logger.info(f"Email sent to {to_email} with subject '{subject}'")
                return True, None
            else:
                raise SMTPError("Failed to send email via SMTP client")
            
        except (ValidationError, SMTPError):
            raise

        except KernelError:
            raise

        except Exception as e:
            raise SMTPError("Failed to send email") from e
        
    async def schedule_email(self, email_dict: Dict[str, Any],
                       send_at: str) -> Tuple[bool, Optional[str]]:
        """Schedule an email to be sent at a later time"""

        parsed_dt, error = DateTimeParser.parse_datetime(send_at)
        if error:
            raise ValidationError(error)

        email_dict["send_at"] = parsed_dt
        email_dict["send_status"] = "pending"

        try:
            from src.core.database import get_database

            db = get_database(self.config)
            await db.save_email("sent_emails", email_dict)

            logger.info(f"Email scheduled to be sent at {send_at}")
            return True, None
        
        except DatabaseError:
            raise
        except KernelError:
            raise
        except Exception as e:
            raise DatabaseError("Failed to schedule email") from e
        
    def _generate_uid(self) -> str:
        """Generate a unique identifier for the email"""

        import uuid

        return f"composed-{uuid.uuid4().hex[:12]}"
    

## DateTime Utilities

class DateTimeParser:
    """Parse and validate date-time strings"""

    @staticmethod
    def parse_datetime(dt_str: str) -> Tuple[Optional[datetime], Optional[str]]:
        """Parse date-time string into datetime object"""

        if not dt_str or not dt_str.strip():
            return None, None
        
        dt_str = dt_str.strip()

        formats = [
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d %H:%M:%S",
            "%Y/%m/%d %H:%M",
            "%d/%m/%Y %H:%M",
            "%m/%d/%Y %H:%M",
        ]

        for fmt in formats:
            try:
                dt = datetime.strptime(dt_str, fmt)

                if dt < datetime.now():
                    return None, f"Date-time '{dt_str}' is in the past."
                
                return dt, None

            except ValueError:
                continue

        try:
            dt = DateTimeParser._parse_natural_language(dt_str)
            if dt:
                if dt < datetime.now():
                    return None, f"Date-time '{dt_str}' is in the past."
                return dt, None
            
        except Exception as e:
            logger.warning(f"Failed to parse natural language date-time: {e}")

        return None, f"Invalid date-time format: '{dt_str}'."
    
    @staticmethod
    def _parse_natural_language(text: str) -> Optional[datetime]:
        """Parse basic natural language date-time strings"""
        
        from datetime import timedelta

        text = text.lower().strip()
        now = datetime.now()

        if "tomorrow" in text:
            base = now + timedelta(days=1)
            time_match = re.search(r'(\d{1,2}):?(\d{2})?\s*(am|pm)?', text)
            if time_match:
                hour = int(time_match.group(1))
                minute = int(time_match.group(2) or 0)
                ampm = time_match.group(3)

                if ampm == "pm" and hour < 12:
                    hour += 12
                elif ampm == "am" and hour == 12:
                    hour = 0

                return base.replace(hour=hour, minute=minute, second=0)
            
            else:
                return base.replace(hour=9, minute=0, second=0)
            
        hours_match = re.search(r'in\s+(\d+)\s+hours?', text)
        if hours_match:
            hours = int(hours_match.group(1))
            return now + timedelta(hours=hours)
        
        days_match = re.search(r'in\s+(\d+)\s+days?', text)
        if days_match:
            days = int(days_match.group(1))
            return now + timedelta(days=days)
        
        return None
    

## Email Validation

class EmailValidator:
    """Validate email addresses and content"""

    @staticmethod
    def is_valid_email(email_address: str) -> bool:
        """Validate email address format"""

        if not email_address or not isinstance(email_address, str):
            return False
        
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

        return bool(re.match(pattern, email_address.strip()))
    
    @staticmethod
    def validate_email_dict(email_dict: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validate structured email dictionary"""

        required_fields = ["uid", "subject", "sender", "recipient", "body"]

        for field in required_fields:
            if field not in email_dict:
                raise ValidationError(f"Missing required field: {field}")
            
            if not email_dict[field] and field != "body":
                raise ValidationError(f"Field '{field}' cannot be empty")
            
        if not EmailValidator.is_valid_email(email_dict["sender"]):
            raise InvalidEmailAddressError(
                f"Invalid sender email address: {email_dict['sender']}"
            )

        if not EmailValidator.is_valid_email(email_dict["recipient"]):
            raise InvalidEmailAddressError(
                f"Invalid recipient email address: {email_dict['recipient']}"
            )

        return True, None


## Test Helper

def create_test_email(subject: str = "Test Email",
                      sender: str = "sender@example.com",
                      recipient: str = "recipient@example.com",
                      body: str = "This is a test email.") -> Dict[str, Any]:
    """Create a test email dictionary"""

    composer = EmailComposer()
    
    return composer.create_email_dict(
        recipient=recipient,
        subject=subject,
        body=body,
        sender=sender
    )