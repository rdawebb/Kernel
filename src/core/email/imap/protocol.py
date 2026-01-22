"""Native Go-backed low-level IMAP command interface."""

import base64
from typing import Dict, List, Optional, cast

from src.native_bridge import NativeBridge, get_bridge
from src.utils.logging import async_log_call, get_logger

logger = get_logger(__name__)


class IMAPProtocol:
    """Native Go-backed IMAP protocol implementation.

    Drop-in replacement for IMAPProtocol that uses Go backend.
    """

    def __init__(self, connection):
        """Initialise native IMAP protocol.

        Args:
            connection: IMAPConnection instance (for compatibility, not used)
        """
        self.connection = connection
        self._handle: Optional[int] = None
        self._bridge: Optional[NativeBridge] = None
        self._selected_folder: Optional[str] = None

    def _get_bridge(self) -> NativeBridge:
        """Type hint for bridge."""
        return cast(NativeBridge, self._bridge)

    async def _ensure_bridge(self):
        """Ensure bridge is connected."""
        if self._bridge is None:
            self._bridge = await get_bridge()

    async def _ensure_connected(self):
        """Ensure IMAP connection is established."""
        if self._handle is None:
            await self._ensure_bridge()

            config = self.connection.config_manager.config.account

            # Get credentials
            await self.connection.credential_manager.validate_and_prompt()
            await self.connection.keystore.initialise()
            password = await self.connection.keystore.retrieve(config.username)

            if not password:
                from src.utils.errors import MissingCredentialsError

                raise MissingCredentialsError("Password not found")

            # Connect via native backend
            result = await self._get_bridge().call(
                "imap",
                "connect",
                {
                    "host": config.imap_server,
                    "port": config.imap_port,
                    "username": config.username,
                    "password": password,
                },
            )

            self._handle = result["handle"]
            logger.info(f"Connected to IMAP via native backend (handle={self._handle})")

    @async_log_call
    async def select_folder(self, folder: str) -> None:
        """Select an IMAP folder for operations.

        Args:
            folder: Folder name (e.g., "INBOX", "SENT")
        """
        if self._selected_folder == folder:
            logger.debug(f"Folder {folder} already selected, skipping")
            return

        await self._ensure_connected()

        await self._get_bridge().call(
            "imap", "select_folder", {"handle": self._handle, "folder": folder}
        )

        self._selected_folder = folder
        logger.debug(f"Selected IMAP folder: {folder}")

    @async_log_call
    async def search_uids(self, criteria: str) -> List[int]:
        """Search for message UIDs matching criteria.

        Args:
            criteria: IMAP search criteria (e.g., "ALL", "UNSEEN")

        Returns:
            List of matching UIDs (sorted ascending)
        """
        await self._ensure_connected()

        result = await self._get_bridge().call(
            "imap", "search_uids", {"handle": self._handle, "criteria": criteria}
        )

        uids = [int(uid) for uid in result["uids"]]
        logger.debug(f"UID search completed: {len(uids)} results")

        return sorted(uids)

    @async_log_call
    async def fetch_messages(self, uids: List[int]) -> Dict[int, bytes]:
        """Fetch raw message data for given UIDs.

        Args:
            uids: List of UIDs to fetch

        Returns:
            Dictionary mapping UID -> raw email bytes
        """
        if not uids:
            return {}

        await self._ensure_connected()

        # Convert to uint32 for Go
        uids_uint32 = [int(uid) for uid in uids]

        result = await self._get_bridge().call(
            "imap", "fetch_messages", {"handle": self._handle, "uids": uids_uint32}
        )

        # Convert base64-encoded messages back to bytes
        messages = {}
        for uid_str, b64_data in result["messages"].items():
            uid = int(uid_str)
            messages[uid] = base64.b64decode(b64_data)

        logger.debug(f"Fetched {len(messages)} messages (requested {len(uids)})")

        return messages

    @async_log_call
    async def set_flags(self, uid: str, flags: List[str], add: bool = True) -> bool:
        """Set or remove flags on a message.

        Args:
            uid: Message UID
            flags: List of IMAP flags
            add: True to add flags, False to remove

        Returns:
            True if successful
        """
        await self._ensure_connected()

        try:
            await self._get_bridge().call(
                "imap",
                "set_flags",
                {
                    "handle": self._handle,
                    "uid": int(uid),
                    "flags": flags,
                    "add": add,
                },
            )
            return True
        except Exception as e:
            logger.error(f"Failed to set flags: {e}")
            return False

    @async_log_call
    async def copy_message(self, uid: str, dest_folder: str) -> bool:
        """Copy a message to another folder.

        Args:
            uid: Message UID to copy
            dest_folder: Destination folder name

        Returns:
            True if successful
        """
        await self._ensure_connected()

        try:
            await self._get_bridge().call(
                "imap",
                "copy_message",
                {
                    "handle": self._handle,
                    "uid": int(uid),
                    "dest_folder": dest_folder,
                },
            )
            return True
        except Exception as e:
            logger.error(f"Failed to copy message: {e}")
            return False

    @async_log_call
    async def expunge(self) -> bool:
        """Permanently remove messages marked with \\Deleted flag.

        Returns:
            True if successful
        """
        await self._ensure_connected()

        try:
            await self._get_bridge().call("imap", "expunge", {"handle": self._handle})
            return True
        except Exception as e:
            logger.error(f"Failed to expunge: {e}")
            return False

    @async_log_call
    async def noop(self) -> bool:
        """Send NOOP command to keep connection alive.

        Returns:
            True if successful
        """
        await self._ensure_connected()

        try:
            await self._get_bridge().call("imap", "noop", {"handle": self._handle})
            return True

        except Exception as e:
            logger.debug(f"NOOP failed: {e}")
            return False

    # Placeholder methods for compatibility (not implemented yet)
    async def get_folder_list(self, pattern: str = "*") -> List[str]:
        """Get list of available folders."""
        # TODO: Implement in Go
        logger.warning("get_folder_list not yet implemented in native backend")
        return []

    async def get_folder_status(self, folder: str) -> Dict[str, int]:
        """Get folder statistics."""
        # TODO: Implement in Go
        logger.warning("get_folder_status not yet implemented in native backend")
        return {}
