"""Main workflow orchestration for email composition."""

import asyncio
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from rich.console import Console

from src.core.database import Database, get_database
from src.core.validation import DateTimeParser, EmailValidator
from src.utils.config import ConfigManager
from src.utils.errors import DatabaseError, KernelError, SMTPError, ValidationError
from src.utils.logging import async_log_call, get_logger

from .display import ComposeDisplay
from .input import CompositionInputManager

logger = get_logger(__name__)


class EmailComposer:
    """Handle email composition and sending"""

    def __init__(self, config=None, smtp_client=None):
        """Initialize EmailComposer with config and SMTP client"""
        self.config = config
        self.smtp_client = smtp_client

    def create_email_dict(self, recipient: str, subject: str, body: str,
                          sender: Optional[str] = None,
                          attachments: Optional[list] = None) -> Dict[str, Any]:
        """Create structured email dictionary for storage"""
        if sender is None and self.config:
            account_config = self.config.get_account_config()
            sender = account_config.get("email", "")

        now = datetime.now()

        return {
            "uid": self._generate_uid(),
            "subject": subject,
            "sender": sender or "",
            "recipient": recipient,
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M"),
            "body": body,
            "attachments": ",".join(attachments) if attachments else "",
        }

    def send_email(self, to_email: str, subject: str, body: str,
                   cc: Optional[list] = None, bcc: Optional[list] = None) -> Tuple[bool, Optional[str]]:
        """Send an email via SMTP client"""
        try:
            if self.smtp_client:
                smtp = self.smtp_client
            else:
                from src.core.email.smtp.client import SMTPClient

                if not self.config:
                    raise ValidationError("No configuration provided for SMTP client")
                
                config = self.config.get_account_config()

                smtp = SMTPClient(
                    host=config.get("smtp_server"),
                    port=config.get("smtp_port", 587),
                    username=config.get("username"),
                    password=config.get("password"),
                    use_tls=config.get("use_tls", True)
                )

            success = smtp.send_email(to_email, subject, body, cc, bcc)

            if success:
                logger.info(f"Email sent to {to_email} with subject '{subject}'")
                return True, None
            else:
                raise SMTPError("Failed to send email via SMTP client")
            
        except (ValidationError, SMTPError):
            raise

        except KernelError:
            raise

        except Exception as e:
            raise SMTPError("Failed to send email") from e
        
    async def schedule_email(self, email_dict: Dict[str, Any],
                       send_at: str) -> Tuple[bool, Optional[str]]:
        """Schedule an email to be sent at a later time"""
        parsed_dt, error = DateTimeParser.parse_datetime(send_at)
        if error:
            raise ValidationError(error)

        email_dict["send_at"] = parsed_dt
        email_dict["send_status"] = "pending"

        try:
            from src.core.database import get_database

            db = get_database(self.config)
            await db.save_email("sent_emails", email_dict)

            logger.info(f"Email scheduled to be sent at {send_at}")
            return True, None
        
        except DatabaseError:
            raise

        except KernelError:
            raise

        except Exception as e:
            raise DatabaseError("Failed to schedule email") from e
        
    def _generate_uid(self) -> str:
        """Generate a unique identifier for the email"""
        import uuid
        return f"composed-{uuid.uuid4().hex[:12]}"
    

