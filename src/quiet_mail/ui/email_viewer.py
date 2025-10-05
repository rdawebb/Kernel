from rich.console import Console

console = Console()

def display_email(email_data):
    console.print(f"[bold]From:[/] {email_data.get('from', 'Unknown')}")
    console.print(f"[bold]Subject:[/] {email_data.get('subject', 'No Subject')}")
    console.print(f"[bold]Date:[/] {email_data.get('date', 'Unknown Date')}")
    console.print(f"[bold]Time:[/] {email_data.get('time', 'Unknown Time')}\n")
    
    # Handle attachments string from database
    attachments_raw = email_data.get('attachments', '')
    if attachments_raw and attachments_raw.strip():
        attachments_list = [att.strip() for att in attachments_raw.split(',') if att.strip()]
        if attachments_list:  # Only show if we have actual attachment names
            console.print(f"[bold]Attachments:[/] {', '.join(attachments_list)}\n")
    
    console.print(email_data.get("body", "[dim]No body available[/]"))