"""IMAP protocol operations - low-level IMAP command interface."""

import re
from typing import Dict, List, Optional

from src.core.email.imap.constants import IMAPResponse
from src.core.email.imap.connection import IMAPConnection
from src.utils.errors import IMAPError
from src.utils.logging import async_log_call, get_logger

logger = get_logger(__name__)


class IMAPProtocol:
    """Low-level IMAP protocol operations & orchestration."""

    def __init__(self, connection: IMAPConnection):
        """Initialise IMAP protocol handler.

        Args:
            connection: IMAPConnection instance for connection management
        """
        self.connection = connection
        self._selected_folder: Optional[str] = None

    async def select_folder(self, folder: str) -> None:
        """Select an IMAP folder for operations.

        Args:
            folder: Folder name (e.g., "INBOX", "SENT", "[Gmail]/Trash")

        Raises:
            IMAPError: If folder selection fails
        """
        if self._selected_folder == folder:
            logger.debug(f"Folder {folder} already selected, skipping")
            return

        client = await self.connection.get_client()

        try:
            response = await client.select(folder)
            if response.result != IMAPResponse.OK:
                raise IMAPError(
                    f"Failed to select folder: {folder}",
                    details={"folder": folder, "response": response.result},
                )

            self._selected_folder = folder
            logger.debug(f"Selected IMAP folder: {folder}")

        except Exception as e:
            raise IMAPError(
                f"IMAP error selecting folder {folder}: {str(e)}",
                details={"folder": folder},
            ) from e

    async def search_uids(self, criteria: str) -> List[int]:
        """Search for message UIDs matching criteria.

        Args:
            criteria: IMAP search criteria (e.g., "ALL", "UNSEEN", "UID 100:*")

        Returns:
            List of matching UIDs (sorted ascending)

        Raises:
            IMAPError: If search fails
        """
        client = await self.connection.get_client()

        try:
            response = await client.uid_search(criteria)
            if response.result != IMAPResponse.OK:
                raise IMAPError(
                    f"UID search failed: {criteria}",
                    details={"criteria": criteria, "response": response.result},
                )

            # Parse UIDs from response
            uid_data = response.lines[0] if response.lines else b""
            uid_list = uid_data.split() if uid_data else []
            uids = [int(uid) for uid in uid_list if uid.isdigit()]

            logger.debug(
                "UID search completed",
                extra={"criteria": criteria, "count": len(uids)},
            )

            return sorted(uids)

        except ValueError as e:
            raise IMAPError(
                "Failed to parse UIDs from search response",
                details={"criteria": criteria},
            ) from e
        except Exception as e:
            raise IMAPError(
                f"IMAP search error: {str(e)}",
                details={"criteria": criteria},
            ) from e

    async def fetch_messages(self, uids: List[int]) -> Dict[int, bytes]:
        """Fetch raw message data for given UIDs.

        Args:
            uids: List of UIDs to fetch

        Returns:
            Dictionary mapping UID -> raw email bytes (RFC822 format)

        Raises:
            IMAPError: If fetch fails

        Note:
            Messages that fail to fetch are logged and excluded from results.
            Partial success is allowed - some messages may be missing from result.
        """
        if not uids:
            return {}

        client = await self.connection.get_client()

        try:
            uid_set = ",".join(str(uid) for uid in uids)
            response = await client.uid("fetch", uid_set, "(RFC822)")
            if response.result != IMAPResponse.OK:
                raise IMAPError(
                    f"FETCH failed for UIDs: {uid_set}",
                    details={"uids": uid_set, "response": response.result},
                )

            messages = {}
            i = 0
            while i < len(response.lines):
                line = response.lines[i]
                if isinstance(line, (bytes, bytearray)):
                    try:
                        line_str = (
                            line.decode("utf-8", errors="ignore")
                            if isinstance(line, bytes)
                            else str(line)
                        )
                    except Exception:
                        line_str = str(line)

                    if "FETCH" in line_str and "RFC822" in line_str:
                        uid = self.parse_uid_from_response(line)
                        if uid is not None:
                            if i + 1 < len(response.lines):
                                next_line = response.lines[i + 1]
                                if isinstance(next_line, (bytes, bytearray)):
                                    message_bytes = (
                                        bytes(next_line)
                                        if isinstance(next_line, bytearray)
                                        else next_line
                                    )
                                    if (
                                        not message_bytes.startswith(b")")
                                        and message_bytes.strip() != b")"
                                    ):
                                        messages[uid] = message_bytes
                i += 1

            logger.debug(
                "Fetched messages",
                extra={
                    "requested": len(uids),
                    "received": len(messages),
                    "missing": len(uids) - len(messages),
                },
            )

            # Log partial success
            if len(messages) < len(uids):
                missing = set(uids) - set(messages.keys())
                logger.warning(
                    "Some messages could not be fetched",
                    extra={"missing_uids": sorted(missing)},
                )

            return messages

        except Exception as e:
            raise IMAPError(
                f"IMAP fetch error: {str(e)}",
                details={"uid_count": len(uids)},
            ) from e

    async def set_flags(self, uid: str, flags: List[str], add: bool = True) -> bool:
        """Set or remove flags on a message.

        Args:
            uid: Message UID
            flags: List of IMAP flags (e.g., ["\\Seen", "\\Flagged"])
            add: True to add flags, False to remove

        Returns:
            True if successful, False otherwise

        Common flags:
            - \\Seen: Mark as read
            - \\Flagged: Mark as flagged/starred
            - \\Deleted: Mark for deletion (call expunge() to permanently delete)
            - \\Answered: Mark as replied to
            - \\Draft: Mark as draft
        """
        client = await self.connection.get_client()

        try:
            operation = "+FLAGS" if add else "-FLAGS"
            flags_str = "(" + " ".join(flags) + ")"

            response = await client.uid("store", str(uid), operation, flags_str)

            success = response.result == IMAPResponse.OK
            if success:
                logger.debug(
                    f"Flags {'added' if add else 'removed'}",
                    extra={"uid": uid, "flags": flags},
                )
            else:
                logger.warning(
                    "Failed to set flags",
                    extra={"uid": uid, "flags": flags, "response": response.result},
                )

            return success

        except Exception as e:
            logger.error(f"Error setting flags for UID {uid}: {e}")
            return False

    async def copy_message(self, uid: str, dest_folder: str) -> bool:
        """Copy a message to another folder.

        Args:
            uid: Message UID to copy
            dest_folder: Destination folder name

        Returns:
            True if successful, False otherwise

        Note:
            Original message remains in current folder.
            Use with set_flags() and expunge() to implement move.
        """
        client = await self.connection.get_client()

        try:
            response = await client.uid("copy", str(uid), dest_folder)

            success = response.result == IMAPResponse.OK
            if success:
                logger.debug(
                    "Message copied",
                    extra={"uid": uid, "destination": dest_folder},
                )
            else:
                logger.warning(
                    "Failed to copy message",
                    extra={
                        "uid": uid,
                        "destination": dest_folder,
                        "response": response.result,
                    },
                )

            return success

        except Exception as e:
            logger.error(f"Error copying message UID {uid}: {e}")
            return False

    async def expunge(self) -> bool:
        """Permanently remove messages marked with \\Deleted flag.

        Returns:
            True if successful, False otherwise

        Note:
            This operation cannot be undone. Messages are permanently deleted.
        """
        client = await self.connection.get_client()

        try:
            response = await client.expunge()

            success = response.result == IMAPResponse.OK
            if success:
                logger.debug("Expunge completed successfully")
            else:
                logger.warning(
                    "Expunge failed",
                    extra={"response": response.result},
                )

            return success

        except Exception as e:
            logger.error(f"Error expunging messages: {e}")
            return False

    async def get_folder_list(self, pattern: str = "*") -> List[str]:
        """Get list of available folders.

        Args:
            pattern: Pattern to match folder names (default: "*" for all)

        Returns:
            List of folder names
        """
        client = await self.connection.get_client()

        try:
            # aioimaplib.list() expects a compiled regex pattern
            response = await client.list("", re.compile(pattern.replace("*", ".*")))
            if response.result != IMAPResponse.OK:
                logger.warning(
                    "Failed to list folders",
                    extra={"pattern": pattern, "response": response.result},
                )
                return []

            folders = []
            for mailbox in response.lines:
                if isinstance(mailbox, bytes):
                    parts = mailbox.decode().split(' "/" ')
                    if len(parts) >= 2:
                        folder_name = parts[1].strip('"')
                        folders.append(folder_name)

            logger.debug(f"Retrieved {len(folders)} folders")
            return folders

        except Exception as e:
            logger.error(f"Error getting folder list: {e}")
            return []

    async def get_folder_status(self, folder: str) -> Dict[str, int]:
        """Get status information for a folder.

        Args:
            folder: Folder name to query

        Returns:
            Dictionary with status information:
            - MESSAGES: Total message count
            - RECENT: Recent message count
            - UNSEEN: Unread message count
        """
        client = await self.connection.get_client()

        try:
            response = await client.status(folder, "(MESSAGES RECENT UNSEEN)")
            if response.result != IMAPResponse.OK:
                logger.warning(
                    "Failed to get folder status",
                    extra={"folder": folder, "response": response.result},
                )
                return {}

            status = {}
            if response.lines:
                status_line = (
                    response.lines[0].decode()
                    if isinstance(response.lines[0], bytes)
                    else response.lines[0]
                )

                parts = status_line.split()
                for i, part in enumerate(parts):
                    if part.isdigit() and i > 0:
                        key = parts[i - 1].strip("()")
                        status[key] = int(part)

            logger.debug("Folder status retrieved", extra={"folder": folder, **status})
            return status

        except Exception as e:
            logger.error(f"Error getting folder status: {e}")
            return {}

    @staticmethod
    def parse_uid_from_response(response_line: bytes) -> Optional[int]:
        """Extract UID from IMAP FETCH response line.

        Args:
            response_line: Raw IMAP response line

        Returns:
            Extracted UID as integer, or None if extraction fails
        """
        try:
            response_str = (
                response_line.decode("utf-8", errors="ignore")
                if isinstance(response_line, bytes)
                else response_line
            )

            # First token should be the UID
            parts = response_str.split()
            if parts and parts[0].isdigit():
                return int(parts[0])

            logger.debug(f"Could not extract UID from response: {response_str[:50]}")
            return None

        except Exception as e:
            logger.error(f"Error extracting UID from response: {e}")
            return None

    @async_log_call
    async def noop(self) -> bool:
        """Send NOOP command to keep connection alive.

        Returns:
            True if successful, False otherwise
        """
        client = await self.connection.get_client()

        try:
            response = await client.noop()
            return response.result == IMAPResponse.OK
        except Exception as e:
            logger.debug(f"NOOP failed: {e}")
            return False
