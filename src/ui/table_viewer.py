"""Unified email table viewer - displays emails in formatted tables with dynamic columns"""

from rich.table import Table
from ..utils.log_manager import get_logger, log_call

logger = get_logger(__name__)


@log_call
def display_email_table(
    emails,
    title="Emails",
    show_source=False,
    show_flagged=False,
    keyword=None,
    console_obj=None
):

    """Display emails in formatted table with optional columns."""
    # Console must be provided by caller (daemon handler or CLI)
    if console_obj is None:
        raise ValueError("console_obj must be provided to display_email_table")
    
    output_console = console_obj
    
    if not emails:
        if keyword:
            output_console.print(f"[yellow]No emails found matching '{keyword}'.[/]")
        else:
            output_console.print("[yellow]No emails to display.[/]")
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

    for email in emails:
        uid_value = email.get("uid")
        uid = str(uid_value) if uid_value is not None else "N/A"
        sender = email.get("from", "N/A")
        subject = email.get("subject", "No Subject")
        date = email.get("date", "Unknown Date")
        time = email.get("time", "Unknown Time")

        attachments_raw = email.get("attachments", "")
        attachments_stripped = attachments_raw.strip() if attachments_raw else ""
        has_attachments = bool(attachments_stripped)
        attachment_indicator = "📎" if has_attachments else ""

        row_data = [
            uid,
            sender,
            subject,
            date,
            time,
            attachment_indicator
        ]

        if show_source:
            source_table = email.get("source_table", "unknown")
            source_display = {
                "inbox": "Inbox",
                "sent_emails": "Sent",
                "drafts": "Drafts",
                "deleted_emails": "Deleted"
            }.get(source_table, source_table)
            row_data.append(source_display)

        if show_flagged:
            flagged_indicator = "🚩" if email.get("flagged") else ""
            row_data.append(flagged_indicator)

        table.add_row(*row_data)

    output_console.print(table)
