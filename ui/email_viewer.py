from rich.console import Console

console = Console()

def display_email(email_data):
    console.print(f"[bold]From:[/] {email_data.get('from', 'Unknown')}")
    console.print(f"[bold]Subject:[/] {email_data.get('subject', 'No Subject')}")
    console.print(f"[bold]Date:[/] {email_data.get('date', 'Unknown Date')}\n")
    console.print(email_data.get("body", "[dim]No body available[/]"))