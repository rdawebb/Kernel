"""Main workflow orchestration for email composition."""

from typing import Optional

from rich.console import Console

from src.core.database import EngineManager, EmailRepository
from src.core.email.services.send import EmailSendService
from src.core.email.services.send_factory import EmailSendServiceFactory
from src.core.models.email import FolderName
from src.utils.config import ConfigManager
from src.utils.errors import ValidationError
from src.utils.logging import async_log_call, get_logger
from src.utils.paths import DATABASE_PATH

from .composer import EmailComposer, EmailDraft
from .display import CompositionDisplay
from .input import CompositionInputManager

logger = get_logger(__name__)


class CompositionWorkflow:
    """Orchestrates the email composition workflow."""

    def __init__(
        self,
        send_service: EmailSendService,
        repository: EmailRepository,
        composer: EmailComposer,
        console: Optional[Console] = None,
    ):
        """Initialise workflow with dependencies.

        Args:
            send_service: EmailSendService for sending
            repository: EmailRepository for drafts
            composer: EmailComposer for domain logic
            console: Optional console for output
        """
        self.send_service = send_service
        self.repository = repository
        self.composer = composer

        self.input_manager = CompositionInputManager()
        self.display = CompositionDisplay(console)

    async def _collect_input(self) -> Optional[dict]:
        """Collect email details from user.

        Returns:
            Dictionary with input details or None if cancelled
        """
        self.display.show_header()
        return await self.input_manager.prompt_all()

    async def _create_and_validate_draft(
        self,
        details: dict,
        send_time: Optional[str] = None,
    ) -> Optional[EmailDraft]:
        """Create draft from input and validate.

        Args:
            details: Input details dictionary
            send_time: Optional scheduled send time string

        Returns:
            EmailDraft or None if validation fails
        """
        try:
            send_at = None
            if send_time:
                from src.core.validation import DateTimeParser

                send_at, error = DateTimeParser.parse_datetime(send_time)
                if error:
                    self.display.show_error(error)
                    return None

            draft = self.composer.create_draft(
                recipient=details["recipient"],
                subject=details["subject"],
                body=details["body"],
                send_at=send_at,
            )

            self.composer.validate_draft(draft)

            return draft

        except ValidationError as e:
            self.display.show_error(e.message)
            return None

    async def _save_draft(self, draft: EmailDraft) -> bool:
        """Save draft to database.

        Args:
            draft: EmailDraft to save

        Returns:
            True if saved successfully
        """
        try:
            email = self.composer.draft_to_entity(draft, FolderName.DRAFTS)
            await self.repository.save(email)
            logger.info(f"Draft saved: {email.id.value}")
            return True

        except Exception as e:
            logger.error(f"Failed to save draft: {e}")
            self.display.show_error("Failed to save draft")
            return False

    async def _send_immediately(self, draft: EmailDraft) -> bool:
        """Send email immediately via service.

        Args:
            draft: EmailDraft to send

        Returns:
            True if sent successfully
        """
        self.display.show_sending()

        stats = await self.send_service.send_email(
            to_email=draft.recipient,
            subject=draft.subject,
            body=draft.body,
            cc=draft.cc,
            bcc=draft.bcc,
            save_to_sent=True,
        )

        if stats.success:
            self.display.show_success(draft.recipient)
            return True
        else:
            self.display.show_error(stats.error_message or "Failed to send email")
            return False

    async def _schedule_send(
        self,
        draft: EmailDraft,
        send_time: str,
    ) -> bool:
        """Schedule email for later sending.

        Args:
            draft: EmailDraft to schedule
            send_time: Time to send (format: YYYY-MM-DD HH:MM)

        Returns:
            True if scheduled successfully
        """
        try:
            # Save as pending in sent folder
            email = self.composer.draft_to_entity(draft, FolderName.SENT)
            await self.repository.save(email)

            self.display.show_scheduled(send_time)
            logger.info(f"Email scheduled for {send_time}: {email.id.value}")

            return True

        except Exception as e:
            logger.error(f"Failed to schedule email: {e}")
            self.display.show_error("Failed to schedule email")
            return False

    @async_log_call
    async def execute(self) -> bool:
        """Execute the complete composition workflow.

        Returns:
            True if email was sent/scheduled successfully, False otherwise
        """
        try:
            details = await self._collect_input()
            if details is None:
                self.display.show_cancelled()
                return False

            send_time = await self.input_manager.prompt_send_time()

            draft = await self._create_and_validate_draft(details, send_time)
            if draft is None:
                return False

            email_dict = self.composer.draft_to_email_dict(draft)
            self.display.show_preview(email_dict)

            if not await self.input_manager.confirm_action("\nSend this email?"):
                self.display.show_cancelled()
                await self._save_draft(draft)
                self.display.show_draft_saved()
                return False

            if send_time:
                return await self._schedule_send(draft, send_time)
            else:
                return await self._send_immediately(draft)

        except KeyboardInterrupt:
            self.display.show_cancelled()
            logger.info("Composition cancelled by user (Ctrl+C)")
            return False

        except Exception as e:
            logger.error(f"Unexpected error in composition workflow: {e}")
            self.display.show_error("An unexpected error occurred")
            return False


## Factory function


async def compose_email(console: Optional[Console] = None) -> bool:
    """Compose and send an email interactively.

    Factory function that creates workflow with all dependencies.

    Args:
        console: Optional console for output

    Returns:
        True if email was sent/scheduled successfully
    """
    async with EmailSendServiceFactory.create() as send_service:
        try:
            config = ConfigManager()
            engine_mgr = EngineManager(DATABASE_PATH)

            try:
                repo = EmailRepository(engine_mgr)
                composer = EmailComposer(config.config.account.email)
                workflow = CompositionWorkflow(send_service, repo, composer, console)

                return await workflow.execute()

            finally:
                await engine_mgr.close()

        except Exception as e:
            logger.error(f"Failed to initialise composition: {e}")
            display = CompositionDisplay(console)
            display.show_error("Failed to initialise email composer")
            return False
