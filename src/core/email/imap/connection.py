"""IMAP connection management - handles connection setup and cleanup."""

import asyncio
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Optional

import aioimaplib

from security.credential_manager import CredentialManager
from security.key_store import get_keystore
from src.utils.config import ConfigManager
from src.utils.errors import (
    IMAPError,
    InvalidCredentialsError,
    MissingCredentialsError,
    NetworkError,
    NetworkTimeoutError,
)
from src.utils.logging import async_log_call, get_logger

from .constants import IMAPResponse, Timeouts

logger = get_logger(__name__)


@dataclass
class ConnectionStats:
    """Tracks IMAP connection metrics."""

    connections_created: int = 0
    reconnections: int = 0
    health_checks_passed: int = 0
    health_checks_failed: int = 0
    operations_count: int = 0
    last_operation_time: Optional[float] = None
    total_operation_time: float = 0.0

    def record_operation(self, duration: float) -> None:
        """Record an operation's duration.

        Args:
            duration: Time taken for the operation in seconds
        """
        self.operations_count += 1
        self.total_operation_time += duration
        self.last_operation_time = time.time()


class IMAPConnection:
    """Manages an IMAP connection lifecycle."""

    def __init__(self, config_manager: ConfigManager):
        """Initialize IMAP connection with config manager.

        Args:
            config_manager: Configuration manager instance
        """
        self.config_manager = config_manager
        self.credential_manager = CredentialManager(config_manager)
        self.keystore = get_keystore()
        self._client: Optional[aioimaplib.IMAP4_SSL] = None
        self._lock = asyncio.Lock()
        self._connection_created_at = None
        self._connection_ttl = getattr(
            self.config_manager.config.account,
            "connection_ttl",
            3600,  # 1 hour
        )
        self._stats = ConnectionStats()

    async def get_client(self) -> aioimaplib.IMAP4_SSL:
        """Get active IMAP client instance.

        Returns:
            Active aioimaplib.IMAP4_SSL client instance

        Raises:
            asyncio.TimeoutError: If connection times out
            InvalidCredentialsError: If credentials are invalid
            NetworkError: If there is a network issue
            IMAPError: If other IMAP errors occur
        """
        return await self._ensure_connection()

    @asynccontextmanager
    async def with_connection(self):
        """Context manager for IMAP connection lifecycle.

        Yields:
            Active aioimaplib.IMAP4_SSL client instance
        """
        client = await self.get_client()
        try:
            yield client
        finally:
            pass

    def _check_response(self, response, operation: str) -> None:
        """Check IMAP response and raise error if not OK.

        Args:
            response: IMAP response object
            operation: Description of the operation performed

        Raises:
            IMAPError: If the response indicates failure
        """
        if response.result != IMAPResponse.OK:
            error_msg = response.lines[0] if response.lines else "No response"
            if isinstance(error_msg, bytes):
                error_msg = error_msg.decode()

            raise IMAPError(
                f"IMAP operation failed: {operation}",
                details={
                    "response": str(error_msg),
                    "operation": operation,
                    "server": self.config_manager.config.account.imap_server,
                },
            )

        self._stats.operations_count += 1

    def _is_connection_expired(self) -> bool:
        """Check if the IMAP connection has expired based on TTL.

        Returns:
            True if connection is expired, False otherwise
        """
        if self._client is None or self._connection_created_at is None:
            return True

        elapsed = time.time() - self._connection_created_at

        return elapsed > self._connection_ttl

    async def _ensure_connection(self) -> aioimaplib.IMAP4_SSL:
        """Ensure an active IMAP connection.

        Returns:
             Active aioimaplib.IMAP4_SSL client instance

        Raises:
            asyncio.TimeoutError: If connection times out
        """
        async with self._lock:
            if self._client is None or self._is_connection_expired():
                if self._client is not None:
                    logger.info(
                        "IMAP connection expired, reconnecting",
                        extra={
                            "age_seconds": (time.time() - self._connection_created_at)
                            if self._connection_created_at is not None
                            else None,
                            "ttl": self._connection_ttl,
                            "operations": self._stats.operations_count,
                        },
                    )

                    self._stats.reconnections += 1

                    try:
                        await self._client.logout()

                    except Exception:
                        pass

                self._client = await self._connect()
                self._connection_created_at = time.time()
                self._stats.connections_created += 1
            else:
                try:
                    await asyncio.wait_for(
                        self._client.noop(), timeout=Timeouts.IMAP_NOOP
                    )
                    self._stats.health_checks_passed += 1
                    logger.debug(
                        "IMAP connection health check passed",
                        extra={
                            "age_seconds": (time.time() - self._connection_created_at)
                            if self._connection_created_at is not None
                            else None,
                            "health_checks": self._stats.health_checks_passed,
                        },
                    )

                except (asyncio.TimeoutError, Exception) as e:
                    self._stats.health_checks_failed += 1
                    self._stats.reconnections += 1
                    logger.warning(
                        "IMAP connection lost, reconnecting",
                        extra={
                            "error": str(e),
                            "age_seconds": (time.time() - self._connection_created_at)
                            if self._connection_created_at is not None
                            else None,
                            "failed_health_checks": self._stats.health_checks_failed,
                        },
                    )
                    try:
                        await self._client.logout()

                    except Exception:
                        pass

                    self._client = await self._connect()
                    self._connection_created_at = time.time()

        return self._client

    def get_stats(self) -> ConnectionStats:
        """Get current connection statistics.

        Returns:
            ConnectionStats object with current metrics
        """
        return self._stats

    async def _connect(self) -> aioimaplib.IMAP4_SSL:
        """Connect to IMAP server asynchronously.

        Returns:
            Connected aioimaplib.IMAP4_SSL client instance

        Raises:
            MissingCredentialsError: If credentials are missing
            InvalidCredentialsError: If authentication fails
            NetworkTimeoutError: If connection times out
            NetworkError: If other network errors occur
            IMAPError: If IMAP errors occur
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
                "Connecting to IMAP server",
                extra={"server": config.imap_server, "port": config.imap_port},
            )

            client = aioimaplib.IMAP4_SSL(
                host=config.imap_server, port=config.imap_port, timeout=30
            )

            await asyncio.wait_for(
                client.wait_hello_from_server(), timeout=Timeouts.IMAP_CONNECT
            )

            response = await asyncio.wait_for(
                client.login(config.username, password), timeout=Timeouts.IMAP_LOGIN
            )

            self._check_response(response, "login")

            connect_duration = time.time() - start_time
            logger.info(
                "IMAP connection established",
                extra={
                    "server": config.imap_server,
                    "username": config.username,
                    "duration_seconds": round(connect_duration, 2),
                },
            )

            return client

        except asyncio.TimeoutError as e:
            logger.error(
                f"IMAP connection timed out after {time.time() - start_time:.2f}s"
            )
            raise NetworkTimeoutError(
                "IMAP connection timeout", details={"server": config.imap_server}
            ) from e

        except InvalidCredentialsError:
            logger.warning(
                "IMAP authentication failed",
                extra={"server": config.imap_server, "username": config.username},
            )
            # Clear the cached password so user gets prompted for the new one
            await self.keystore.delete(config.username)
            raise InvalidCredentialsError(
                "Authentication failed. Please try again with the correct password.",
                details={"server": config.imap_server, "username": config.username},
            )

        except aioimaplib.AioImapException as e:
            error_msg = str(e).lower()
            if "authentication failed" in error_msg or "login" in error_msg:
                raise InvalidCredentialsError(
                    "IMAP authentication failed",
                    details={"server": config.imap_server, "username": config.username},
                ) from e

            else:
                raise IMAPError(
                    f"IMAP connection error: {str(e)}",
                    details={"server": config.imap_server},
                ) from e

        except IMAPError as e:
            # Check if this is an authentication error from _check_response
            error_msg = str(e).lower()
            if "login" in error_msg or "authentication" in error_msg:
                # Clear the cached password so user gets prompted for the new one
                await self.keystore.delete(config.username)
                raise InvalidCredentialsError(
                    "IMAP authentication failed. Password may be incorrect.",
                    details={"server": config.imap_server, "username": config.username},
                ) from e
            else:
                raise

        except (MissingCredentialsError, InvalidCredentialsError):
            raise

        except Exception as e:
            raise NetworkError(
                f"Failed to connect to IMAP server: {str(e)}",
                details={"server": config.imap_server},
            ) from e

    @async_log_call
    async def close_connection(self) -> None:
        """Close the IMAP connection."""
        async with self._lock:
            if self._client:
                try:
                    await asyncio.wait_for(self._client.logout(), timeout=5.0)
                    logger.debug("IMAP connection closed successfully")

                except Exception as e:
                    logger.debug(f"Error closing IMAP connection: {str(e)}")

                finally:
                    self._client = None
                    self._connection_created_at = None

    ## Context Manager Helpers

    async def __aenter__(self):
        """Enter async context manager."""
        await self._ensure_connection()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context manager."""
        await self.close_connection()
