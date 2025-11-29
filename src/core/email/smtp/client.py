"""SMTP client for sending emails via an SMTP server"""

## TODO: add support for HTML emails and attachments

import asyncio
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List, Optional

import aiosmtplib

from src.core.email.constants import Timeouts
from src.utils.errors import NetworkTimeoutError, SMTPError
from src.utils.logging import get_logger

from .connection import SMTPConnection

logger = get_logger(__name__)


TRANSIENT_ERRORS = [
    421,  # Service not available, closing transmission channel
    450,  # Mailbox unavailable (e.g. busy)
    451,  # Local error in processing
    452,  # Insufficient system storage
]


class SMTPClient:
    """Asynchronous SMTP client for email operations."""

    def __init__(self, config, max_retries: int = 3):
        """Initialize SMTP client with configuration.

        Args:
            config: SMTP configuration object
            max_retries: Maximum number of retry attempts for sending emails
        """
        self.config = config
        self._connection = SMTPConnection(config)
        self.max_retries = max_retries

    def get_connection_stats(self) -> dict:
        """Get current SMTP connection statistics.

        Returns:
            Dictionary of connection statistics
        """
        stats = self._connection.get_stats()
        return {
            "connections_created": stats.connections_created,
            "reconnections": stats.reconnections,
            "emails_sent": stats.emails_sent,
            "send_failures": stats.send_failures,
            "avg_send_time": round(stats.total_send_time / stats.emails_sent, 2)
            if stats.emails_sent > 0
            else 0,
        }

    def _is_transient_error(self, error: Exception) -> bool:
        """Check if an error is transient and worth retrying.

        Args:
            error: Exception instance to check

        Returns:
            True if error is transient, False otherwise
        """
        if isinstance(error, aiosmtplib.SMTPConnectResponseError):
            return error.code in TRANSIENT_ERRORS

        if isinstance(error, (aiosmtplib.SMTPServerDisconnected, ConnectionError)):
            return True

        return False

    async def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
    ) -> bool:
        """Send an email via SMTP with retry logic for transient errors.

        Args:
            to_email: Recipient email address
            subject: Email subject line
            body: Email body content
            cc: Optional list of CC email addresses
            bcc: Optional list of BCC email addresses

        Returns:
            True if email sent successfully, False otherwise

        Raises:
            NetworkTimeoutError: If sending times out
            SMTPError: If sending fails after retries
        """
        send_start = time.time()
        attempt = 0
        last_error = None

        logger.info(
            "Sending email", extra={"recipient": to_email, "subject": subject[:50]}
        )

        while attempt <= self.max_retries:
            try:
                client = await self._connection._ensure_connection()

                msg = MIMEMultipart()
                msg["From"] = self.config.config.account.email
                msg["To"] = to_email
                msg["Subject"] = subject

                if cc:
                    msg["Cc"] = ", ".join(cc) if isinstance(cc, list) else cc
                if bcc:
                    msg["Bcc"] = ", ".join(bcc) if isinstance(bcc, list) else bcc

                msg.attach(MIMEText(body, "plain"))

                recipients = [to_email]
                if cc:
                    recipients.extend(cc if isinstance(cc, list) else [cc])
                if bcc:
                    recipients.extend(bcc if isinstance(bcc, list) else [bcc])

                await asyncio.wait_for(
                    client.send_message(msg, recipients=recipients),
                    timeout=Timeouts.SMTP_SEND,
                )
                send_duration = time.time() - send_start
                self._connection._stats.emails_sent += 1

                logger.info(
                    "Email sent successfully",
                    extra={
                        "recipient": to_email,
                        "duration_seconds": round(send_duration, 2),
                        "attempts": attempt + 1,
                    },
                )
                return True

            except asyncio.TimeoutError as e:
                self._connection.get_stats().record_send(time.time() - send_start)
                raise NetworkTimeoutError(
                    "SMTP send operation timed out", details={"recipient": to_email}
                ) from e

            except Exception as e:
                last_error = e
                attempt += 1

                if self._is_transient_error(e) and attempt <= self.max_retries:
                    delay = 2 ** (attempt - 1)
                    logger.warning(
                        "Transient SMTP error, retrying",
                        extra={
                            "attempt": attempt,
                            "max_retries": self.max_retries,
                            "retry_delay": delay,
                        },
                    )

                    await asyncio.sleep(delay)
                    await self._connection.close_connection()
                    continue

                send_duration = time.time() - send_start
                self._connection.get_stats().record_send(send_duration, success=False)

                logger.error(
                    "Failed to send email",
                    extra={
                        "recipient": to_email,
                        "attempts": attempt,
                        "duration_seconds": round(send_duration, 2),
                        "error": str(last_error),
                    },
                )

                error_msg = f"Failed to send email after {attempt} attempt(s): {str(last_error)}"
                raise SMTPError(
                    error_msg, details={"recipient": to_email, "attempts": attempt}
                ) from last_error

        return False


## SMTP Client Factory


def get_smtp_client(config) -> SMTPClient:
    """Factory function to get an SMTPClient instance."""
    return SMTPClient(config)
