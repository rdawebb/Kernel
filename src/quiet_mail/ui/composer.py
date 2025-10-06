from rich.console import Console
from email_validator import validate_email, EmailNotValidError
from quiet_mail.core.smtp_client import send_email
from quiet_mail.utils.ui_helpers import confirm_action

console = Console()

def compose_email():
    """
    Interactive email composer - prompts user for all email details
    """
    console.print("[bold green]Compose a new email[/bold green]")

    recipient = console.input("To: ")
    if not recipient or recipient.strip() == "":
        console.print("[bold red]Recipient email is required.[/bold red]")
        return False
    
    try:
        valid = validate_email(recipient)
        recipient = valid.email
    except EmailNotValidError as e:
        console.print(f"[bold red]Invalid email address: {e}[/bold red]")
        return False
    
    email_subject = console.input("Subject: ")
    if not email_subject or email_subject.strip() == "":
        if not confirm_action("Subject is empty, continue anyway?"):
            return False

    # Get body with multi-line support
    console.print("Body (press Enter twice when finished):")
    body_lines = []
    while True:
        line = console.input("")
        if line == "" and body_lines and body_lines[-1] == "":
            break
        body_lines.append(line)
    
    email_body = "\n".join(body_lines[:-1])  # Remove the last empty line
    
    if not email_body or email_body.strip() == "":
        if not confirm_action("Body is empty, continue anyway?"):
            return False

    console.print("\n[bold yellow]Email Preview:[/bold yellow]")
    console.print(f"[bold]To:[/bold] {recipient}")
    console.print(f"[bold]Subject:[/bold] {email_subject}")
    console.print(f"[bold]Body:[/bold]\n{email_body}")
    
    if not confirm_action("\nSend this email?"):
        console.print("[yellow]Email cancelled.[/yellow]")
        return False

    try:
        success = send_email(
            to_email=recipient,
            subject=email_subject,
            body=email_body
        )
        if success:
            console.print("[bold green]Email sent successfully![/bold green]")
            return True
        else:
            console.print("[bold red]Failed to send email.[/bold red]")
            return False
    except Exception as e:
        console.print(f"[bold red]Error sending email: {e}[/bold red]")
        return False