"""Email viewer using Rich library for formatted console output"""

from rich.text import Text
from ..utils.log_manager import get_logger, log_call

logger = get_logger(__name__)

@log_call
def display_email(email_data, console_obj=None):
    """Display a formatted email in the console using Rich formatting"""
    
    # Console must be provided by caller
    if console_obj is None:
        raise ValueError("console_obj must be provided to display_email")
    
    output_console = console_obj
    
    details = [
        f"[bold]From:[/] {email_data.get('from', 'Unknown')}",
        f"[bold]Date:[/] {email_data.get('date', 'Unknown Date')}",
        f"[bold]Time:[/] {email_data.get('time', 'Unknown Time')}",
        f"[bold]Subject:[/] {email_data.get('subject', 'No Subject')}\n"
    ]

    max_len = max(len(Text.from_markup(line)) for line in details)
    separator = "-" * max_len
    
    output_console.print(separator)
    output_console.print("\n".join(details))

    attachments_raw = email_data.get('attachments', '')
    if attachments_raw and attachments_raw.strip():
        attachments_list = [att.strip() for att in attachments_raw.split(',') if att.strip()]
        if attachments_list:
            output_console.print(f"[bold]Attachments:[/] {', '.join(attachments_list)}\n")
    
    body = email_data.get("body")
    if not body:
        output_console.print("[dim]No body available[/]")
    else:
        output_console.print(body)
    output_console.print(separator)
