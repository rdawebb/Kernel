from rich.table import Table
from rich.console import Console

console = Console()

def display_inbox(emails):
    table = Table(title="Inbox")

    table.add_column("ID", justify="right", style="cyan", no_wrap=True)
    table.add_column("From", style="magenta")
    table.add_column("Subject", style="green")
    table.add_column("Date", justify="right", style="yellow")

    for email in emails:
        table.add_row(
            str(email.get("id")),
            email.get("from", "N/A"),
            email.get("subject", "No Subject"),
            email.get("date", "Unknown Date")
        )

    console.print(table)