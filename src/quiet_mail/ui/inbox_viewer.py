from rich.table import Table
from rich.console import Console

console = Console()

def display_inbox(table_name, emails):
    table = Table(title=table_name.capitalize())

    table.add_column("ID", justify="right", style="cyan", no_wrap=True)
    table.add_column("From", style="magenta", min_width=20)
    table.add_column("Subject", style="green", min_width=15)
    table.add_column("Date", justify="right", style="yellow")
    table.add_column("Time", justify="right", style="yellow")
    table.add_column("", style="blue", width=3)  # Attachments column

    if table_name == "inbox":
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
        
        if table_name == "inbox":
            flag_indicator = "🚩" if email.get("flagged") else ""
            row_data.append(flag_indicator)
        
        table.add_row(*row_data)

    console.print(table)