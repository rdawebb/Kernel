"""Input collection for email composition using prompt-toolkit."""

from typing import Optional

from prompt_toolkit import PromptSession
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import Style
from prompt_toolkit.validation import ValidationError, Validator

from src.utils.logging import async_log_call, get_logger

logger = get_logger(__name__)


class EmailAddressValidator(Validator):
    """Validator for email addresses using email-validator library."""
    
    def __init__(self):
        """Initialize validator with lazy-loaded email-validator."""
        self._validator = None
        self._error_class = None
    
    def _get_validator(self):
        """Lazy load email-validator library."""
        if self._validator is None:
            try:
                from email_validator import validate_email, EmailNotValidError
                self._validator = validate_email
                self._error_class = EmailNotValidError
            except ImportError:
                logger.warning("email-validator not installed, using basic validation")
                import re
                # Fallback to regex
                self._pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
        
        return self._validator, self._error_class
    
    def validate(self, document):
        """Validate email address."""
        email = document.text.strip()
        
        if not email:
            raise ValidationError(
                message="Email address is required",
                cursor_position=len(document.text)
            )
        
        validator_fn, error_class = self._get_validator()
        
        if validator_fn:
            try:
                # Don't check deliverability to avoid DNS lookups
                validator_fn(email, check_deliverability=False)
            except error_class as e:
                raise ValidationError(
                    message=str(e),
                    cursor_position=len(document.text)
                )
        else:
            # Fallback regex validation
            if not self._pattern.match(email):
                raise ValidationError(
                    message="Invalid email address format",
                    cursor_position=len(document.text)
                )


class CompositionInputManager:
    """Manages input collection for email composition."""
    
    def __init__(self):
        """Initialize input manager with prompt-toolkit session."""
        self.session = PromptSession()
        self.style = Style.from_dict({
            'prompt': 'cyan bold',
            'bottom-toolbar': 'bg:#333333 #ffffff',
            'validation-toolbar': 'bg:#aa0000 #ffffff',
        })
    
    def _create_body_key_bindings(self) -> KeyBindings:
        """Create key bindings for body input (Ctrl+D to finish)."""
        kb = KeyBindings()
        
        @kb.add('c-d')
        def _(event):
            """Ctrl+D to finish input."""
            event.current_buffer.validate_and_handle()
        
        return kb
    
    @async_log_call
    async def prompt_recipient(self) -> Optional[str]:
        """Prompt for recipient email address with validation.
        
        Returns:
            Email address or None if cancelled
        """
        try:
            result = await self.session.prompt_async(
                'To: ',
                validator=EmailAddressValidator(),
                validate_while_typing=False,
                style=self.style,
                bottom_toolbar="Enter recipient email address (or Ctrl+C to cancel)"
            )
            return result.strip() if result else None
            
        except KeyboardInterrupt:
            logger.info("Recipient input cancelled by user")
            return None
        except Exception as e:
            logger.error(f"Error during recipient input: {e}")
            return None
    
    @async_log_call
    async def prompt_subject(self) -> Optional[str]:
        """Prompt for email subject.
        
        Returns:
            Subject string or None if cancelled
        """
        try:
            result = await self.session.prompt_async(
                'Subject: ',
                style=self.style,
                bottom_toolbar="Enter email subject (or Ctrl+C to cancel)"
            )
            
            # Allow empty subject with confirmation
            if not result or not result.strip():
                confirm = await self.session.prompt_async(
                    'Subject is empty. Continue anyway? (y/n): ',
                    style=self.style
                )
                if confirm.lower() not in ('y', 'yes'):
                    return None
                return "(No subject)"
            
            return result.strip()
            
        except KeyboardInterrupt:
            logger.info("Subject input cancelled by user")
            return None
        except Exception as e:
            logger.error(f"Error during subject input: {e}")
            return None
    
    @async_log_call
    async def prompt_body(self) -> Optional[str]:
        """Prompt for email body with multi-line support.
        
        Uses Ctrl+D to finish input (standard Unix convention).
        
        Returns:
            Body text or None if cancelled
        """
        try:
            print("\n[Body - Press Ctrl+D when finished, Ctrl+C to cancel]\n")
            
            result = await self.session.prompt_async(
                '',  # No prompt prefix for body
                multiline=True,
                key_bindings=self._create_body_key_bindings(),
                style=self.style,
                bottom_toolbar="Press Ctrl+D to finish, Ctrl+C to cancel"
            )
            
            body = result.strip() if result else ""
            
            # Allow empty body with confirmation
            if not body:
                print()  # Newline for better formatting
                confirm = await self.session.prompt_async(
                    'Body is empty. Continue anyway? (y/n): ',
                    style=self.style
                )
                if confirm.lower() not in ('y', 'yes'):
                    return None
            
            return body
            
        except KeyboardInterrupt:
            logger.info("Body input cancelled by user")
            return None
        except EOFError:
            # Ctrl+D pressed - this is expected for finishing
            logger.debug("Body input completed with Ctrl+D")
            return ""
        except Exception as e:
            logger.error(f"Error during body input: {e}")
            return None
    
    @async_log_call
    async def prompt_send_time(self) -> Optional[str]:
        """Prompt for optional scheduled send time.
        
        Returns:
            ISO format datetime string, empty string for immediate, or None if cancelled
        """
        try:
            result = await self.session.prompt_async(
                '\nSchedule send time (or press Enter to send now): ',
                style=self.style,
                bottom_toolbar="Format: YYYY-MM-DD HH:MM, 'tomorrow 9am', 'in 2 hours', etc."
            )
            
            if not result or not result.strip():
                return ""  # Send immediately
            
            # Parse and validate datetime
            from src.core.email_handling import DateTimeParser
            
            parsed_dt, error = DateTimeParser.parse_datetime(result.strip())
            if error:
                print(f"\nError: {error}")
                
                retry = await self.session.prompt_async(
                    'Try again? (y/n): ',
                    style=self.style
                )
                if retry.lower() in ('y', 'yes'):
                    return await self.prompt_send_time()  # Recursive retry
                return ""  # Send immediately on decline
            
            return parsed_dt.strftime("%Y-%m-%d %H:%M")
            
        except KeyboardInterrupt:
            logger.info("Send time input cancelled - will send immediately")
            return ""  # Default to immediate send
        except Exception as e:
            logger.error(f"Error during send time input: {e}")
            return ""
    
    @async_log_call
    async def confirm_action(self, message: str) -> bool:
        """Prompt for yes/no confirmation.
        
        Args:
            message: Confirmation message
            
        Returns:
            True if confirmed, False otherwise
        """
        try:
            result = await self.session.prompt_async(
                f'{message} (y/n): ',
                style=self.style
            )
            return result.strip().lower() in ('y', 'yes')
            
        except KeyboardInterrupt:
            return False
        except Exception as e:
            logger.error(f"Error during confirmation: {e}")
            return False
    
    async def prompt_all(self) -> Optional[dict]:
        """Prompt for all email details in sequence.
        
        Returns:
            Dictionary with 'recipient', 'subject', 'body' or None if cancelled
        """
        print("\n[bold cyan]Compose New Email[/bold cyan]\n")
        
        # Recipient
        recipient = await self.prompt_recipient()
        if recipient is None:
            return None
        
        # Subject
        subject = await self.prompt_subject()
        if subject is None:
            return None
        
        # Body
        body = await self.prompt_body()
        if body is None:
            return None
        
        return {
            'recipient': recipient,
            'subject': subject,
            'body': body
        }