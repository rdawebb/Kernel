"""SMTP connection management"""

import asyncio
import time
from dataclasses import dataclass
from typing import Optional

import aiosmtplib

from security.credential_manager import CredentialManager
from security.key_store import get_keystore
from src.core.email.constants import Timeouts
from src.utils.config import ConfigManager
from src.utils.errors import (
    AuthenticationError,
    MissingCredentialsError,
    NetworkError,
    NetworkTimeoutError,
)
from src.utils.logging import async_log_call, get_logger

logger = get_logger(__name__)


@dataclass
class SMTPConnectionStats:
    """Statistics for SMTP connection usage."""

    connections_created: int = 0
    reconnections: int = 0
    health_checks_passed: int = 0
    health_checks_failed: int = 0
    emails_sent: int = 0
    send_failures: int = 0
    total_send_time: float = 0.0

    def record_send(self, duration: float, success: bool) -> None:
        """Record an email send attempt.

        Args:
            duration: Time taken to send the email
            success: Whether the send was successful
        """
        self.total_send_time += duration
        if success:
            self.emails_sent += 1
        else:
            self.send_failures += 1


class SMTPConnection:
    """Manages an SMTP connection lifecyle."""

    def __init__(self, config: ConfigManager) -> None:
        """Initialises SMTP connection with configuration.

        Args:
            config: Configuration manager instance
        """
        self.config = config
        self.auth = CredentialManager(config)
        self.keystore = get_keystore()
        self._client: Optional[aiosmtplib.SMTP] = None
        self._lock = asyncio.Lock()
        self._connection_created_at = None
        self._connection_ttl = getattr(
            self.config.config.account,
            "smtp_connection_ttl",
            1800,  # 30 minutes
        )
        self._stats = SMTPConnectionStats()

    def get_stats(self) -> SMTPConnectionStats:
        """Returns current connection statistics.

        Returns:
             SMTPConnectionStats instance
        """
        return self._stats

    def _is_connection_expired(self) -> bool:
        """Checks if the current connection has expired based on TTL.

        Returns:
             True if connection is expired, False otherwise
        """
        if self._client is None or self._connection_created_at is None:
            return True

        elapsed = time.time() - self._connection_created_at

        return elapsed > self._connection_ttl

    async def _ensure_connection(self) -> aiosmtplib.SMTP:
        """Ensures there is an active SMTP connection.

        Returns:
             Active aiosmtplib.SMTP client instance

        Raises:
            asyncio.TimeoutError: If connection times out
        """
        async with self._lock:
            if self._client is None or self._is_connection_expired():
                if self._client is not None:
                    logger.info(
                        "SMTP connection expired, reconnecting",
                        extra={
                            "age_seconds": time.time() - self._connection_created_at,
                            "ttl": self._connection_ttl,
                            "emails_sent": self._stats.emails_sent,
                        },
                    )
                    self._stats.reconnections += 1

                    try:
                        await self._client.quit()

                    except Exception:
                        pass

                self._client = await self._connect()
                self._connection_created_at = time.time()
                self._stats.connections_created += 1
            else:
                try:
                    await asyncio.wait_for(
                        self._client.noop(), timeout=Timeouts.SMTP_NOOP
                    )
                    self._stats.health_checks_passed += 1
                    logger.debug(
                        "SMTP connection health check passed",
                        extra={"health_checks": self._stats.health_checks_passed},
                    )

                except (asyncio.TimeoutError, Exception) as e:
                    self._stats.health_checks_failed += 1
                    self._stats.reconnections += 1
                    logger.warning(
                        "SMTP connection lost, reconnecting", extra={"error": str(e)}
                    )

                    try:
                        await self._client.quit()

                    except Exception:
                        pass

                    self._client = await self._connect()
                    self._connection_created_at = time.time()

        return self._client

    async def _connect(self) -> aiosmtplib.SMTP:
        """Establishes a new SMTP connection.

        Returns:
            Connected aiosmtplib.SMTP client instance

        Raises:
            MissingCredentialsError: If credentials are missing
            AuthenticationError: If authentication fails
            NetworkTimeoutError: If connection times out
            NetworkError: If other network errors occur
        """
        config = self.config.config.account
        start_time = time.time()

        try:
            await self.auth.validate_and_prompt()

            password = self.keystore.retrieve(config.username)
            if not password:
                raise MissingCredentialsError("No SMTP password found in keystore.")

            logger.info(
                "Connecting to SMTP server",
                extra={"server": config.smtp_server, "port": config.smtp_port},
            )

            client = aiosmtplib.SMTP(
                hostname=config.smtp_server,
                port=config.smtp_port,
                timeout=30,
                use_tls=True,
            )

            await asyncio.wait_for(client.connect(), timeout=Timeouts.SMTP_CONNECT)

            await asyncio.wait_for(
                client.login(config.username, password), timeout=Timeouts.SMTP_LOGIN
            )

            connect_duration = time.time() - start_time
            logger.info(
                "Connected to SMTP server",
                extra={
                    "server": config.smtp_server,
                    "username": config.username,
                    "duration_seconds": round(connect_duration, 2),
                },
            )
            return client

        except asyncio.TimeoutError as e:
            logger.error(
                f"SMTP connection timed out after {time.time() - start_time:.2f}s"
            )
            raise NetworkTimeoutError(
                "SMTP connection timed out", details={"server": config.smtp_server}
            ) from e

        except aiosmtplib.SMTPAuthenticationError:
            logger.warning(
                "SMTP authentication failed",
                extra={"server": config.smtp_server, "username": config.username},
            )
            await self.auth.handle_auth_failure()
            logger.info("Retrying SMTP with new credentials...")
            return await self._connect()

        except (MissingCredentialsError, AuthenticationError):
            raise

        except Exception as e:
            raise NetworkError(
                f"Failed to connect to SMTP server: {str(e)}",
                details={"server": config.smtp_server, "error": str(e)},
            ) from e

    @async_log_call
    async def close_connection(self) -> None:
        """Closes the SMTP connection."""
        async with self._lock:
            if self._client:
                try:
                    await asyncio.wait_for(
                        self._client.quit(), timeout=Timeouts.SMTP_QUIT
                    )

                    logger.debug("SMTP connection closed.")

                except Exception as e:
                    logger.debug(f"Error closing SMTP connection: {str(e)}")

                finally:
                    self._client = None
                    self._connection_created_at = None

    ## Context Manager Helpers

    async def __aenter__(self):
        """Enter async context manager."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context manager."""
        await self.close_connection()
