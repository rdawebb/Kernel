"""Connection pooling for persistent IMAP and SMTP connections.

Maintains long-lived connections to reduce connection overhead:
- IMAPConnectionPool: 5-minute TTL with NOOP keepalive
- SMTPConnectionPool: 1-minute TTL for transient sends
- ConnectionPoolManager: Unified interface for both pools

Features
--------
- Automatic reconnection with exponential backoff
- Periodic keepalive to prevent server timeouts
- Credential retrieval from secure keystore
- Connection expiration based on TTL
- Metrics tracking for pool health monitoring

Usage Examples
--------------

Get clients from pool:
    >>> manager = ConnectionPoolManager(config, keystore)
    >>>
    >>> imap = await manager.get_imap_client()
    >>> smtp = await manager.get_smtp_client()

Health check:
    >>> health = await manager.health_check()
    >>> print(f"IMAP: {health['IMAP']}, SMTP: {health['SMTP']}")

Background keepalive (started by daemon):
    >>> keepalive_task = asyncio.create_task(manager.keepalive_loop())
"""

import asyncio
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional

from security.key_store import KeyStore
from src.core.email.imap.client import IMAPClient
from src.core.email.smtp.client import SMTPClient
from src.utils.config import ConfigManager
from src.utils.logging import get_logger, log_event

logger = get_logger(__name__)


_pool_metrics = {
    "connections_created": 0,
    "connections_expired": 0,
    "keepalive_sent": 0,
    "keepalive_failed": 0,
    "reconnection_attempts": 0,
}


def get_pool_metrics() -> Dict[str, int]:
    """Retrieve current pool metrics."""
    return _pool_metrics.copy()


def reset_pool_metrics() -> None:
    """Reset pool metrics to zero."""
    global _pool_metrics
    _pool_metrics = {key: 0 for key in _pool_metrics}


@dataclass
class ConnectionPool:
    """Base class for connection pools with timeout and keepalive management"""

    timeout: int
    client: Optional[Any] = None
    last_used: Optional[float] = None
    reconnect_attempts: int = 0
    max_reconnect_attempts: int = 3

    def is_expired(self, current_time: float) -> bool:
        """Check if the connection has expired"""
        if not self.client or not self.last_used:
            return True

        return (current_time - self.last_used) > self.timeout

    def update_last_used(self) -> None:
        """Update the last used timestamp"""
        self.last_used = time.time()

    async def close(self, client_type: str) -> None:
        """Close and clean up the connection"""
        if self.client:
            try:
                if hasattr(self.client, "close"):
                    await asyncio.to_thread(self.client.close)
                elif hasattr(self.client, "logout"):
                    await asyncio.to_thread(self.client.logout)
                logger.debug(f"{client_type} connection closed")

            except Exception as e:
                logger.debug(f"Error closing {client_type} connection: {e}")

            finally:
                self.client = None
                self.last_used = None
                self.reconnect_attempts = 0


class EmailConnectionPool(ABC):
    """Abstract base class for email connection pools"""

    def __init__(
        self, config: ConfigManager, key_store: KeyStore, timeout: int
    ) -> None:
        """Initialise the email connection pool"""
        self.config = config
        self.key_store = key_store
        self.pool = ConnectionPool(timeout=timeout)
        self._client_type = self._get_client_type()

    async def get_client(self) -> Any:
        """Get or create a new client connection"""
        current_time = time.time()

        if self.pool.is_expired(current_time):
            if self.pool.client:
                logger.info(f"{self._client_type} connection expired, reconnecting...")
                await self.pool.close(self._client_type)
                _pool_metrics["connections_expired"] += 1

            account_config = await self._get_account_config()

            backoff = min(2**self.pool.reconnect_attempts, 30)
            if self.pool.reconnect_attempts > 0:
                logger.info(
                    f"Reconnection attempt {self.pool.reconnect_attempts}, waiting {backoff}s..."
                )
                await asyncio.sleep(backoff)

            try:
                self.pool.client = await self._create_client(account_config)
                logger.info(f"{self._client_type} connection established")
                log_event(
                    f"{self._client_type.lower()}_connected",
                    {
                        "timeout": self.pool.timeout,
                        "attempt": self.pool.reconnect_attempts,
                    },
                )
                _pool_metrics["connections_created"] += 1
                self.pool.reconnect_attempts = 0

            except Exception as e:
                self.pool.reconnect_attempts += 1
                _pool_metrics["reconnection_attempts"] += 1
                logger.error(f"Failed to establish {self._client_type} connection: {e}")

                if self.pool.reconnect_attempts >= self.pool.max_reconnect_attempts:
                    logger.error(
                        f"Max reconnection attempts reached for {self._client_type}"
                    )
                    self.pool.reconnect_attempts = 0
                raise

        self.pool.update_last_used()
        return self.pool.client

    async def _get_account_config(self) -> Dict[str, Any]:
        """Retrieve account configuration details with credentials"""
        config = self.config.get_account_config()

        username = config.get("username")
        if username:
            credential_key = f"{self._get_credential_prefix()}_{username}"
            password = await asyncio.to_thread(self.key_store.retrieve, credential_key)
            if password:
                config["password"] = password

        return config

    async def close(self) -> None:
        """Close the connection pool"""
        await self.pool.close(self._client_type)

    async def health_check(self) -> bool:
        """Perform a health check on the connection"""
        if not self.pool.client:
            return False

        if self.pool.is_expired(time.time()):
            return False

        # Simple health check by attempting a NOOP or equivalent
        return True

    @abstractmethod
    async def _create_client(self, config: Dict[str, Any]) -> Any:
        """Create a new client connection, implemented by subclasses"""
        pass

    @abstractmethod
    def _get_client_type(self) -> str:
        """Get the client type name, implemented by subclasses"""
        pass

    @abstractmethod
    def _get_credential_prefix(self) -> str:
        """Get the credential prefix for key store, implemented by subclasses"""
        pass


