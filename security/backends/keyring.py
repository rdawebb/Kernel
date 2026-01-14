"""System keyring backend"""

import asyncio
from typing import Optional

import keyring

from src.utils.logging import get_logger

from .base import CredentialBackend

logger = get_logger(__name__)


class KeyringBackend(CredentialBackend):
    """System keyring backend."""

    @property
    def name(self) -> str:
        return "System Keyring"

    @property
    def priority(self) -> int:
        return 3

    async def is_available(self) -> bool:
        """Check if keyring is available.

        Returns:
            bool: True if keyring is available, False otherwise.
        """
        try:
            await asyncio.to_thread(keyring.get_keyring)
            return True
        except Exception as e:
            logger.debug(f"Keyring availability check failed: {e}")
            return False

    async def store(self, service: str, key: str, value: str) -> None:
        """Store in system keyring.

        Args:
            service (str): The name of the service.
            key (str): The key for the credential.
            value (str): The value of the credential.
        """
        await asyncio.to_thread(keyring.set_password, service, key, value)

    async def retrieve(self, service: str, key: str) -> Optional[str]:
        """Retrieve from system keyring.

        Args:
            service (str): The name of the service.
            key (str): The key for the credential.

        Returns:
            Optional[str]: The value of the credential, or None if not found.
        """
        try:
            return await asyncio.to_thread(keyring.get_password, service, key)

        except asyncio.TimeoutError:
            logger.error(
                f"Keyring retrieval timed out for service: {service}, key: {key}"
            )
            return None
        except Exception as e:
            logger.error(f"Keyring retrieval failed: {e}")
            return None

    async def delete(self, service: str, key: str) -> None:
        """Delete from system keyring.

        Args:
            service (str): The name of the service.
            key (str): The key for the credential.
        """
        try:
            await asyncio.to_thread(keyring.delete_password, service, key)
        except Exception as e:
            logger.error(f"Keyring deletion failed: {e}")
