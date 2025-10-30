"""Unified email processing module"""

import email
import re
from datetime import datetime
from email import message_from_bytes
from typing import Any, Dict, Optional, Tuple
from src.utils.log_manager import get_logger
from src.utils.error_handling import (
    KernelError,
    InvalidEmailAddressError,
    ValidationError,
    SMTPError,
    DatabaseError,
)

logger = get_logger(__name__)


## Email Parsing

class EmailParser:
    """Parse MIME email messages into structured data"""

    @staticmethod
    def parse_from_bytes(raw_email: bytes, uid: str) -> Dict[str, Any]:
        """Parse raw email bytes into structured dictionary"""

        try:
            message = message_from_bytes(raw_email)
            return EmailParser.parse_from_message(message, uid)
        
        except KernelError:
            raise
        
        except Exception as e:
            raise ValidationError("Failed to parse email bytes") from e
        
    
    @staticmethod
    def parse_from_message(message: email.message.Message, uid: str) -> Dict[str, Any]:
        """Parse email.message.Message into structured dictionary"""

        try:
            email_dict = {
                "uid": uid,
                "subject": EmailParser._decode_header(message.get("Subject", "")),
                "sender": EmailParser._decode_header(message.get("From", "")),
                "recipient": EmailParser._decode_header(message.get("To", "")),
                "date": EmailParser._extract_date(message.get("Date", "")),
                "time": EmailParser._extract_time(message.get("Date", "")),
                "body": EmailParser._extract_body(message),
                "attachments": "",
                "flagged": 0,
            }

            return email_dict
        
        except KernelError:
            raise
        
        except Exception as e:
            raise ValidationError("Failed to parse email message") from e
        
    
    @staticmethod
    def _decode_header(header: str) -> str:
        """Decode email header (handles various encodings)"""

        if not header:
            return ""
        
        try:
            decoded_parts = email.header.decode_header(header)
            decoded_str = ""

            for content, encoding in decoded_parts:
                if isinstance(content, bytes):
                    decoded_str += content.decode(encoding or "utf-8", errors="replace")
                else:
                    decoded_str += content

            return decoded_str.strip()
        
        except Exception as e:
            logger.warning(f"Failed to decode header '{header[:50]}...': {e}")
            return str(header)
        
    
    @staticmethod
    def _extract_body(message: email.message.Message) -> str:
        """Extract plain text body from email message"""

        body = ""

        try:
            if message.is_multipart():
                for part in message.walk():
                    content_type = part.get_content_type()

                    if content_type == "text/plain":
                        payload = part.get_payload(decode=True)
                        if payload:
                            charset = part.get_content_charset() or "utf-8"
                            body += payload.decode(charset, errors="replace")
                    
                    elif content_type == "text/html" and not body:
                        payload = part.get_payload(decode=True)
                        if payload:
                            charset = part.get_content_charset() or "utf-8"
                            html_body = payload.decode(charset, errors="replace")
                            body = EmailParser._html_to_text(html_body)

            else:
                payload = message.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    body = payload.decode(charset, errors="replace")

        except Exception as e:
            logger.warning(f"Failed to extract body: {e}")

        return body.strip()
    

    @staticmethod
    def _html_to_text(html: str) -> str:
        """Convert HTML to plain text"""

        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)

        text = re.sub(r'<[^>]+>', '', html)

        import html as html_module

        text = html_module.unescape(text)
        text = re.sub(r'\s+', ' ', text)

        return text.strip()
    

    @staticmethod
    def _extract_date(date_header: str) -> str:
        """Extract date in YYYY-MM-DD format from Date header"""

        if not date_header:
            return datetime.now().strftime("%Y-%m-%d")
        
        try:
            from email.utils import parsedate_to_datetime
            dt = parsedate_to_datetime(date_header)
            return dt.strftime("%Y-%m-%d")
        
        except Exception:
            date_match = re.search(r'(\d{1,2})\s+(\w{3})\s+(\d{4})', date_header)
            if date_match:
                day, month_str, year = date_match.groups()
                month_map = {
                    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4,
                    "May": 5, "Jun": 6, "Jul": 7, "Aug": 8,
                    "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12
                }
                month = month_map.get(month_str, "01")
                return f"{year}-{month}-{day.zfill(2)}"
            
            return datetime.now().strftime("%Y-%m-%d")
        
    
    @staticmethod
    def _extract_time(date_header: str) -> str:
        """Extract time in HH:MM format from Date header"""

        if not date_header:
            return datetime.now().strftime("%H:%M")
        
        try:
            from email.utils import parsedate_to_datetime
            dt = parsedate_to_datetime(date_header)
            return dt.strftime("%H:%M")
        
        except Exception:
            time_match = re.search(r'(\d{1,2}):(\d{2})', date_header)
            if time_match:
                hour, minute = time_match.groups()
                return f"{hour.zfill(2)}:{minute}"
            
            return datetime.now().strftime("%H:%M")
        
    
    @staticmethod
    def _empty_email_dict(uid: str) -> Dict[str, Any]:
        """Return an empty email dictionary with UID"""

        return {
            "uid": uid,
            "subject": "[Error parsing email]",
            "sender": "",
            "recipient": "",
            "date": datetime.now().strftime("%Y-%m-%d"),
            "time": datetime.now().strftime("%H:%M"),
            "body": "",
            "attachments": "",
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
        

    def schedule_email(self, email_dict: Dict[str, Any],
                       send_at: str) -> Tuple[bool, Optional[str]]:
        """Schedule an email to be sent at a later time"""

        parsed_dt, error = DateTimeParser.parse_datetime(send_at)
        if error:
            raise ValidationError(error)
        
        email_dict["send_at"] = send_at
        email_dict["send_status"] = "pending"

        try:
            from src.core.database import get_database

            db = get_database(self.config)
            db.save_email("sent_emails", email_dict)

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
            raise InvalidEmailAddressError(f"Invalid sender email address: {email_dict['sender']}")
        
        if not EmailValidator.is_valid_email(email_dict["recipient"]):
            raise InvalidEmailAddressError(f"Invalid recipient email address: {email_dict['recipient']}")

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