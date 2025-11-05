"""UI logic for interactive email composer - handles all user prompts and console output"""

from typing import Any, Dict, Optional

from rich.console import Console
from rich.panel import Panel

from src.core.email_handling import DateTimeParser, EmailValidator
from src.utils.console import get_console
from src.utils.log_manager import async_log_call, get_logger
from src.utils.ui_helpers import confirm_action

logger = get_logger(__name__)


@async_log_call
async def prompt_recipient(console: Optional[Console] = None) -> Optional[str]:
    """Prompt user for recipient email address with validation"""
    output_console = console or get_console()

    while True:
        try:
            recipient = output_console.input("\nTo: ").strip()
            
            if not recipient:
                output_console.print("[red]Recipient email address is required[/]")
                if not await confirm_action("Try entering the email address again?", console=output_console):
                    return None
                continue

            if EmailValidator.is_valid_email(recipient):
                return recipient
            else:
                output_console.print("[red]Invalid email address format[/]")
                if not await confirm_action("Try entering the email address again?", console=output_console):
                    return None
                continue
        
        except (KeyboardInterrupt, EOFError):
            output_console.print("\n[yellow]Input cancelled by user.[/]")
            return None
        
        except Exception as e:
            logger.error(f"Error during recipient prompt: {e}")
            output_console.print(f"[red]An unexpected error occurred: {e}[/]")
            return None
        
@async_log_call
async def prompt_subject(console: Optional[Console] = None) -> Optional[str]:
    """Prompt user for email subject"""
    output_console = console or get_console()

    while True:
        try:
            subject = output_console.input("Subject: ").strip()
            
            if subject:
                return subject
            
            if await confirm_action("Subject is empty, continue anyway?", console=output_console):
                return "(No subject)"
            else:
                if not await confirm_action("Try entering the subject again?", console=output_console):
                    return None
                
        except (KeyboardInterrupt, EOFError):
            output_console.print("\n[yellow]Input cancelled by user.[/]")
            return None
        
        except Exception as e:
            logger.error(f"Error during subject prompt: {e}")
            output_console.print(f"[red]An unexpected error occurred: {e}[/]")
            return None
        
@async_log_call
async def prompt_body(console: Optional[Console] = None) -> Optional[str]:
    """Prompt user for email body content"""
    output_console = console or get_console()

    try:
        output_console.print("Body (type '/end' on a new line to finish):\n")

        lines = []
        while True:
            try:
                line = output_console.input("")
                if line == "/end":
                    break

                lines.append(line)

            except (KeyboardInterrupt, EOFError):
                output_console.print("\n[yellow]Input cancelled by user.[/]")
                return None

        if lines and lines[-1] == "/end":
            lines = lines[:-1]    
        body = "\n".join(lines).strip()
                    
        if not body:
            if not await confirm_action("Email body is empty, continue anyway?", console=output_console):
                return None

        return body
    
    except Exception as e:
        logger.error(f"Error during body prompt: {e}")
        output_console.print(f"[red]An unexpected error occurred: {e}[/]")
        return None
    
@async_log_call
async def prompt_email_details(console: Optional[Console] = None) -> Optional[Dict[str, str]]:
    """Prompt user for all email details: recipient, subject, body"""
    output_console = console or get_console()

    try:
        output_console.print("[bold green]Compose New Email[/]\n")

        recipient = await prompt_recipient(console=output_console)
        if recipient is None:
            return None
        
        subject = await prompt_subject(console=output_console)
        if subject is None:
            return None
        
        body = await prompt_body(console=output_console)
        if body is None:
            return None
        
        return {
            "recipient": recipient,
            "subject": subject,
            "body": body
        }
    
    except Exception as e:
        logger.error(f"Error during email details prompt: {e}")
        output_console.print(f"[red]An unexpected error occurred: {e}[/]")
        return None
    
