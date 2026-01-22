"""1Password backend"""

import asyncio
import json
from typing import Optional

from src.utils.logging import get_logger

from .base import BackendCapabilities, CredentialBackend

logger = get_logger(__name__)


class OnePasswordBackend(CredentialBackend):
    """1Password CLI backend."""

    CLI_COMMAND = "op"

    @property
    def name(self) -> str:
        return "1Password"

    @property
    def priority(self) -> int:
        return 1  # Highest priority

    async def is_available(self) -> bool:
        """Check if 'op' CLI is available.

        Returns:
            bool: True if 'op' CLI is available, False otherwise.
        """
        try:
            result = await asyncio.create_subprocess_exec(
                self.CLI_COMMAND,
                "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(result.wait(), timeout=2.0)
            return result.returncode == 0
        except (FileNotFoundError, asyncio.TimeoutError):
            return False
        except Exception as e:
            logger.debug(f"1Password availability check failed: {e}")
            return False

    async def store(self, service: str, key: str, value: str) -> None:
        """Store credential in 1Password.

        Args:
            service (str): The name of the service.
            key (str): The key for the credential.
            value (str): The value of the credential.
        """
        item_name = f"{service}_{key}"

        exists = await self._item_exists(item_name)

        if exists:
            await self._update_item(item_name, value)
        else:
            await self._create_item(item_name, value, service)

    async def retrieve(self, service: str, key: str) -> Optional[str]:
        """Retrieve credential from 1Password.

        Args:
            service (str): The name of the service.
            key (str): The key for the credential.

        Returns:
            Optional[str]: The value of the credential, or None if not found.
        """
        item_name = f"{service}_{key}"

        try:
            result = await asyncio.create_subprocess_exec(
                self.CLI_COMMAND,
                "item",
                "get",
                item_name,
                "--fields",
                "label=password",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, _ = await asyncio.wait_for(result.communicate(), timeout=10.0)

            if result.returncode != 0:
                return None

            password = stdout.decode().strip()
            return password if password else None

        except asyncio.TimeoutError:
            logger.error(f"Timeout retrieving from 1Password: {item_name}")
            return None
        except Exception as e:
            logger.error(f"Error retrieving from 1Password: {e}")
            return None

    async def delete(self, service: str, key: str) -> None:
        """Delete credential from 1Password.

        Args:
            service (str): The name of the service.
            key (str): The key for the credential.
        """
        item_name = f"{service}_{key}"

        try:
            result = await asyncio.create_subprocess_exec(
                self.CLI_COMMAND,
                "item",
                "delete",
                item_name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            await asyncio.wait_for(result.wait(), timeout=10.0)

            if result.returncode != 0:
                logger.warning(f"Failed to delete from 1Password: {item_name}")

        except Exception as e:
            logger.error(f"Error deleting from 1Password: {e}")

    def get_capabilities(self) -> BackendCapabilities:
        """Get backend capabilities.

        Returns:
            BackendCapabilities: The capabilities of the backend.
        """
        return BackendCapabilities(
            supports_delete=True, supports_list=True, requires_authentication=True
        )

    async def _item_exists(self, item_name: str) -> bool:
        """Check if item exists.

        Args:
            item_name (str): The name of the item to check.

        Returns:
            bool: True if the item exists, False otherwise.
        """
        try:
            result = await asyncio.create_subprocess_exec(
                self.CLI_COMMAND,
                "item",
                "get",
                item_name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(result.wait(), timeout=5.0)
            return result.returncode == 0
        except Exception:
            return False

    async def _create_item(self, item_name: str, password: str, vault: str) -> None:
        """Create new item in 1Password.

        Args:
            item_name (str): The name of the item.
            password (str): The password for the item.
            vault (str): The vault to store the item in.
        """
        item_json = json.dumps(
            {
                "title": item_name,
                "vault": vault,
                "category": "password",
                "fields": [
                    {
                        "id": "password",
                        "type": "CONCEALED",
                        "label": "password",
                        "value": password,
                    }
                ],
            }
        )

        result = await asyncio.create_subprocess_exec(
            self.CLI_COMMAND,
            "item",
            "create",
            "--template",
            item_json,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        await asyncio.wait_for(result.wait(), timeout=10.0)

        if result.returncode != 0:
            raise RuntimeError(f"Failed to create 1Password item: {item_name}")

    async def _update_item(self, item_name: str, password: str) -> None:
        """Update existing item.

        Args:
            item_name (str): The name of the item.
            password (str): The new password for the item.
        """
        result = await asyncio.create_subprocess_exec(
            self.CLI_COMMAND,
            "item",
            "edit",
            item_name,
            f"password={password}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        await asyncio.wait_for(result.wait(), timeout=10.0)

        if result.returncode != 0:
            raise RuntimeError(f"Failed to update 1Password item: {item_name}")
