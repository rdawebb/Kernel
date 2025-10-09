"""Search results viewer - displays search results in a formatted table with dynamic columns based on source"""

## TODO: refactor to reduce redundancy, improve error handling
## TODO: combine with inbox_viewer.py if possible or create shared base class
## TODO: add pagination for large result sets?
## TODO: consider adding sorting options
## TODO: improve handling of missing data (e.g. missing subject, sender)

from rich.table import Table
from rich.console import Console

console = Console()

def display_search_results(table_name, emails, keyword):
    """Display search results in a formatted table with dynamic columns based on source"""
    if not emails:
        console.print(f"[yellow]No emails found in '{table_name}' matching '{keyword}'.[/]")
        return

    table = Table(title=f"Search Results for '{keyword}' in {table_name}")

    table.add_column("ID", justify="right", style="cyan", no_wrap=True)
    table.add_column("From", style="magenta", min_width=20)
    table.add_column("Subject", style="green", min_width=15)
    table.add_column("Date", justify="right", style="yellow")
    table.add_column("Time", justify="right", style="yellow")
    table.add_column("", style="blue", width=3)  # Attachments column

    has_flagged_emails = False
    if table_name == "all emails":
        table.add_column("Source", style="bright_white", width=12)
        has_flagged_emails = any(email.get("flagged") is not None for email in emails)
        if has_flagged_emails:
            table.add_column("", justify="center", style="red", width=3)  # Flagged column
    elif table_name == "inbox":
        table.add_column("", justify="center", style="red", width=3)  # Flagged column

    for email in emails:
        attachments_raw = email.get("attachments", "")
        has_attachments = bool(attachments_raw and attachments_raw.strip())
        attachments = "📎" if has_attachments else ""
        
        row_data = [
            str(email.get("uid")) if email.get("uid") is not None else "N/A",
            email.get("from", "N/A"),
            email.get("subject", "No Subject"),
            email.get("date", "Unknown Date"),
            email.get("time", "Unknown Time"),
            attachments
        ]
        
        if table_name == "all emails":
            source_table = email.get("source_table", "unknown")
            
            source_display = {
                "inbox": "Inbox",
                "sent_emails": "Sent", 
                "drafts": "Drafts",
                "deleted_emails": "Deleted"
            }.get(source_table, source_table)
            row_data.append(source_display)
            
            if has_flagged_emails:
                flagged_status = "🚩" if email.get("flagged") else ""
                row_data.append(flagged_status)
                
        elif table_name == "inbox":
            flagged_status = "🚩" if email.get("flagged") else ""
            row_data.append(flagged_status)
        
        table.add_row(*row_data)

    console.print(table)