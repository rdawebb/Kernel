"""Email send service - orchestrates email sending with retry logic."""

import asyncio
import time
from dataclasses import dataclass
from typing import List, Optional

from src.core.database import EmailRepository
from src.core.email.smtp.client import SMTPClient
from src.core.email.smtp.constants import TransientErrors
from src.core.email.smtp.protocol import SMTPProtocol
from src.core.models.email import Email, EmailAddress, EmailId, FolderName
from src.utils.logging import async_log_call, get_logger

logger = get_logger(__name__)


@dataclass
class SendStats:
    """Statistics for email send operations."""

    attempts: int = 0
    send_duration: float = 0.0
    success: bool = False
    error_message: Optional[str] = None


class EmailSendService:
    """Service for sending emails with retry logic and persistence."""

    def __init__(
        self,
        protocol: SMTPProtocol,
        repository: EmailRepository,
        sender_email: str,
        max_retries: int = 3,
    ):
        """Initialise email send service.

        Args:
            protocol: SMTPProtocol instance for SMTP operations
            repository: EmailRepository for database operations
            sender_email: Sender email address
            max_retries: Maximum retry attempts for transient failures
        """
        self._protocol = protocol
        self._repository = repository
        self._smtp_client = SMTPClient(protocol, sender_email)
        self.max_retries = max_retries

    @property
    def client(self) -> SMTPClient:
        """Get SMTP client for direct email operations.

        Returns:
            SMTPClient instance
        """
        return self._smtp_client

    def _is_transient_error(self, error: Exception) -> bool:
        """Check if error is transient and retry-worthy.

        Args:
            error: Exception to check

        Returns:
            True if transient, False otherwise
        """
        import aiosmtplib

        if isinstance(error, aiosmtplib.SMTPConnectResponseError):
            return TransientErrors.is_transient(error.code)

        if isinstance(
            error,
            (
                aiosmtplib.SMTPServerDisconnected,
                ConnectionError,
                asyncio.TimeoutError,
            ),
        ):
            return True

        return False

    @async_log_call
    async def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        save_to_sent: bool = True,
    ) -> SendStats:
        """Send email with automatic retry logic.

        Args:
            to_email: Recipient email address
            subject: Email subject
            body: Email body text
            cc: Optional CC recipients
            bcc: Optional BCC recipients
            save_to_sent: Whether to save to sent folder

        Returns:
            SendStats with operation statistics
        """
        stats = SendStats()
        start_time = time.time()
        last_error = None

        logger.info(
            "Sending email", extra={"recipient": to_email, "subject": subject[:50]}
        )

        while stats.attempts <= self.max_retries:
            try:
                success = await self._smtp_client.send_text_email(
                    to_email, subject, body, cc, bcc
                )

                stats.send_duration = time.time() - start_time
                stats.attempts += 1

                if success:
                    stats.success = True

                    if save_to_sent:
                        await self._save_to_sent_folder(
                            to_email, subject, body, cc, bcc
                        )

                    logger.info(
                        "Email sent successfully",
                        extra={
                            "recipient": to_email,
                            "duration": round(stats.send_duration, 2),
                            "attempts": stats.attempts,
                        },
                    )

                    return stats

                # If send returned False, treat as non-retryable error
                stats.send_duration = time.time() - start_time
                stats.error_message = "Send operation failed (returned False)"
                logger.error(
                    "Email send failed",
                    extra={
                        "recipient": to_email,
                        "attempts": stats.attempts,
                        "error": stats.error_message,
                    },
                )
                return stats

            except Exception as e:
                last_error = e
                stats.attempts += 1

                if self._is_transient_error(e) and stats.attempts <= self.max_retries:
                    delay = 2 ** (stats.attempts - 1)
                    logger.warning(
                        "Transient SMTP error, retrying",
                        extra={
                            "attempt": stats.attempts,
                            "max_retries": self.max_retries,
                            "retry_delay": delay,
                            "error": str(e),
                        },
                    )
                    await asyncio.sleep(delay)
                    continue

                # Non-transient error or max retries exceeded
                break

        # Failed after all retries
        stats.send_duration = time.time() - start_time
        stats.success = False
        stats.error_message = str(last_error) if last_error else "Unknown error"

        logger.error(
            "Failed to send email after retries",
            extra={
                "recipient": to_email,
                "attempts": stats.attempts,
                "duration": round(stats.send_duration, 2),
                "error": stats.error_message,
            },
        )

        return stats

    async def _save_to_sent_folder(
        self,
        to_email: str,
        subject: str,
        body: str,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
    ) -> None:
        """Save sent email to sent folder.

        Args:
            to_email: Recipient email address
            subject: Email subject
            body: Email body text
            cc: Optional CC recipients
            bcc: Optional BCC recipients
        """
        try:
            import uuid
            from datetime import datetime

            # Create Email domain object
            uid = f"sent-{uuid.uuid4().hex[:12]}"
            sender = EmailAddress(self._smtp_client.sender_email)
            recipients = [EmailAddress(to_email)]

            if cc:
                recipients.extend(EmailAddress(addr) for addr in cc)

            email = Email(
                id=EmailId(uid),
                subject=subject,
                sender=sender,
                recipients=recipients,
                body=body,
                received_at=datetime.now(),
                folder=FolderName.SENT,
                is_read=True,  # Sent emails are "read"
            )

            await self._repository.save(email)
            logger.debug(f"Saved sent email to database: {uid}")

        except Exception as e:
            logger.error(f"Failed to save sent email: {e}")
            # Don't fail the send operation if saving fails
