"""SMTP protocol operations - low-level SMTP command interface."""

import asyncio
from email.mime.multipart import MIMEMultipart
from typing import List

from .connection import SMTPConnection
from .constants import Timeouts
from src.utils.logging import async_log_call, get_logger

logger = get_logger(__name__)


class SMTPProtocol:
    """Low-level SMTP protocol operations & orchestration."""

    def __init__(self, connection: SMTPConnection):
        """Initialise SMTP protocol handler.

        Args:
            connection: SMTPConnection instance for connection management
        """
        self.connection = connection

    @async_log_call
    async def send_message(
        self,
        message: MIMEMultipart,
        recipients: List[str],
    ) -> bool:
        """Send a MIME message to recipients.

        Args:
            message: Constructed MIME message
            recipients: List of recipient email addresses

        Returns:
            True if sent successfully, False otherwise
        """
        try:
            client = await self.connection.get_client()

            await asyncio.wait_for(
                client.send_message(message, recipients=recipients),
                timeout=Timeouts.SMTP_SEND,
            )

            return True

        except asyncio.TimeoutError as e:
            logger.error(f"SMTP send timeout: {e}")
            return False

        except Exception as e:
            logger.error(f"SMTP send error: {e}")
            return False

    @async_log_call
    async def verify_recipient(self, email: str) -> bool:
        """Verify if a recipient address is valid (VRFY command).

        Args:
            email: Email address to verify

        Returns:
            True if valid, False otherwise

        Note:
            Many servers disable VRFY for security, so this may not work.
        """
        try:
            client = await self.connection.get_client()

            code, message = await asyncio.wait_for(
                client.vrfy(email),
                timeout=Timeouts.SMTP_VRFY,
            )

            return code == 250

        except Exception as e:
            logger.debug(f"VRFY not supported or failed: {e}")
            return True  # Assume valid if VRFY not supported

    @async_log_call
    async def noop(self) -> bool:
        """Send NOOP command to keep connection alive.

        Returns:
            True if successful, False otherwise
        """
        try:
            client = await self.connection.get_client()

            await asyncio.wait_for(
                client.noop(),
                timeout=Timeouts.SMTP_NOOP,
            )

            return True

        except Exception as e:
            logger.debug(f"NOOP failed: {e}")
            return False
