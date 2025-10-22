"""Unified email table viewer - displays emails in formatted tables with dynamic columns"""

from rich.table import Table
from rich.console import Console
from ..utils.log_manager import get_logger, log_call

logger = get_logger(__name__)
console = Console()


def _format_attachment_indicator(email):
    """Return 📎 if email has attachments."""
    attachments_raw = email.get("attachments", "")
    has_attachments = bool(attachments_raw and attachments_raw.strip())
    return "📎" if has_attachments else ""

def _get_source_display(source_table):
    """Convert source table name to human-readable format."""
    return {
        "inbox": "Inbox",
        "sent_emails": "Sent",
        "drafts": "Drafts",
        "deleted_emails": "Deleted"
    }.get(source_table, source_table)

def _format_flagged_indicator(email):
    """Return 🚩 if email is flagged."""
    return "🚩" if email.get("flagged") else ""

@log_call
def display_email_table(
    emails,
    title="Emails",
    show_source=False,
    show_flagged=False,
    keyword=None
):
    """Display emails in formatted table with optional columns."""
    if not emails:
        if keyword:
            console.print(f"[yellow]No emails found matching '{keyword}'.[/]")
        else:
            console.print("[yellow]No emails to display.[/]")
        return

    table = Table(title=title)

    # Base columns
    table.add_column("ID", justify="right", style="cyan", no_wrap=True)
    table.add_column("From", style="magenta", min_width=20)
    table.add_column("Subject", style="green", min_width=15)
    table.add_column("Date", justify="right", style="yellow")
    table.add_column("Time", justify="right", style="yellow")
    table.add_column("", style="blue", width=3)  # Attachments column

    # Optional columns
    if show_source:
        table.add_column("Source", style="bright_white", width=12)
    if show_flagged:
        table.add_column("", justify="center", style="red", width=3)  # Flagged column

    # Add rows
    for email in emails:
        row_data = [
            str(email.get("uid")) if email.get("uid") is not None else "N/A",
            email.get("from", "N/A"),
            email.get("subject", "No Subject"),
            email.get("date", "Unknown Date"),
            email.get("time", "Unknown Time"),
            _format_attachment_indicator(email)
        ]

        if show_source:
            source_table = email.get("source_table", "unknown")
            row_data.append(_get_source_display(source_table))

        if show_flagged:
            row_data.append(_format_flagged_indicator(email))

        table.add_row(*row_data)

    console.print(table)
