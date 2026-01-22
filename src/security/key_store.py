"""Key management for encryption and decryption of sensitive data."""

from typing import Optional

from src.utils.logging import get_logger
from src.utils.errors import KeyStoreError

from .backends.base import CredentialBackend
from .backends.onepassword import OnePasswordBackend
from .backends.bitwarden import BitwardenBackend
from .backends.keyring import KeyringBackend
from .backends.encrypted_file import EncryptedFileBackend

logger = get_logger(__name__)


class KeyStore:
    """
    Simplified key store with pluggable backends.

    Automatically selects best available backend.
    """

    # Available backends in priority order
    AVAILABLE_BACKENDS = [
        OnePasswordBackend,
        BitwardenBackend,
        KeyringBackend,
        EncryptedFileBackend,  # Always available as fallback
    ]

    def __init__(self, service_name: str = "kernel"):
        self.service_name = service_name
        self.backend: Optional[CredentialBackend] = None
        self._initialised = False

    async def initialise(self) -> None:
        """Initialise key store with best available backend."""
        if self._initialised:
            return

        self.backend = await self._select_backend()
        self._initialised = True

        logger.info(f"KeyStore initialised with backend: {self.backend.name}")

    async def _select_backend(self) -> CredentialBackend:
        """Select best available backend.

        Returns:
            CredentialBackend: The selected backend.
        """
        # Try backends in priority order
        for backend_class in self.AVAILABLE_BACKENDS:
            backend = backend_class()

            try:
                if await backend.is_available():
                    logger.debug(f"Selected backend: {backend.name}")
                    return backend

            except Exception as e:
                logger.debug(f"Backend {backend.name} not available: {e}")
                continue

        # Should never reach here (EncryptedFileBackend always available)
        raise KeyStoreError("No credential backend available")

    async def store(self, key: str, value: str) -> None:
        """Store credential.

        Args:
            key (str): The key under which to store the credential.
            value (str): The credential value to store.
        """
        await self._ensure_initialised()

        if self.backend is None:
            raise KeyStoreError("Credential backend is not initialised")

        try:
            await self.backend.store(self.service_name, key, value)
            logger.info(f"Stored credential for key: {key}")

        except Exception as e:
            raise KeyStoreError(
                f"Failed to store credential: {str(e)}",
                details={"key": key, "backend": self.backend.name},
            ) from e

    async def retrieve(self, key: str) -> Optional[str]:
        """Retrieve credential.

        Args:
            key (str): The key under which the credential is stored.

        Returns:
            Optional[str]: The retrieved credential value, or None if not found.
        """
        await self._ensure_initialised()

        if self.backend is None:
            logger.error("Credential backend is not initialised")
            return None
        try:
            value = await self.backend.retrieve(self.service_name, key)

            if value:
                logger.debug(f"Retrieved credential for key: {key}")
            else:
                logger.debug(f"Credential not found for key: {key}")

            return value

        except Exception as e:
            logger.error(f"Failed to retrieve credential for {key}: {e}")
            return None

    async def delete(self, key: str) -> None:
        """Delete credential.

        Args:
            key (str): The key under which the credential is stored.
        """
        await self._ensure_initialised()

        if self.backend is None:
            logger.warning("Credential backend is not initialised")
            return

        capabilities = self.backend.get_capabilities()
        if not capabilities.supports_delete:
            logger.warning(f"Backend {self.backend.name} does not support delete")
            return

        try:
            await self.backend.delete(self.service_name, key)
            logger.info(f"Deleted credential for key: {key}")

        except Exception as e:
            raise KeyStoreError(
                f"Failed to delete credential: {str(e)}",
                details={"key": key, "backend": self.backend.name},
            ) from e

    async def _ensure_initialised(self) -> None:
        """Ensure keystore is initialised."""
        if not self._initialised:
            await self.initialise()

    def get_backend_info(self) -> dict:
        """Get information about current backend.

        Returns:
            dict: Information about the current backend.
        """
        if not self.backend:
            return {"status": "not_initialised"}

        capabilities = self.backend.get_capabilities()
        return {
            "backend": self.backend.name,
            "priority": self.backend.priority,
            "capabilities": {
                "delete": capabilities.supports_delete,
                "list": capabilities.supports_list,
                "requires_auth": capabilities.requires_authentication,
            },
        }


# Singleton
_keystore: Optional[KeyStore] = None


def get_keystore(service_name: str = "kernel") -> KeyStore:
    """Get or create keystore singleton.

    Args:
        service_name (str): The name of the service for the keystore.

    Returns:
        KeyStore: The keystore singleton instance.
    """
    global _keystore

    if _keystore is None:
        _keystore = KeyStore(service_name)

    return _keystore


async def initialise_keystore(service_name: str = "kernel") -> KeyStore:
    """Initialise and return keystore (async).

    Args:
        service_name (str): The name of the service for the keystore.

    Returns:
        KeyStore: The initialised keystore instance.
    """
    keystore = get_keystore(service_name)
    await keystore.initialise()

    return keystore
