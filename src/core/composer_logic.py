"""Email composer logic - handles sending, scheduling, and saving emails"""

import datetime
from .smtp_client import send_email
from .storage_api import save_sent_email, save_draft_email
from ..utils.config_manager import ConfigManager
from ..utils.email_utils import create_email_dict, parse_send_datetime
from ..utils.log_manager import get_logger, log_call

logger = get_logger(__name__)
config_manager = ConfigManager()


@log_call
def prepare_email_data(recipient, subject, body, attachments=None):
    """Create email data dict with sender from config."""
    email_addr = config_manager.get_config('account.email')
    return create_email_dict(
        subject=subject,
        sender=email_addr,
        recipient=recipient,
        body=body,
        attachments=attachments
    )

@log_call
def save_as_draft(email_data):
    """Save email as draft."""
    try:
        save_draft_email(email_data)
        logger.info("Email saved as draft")
        return True
    except Exception as e:
        logger.error(f"Failed to save email as draft: {e}")
        return False

@log_call
def schedule_email(email_data, send_time_str):
    """Schedule email for sending at specified time."""
    parsed_datetime, error = parse_send_datetime(send_time_str)
    if error:
        return False, error
    
    if parsed_datetime is None:
        # Empty string means immediate send
        return send_email_now(email_data)
    
    try:
        email_data["send_at"] = send_time_str
        email_data["sent_status"] = "pending"
        save_sent_email(email_data)
        logger.info(f"Email scheduled for {send_time_str}")
        return True, None
    except Exception as e:
        logger.error(f"Failed to schedule email: {e}")
        return False, str(e)

@log_call
def send_email_now(email_data):
    """Send email immediately."""
    try:
        success = send_email(
            to_email=email_data["to"],
            subject=email_data["subject"],
            body=email_data["body"]
        )
        
        if success:
            email_data["sent_status"] = "sent"
            email_data["send_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            save_sent_email(email_data)
            logger.info("Email sent successfully")
            return True, None
        else:
            # Save as pending if send failed
            email_data["sent_status"] = "pending"
            email_data["send_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            save_sent_email(email_data)
            logger.error("Failed to send email, saved as pending")
            return False, "Failed to send email"
            
    except Exception as e:
        # Save as pending on exception
        email_data["sent_status"] = "pending"
        email_data["send_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        save_sent_email(email_data)
        logger.error(f"Error sending email: {e}")
        return False, str(e)

@log_call
def handle_send_decision(email_data, send_time_str=None):
    """Handle send, schedule, or cancel decision."""
    if send_time_str:
        success, error = schedule_email(email_data, send_time_str)
        return success
    else:
        success, error = send_email_now(email_data)
        return success
