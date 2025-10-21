"""Interactive email composer - orchestrates UI, logic, and utilities"""

from src.ui.composer_ui import (
    prompt_email_details,
    show_email_preview,
    confirm_action,
    prompt_send_later,
    show_send_success,
    show_send_scheduled,
    show_send_failed,
    show_draft_saved
)
from src.core.composer_logic import (
    prepare_email_data,
    save_as_draft,
    send_email_now,
    schedule_email
)
from src.utils.log_manager import get_logger

logger = get_logger()


def compose_email():
    """Orchestrate email composition workflow with preview, send, and schedule options."""
    
    email_details = prompt_email_details()
    if not email_details:
        return False
    
    email_data = prepare_email_data(
        recipient=email_details["recipient"],
        subject=email_details["subject"],
        body=email_details["body"]
    )
    
    show_email_preview(email_data)
    
    if not confirm_action("\nSend this email?"):
        logger.info("Email cancelled - saved as draft")
        show_draft_saved()
        save_as_draft(email_data)
        return False
    
    send_time = prompt_send_later()
    
    if send_time:
        success, error = schedule_email(email_data, send_time)
        if success:
            show_send_scheduled(send_time)
            return True
        else:
            show_send_failed(error)
            return False
    else:
        success, error = send_email_now(email_data)
        if success:
            show_send_success(email_data)
            return True
        else:
            show_send_failed(error)
            return False