"""Unified email table viewer - displays emails in formatted tables with dynamic columns"""

from typing import Any, Dict, List, Optional

from rich.table import Table
from rich.console import Console

from src.utils.console import get_console
from src.utils.error_handling import ValidationError
from src.utils.log_manager import async_log_call, get_logger

logger = get_logger(__name__)


def _validate_email_list(emails: List[Dict[str, Any]]) -> None:
    """Validate the list of emails before display"""
    if not isinstance(emails, list):
        raise ValidationError(
            f"Emails must be provided as a list, got {type(emails).__name__} instead.",
            details={"type": type(emails).__name__}
        )
    
    for idx, email in enumerate(emails):
        if not isinstance(email, dict):
            raise ValidationError(
                f"Each email must be a dictionary, got {type(email).__name__} at index {idx}.",
                details={"index": idx, "type": type(email).__name__}
            )
        
def _build_table_columns(table: Table, show_source: bool, 
                         show_flagged: bool) -> None:
    """Dynamically add columns to the table based on flags"""
    table.add_column("ID", justify="right", style="cyan", no_wrap=True)
    table.add_column("From", style="magenta", min_width=20)
    table.add_column("Subject", style="green", min_width=20)
    table.add_column("Date", justify="right", style="yellow")
    table.add_column("Time", justify="right", style="yellow")
    table.add_column("", justify="center", width=3)  # Attachments indicator

    if show_source:
        table.add_column("Source", style="white", min_width=12)

    if show_flagged:
        table.add_column("", justify="center", width=3) # Flagged indicator

def _format_source_display(source_table: str) -> str:
    """Format the source table name for display"""
    source_map = {
        "inbox": "Inbox",
        "sent": "Sent",
        "drafts": "Drafts",
        "trash": "Trash",
    }

    return source_map.get(source_table, source_table.title())

def _build_table_rows(email: Dict[str, Any], show_source: bool, 
                      show_flagged: bool) -> List[Any]:
    """Build a row for the table based on email data and flags"""
    uid_value = email.get("uid")
    uid = str(uid_value) if uid_value is not None else "N/A"
    sender = email.get("from", "N/A")
    subject = email.get("subject", "No Subject")
    date = email.get("date", "Unknown Date")
    time = email.get("time", "Unknown Time")

    attachments_raw = email.get("attachments", "")
    if isinstance(attachments_raw, list):
        attachments_indicator = "📎" if attachments_raw else ""
    else:
        attachments_stripped = attachments_raw.strip() if attachments_raw else ""
        attachments_indicator = "📎" if bool(attachments_stripped) else ""

    row_data = [
        uid,
        sender,
        subject,
        date,
        time,
        attachments_indicator
    ]
    
    if show_source:
        source_table = email.get("source_table", "unknown")
        row_data.append(_format_source_display(source_table))

    if show_flagged:
        flagged_indicator = "🚩" if email.get("flagged") else ""
        row_data.append(flagged_indicator)

    return row_data

def _display_empty_message(console: Console, keyword: Optional[str] = None) -> None:
    """Display a message when there are no emails to show"""
    if keyword:
        console.print(f"[yellow]No emails found matching the keyword '{keyword}'.[/]")
    else:
        console.print("[yellow]No emails to display.[/]")
    
@async_log_call
async def display_email_table(emails: List[Dict[str, Any]], 
                              title: str = "Emails", 
                              show_source: bool = False, 
                              show_flagged: bool = False,
                              keyword: Optional[str] = None,
                              console: Optional[Console] = None) -> None:
    """Display emails in a formatted table with dynamic columns"""
    _validate_email_list(emails)

    output_console = console or get_console()

    try:
        if not emails:
            _display_empty_message(output_console, keyword)
            logger.debug(f"No emails to display for table: {title}.")
            return
        
        table = Table(title=title)
        _build_table_columns(table, show_source, show_flagged)

        for email in emails:
            try:
                row_data = _build_table_rows(email, show_source, show_flagged)
                table.add_row(*row_data)

            except Exception as e:
                logger.warning(
                    f"Error building email row: {e}",
                    extra={"email_uid": email.get("uid")}
                )
                continue

        output_console.print(table)
        logger.debug(f"Displayed email table '{title}' with {len(emails)} emails.")

    except Exception as e:
        logger.error(f"Error displaying email table: {e}")
        raise ValidationError(
            "Failed to display email table.",
            details={"error": str(e), "title": title, "email_count": len(emails)}
        ) from e
    