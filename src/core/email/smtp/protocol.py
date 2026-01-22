"""Native Go-backed low-level SMTP command interface."""

import base64
from email.mime.multipart import MIMEMultipart
from typing import List, Optional, cast

from src.native_bridge import NativeBridge, get_bridge
from src.utils.logging import async_log_call, get_logger

logger = get_logger(__name__)


class SMTPProtocol:
    """Native Go-backed SMTP protocol implementation."""

    def __init__(self, connection):
        """Initialise native SMTP protocol.

        Args:
            connection: SMTPConnection instance (for compatibility)
        """
        self.connection = connection
        self._handle: Optional[int] = None
        self._bridge = None

    def _get_bridge(self) -> NativeBridge:
        """Type hint for bridge."""
        return cast(NativeBridge, self._bridge)

    async def _ensure_bridge(self):
        """Ensure bridge is connected."""
        if self._bridge is None:
            self._bridge = await get_bridge()

    async def _ensure_connected(self):
        """Ensure SMTP connection is established."""
        if self._handle is None:
            await self._ensure_bridge()

            config = self.connection.config_manager.config.account

            # Get credentials
            await self.connection.credential_manager.validate_and_prompt()
            await self.connection.keystore.initialise()
            password = await self.connection.keystore.retrieve(config.username)

            if not password:
                from src.utils.errors import MissingCredentialsError

                raise MissingCredentialsError("Password not found")

            # Connect via native backend
            result = await self._get_bridge().call(
                "smtp",
                "connect",
                {
                    "host": config.smtp_server,
                    "port": config.smtp_port,
                    "username": config.username,
                    "password": password,
                },
            )

            self._handle = result["handle"]
            logger.info(f"Connected to SMTP via native backend (handle={self._handle})")

    @async_log_call
    async def send_message(self, message: MIMEMultipart, recipients: List[str]) -> bool:
        """Send a MIME message to recipients.

        Args:
            message: Constructed MIME message
            recipients: List of recipient email addresses

        Returns:
            True if sent successfully
        """
        await self._ensure_connected()

        try:
            # Get sender from message
            sender = message["From"]

            # Convert message to bytes and base64 encode
            message_bytes = message.as_bytes()
            message_b64 = base64.b64encode(message_bytes).decode("utf-8")

            await self._get_bridge().call(
                "smtp",
                "send",
                {
                    "handle": self._handle,
                    "from": sender,
                    "to": recipients,
                    "message_b64": message_b64,
                },
            )

            logger.info(
                f"Email sent via native backend to {len(recipients)} recipients"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False

    @async_log_call
    async def noop(self) -> bool:
        """Send NOOP command to keep connection alive.

        Returns:
            True if successful
        """
        await self._ensure_connected()

        try:
            await self._get_bridge().call("smtp", "noop", {"handle": self._handle})
            return True
        except Exception as e:
            logger.debug(f"NOOP failed: {e}")
            return False
