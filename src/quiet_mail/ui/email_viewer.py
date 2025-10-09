"""Email viewer using Rich library for formatted console output"""

from rich.console import Console

console = Console()

def display_email(email_data):
    """Display a formatted email in the console using Rich formatting"""
    console.print(f"[bold]From:[/] {email_data.get('from', 'Unknown')}")
    console.print(f"[bold]Subject:[/] {email_data.get('subject', 'No Subject')}")
    console.print(f"[bold]Date:[/] {email_data.get('date', 'Unknown Date')}")
    console.print(f"[bold]Time:[/] {email_data.get('time', 'Unknown Time')}\n")
    
    attachments_raw = email_data.get('attachments', '')
    if attachments_raw and attachments_raw.strip():
        attachments_list = [att.strip() for att in attachments_raw.split(',') if att.strip()]
        if attachments_list:
            console.print(f"[bold]Attachments:[/] {', '.join(attachments_list)}\n")
    
    console.print(email_data.get("body", "[dim]No body available[/]"))