async def show_email_preview(email_data: Dict[str, Any], console: Optional[Console] = None) -> None:
    """Display a preview of the composed email"""
    output_console = console or get_console()

    try:
        output_console.print("\n[bold yellow]Email Preview:[/]\n")
        
        preview_lines = [
            f"[bold]To:[/] {email_data['recipient']}",
            f"[bold]Subject:[/] {email_data['subject']}",
            "\n[bold]Body:[/]\n",
            email_data['body']
        ]
        
        preview_panel = Panel(
            "\n".join(preview_lines),
            border_style="cyan",
            padding=(1, 2)
        )
        
        output_console.print(preview_panel)

    except Exception as e:
        logger.error(f"Error displaying email preview: {e}")
        output_console.print(f"[red]An unexpected error occurred while displaying preview: {e}[/]")

@async_log_call
async def prompt_send_later(console: Optional[Console] = None) -> str:
    """Prompt user for optional scheduled send time"""
    output_console = console or get_console()

    while True:
        try:
            send_at = output_console.input(
                "\nTo send later, enter date/time (e.g. 'tomorrow 9am', 'in 2 days', '2023-12-31 15:00'), or press Enter to send now: "
            ).strip()

            if not send_at:
                return ""
            
            parsed_dt, error = DateTimeParser.parse_datetime(send_at)
            if error:
                output_console.print(f"[red]{error}[/]")
                if not await confirm_action("Try entering the date/time again?", console=output_console):
                    return ""
                continue

            return parsed_dt.isoformat()
    
        except (KeyboardInterrupt, EOFError):
            output_console.print("\n[yellow]Input cancelled, sending immediately.[/]")
            return ""
    
        except Exception as e:
            logger.error(f"Error during send later prompt: {e}")
            output_console.print(f"[red]An unexpected error occurred: {e}[/]")
            return ""
    
async def show_send_success(email_data: Dict[str, Any], 
                            console: Optional[Console] = None) -> None:
    """Display success message after sending email"""
    output_console = console or get_console()

    try:
        output_console.print(
            Panel.fit(
                f"[bold green]Email sent successfully to {email_data['recipient']}![/]",
                border_style="green",
                padding=(1, 2)
            )
        )

    except Exception as e:
        logger.error(f"Error displaying send success message: {e}")
        output_console.print(f"[red]An unexpected error occurred: {e}[/]")

async def show_send_scheduled(send_time: str, 
                              console: Optional[Console] = None) -> None:
    """Display success message after scheduling email"""
    output_console = console or get_console()

    try:
        output_console.print(
            Panel.fit(
                f"[yellow]Email scheduled to be sent at {send_time}![/]",
                border_style="yellow",
                padding=(1, 2)
            )
        )

    except Exception as e:
        logger.error(f"Error displaying send scheduled message: {e}")
        output_console.print(f"[red]An unexpected error occurred: {e}[/]")

async def show_send_failed(error_message: str, 
                           console: Optional[Console] = None) -> None:
    """Display failure message after failed send attempt"""
    output_console = console or get_console()

    try:
        if error_message:
            message = f"[bold red]Failed to send email: {error_message}[/]"
        else:
            message = "[bold red]Failed to send email due to unknown error.[/]"

        output_console.print(
            Panel.fit(
                message + "\n[red]Email will be retried later.[/]",
                border_style="red",
                padding=(1, 2)
            )
        )

    except Exception as e:
        logger.error(f"Error displaying send failed message: {e}")
        output_console.print(f"[red]An unexpected error occurred: {e}[/]")

async def show_draft_saved(console: Optional[Console] = None) -> None:
    """Display message after saving email as draft"""
    output_console = console or get_console()

    try:
        output_console.print(
            Panel.fit(
                "[yellow]Email cancelled - saved as draft.[/]",
                border_style="yellow",
                padding=(1, 2)
            )
        )

    except Exception as e:
        logger.error(f"Error displaying draft saved message: {e}")
        output_console.print(f"[red]An unexpected error occurred: {e}[/]")
