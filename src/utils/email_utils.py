"""Email utilities for constructing and validating email data"""

import datetime
import uuid
from email_validator import validate_email, EmailNotValidError
from .log_manager import get_logger, log_call

logger = get_logger(__name__)


def create_email_dict(subject, sender, recipient, body, attachments=None):
    """Create standardized email dictionary for storage."""
    return {
        "uid": str(uuid.uuid4()),
        "subject": subject,
        "from": sender,
        "to": recipient,
        "date": datetime.date.today().isoformat(),
        "time": datetime.datetime.now().time().strftime("%H:%M:%S"),
        "body": body,
        "attachments": attachments or []
    }

@log_call
def validate_email_address(email_str):
    """Validate email address."""
    if not email_str or email_str.strip() == "":
        logger.warning("Email address is required.")
        return None, "Email address is required."
    
    try:
        valid = validate_email(email_str)
        return valid.email, None
    except EmailNotValidError as e:
        error_msg = f"Invalid email address: {e}"
        logger.error(error_msg)
        return None, error_msg

@log_call
def parse_send_datetime(datetime_str):
    """Parse and validate scheduled send datetime (YYYY-MM-DD HH:MM)."""
    if not datetime_str or datetime_str.strip() == "":
        return None, None  # Not an error, just not scheduled
    
    try:
        dt = datetime.datetime.strptime(datetime_str, "%Y-%m-%d %H:%M")
        return dt, None
    except ValueError:
        error_msg = f"Invalid date format: {datetime_str}. Please use YYYY-MM-DD HH:MM"
        logger.error(error_msg)
        return None, error_msg
