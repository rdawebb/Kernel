"""Email composer logic - handles sending, scheduling, and saving emails"""

import datetime
from src.core.smtp_client import send_email
from src.core.storage_api import save_sent_email, save_draft_email
from src.utils.config import load_config
from src.utils.email_utils import create_email_dict, parse_send_datetime
from src.utils import log_manager

log_manager = log_manager.get_logger()


def prepare_email_data(recipient, subject, body, attachments=None):
    """Create email data dict with sender from config."""
    config = load_config()
    return create_email_dict(
        subject=subject,
        sender=config["email"],
        recipient=recipient,
        body=body,
        attachments=attachments
    )

def save_as_draft(email_data):
    """Save email as draft."""
    try:
        save_draft_email(email_data)
        log_manager.info("Email saved as draft")
        return True
    except Exception as e:
        log_manager.error(f"Failed to save email as draft: {e}")
        return False

def schedule_email(email_data, send_time_str):
    """Schedule email for sending at specified time."""
    datetime, error = parse_send_datetime(send_time_str)
    if error:
        return False, error
    
    if datetime is None:
        # Empty string means immediate send
        return send_email_now(email_data)
    
    try:
        email_data["send_at"] = send_time_str
        email_data["sent_status"] = "pending"
        save_sent_email(email_data)
        log_manager.info(f"Email scheduled for {send_time_str}")
        return True, None
    except Exception as e:
        log_manager.error(f"Failed to schedule email: {e}")
        return False, str(e)

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
            log_manager.info("Email sent successfully")
            return True, None
        else:
            # Save as pending if send failed
            email_data["sent_status"] = "pending"
            email_data["send_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            save_sent_email(email_data)
            log_manager.error("Failed to send email, saved as pending")
            return False, "Failed to send email"
            
    except Exception as e:
        # Save as pending on exception
        email_data["sent_status"] = "pending"
        email_data["send_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        save_sent_email(email_data)
        log_manager.error(f"Error sending email: {e}")
        return False, str(e)

def handle_send_decision(email_data, send_time_str=None):
    """Handle send, schedule, or cancel decision."""
    if send_time_str:
        success, error = schedule_email(email_data, send_time_str)
        return success
    else:
        success, error = send_email_now(email_data)
        return success
