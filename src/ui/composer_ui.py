"""UI logic for interactive email composer - handles all user prompts and console output"""

from ..utils.ui_helpers import confirm_action
from ..utils.email_utils import validate_email_address
from ..utils.log_manager import get_logger, log_call

logger = get_logger(__name__)

# Lazy load console
def _get_console():
    """Get or create console instance."""
    from rich.console import Console
    return Console()


@log_call
def prompt_recipient():
    """Prompt for and validate recipient email address."""

    while True:
        recipient = _get_console().input("To: ").strip()

        valid_email, error = validate_email_address(recipient)
        if error:
            _get_console().print(f"[bold red]{error}[/bold red]")
            
            if not confirm_action("Would you like to re-enter the recipient email address?"):
              return None, True
            continue

        return valid_email, False

@log_call
def prompt_subject():
    """Prompt for email subject."""
    
    while True:
        subject = _get_console().input("Subject: ").strip()

        if subject:
            return subject, False
        
        if confirm_action("Subject is empty, continue anyway?"):
            return "(No subject)", False
        else:
            if not confirm_action("Would you like to re-enter the subject?"):
                return None, True

@log_call
def prompt_body():
    """Prompt for multi-line email body (ends with empty line)."""
    _get_console().print("Body (press Enter twice when finished):")
    body_lines = []
    
    while True:
        line = _get_console().input("")
        if line == "" and body_lines and body_lines[-1] == "":
            break
        body_lines.append(line)
    
    body = "\n".join(body_lines[:-1]).strip()  # Remove trailing empty line
    
    if not body:
        if not confirm_action("Body is empty, continue anyway?"):
            return None, True
    
    return body, False

@log_call
def prompt_email_details():
    """Prompt for recipient, subject, and body."""
    _get_console().print("[bold green]Compose a new email[/bold green]")
    
    # Prompt for recipient
    recipient, cancelled = prompt_recipient()
    if cancelled or recipient is None:
        return None
    
    # Prompt for subject
    subject, cancelled = prompt_subject()
    if cancelled or subject is None:
        return None
    
    # Prompt for body
    body, cancelled = prompt_body()
    if cancelled or body is None:
        return None
    
    return {
        "recipient": recipient,
        "subject": subject,
        "body": body
    }

def show_email_preview(email_data):
    """Display email preview to user."""
    _get_console().print("\n[bold yellow]Email Preview:[/bold yellow]")
    _get_console().print(f"[bold]From:[/bold] {email_data.get('from', 'Not set')}")
    _get_console().print(f"[bold]To:[/bold] {email_data['recipient']}")
    _get_console().print(f"[bold]Subject:[/bold] {email_data['subject']}")
    _get_console().print(f"[bold]Body:[/bold]\n{email_data['body']}")

@log_call
def prompt_send_later():
    """Prompt for optional scheduled send time."""
    send_at = _get_console().input(
        "\nTo send later, enter send time (YYYY-MM-DD HH:MM) or leave blank for immediate: "
    ).strip()
    
    return send_at

def show_send_success(email_data):
    """Display successful send message."""
    _get_console().print("[bold green]Email sent successfully![/bold green]")

def show_send_scheduled(send_time):
    """Display scheduled send message."""
    _get_console().print(f"[yellow]Email scheduled for {send_time} - saved to sent_emails.[/yellow]")

def show_send_failed(error_msg=None):
    """Display send failure message."""
    if error_msg:
        _get_console().print(f"[bold red]Failed to send email: {error_msg}[/bold red]")
        _get_console().print("[bold red]Email will be retried later.[/bold red]")
    else:
        _get_console().print("[bold red]Failed to send email - will try again later.[/bold red]")

def show_draft_saved():
    """Display draft save message."""
    _get_console().print("[yellow]Email cancelled - saved as draft.[/yellow]")