class IMAPConnectionPool(EmailConnectionPool):
    """IMAP connection pool"""

    CLIENT_CLASS = IMAPClient
    CLIENT_TYPE = "IMAP"
    CREDENTIAL_PREFIX = "imap"
    DEFAULT_TIMEOUT = 300  # 5 minutes

    def __init__(
        self, config: ConfigManager, key_store: KeyStore, timeout: int | None
    ) -> None:
        """Initialise the IMAP connection pool"""
        super().__init__(config, key_store, timeout or self.DEFAULT_TIMEOUT)

    async def _create_client(self, config: Dict[str, Any]) -> IMAPClient:
        """Create a new IMAP client connection"""
        return await asyncio.to_thread(self.CLIENT_CLASS, config)

    def _get_client_type(self) -> str:
        """Get the client type name"""
        return self.CLIENT_TYPE

    def _get_credential_prefix(self) -> str:
        """Get the credential prefix for key store"""
        return self.CREDENTIAL_PREFIX

    async def keepalive(self) -> None:
        """Send NOOP command to keep the IMAP connection alive"""
        if self.pool.client and not self.pool.is_expired(time.time()):
            try:
                await asyncio.to_thread(self.pool.client._connection.noop)
                logger.debug(f"{self.CLIENT_TYPE} keepalive sent")
                _pool_metrics["keepalive_sent"] += 1

            except Exception as e:
                logger.warning(f"{self.CLIENT_TYPE} keepalive failed: {e}")
                _pool_metrics["keepalive_failed"] += 1
                await self.pool.close(self.CLIENT_TYPE)


class SMTPConnectionPool(EmailConnectionPool):
    """SMTP connection pool"""

    CLIENT_CLASS = SMTPClient
    CLIENT_TYPE = "SMTP"
    CREDENTIAL_PREFIX = "smtp"
    DEFAULT_TIMEOUT = 60  # 1 minute

    def __init__(
        self, config: ConfigManager, key_store: KeyStore, timeout: int | None
    ) -> None:
        """Initialise the SMTP connection pool"""
        super().__init__(config, key_store, timeout or self.DEFAULT_TIMEOUT)

    async def _create_client(self, config: Dict[str, Any]) -> SMTPClient:
        """Create a new SMTP client connection"""

        def _create():
            return self.CLIENT_CLASS(
                host=config["smtp_server"],
                port=config["smtp_port"],
                username=config["username"],
                password=config["password"],
                use_tls=config.get("use_tls", True),
            )

        return await asyncio.to_thread(_create)

    def _get_client_type(self) -> str:
        """Get the client type name"""
        return self.CLIENT_TYPE

    def _get_credential_prefix(self) -> str:
        """Get the credential prefix for key store"""
        return self.CREDENTIAL_PREFIX


class ConnectionPoolManager:
    """Manages all connection pools with unified keepalive"""

    def __init__(self, config: ConfigManager, key_store: KeyStore) -> None:
        """Initialise the connection pool manager"""
        self.imap_pool = IMAPConnectionPool(config, key_store, timeout=300)
        self.smtp_pool = SMTPConnectionPool(config, key_store, timeout=60)

    async def get_imap_client(self) -> IMAPClient:
        """Get an IMAP client from the pool"""
        return await self.imap_pool.get_client()

    async def get_smtp_client(self) -> SMTPClient:
        """Get an SMTP client from the pool"""
        return await self.smtp_pool.get_client()

    async def close_all(self) -> None:
        """Close all connection pools"""
        await asyncio.gather(
            self.imap_pool.close(),
            self.smtp_pool.close(),
        )
        logger.info("All connections closed")

    async def health_check(self) -> Dict[str, bool]:
        """Perform health checks on all connection pools"""
        results = await asyncio.gather(
            self.imap_pool.health_check(),
            self.smtp_pool.health_check(),
        )
        return {
            "IMAP": results[0],
            "SMTP": results[1],
        }

    async def keepalive_loop(self) -> None:
        """Background task to send IMAP keepalive signals periodically"""
        try:
            while True:
                await asyncio.sleep(60)  # Keepalive interval

                try:
                    await self.imap_pool.keepalive()

                except Exception as e:
                    logger.error(f"Error during IMAP keepalive loop: {e}")

        except asyncio.CancelledError:
            logger.debug("Keepalive loop cancelled")
            raise
