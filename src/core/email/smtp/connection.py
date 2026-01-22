"""SMTP connection management - handles connection setup, health, and cleanup."""

import asyncio
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Optional

import aiosmtplib

from src.security.credential_manager import CredentialManager
from src.security.key_store import get_keystore
from src.utils.config import ConfigManager
from src.utils.errors import (
    AuthenticationError,
    MissingCredentialsError,
    NetworkError,
    NetworkTimeoutError,
    SMTPError,
)
from src.utils.logging import async_log_call, get_logger

from .constants import SMTPPorts, Timeouts

logger = get_logger(__name__)


@dataclass
class SMTPConnectionStats:
    """Tracks SMTP connection metrics."""

    connections_created: int = 0
    reconnections: int = 0
    health_checks_passed: int = 0
    health_checks_failed: int = 0
    emails_sent: int = 0
    send_failures: int = 0
    total_send_time: float = 0.0
    last_operation_time: Optional[float] = None

    def record_send(self, duration: float, success: bool = True) -> None:
        """Record an email send attempt.

        Args:
            duration: Time taken to send the email in seconds
            success: Whether the send was successful
        """
        self.total_send_time += duration
        self.last_operation_time = time.time()

        if success:
            self.emails_sent += 1
        else:
            self.send_failures += 1

    @property
    def avg_send_time(self) -> float:
        """Calculate average send time.

        Returns:
            Average send time in seconds, or 0.0 if no emails sent
        """
        if self.emails_sent == 0:
            return 0.0
        return self.total_send_time / self.emails_sent

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage.

        Returns:
            Success rate (0-100), or 0.0 if no attempts
        """
        total = self.emails_sent + self.send_failures
        if total == 0:
            return 0.0
        return (self.emails_sent / total) * 100


class SMTPConnection:
    """Manages an SMTP connection lifecycle with automatic health checks and TTL."""

    def __init__(self, config_manager: ConfigManager):
        """initialise SMTP connection with config manager.

        Args:
            config_manager: Configuration manager instance
        """
        self.config_manager = config_manager
        self.credential_manager = CredentialManager(config_manager)
        self.keystore = get_keystore()
        self._client: Optional[aiosmtplib.SMTP] = None
        self._lock = asyncio.Lock()
        self._connection_created_at: Optional[float] = None
        self._connection_ttl = getattr(
            self.config_manager.config.account,
            "smtp_connection_ttl",
            1800,  # 30 minutes default
        )
        self._stats = SMTPConnectionStats()

    async def get_client(self) -> aiosmtplib.SMTP:
        """Get active SMTP client instance.

        Returns:
            Active aiosmtplib.SMTP client instance

        Raises:
            asyncio.TimeoutError: If connection times out
            AuthenticationError: If credentials are invalid
            NetworkError: If there is a network issue
            SMTPError: If other SMTP errors occur
        """
        return await self._ensure_connection()

    @asynccontextmanager
    async def with_connection(self):
        """Context manager for SMTP connection lifecycle.

        Yields:
            Active aiosmtplib.SMTP client instance

        Example:
            >>> async with connection.with_connection() as client:
            ...     await client.send_message(msg)
        """
        client = await self.get_client()
        try:
            yield client
        finally:
            pass  # Connection is managed by the connection manager

    def get_stats(self) -> SMTPConnectionStats:
        """Get current connection statistics.

        Returns:
            SMTPConnectionStats object with current metrics
        """
        return self._stats

    def _is_connection_expired(self) -> bool:
        """Check if the SMTP connection has expired based on TTL.

        Returns:
            True if connection is expired, False otherwise
        """
        if self._client is None or self._connection_created_at is None:
            return True

        elapsed = time.time() - self._connection_created_at
        return elapsed > self._connection_ttl

    async def _ensure_connection(self) -> aiosmtplib.SMTP:
        """Ensure an active SMTP connection exists.

        Creates new connection if:
        - No connection exists
        - Connection has expired (based on TTL)
        - Health check fails

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
                            "age_seconds": (
                                time.time() - self._connection_created_at
                                if self._connection_created_at is not None
                                else None
                            ),
                            "ttl": self._connection_ttl,
                            "emails_sent": self._stats.emails_sent,
                        },
                    )
                    self._stats.reconnections += 1

                    try:
                        await asyncio.wait_for(
                            self._client.quit(), timeout=Timeouts.SMTP_QUIT
                        )
                    except Exception:
                        pass  # Ignore errors when closing expired connection

                self._client = await self._connect()
                self._connection_created_at = time.time()
                self._stats.connections_created += 1

            else:
                # Connection exists and not expired - perform health check
                try:
                    await asyncio.wait_for(
                        self._client.noop(), timeout=Timeouts.SMTP_NOOP
                    )
                    self._stats.health_checks_passed += 1
                    logger.debug(
                        "SMTP connection health check passed",
                        extra={
                            "age_seconds": (
                                time.time() - self._connection_created_at
                                if self._connection_created_at is not None
                                else None
                            ),
                            "health_checks": self._stats.health_checks_passed,
                        },
                    )

                except (asyncio.TimeoutError, Exception) as e:
                    self._stats.health_checks_failed += 1
                    self._stats.reconnections += 1
                    logger.warning(
                        "SMTP connection lost, reconnecting",
                        extra={
                            "error": str(e),
                            "age_seconds": (
                                time.time() - self._connection_created_at
                                if self._connection_created_at is not None
                                else None
                            ),
                            "failed_health_checks": self._stats.health_checks_failed,
                        },
                    )

                    try:
                        await asyncio.wait_for(
                            self._client.quit(), timeout=Timeouts.SMTP_QUIT
                        )
                    except Exception:
                        pass  # Ignore errors when closing failed connection

                    self._client = await self._connect()
                    self._connection_created_at = time.time()

        return self._client

    async def _connect(self) -> aiosmtplib.SMTP:
        """Connect to SMTP server asynchronously.

        Returns:
            Connected aiosmtplib.SMTP client instance

        Raises:
            MissingCredentialsError: If credentials are missing
            AuthenticationError: If authentication fails
            NetworkTimeoutError: If connection times out
            NetworkError: If other network errors occur
            SMTPError: If SMTP errors occur
        """
        config = self.config_manager.config.account
        start_time = time.time()

        try:
            await self.credential_manager.validate_and_prompt()
            await self.keystore.initialise()

            password = await self.keystore.retrieve(config.username)
            if not password:
                raise MissingCredentialsError("Password not found after validation")

            logger.info(
                "Connecting to SMTP server",
                extra={
                    "server": config.smtp_server,
                    "port": config.smtp_port,
                    "ssl_mode": "implicit"
                    if config.smtp_port == SMTPPorts.SUBMISSION_SSL
                    else "starttls",
                },
            )

            # Create client with appropriate SSL mode
            if SMTPPorts.is_implicit_ssl(config.smtp_port):
                # Implicit SSL (port 465)
                client = aiosmtplib.SMTP(
                    hostname=config.smtp_server,
                    port=config.smtp_port,
                    timeout=Timeouts.SMTP_CONNECT,
                    use_tls=True,
                )
            else:
                # STARTTLS (port 587 or 25)
                client = aiosmtplib.SMTP(
                    hostname=config.smtp_server,
                    port=config.smtp_port,
                    timeout=Timeouts.SMTP_CONNECT,
                    use_tls=False,
                )

            # Connect to server
            await asyncio.wait_for(client.connect(), timeout=Timeouts.SMTP_CONNECT)

            # Perform STARTTLS if not using implicit SSL
            if SMTPPorts.requires_starttls(config.smtp_port):
                await asyncio.wait_for(
                    client.starttls(), timeout=Timeouts.SMTP_STARTTLS
                )

            # Authenticate
            await asyncio.wait_for(
                client.login(config.username, password),
                timeout=Timeouts.SMTP_LOGIN,
            )

            connect_duration = time.time() - start_time
            logger.info(
                "SMTP connection established",
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
                "SMTP connection timeout",
                details={"server": config.smtp_server},
            ) from e

        except aiosmtplib.SMTPAuthenticationError as e:
            logger.warning(
                "SMTP authentication failed",
                extra={
                    "server": config.smtp_server,
                    "username": config.username,
                },
            )
            # Clear cached password so user gets prompted
            await self.keystore.delete(config.username)
            raise AuthenticationError(
                "SMTP authentication failed. Please verify your credentials.",
                details={
                    "server": config.smtp_server,
                    "username": config.username,
                },
            ) from e

        except aiosmtplib.SMTPConnectError as e:
            logger.error(
                "Failed to connect to SMTP server",
                extra={
                    "server": config.smtp_server,
                    "port": config.smtp_port,
                    "error": str(e),
                },
            )
            raise NetworkError(
                f"Failed to connect to SMTP server: {str(e)}",
                details={
                    "server": config.smtp_server,
                    "port": config.smtp_port,
                },
            ) from e

        except aiosmtplib.SMTPException as e:
            logger.error(f"SMTP error during connection: {e}")
            raise SMTPError(
                f"SMTP connection error: {str(e)}",
                details={"server": config.smtp_server},
            ) from e

        except (MissingCredentialsError, AuthenticationError):
            raise  # Re-raise credential errors as-is

        except Exception as e:
            logger.error(f"Unexpected error connecting to SMTP server: {e}")
            raise NetworkError(
                f"Failed to connect to SMTP server: {str(e)}",
                details={"server": config.smtp_server},
            ) from e

    @async_log_call
    async def close_connection(self) -> None:
        """Close the SMTP connection gracefully."""
        async with self._lock:
            if self._client:
                try:
                    await asyncio.wait_for(
                        self._client.quit(), timeout=Timeouts.SMTP_QUIT
                    )
                    logger.debug(
                        "SMTP connection closed successfully",
                        extra={
                            "emails_sent": self._stats.emails_sent,
                            "avg_send_time": round(self._stats.avg_send_time, 2),
                        },
                    )

                except Exception as e:
                    logger.debug(f"Error closing SMTP connection: {str(e)}")

                finally:
                    self._client = None
                    self._connection_created_at = None

    ## Context Manager Support

    async def __aenter__(self):
        """Enter async context manager."""
        await self._ensure_connection()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context manager."""
        await self.close_connection()
