"""Compose command - create and send new emails"""

from typing import Any, Dict

from src.ui.composer import compose_email
from src.utils.console import print_status
from src.utils.error_handling import DatabaseError
from src.utils.log_manager import async_log_call

from .base import BaseCommandHandler, CommandResult


class ComposeCommandHandler(BaseCommandHandler):
    """Handler for the 'compose' command to compose and send emails."""

    @async_log_call
    async def execute_cli(self, args, config_manager) -> bool:
        """Compose and send a new email (CLI mode)."""
        
        # Check if direct composition arguments were provided
        to = getattr(args, "to", None)
        subject = getattr(args, "subject", None)
        body = getattr(args, "body", None)
        
        try:
            # If direct arguments provided, use them (non-interactive mode)
            if to or subject or body:
                # TODO: Implement non-interactive composition with direct arguments
                await print_status("Direct composition with arguments not yet fully implemented.")
                await print_status("Falling back to interactive mode...")
                self.logger.debug("Direct composition attempted but not fully implemented")
            
            # Interactive composition
            result = await compose_email()

            if not result:
                self.logger.info("Email composition cancelled or failed")
                return False
            else:
                self.logger.info("Email composed and sent successfully")
                return True

        except DatabaseError as e:
            self.logger.error(f"Database error during composition: {e}")
            return False

        except Exception as e:
            self.logger.error(f"Failed to compose/send email: {e}")
            return False

    @async_log_call
    async def execute_daemon(self, daemon, args: Dict[str, Any]) -> CommandResult:
        """Compose and send a new email (daemon mode)."""

        recipient = args.get("to", "")
        subject = args.get("subject", "")
        body = args.get("body", "")

        try:
            if not recipient or not subject:
                return self.error_result(
                    "Email requires 'to' and 'subject' fields",
                    to=recipient,
                    subject=subject
                )

            email_data = {
                "to": recipient,
                "subject": subject,
                "body": body,
            }

            return self.success_result(
                data="Email composition initiated",
                email_data=email_data,
                mode="compose"
            )

        except DatabaseError as e:
            return self.error_result(str(e))
