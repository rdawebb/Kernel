"""Compose command - create and send new emails"""

from typing import Any, Dict

from src.ui.composer import Composer
from src.utils.console import print_status
from src.utils.error_handling import DatabaseError
from src.utils.log_manager import async_log_call

from .base import BaseCommandHandler, CommandResult


class ComposeCommandHandler(BaseCommandHandler):
    """Handler for the 'compose' command to compose and send emails."""

    @async_log_call
    async def execute_cli(self, args, config_manager) -> None:
        """Compose and send a new email (CLI mode)."""
        
        # Check if direct composition arguments were provided
        to = getattr(args, "to", None)
        subject = getattr(args, "subject", None)
        body = getattr(args, "body", None)
        cc = getattr(args, "cc", None)
        bcc = getattr(args, "bcc", None)
        
        try:
            composer = Composer()
            
            # If direct arguments provided, use them (non-interactive mode)
            if to or subject or body:
                # TODO: Implement non-interactive composition with direct arguments
                print_status("Direct composition with arguments not yet fully implemented.", color="yellow")
                print_status("Falling back to interactive mode...")
                self.logger.warning("Direct composition attempted but not fully implemented")
            
            # Interactive composition
            result = composer.compose_email()

            if not result:
                print_status("Email composition cancelled or failed.", color="yellow")
                self.logger.info("Email composition cancelled or failed")
            else:
                print_status("Email composed and sent successfully.")
                self.logger.info("Email composed and sent successfully")

        except DatabaseError:
            raise
        except Exception as e:
            print_status(f"Failed to compose/send email: {e}", color="red")
            self.logger.error(f"Failed to compose/send email: {e}")
            raise

    @async_log_call
    async def execute_daemon(self, daemon, args: Dict[str, Any]) -> CommandResult:
        """Compose and send a new email (daemon mode)."""

        recipient = args.get("to", "")
        subject = args.get("subject", "")
        body = args.get("body", "")
        cc = args.get("cc", [])
        bcc = args.get("bcc", [])

        try:
            # Validate required fields
            if not recipient or not subject:
                return self.error_result(
                    "Email requires 'to' and 'subject' fields",
                    to=recipient,
                    subject=subject
                )

            # In daemon mode, create email data dictionary instead of interactive compose
            email_data = {
                "to": recipient,
                "subject": subject,
                "body": body,
            }
            
            # Add cc and bcc if provided
            if cc:
                email_data["cc"] = cc if isinstance(cc, list) else [cc]
            if bcc:
                email_data["bcc"] = bcc if isinstance(bcc, list) else [bcc]

            return self.success_result(
                data="Email composition initiated",
                email_data=email_data,
                mode="compose"
            )

        except DatabaseError as e:
            return self.error_result(str(e))
