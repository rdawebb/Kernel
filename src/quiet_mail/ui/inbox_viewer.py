from rich.table import Table
from rich.console import Console

console = Console()

def display_inbox(emails):
    table = Table(title="Inbox")

    table.add_column("ID", justify="right", style="cyan", no_wrap=True)
    table.add_column("From", style="magenta")
    table.add_column("Subject", style="green")
    table.add_column("Date", justify="right", style="yellow")
    table.add_column("Time", justify="right", style="yellow")
    table.add_column("Flagged", justify="center", style="red")

    for email in emails:
        flagged_status = "🚩" if email.get("flagged") else ""
        table.add_row(
            str(email.get("id")),
            email.get("from", "N/A"),
            email.get("subject", "No Subject"),
            email.get("date", "Unknown Date"),
            email.get("time", "Unknown Time"),
            flagged_status
        )

    console.print(table)