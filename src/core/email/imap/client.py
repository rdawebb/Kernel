"""IMAP client for email operations - fetch, delete, and synchronization."""

import asyncio
import time
from enum import Enum
from typing import List, Optional

import aioimaplib

from src.core.email.constants import BatchSizes, IMAPResponse, Timeouts
from src.core.email.parser import EmailParser
from src.utils.errors import IMAPError, NetworkError, NetworkTimeoutError
from src.utils.logging import async_log_call, get_logger

from .connection import IMAPConnection

logger = get_logger(__name__)


class SyncMode(Enum):
    """Synchronization modes for IMAP client."""

    INCREMENTAL = "incremental"
    FULL = "full"


class IMAPClient:
    """Asynchronous IMAP client for email operations."""

    def __init__(self, config_manager):
        """Initialize IMAP client with config manager."""
        self.config_manager = config_manager
        self._connection = IMAPConnection(config_manager)
        self._selected_folder = None

    def get_connection_stats(self) -> dict:
        """Get IMAP connection statistics.

        Returns:
            Dictionary of connection statistics
        """
        stats = self._connection.get_stats()
        return {
            "connections_created": stats.connections_created,
            "reconnections": stats.reconnections,
            "health_checks_passed": stats.health_checks_passed,
            "health_checks_failed": stats.health_checks_failed,
            "operations_count": stats.operations_count,
        }

    async def _select_folder(self, folder: str = "INBOX") -> None:
        """Select IMAP folder if not already selected.

        Args:
            folder: Folder name to select

        Raises:
            IMAPError: If folder selection fails
        """
        if self._selected_folder != folder:
            client = await self._connection._ensure_connection()

            start_time = time.time()
            response = await asyncio.wait_for(
                client.select(folder), timeout=Timeouts.IMAP_SELECT
            )

            self._connection._check_response(response, f"select folder '{folder}'")

            self._selected_folder = folder
            duration = time.time() - start_time
            logger.debug(
                "Selected IMAP folder",
                extra={"folder": folder, "duration_seconds": round(duration, 3)},
            )

    ## Email Fetching

    @async_log_call
    async def fetch_new_emails(self, sync_mode: SyncMode = SyncMode.INCREMENTAL) -> int:
        """Fetch new emails from the IMAP server with batch saving.

        Args:
            sync_mode: Synchronization mode (incremental or full)

        Returns:
            Number of new emails fetched and saved

        Raises:
            IMAPError: If fetching emails fails
            NetworkError: If network error occurs
            NetworkTimeoutError: If network timeout occurs
        """
        start_time = time.time()
        logger.info(
            "Starting email fetch from IMAP server",
            extra={"sync_mode": sync_mode.value},
        )

        try:
            client = await self._connection._ensure_connection()
            await self._select_folder("INBOX")

            from src.core.database import get_database

            db = get_database(self.config_manager)

            search_start = time.time()
            email_uids = await self._search_emails(client, sync_mode, db)
            search_duration = time.time() - search_start

            if not email_uids:
                logger.info(
                    "No new emails found",
                    extra={
                        "sync_mode": sync_mode.value,
                        "search_duration": round(search_duration, 2),
                    },
                )
                return 0

            logger.info(
                "Found new emails to fetch",
                extra={
                    "email_count": len(email_uids),
                    "sync_mode": sync_mode.value,
                    "search_duration": round(search_duration, 2),
                },
            )
            emails_to_save = []
            failed_count = 0
            parse_failures = 0

            fetch_start = time.time()
            for i in range(0, len(email_uids), BatchSizes.IMAP_FETCH_BATCH):
                batch = email_uids[i : i + BatchSizes.IMAP_FETCH_BATCH]
                batch_start = time.time()

                for email_uid in batch:
                    try:
                        raw_email = await self._fetch_email(client, email_uid)
                        if not raw_email:
                            failed_count += 1
                            continue

                        email_dict = EmailParser.parse_from_bytes(
                            raw_email, str(email_uid), strict=False
                        )

                        if email_dict is None:
                            logger.warning(f"Skipping malformed email UID {email_uid}")
                            parse_failures += 1
                            failed_count += 1
                            continue

                        if sync_mode == SyncMode.INCREMENTAL:
                            if await db.email_exists("emails", email_dict["uid"]):
                                continue

                        emails_to_save.append(email_dict)

                    except Exception as e:
                        logger.error(
                            "Failed to process email UID",
                            extra={
                                "email_uid": email_uid,
                                "error": str(e),
                                "error_type": type(e).__name__,
                            },
                        )
                        failed_count += 1
                        continue

                batch_duration = time.time() - batch_start
                logger.debug(
                    "Processed batch",
                    extra={
                        "batch_size": len(batch),
                        "duration_seconds": round(batch_duration, 2),
                        "emails_per_second": round(len(batch) / batch_duration, 2),
                    },
                )

                if i + BatchSizes.IMAP_FETCH_BATCH < len(email_uids):
                    await asyncio.sleep(BatchSizes.IMAP_FETCH_DELAY)

            fetch_duration = time.time() - fetch_start

            if emails_to_save:
                save_start = time.time()
                saved_count = await db.save_emails_batch(
                    "inbox", emails_to_save, batch_size=BatchSizes.DB_SAVE_BATCH
                )
                save_duration = time.time() - save_start
                total_duration = time.time() - start_time

                logger.info(
                    "Fetched and saved new emails",
                    extra={
                        "saved": saved_count,
                        "failed": failed_count,
                        "parse_failures": parse_failures,
                        "fetch_duration": round(fetch_duration, 2),
                        "save_duration": round(save_duration, 2),
                        "total_duration": round(total_duration, 2),
                        "emails_per_second": round(saved_count / total_duration, 1)
                        if total_duration > 0
                        else 0,
                    },
                )

                return saved_count
            else:
                logger.info(
                    "No new emails to save",
                    extra={
                        "total_found": len(email_uids),
                        "failed": failed_count,
                        "duration": round(time.time() - start_time, 2),
                    },
                )
                return 0

        except (IMAPError, NetworkError, NetworkTimeoutError):
            raise

        except Exception as e:
            logger.exception(
                "Unexpected error fetching emails",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "duration": round(time.time() - start_time, 2),
                },
            )
            raise IMAPError(
                "Failed to fetch emails from server", details={"error": str(e)}
            ) from e

    async def _search_emails(
        self, client: aioimaplib.IMAP4_SSL, sync_mode: SyncMode, db
    ) -> List[bytes]:
        """Search for new emails based on sync mode.

        Args:
            client: IMAP client instance
            sync_mode: Synchronization mode
            db: Database instance

        Returns:
            List of email UIDs to fetch

        Raises:
            asyncio.TimeoutError: If search operation times out
        """
        try:
            if sync_mode == SyncMode.FULL:
                response = await asyncio.wait_for(
                    client.uid_search("ALL"), timeout=Timeouts.IMAP_SEARCH
                )
            else:
                highest_uid = await db.get_highest_uid()
                if highest_uid:
                    response = await asyncio.wait_for(
                        client.uid_search(f"(UID {highest_uid + 1}:*)"),
                        timeout=Timeouts.IMAP_SEARCH,
                    )
                else:
                    response = await asyncio.wait_for(
                        client.uid_search("ALL"), timeout=Timeouts.IMAP_SEARCH
                    )

            self._connection._check_response(response, "search emails")

            uid_data = response.lines[0] if response.lines else b""
            if not uid_data or uid_data == b"":
                return []

            uid_str = (
                uid_data.decode() if isinstance(uid_data, bytes) else str(uid_data)
            )
            email_uids = [int(uid) for uid in uid_str.split() if uid.strip().isdigit()]

            return email_uids

        except asyncio.TimeoutError as e:
            raise NetworkTimeoutError("IMAP search operation timeout") from e

        except Exception as e:
            raise IMAPError(f"Failed to search emails: {str(e)}") from e

    async def _fetch_email(
        self, client: aioimaplib.IMAP4_SSL, email_uid: int
    ) -> Optional[bytes]:
        """Fetch a single email by UID from the server.

        Args:
            client: IMAP client instance
            email_uid: UID of the email to fetch

        Returns:
            Raw email bytes or None if fetch fails

        Raises:
            asyncio.TimeoutError: If fetch operation times out
        """
        try:
            start_time = time.time()
            response = await asyncio.wait_for(
                client.uid("fetch", str(email_uid), "(RFC822)"),
                timeout=Timeouts.IMAP_FETCH,
            )
            duration = time.time() - start_time

            if response.result != IMAPResponse.OK:
                logger.warning(
                    "Failed to fetch email",
                    extra={"uid": email_uid, "duration": round(duration, 3)},
                )
                return None

            raw_email = None

            for line in response.lines:
                if isinstance(line, bytes) and len(line) > 100:
                    raw_email = line
                    break

            if not raw_email:
                logger.warning("Empty email data received", extra={"uid": email_uid})
                return None

            logger.debug(
                "Fetched email",
                extra={
                    "uid": email_uid,
                    "size_bytes": len(raw_email),
                    "duration": round(duration, 3),
                },
            )

            return raw_email

        except asyncio.TimeoutError:
            logger.error("Timeout fetching email", extra={"uid": email_uid})
            return None

        except Exception as e:
            logger.error(
                "Failed to fetch email", extra={"uid": email_uid, "error": str(e)}
            )
            return None

    ## Email Operations

    async def _store_flags(
        self, email_uid: str, operation: str, flags: str, add: bool = True
    ) -> bool:
        """Generic flag store operation for emails.

        Args:
            email_uid: UID of the email
            operation: Description of the operation (for logging)
            flags: Flags to store (e.g., r"(\Seen)")
            add: Whether to add or remove the flags

        Returns:
            True if operation succeeded, False otherwise

        Raises:
            IMAPError: If store operation fails
        """
        try:
            client = await self._connection._ensure_connection()
            await self._select_folder("INBOX")

            flag_op = "+FLAGS" if add else "-FLAGS"
            response = await asyncio.wait_for(
                client.uid("STORE", email_uid, flag_op, flags),
                timeout=Timeouts.IMAP_STORE,
            )

            self._connection._check_response(
                response, f"{operation} for UID {email_uid}"
            )
            logger.info(f"{operation.capitalize()} email UID {email_uid} successfully")
            return True

        except IMAPError:
            raise

        except Exception as e:
            logger.exception(f"Error in {operation} for UID {email_uid}: {str(e)}")
            return False

    ## Email Deletion

    @async_log_call
    async def delete_email(self, email_uid: str) -> bool:
        """Delete an email by UID on the server.

        Args:
            email_uid: UID of the email to delete

        Returns:
            True if deletion succeeded, False otherwise
        """
        try:
            if not await self._store_flags(
                email_uid, "mark for deletion", r"(\Deleted)"
            ):
                return False

            client = await self._connection._ensure_connection()
            response = await asyncio.wait_for(
                client.expunge(), timeout=Timeouts.IMAP_EXPUNGE
            )

            self._connection._check_response(
                response, f"expunge after delete UID {email_uid}"
            )
            logger.info(f"Deleted email UID {email_uid} from IMAP server")
            return True

        except Exception as e:
            logger.exception(
                f"Unexpected error deleting email UID {email_uid}: {str(e)}"
            )
            return False

    ## Mark as Read/Unread

    @async_log_call
    async def update_read_status(self, email_uid: str, read: bool = True) -> bool:
        """Mark an email as read or unread by UID on the server.

        Args:
            email_uid: UID of the email
            read: True to mark as read, False to mark as unread

        Returns:
            True if operation succeeded, False otherwise
        """
        return await self._store_flags(
            email_uid, f"mark as {'read' if read else 'unread'}", r"(\Seen)", add=read
        )

    ## Flag/Unflag Emails

    @async_log_call
    async def update_flag_status(self, email_uid: str, flagged: bool = True) -> bool:
        """Flag or unflag an email by UID on the server.

        Args:
            email_uid: UID of the email
            flagged: True to flag, False to unflag

        Returns:
            True if operation succeeded, False otherwise
        """
        return await self._store_flags(
            email_uid, f"{'flag' if flagged else 'unflag'}", r"(\Flagged)", add=flagged
        )

    ## Move Emails

    @async_log_call
    async def move_email(self, email_uid: str, dest_folder: str) -> bool:
        """Move an email by UID to another folder on the server.

        Args:
            email_uid: UID of the email
            dest_folder: Destination folder name

        Returns:
            True if move succeeded, False otherwise
        """
        try:
            client = await self._connection._ensure_connection()
            await self._select_folder("INBOX")

            # Copy email to destination folder
            response = await asyncio.wait_for(
                client.uid("copy", email_uid, dest_folder), timeout=Timeouts.IMAP_COPY
            )

            self._connection._check_response(
                response, f"copy email UID {email_uid} to {dest_folder}"
            )

            # Mark original email as deleted using flag store operation
            if not await self._store_flags(
                email_uid, "mark for deletion in move", r"(\Deleted)"
            ):
                logger.warning(
                    f"Failed to mark source email UID {email_uid} for deletion after copy"
                )
                return False

            # Expunge the marked email
            response = await asyncio.wait_for(
                client.expunge(), timeout=Timeouts.IMAP_EXPUNGE
            )

            self._connection._check_response(
                response, f"expunge after move UID {email_uid}"
            )
            logger.info(f"Moved email UID {email_uid} to {dest_folder} on IMAP server")
            return True

        except Exception as e:
            logger.exception(
                f"Unexpected error moving email UID {email_uid} to folder {dest_folder}: {str(e)}"
            )
            return False

    ## Folder Management

    @async_log_call
    async def get_folder_list(self) -> List[str]:
        """Retrieve the list of folders from the IMAP server.

        Returns:
            List of folder names

        Raises:
            IMAPError: If retrieval fails
        """
        try:
            client = await self._connection._ensure_connection()

            response = await asyncio.wait_for(client.list(), timeout=Timeouts.IMAP_LIST)

            self._connection._check_response(response, "list folders")

            import re

            folders = []
            for line in response.lines[:-1]:
                line_str = line.decode("utf-8") if isinstance(line, bytes) else line
                match = re.search(r'"([^"]+)"$', line_str)
                if match:
                    folders.append(match.group(1))

            logger.debug(f"Retrieved {len(folders)} folders from IMAP server")
            return folders

        except Exception as e:
            logger.error(f"Failed to retrieve folder list: {str(e)}")
            raise IMAPError(
                "Failed to retrieve folder list from server", details={"error": str(e)}
            ) from e

    @async_log_call
    async def get_folder_status(self, folder: str = "INBOX") -> dict:
        """Get status of a folder from the IMAP server.

        Args:
            folder: Folder name to get status for

        Returns:
            Dictionary with folder status details

        Raises:
            IMAPError: If retrieval fails
        """
        try:
            client = await self._connection._ensure_connection()

            response = await asyncio.wait_for(
                client.status(folder, "(MESSAGES UNSEEN RECENT)"),
                timeout=Timeouts.IMAP_STATUS,
            )

            self._connection._check_response(
                response, f"get status for folder '{folder}'"
            )

            status = {}
            if response.lines:
                line = response.lines[0]
                if isinstance(line, bytes):
                    line = line.decode("utf-8")

                import re

                messages_match = re.search(r"MESSAGES (\d+)", line)
                unseen_match = re.search(r"UNSEEN (\d+)", line)
                recent_match = re.search(r"RECENT (\d+)", line)

                if messages_match:
                    status["messages"] = int(messages_match.group(1))
                else:
                    status["messages"] = 0
                if unseen_match:
                    status["unseen"] = int(unseen_match.group(1))
                else:
                    status["unseen"] = 0
                if recent_match:
                    status["recent"] = int(recent_match.group(1))
                else:
                    status["recent"] = 0

            logger.debug(f"Folder {folder} status: {status}")
            return status

        except Exception as e:
            logger.error(f"Failed to retrieve status for folder {folder}: {str(e)}")
            raise IMAPError(
                f"Failed to retrieve status for folder {folder}",
                details={"error": str(e)},
            ) from e


## IMAP Client Factory


def get_imap_client(config) -> IMAPClient:
    """Get an IMAP client instance.

    Args:
        config: Configuration object

    Returns:
        Configured IMAPClient instance
    """
    return IMAPClient(config)
