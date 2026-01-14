"""Encrypted file backend"""

import asyncio
import json
from typing import Optional

from cryptography.fernet import Fernet

from security.backends.base import BackendCapabilities, CredentialBackend
from src.utils.paths import MASTER_KEY_PATH, SECRETS_DIR


class EncryptedFileBackend(CredentialBackend):
    """Encrypted file backend (fallback)."""

    def __init__(self):
        self._secrets_path = SECRETS_DIR / "credentials.enc"
        self._master_key: Optional[bytes] = None

    @property
    def name(self) -> str:
        return "Encrypted File"

    @property
    def priority(self) -> int:
        return 99  # Lowest priority (fallback)

    async def is_available(self) -> bool:
        """Always available as fallback."""
        return True

    async def store(self, service: str, key: str, value: str) -> None:
        """Store in encrypted file.

        Args:
            service (str): The service name.
            key (str): The key name.
            value (str): The value to store.
        """
        credentials = await self._load_credentials()

        compound_key = f"{service}:{key}"
        credentials[compound_key] = value

        await self._save_credentials(credentials)

    async def retrieve(self, service: str, key: str) -> Optional[str]:
        """Retrieve from encrypted file.

        Args:
            service (str): The service name.
            key (str): The key name.

        Returns:
            Optional[str]: The retrieved value or None if not found.
        """
        credentials = await self._load_credentials()
        compound_key = f"{service}:{key}"
        return credentials.get(compound_key)

    async def delete(self, service: str, key: str) -> None:
        """Delete from encrypted file.

        Args:
            service (str): The service name.
            key (str): The key name.
        """
        credentials = await self._load_credentials()
        compound_key = f"{service}:{key}"
        credentials.pop(compound_key, None)
        await self._save_credentials(credentials)

    def get_capabilities(self) -> BackendCapabilities:
        return BackendCapabilities(
            supports_delete=True, supports_list=True, requires_authentication=False
        )

    async def _get_master_key(self) -> bytes:
        """Get or create master encryption key.

        Returns:
            bytes: The master encryption key.
        """
        if self._master_key:
            return self._master_key

        def load_or_create():
            MASTER_KEY_PATH.parent.mkdir(parents=True, exist_ok=True)

            if MASTER_KEY_PATH.exists():
                return MASTER_KEY_PATH.read_bytes()
            else:
                key = Fernet.generate_key()
                MASTER_KEY_PATH.write_bytes(key)
                MASTER_KEY_PATH.chmod(0o600)
                return key

        self._master_key = await asyncio.to_thread(load_or_create)
        return self._master_key

    async def _load_credentials(self) -> dict:
        """Load and decrypt credentials.

        Returns:
            dict: The decrypted credentials.
        """
        if not self._secrets_path.exists():
            return {}

        def load(master_key):
            encrypted_data = self._secrets_path.read_text()
            if not encrypted_data:
                return {}

            cipher = Fernet(master_key)
            decrypted = cipher.decrypt(encrypted_data.encode())
            return json.loads(decrypted)

        master_key = await self._get_master_key()
        return await asyncio.to_thread(load, master_key)

    async def _save_credentials(self, credentials: dict) -> None:
        """Encrypt and save credentials.

        Args:
            credentials (dict): The credentials to save.
        """

        def save(master_key):
            self._secrets_path.parent.mkdir(parents=True, exist_ok=True)

            cipher = Fernet(master_key)
            data = json.dumps(credentials)
            encrypted = cipher.encrypt(data.encode())

            # Atomic write
            temp_path = self._secrets_path.with_suffix(".tmp")
            temp_path.write_bytes(encrypted)
            temp_path.chmod(0o600)  # TODO: replace with OS-agnostic permissions
            temp_path.replace(self._secrets_path)

        master_key = await self._get_master_key()
        await asyncio.to_thread(save, master_key)
