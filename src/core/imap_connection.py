"""IMAP connection management - handles connection setup and cleanup."""

import aioimaplib
import asyncio
import time
from typing import Optional

from security.credential_manager import CredentialManager
from security.key_store import get_keystore
from src.utils.config_manager import ConfigManager
from src.utils.error_handling import (
    IMAPError,
    InvalidCredentialsError,
    MissingCredentialsError,
    NetworkError,
    NetworkTimeoutError
)
from src.utils.log_manager import async_log_call, get_logger

logger = get_logger(__name__)

RESPONSE_OK = "OK"


class IMAPConnection:
    """Manages an IMAP connection lifecycle."""

    def __init__(self, config_manager: ConfigManager):
        """Initialize IMAP connection with config manager."""

        self.config_manager = config_manager
        self.credential_manager = CredentialManager(config_manager)
        self.keystore = get_keystore()
        self._client: Optional[aioimaplib.IMAP4_SSL] = None
        self._lock = asyncio.Lock()
        self._connection_created_at = None
        self._connection_ttl = getattr(
            self.config_manager.config.account,
            "connection_ttl",
            3600
        )  # Default to 1 hour

    def _check_response(self, response, operation: str) -> None:
        """Check IMAP response and raise error if not OK."""
        
        if response.result != RESPONSE_OK:
            error_msg = response.lines[0] if response.lines else "No response"
            if isinstance(error_msg, bytes):
                error_msg = error_msg.decode()
            
            raise IMAPError(
                f"IMAP operation failed: {operation}",
                details={"response": str(error_msg)}
            )
        
    def _is_connection_expired(self) -> bool:
        """Check if the IMAP connection has expired based on TTL."""

        if self._client is None or self._connection_created_at is None:
            return True
        
        elapsed = time.time() - self._connection_created_at

        return elapsed > self._connection_ttl

    async def _ensure_connection(self) -> aioimaplib.IMAP4_SSL:
        """Ensure an active IMAP connection."""

        async with self._lock:
            if self._client is None or self._is_connection_expired():
                if self._client is not None:
                    logger.info("IMAP connection expired, reconnecting...")
                    try:
                        await self._client.logout()
                    
                    except Exception:
                        pass

                self._client = await self._connect()
                self._connection_created_at = time.time()
            else:
                try:
                    await asyncio.wait_for(self._client.noop(), timeout=5.0)
                    logger.debug("IMAP connection health check passed.")
                
                except (asyncio.TimeoutError, Exception) as e:
                    logger.warning(f"IMAP connection lost: {e}, reconnecting...")
                    try:
                        await self._client.logout()

                    except Exception:
                        pass

                    self._client = await self._connect()
                    self._connection_created_at = time.time()

        return self._client

    async def _connect(self) -> aioimaplib.IMAP4_SSL:
        """Connect to IMAP server asynchronously."""

        config = self.config_manager.config.account

        try:
            await self.credential_manager.validate_and_prompt()

            password = self.keystore.retrieve(config.username)
            if not password:
                raise MissingCredentialsError("Password not found after validation.")

            logger.info(f"Connecting to IMAP server: {config.imap_server}...")
            
            client = aioimaplib.IMAP4_SSL(
                host=config.imap_server,
                port=config.imap_port,
                timeout=30
            )

            await asyncio.wait_for(
                client.wait_hello_from_server(),
                timeout=30.0
            )

            response = await asyncio.wait_for(
                client.login(config.username, password),
                timeout=30.0
            )

            self._check_response(response, "login")
            
            logger.info(f"Connected to IMAP server: {config.imap_server} as {config.username}")

            return client
        
        except asyncio.TimeoutError as e:
            raise NetworkTimeoutError(
                "IMAP connection timeout",
                details={"server": config.imap_server}
            ) from e

        except InvalidCredentialsError as e:
            logger.warning(f"Authentication failed: {e.message}")

            await self.credential_manager.handle_auth_failure()
            logger.info("Retrying connection with new credentials...")
            return await self._connect()

        except aioimaplib.AioImapException as e:
            error_msg = str(e).lower()
            if "authentication failed" in error_msg or "login" in error_msg:
                raise InvalidCredentialsError(
                    "IMAP authentication failed",
                    details={"server": config.imap_server, "username": config.username}
                ) from e
            
            else:
                raise IMAPError(
                    f"IMAP connection error: {str(e)}",
                    details={"server": config.imap_server}
                ) from e
            
        except (MissingCredentialsError, InvalidCredentialsError):
            raise
        
        except Exception as e:
            raise NetworkError(
                f"Failed to connect to IMAP server: {str(e)}",
                details={"server": config.imap_server}
            ) from e

    @async_log_call
    async def close_connection(self) -> None:
        """Close the IMAP connection."""

        async with self._lock:
            if self._client:
                try:
                    await asyncio.wait_for(
                        self._client.logout(),
                        timeout=5.0
                    )
                    logger.debug("IMAP connection closed successfully.")
                
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
