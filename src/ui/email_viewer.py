"""Email viewer using Rich library for formatted console output"""

from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.text import Text
from rich.panel import Panel

from src.utils.console import get_console
from src.utils.error_handling import ValidationError
from src.utils.log_manager import async_log_call, get_logger

logger = get_logger(__name__)


def _validate_email_data(email_data: Dict[str, Any]) -> None:
    """Validate email data structure before display"""
    if not email_data:
        raise ValidationError(
            "Email data is empty or None.",
            details={"email_data": email_data}
        )
    
    if not isinstance(email_data, dict):
        raise ValidationError(
            f"Email data must be a dictionary, got {type(email_data).__name__} instead.",
            details={"type": type(email_data).__name__}
        )
    
    required_fields = ["from", "subject"]
    missing_fields = [field for field in required_fields if field not in email_data]

    if missing_fields:
        raise ValidationError(
            f"Email data is missing required fields: {', '.join(missing_fields)}",
            details={"missing_fields": missing_fields, "available_fields": list(email_data.keys())}
        )
    
def _format_email_details(email_data: Dict[str, Any]) -> List[str]:
    """Format email header details for display"""
    return [
        f"[bold]From:[/] {email_data.get('from', 'Unknown')}",
        f"[bold]To:[/] {email_data.get('to', 'Unknown')}",
        f"[bold]Date:[/] {email_data.get('date', 'Unknown Date')}",
        f"[bold]Time:[/] {email_data.get('time', 'Unknown Time')}\n",
        f"[bold]Subject:[/] {email_data.get('subject', 'No Subject')}",
    ]

def _format_attachments(email_data: Dict[str, Any]) -> Optional[str]:
    """Format attachment information for display if present"""
    attachments_raw = email_data.get("attachments", "")

    if not attachments_raw or not attachments_raw.strip():
        return None
    
    if isinstance(attachments_raw, list):
        attachments_list = [att.strip() for att in attachments_raw if att and att.strip()]
    else:
        attachments_list = [att.strip() for att in attachments_raw.split(",") if att.strip()]

    if attachments_list:
        return f"[bold]Attachments:[/] {', '.join(attachments_list)}\n"

    return None
    
@async_log_call
async def display_email(email_data: Dict[str, Any], 
                        console: Optional[Console] = None) -> None:
    """Display formatted email content in the console"""
    _validate_email_data(email_data)

    output_console = console or get_console()

    try:
        header = _format_email_details(email_data)

        panel_width = int(output_console.size.width * 0.6)

        output_console.print(Panel(
            Text.from_markup("\n".join(header)),
            title=Text.from_markup(f"[bold]Email UID:[/] {email_data.get('uid')}"),
            border_style="cyan dim",
            padding=(1, 2),
            width=panel_width
        ))

        attachments_str = _format_attachments(email_data).strip()
        if attachments_str:
            output_console.print(Panel(
                Text.from_markup(attachments_str),
                border_style="magenta dim",
                padding=(0, 2),
                width=panel_width
            ))

        body = email_data.get("body")
        if not body or not body.strip():
            body = "[italic dim]No content in email body.[/italic dim]"
        else:
            body = Text.from_markup(body)

        output_console.print(Panel(
            body, border_style="cyan dim", 
            padding=(1, 2), 
            width=panel_width
        ))
        logger.debug(f"Displayed email ID {email_data.get('uid')} successfully.")

    except Exception as e:
        logger.error(f"Error displaying email: {e}")
        raise ValidationError(
            "Failed to display email content.",
            details={"error": str(e), "email_id": email_data.get('uid')}
        ) from e
        