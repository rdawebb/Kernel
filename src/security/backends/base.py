"""Base classes for security backends."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class BackendCapabilities:
    """Capabilities supported by backend."""

    supports_delete: bool = True
    supports_list: bool = False
    requires_authentication: bool = False


class CredentialBackend(ABC):
    """Abstract base for credential storage backends."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Backend name for display.

        Returns:
            str: Backend name.
        """
        pass

    @property
    @abstractmethod
    def priority(self) -> int:
        """Priority for auto-selection (lower = higher priority).

        Returns:
            int: Priority value.
        """
        pass

    @abstractmethod
    async def is_available(self) -> bool:
        """Check if backend is available on system.

        Returns:
            bool: True if available, False otherwise.
        """
        pass

    @abstractmethod
    async def store(self, service: str, key: str, value: str) -> None:
        """Store credential.

        Args:
            service (str): The service name.
            key (str): The credential key.
            value (str): The credential value.
        """
        pass

    @abstractmethod
    async def retrieve(self, service: str, key: str) -> Optional[str]:
        """Retrieve credential.

        Args:
            service (str): The service name.
            key (str): The credential key.

        Returns:
            Optional[str]: The credential value, or None if not found.
        """
        pass

    @abstractmethod
    async def delete(self, service: str, key: str) -> None:
        """Delete credential.

        Args:
            service (str): The service name.
            key (str): The credential key.
        """
        pass

    def get_capabilities(self) -> BackendCapabilities:
        """Get backend capabilities.

        Returns:
            BackendCapabilities: The capabilities of the backend.
        """
        return BackendCapabilities()
