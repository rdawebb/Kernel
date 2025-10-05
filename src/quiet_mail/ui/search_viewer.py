from rich.table import Table
from rich.console import Console

console = Console()

def display_search_results(emails, keyword):
    if not emails:
        console.print(f"[yellow]No emails found matching '{keyword}'.[/]")
        return
    
    table = Table(title=f"Search Results for '{keyword}'")

    table.add_column("ID", justify="right", style="cyan", no_wrap=True)
    table.add_column("From", style="magenta", min_width=20)
    table.add_column("Subject", style="green", min_width=15)
    table.add_column("Date", justify="right", style="yellow")
    table.add_column("Time", justify="right", style="yellow")
    table.add_column("", justify="center", style="red", width=3)  # Flagged column
    table.add_column("", style="blue", width=3)  # Attachments column

    for email in emails:
        flagged_status = "🚩" if email.get("flagged") else ""
        
        attachments_raw = email.get("attachments", "")
        has_attachments = bool(attachments_raw and attachments_raw.strip())
        attachments = "📎" if has_attachments else ""
        
        table.add_row(
            str(email.get("id")),
            email.get("from", "N/A"),
            email.get("subject", "No Subject"),
            email.get("date", "Unknown Date"),
            email.get("time", "Unknown Time"),
            flagged_status,
            attachments
        )

    console.print(table)