class CompositionWorkflow:
    """Orchestrates the email composition workflow.
    
    This class handles the complete composition flow:
    1. Collect input (recipient, subject, body)
    2. Validate email data
    3. Show preview
    4. Confirm send
    5. Send or schedule
    6. Save to database
    """
    
    def __init__(
        self,
        config: ConfigManager,
        database: Database,
        composer: EmailComposer,
        console: Optional[Console] = None
    ):
        """Initialize workflow with dependencies.
        
        Args:
            config: Configuration manager
            database: Database instance
            composer: Email composer for sending
            console: Optional console for output
        """
        self.config = config
        self.db = database
        self.composer = composer
        
        # Initialize UI components
        self.input_manager = CompositionInputManager()
        self.display = ComposeDisplay(console)

    async def _create_email_data(self, details: dict) -> dict:
        """Create email data structure from input details.
        
        Args:
            details: Dictionary with 'recipient', 'subject', 'body'
            
        Returns:
            Complete email data dictionary
        """
        return self.composer.create_email_dict(
            recipient=details['recipient'],
            subject=details['subject'],
            body=details['body']
        )
    
    async def _validate_email(self, email_data: dict) -> bool:
        """Validate email data structure.
        
        Args:
            email_data: Email data to validate
            
        Returns:
            True if valid
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            EmailValidator.validate_email_dict(email_data)
            return True
        except ValidationError as e:
            self.display.show_error(e.message)
            raise
    
    async def _save_draft(self, email_data: dict) -> bool:
        """Save email as draft.
        
        Args:
            email_data: Email data to save
            
        Returns:
            True if saved successfully
        """
        try:
            await self.db.save_email("drafts", email_data)
            logger.info(f"Draft saved: {email_data.get('uid')}")
            return True
        except Exception as e:
            logger.error(f"Failed to save draft: {e}")
            self.display.show_error("Failed to save draft", show_details=True)
            return False
    
    async def _save_to_sent(self, email_data: dict, status: str = "sent") -> bool:
        """Save email to sent folder.
        
        Args:
            email_data: Email data to save
            status: Send status ('sent' or 'pending')
            
        Returns:
            True if saved successfully
        """
        try:
            email_data['sent_status'] = status
            await self.db.save_email("sent", email_data)
            logger.info(f"Email saved to sent folder: {email_data.get('uid')}")
            return True
        except Exception as e:
            logger.error(f"Failed to save to sent folder: {e}")
            return False
    
    async def _send_immediately(self, email_data: dict) -> bool:
        """Send email immediately via SMTP.
        
        Args:
            email_data: Email data to send
            
        Returns:
            True if sent successfully
        """
        try:
            self.display.show_sending()
            
            # SMTPClient.send_email is synchronous
            success, error = await asyncio.to_thread(
                self.composer.send_email,
                to_email=email_data['recipient'],
                subject=email_data['subject'],
                body=email_data['body']
            )
            
            if success:
                await self._save_to_sent(email_data, status="sent")
                self.display.show_success(email_data['recipient'])
                return True
            else:
                self.display.show_error(error or "Failed to send email")
                return False
                
        except KernelError as e:
            logger.error(f"Send failed: {e.message}")
            self.display.show_error(e.message)
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending email: {e}")
            self.display.show_error("An unexpected error occurred")
            return False
    
    async def _schedule_send(self, email_data: dict, send_time: str) -> bool:
        """Schedule email for later sending.
        
        Args:
            email_data: Email data to schedule
            send_time: Time to send (format: YYYY-MM-DD HH:MM)
            
        Returns:
            True if scheduled successfully
        """
        try:
            success, error = await self.composer.schedule_email(
                email_data,
                send_time
            )
            
            if success:
                self.display.show_scheduled(send_time)
                return True
            else:
                self.display.show_error(error or "Failed to schedule email")
                return False
                
        except KernelError as e:
            logger.error(f"Schedule failed: {e.message}")
            self.display.show_error(e.message)
            return False
        except Exception as e:
            logger.error(f"Unexpected error scheduling email: {e}")
            self.display.show_error("An unexpected error occurred")
            return False
    
    @async_log_call
    async def execute(self) -> bool:
        """Execute the complete composition workflow.
        
        Returns:
            True if email was sent/scheduled successfully, False otherwise
        """
        try:
            # Show header
            self.display.show_header()
            
            # Step 1: Collect input
            details = await self.input_manager.prompt_all()
            if details is None:
                self.display.show_cancelled()
                return False
            
            # Step 2: Create email data structure
            email_data = await self._create_email_data(details)
            
            # Step 3: Validate
            try:
                await self._validate_email(email_data)
            except ValidationError:
                # Error already displayed
                return False
            
            # Step 4: Show preview
            self.display.show_preview(email_data)
            
            # Step 5: Confirm send
            if not await self.input_manager.confirm_action("\nSend this email?"):
                self.display.show_cancelled()
                self.display.show_draft_saved()
                await self._save_draft(email_data)
                return False
            
            # Step 6: Check for scheduled send
            send_time = await self.input_manager.prompt_send_time()
            
            if send_time:
                # Schedule for later
                return await self._schedule_send(email_data, send_time)
            else:
                # Send immediately
                return await self._send_immediately(email_data)
                
        except KeyboardInterrupt:
            self.display.show_cancelled()
            logger.info("Composition cancelled by user (Ctrl+C)")
            return False
        except Exception as e:
            logger.error(f"Unexpected error in composition workflow: {e}")
            self.display.show_error("An unexpected error occurred")
            return False


# Factory function for easy instantiation
async def compose_email(console: Optional[Console] = None) -> bool:
    """Compose and send an email interactively.
    
    Factory function that creates workflow with all dependencies.
    
    Args:
        console: Optional console for output
        
    Returns:
        True if email was sent/scheduled successfully
    """
    try:
        # Initialize dependencies
        config = ConfigManager()
        db = get_database(config)
        composer = EmailComposer(config=config)
        
        # Create and execute workflow
        workflow = CompositionWorkflow(config, db, composer, console)
        return await workflow.execute()
        
    except Exception as e:
        logger.error(f"Failed to initialize composition: {e}")
        display = ComposeDisplay(console)
        display.show_error("Failed to initialize email composer")
        return False


## Test Helper

def create_test_email(subject: str = "Test Email",
                      sender: str = "sender@example.com",
                      recipient: str = "recipient@example.com",
                      body: str = "This is a test email.") -> Dict[str, Any]:
    """Create a test email dictionary"""
    composer = EmailComposer()
    
    return composer.create_email_dict(
        recipient=recipient,
        subject=subject,
        body=body,
        sender=sender
    )