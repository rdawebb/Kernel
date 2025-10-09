"""Interactive email composer - prompts user for all email details and handles sending or saving as draft"""

## TODO: refactor to separate sending logic from UI, improve error handling and validation

import datetime
import uuid
from rich.console import Console
from email_validator import validate_email, EmailNotValidError
from quiet_mail.core.smtp_client import send_email
from quiet_mail.utils.ui_helpers import confirm_action
from quiet_mail.core.storage_api import save_sent_email, save_draft_email
from quiet_mail.utils.config import load_config
from quiet_mail.utils.logger import get_logger

console = Console()
logger = get_logger()

def create_email_dict(subject, sender, recipient, body, attachments=None):
    """Create a standardized email dictionary for storage"""
    return {
        "uid": str(uuid.uuid4()),
        "subject": subject,
        "from": sender,
        "to": recipient,
        "date": datetime.date.today().isoformat(),
        "time": datetime.datetime.now().time().strftime("%H:%M:%S"),
        "body": body,
        "attachments": attachments or []
    }

def compose_email():
    """Interactive email composer - prompts user for all email details"""
    console.print("[bold green]Compose a new email[/bold green]")

    recipient = console.input("To: ")
    if not recipient or recipient.strip() == "":
        console.print("[bold red]Recipient email is required.[/bold red]")
        return False
    
    try:
        valid = validate_email(recipient)
        recipient = valid.email
    except EmailNotValidError as e:
        logger.error(f"Invalid email address: {e}")
        console.print(f"[bold red]Invalid email address: {e}[/bold red]")
        return False
    
    email_subject = console.input("Subject: ")
    if not email_subject or email_subject.strip() == "":
        if not confirm_action("Subject is empty, continue anyway?"):
            return False

    console.print("Body (press Enter twice when finished):")
    body_lines = []
    while True:
        line = console.input("")
        if line == "" and body_lines and body_lines[-1] == "":
            break
        body_lines.append(line)
    
    email_body = "\n".join(body_lines[:-1])
    
    if not email_body or email_body.strip() == "":
        if not confirm_action("Body is empty, continue anyway?"):
            return False

    console.print("\n[bold yellow]Email Preview:[/bold yellow]")
    console.print(f"[bold]To:[/bold] {recipient}")
    console.print(f"[bold]Subject:[/bold] {email_subject}")
    console.print(f"[bold]Body:[/bold]\n{email_body}")
    
    config = load_config()
    email_data = create_email_dict(
        subject=email_subject,
        sender=config["email"],
        recipient=recipient,
        body=email_body
    )

    if not confirm_action("\nSend this email?"):
        logger.info("Email cancelled - saved as draft.")
        console.print("[yellow]Email cancelled - saved as draft.[/yellow]")
        save_draft_email(email_data)
        return False

    send_at = console.input("To send later, enter send time (YYYY-MM-DD HH:MM) or leave blank for immediate: ").strip()
    
    is_scheduled = bool(send_at)
    
    if is_scheduled:
        try:
            datetime.datetime.strptime(send_at, "%Y-%m-%d %H:%M")
            email_data["send_at"] = send_at
            email_data["sent_status"] = "pending"
            logger.info(f"Email scheduled for {send_at} - saved to sent_emails.")
            console.print(f"[yellow]Email scheduled for {send_at} - saved to sent_emails.[/yellow]")
            save_sent_email(email_data)
            return True
        except ValueError:
            logger.error("Invalid date format for scheduled email.")
            console.print("[red]Invalid date format. Please use YYYY-MM-DD HH:MM[/red]")
            return False
    else:
        try:
            success = send_email(
                to_email=recipient,
                subject=email_subject,
                body=email_body
            )
            if success:
                logger.info("Email sent successfully")
                console.print("[bold green]Email sent successfully![/bold green]")
                email_data["sent_status"] = "sent"
                email_data["send_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                save_sent_email(email_data)
                return True
            else:
                logger.error("Failed to send email")
                console.print("[bold red]Failed to send email - will try again later.[/bold red]")
                email_data["sent_status"] = "pending"
                email_data["send_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                save_sent_email(email_data)
                return False
        except Exception as e:
            logger.error(f"Error sending email: {e}")
            console.print(f"[bold red]Error sending email: {e} - will try again later.[/bold red]")
            email_data["sent_status"] = "pending"
            email_data["send_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            save_sent_email(email_data)
            return False