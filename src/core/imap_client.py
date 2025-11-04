"""IMAP client for email operations - fetch, delete, and synchronization."""

import aioimaplib
import asyncio
from enum import Enum
from typing import List, Optional

from src.core.email_handling import EmailParser
from src.utils.error_handling import (
    IMAPError,
    NetworkError,
    NetworkTimeoutError
)
from src.utils.log_manager import async_log_call, get_logger
from .imap_connection import IMAPConnection

logger = get_logger(__name__)


class SyncMode(Enum):
    """Synchronization modes for IMAP client."""

    INCREMENTAL = "incremental"
    FULL = "full"


class IMAPClient:
    """Asynchronous IMAP client for email operations."""

    RESONSE_OK = "OK"
    RESONSE_NO = "NO"
    RESONSE_BAD = "BAD"

    def __init__(self, config_manager):
        """Initialize IMAP client with config manager."""

        self.config_manager = config_manager
        self._connection = IMAPConnection(config_manager)
        self._selected_folder = None

    def _check_response(self, response, operation: str) -> None:
        """Check IMAP response and raise error if not OK."""
        
        if response.result != self.RESONSE_OK:
            error_msg = response.lines[0] if response.lines else "No response"
            if isinstance(error_msg, bytes):
                error_msg = error_msg.decode()
            
            raise IMAPError(
                f"IMAP operation failed: {operation}",
                details={"response": str(error_msg)}
            )

    async def _ensure_connection(self) -> aioimaplib.IMAP4_SSL:
        """Ensure IMAP connection is established and valid."""

        return await self._connection._ensure_connection()

    async def _select_folder(self, folder: str = "INBOX") -> None:
        """Select IMAP folder if not already selected."""

        if self._selected_folder != folder:
            client = await self._ensure_connection()

            response = await asyncio.wait_for(
                client.select(folder),
                timeout=10.0
            )

            self._check_response(response, f"select folder '{folder}'")

            self._selected_folder = folder
            logger.debug(f"Selected IMAP folder: {folder}")


    ## Email Fetching

    @async_log_call
    async def fetch_new_emails(self, sync_mode: SyncMode = SyncMode.INCREMENTAL) -> int:
        """Fetch new emails from the IMAP server with batch saving."""

        try:
            client = await self._ensure_connection()
            await self._select_folder("INBOX")

            from src.core.database import get_database
            db = get_database(self.config_manager)

            email_uids = await self._search_emails(client, sync_mode, db)
            if not email_uids:
                logger.info("No new emails found.")
                return 0

            logger.info(f"Found {len(email_uids)} new emails to fetch.")
            emails_to_save = 0
            failed_count = 0

            fetch_batch_size = 50
            for i in range(0, len(email_uids), fetch_batch_size):
                batch = email_uids[i:i + fetch_batch_size]

                for email_uid in batch:
                    try:
                        raw_email = await self._fetch_email(client, email_uid)
                        if not raw_email:
                            failed_count += 1
                            continue

                        email_dict = EmailParser.parse_from_bytes(raw_email, str(email_uid))

                        if sync_mode == SyncMode.INCREMENTAL:
                            if await db.email_exists("emails", email_dict["uid"]):
                                continue
                        
                        emails_to_save.append(email_dict)

                    except Exception as e:
                        logger.error(f"Failed to process email UID {email_uid}: {str(e)}")
                        failed_count += 1
                        continue

                if i + fetch_batch_size < len(email_uids):
                    await asyncio.sleep(0.1)

            if emails_to_save:
                logger.info(f"Saving {len(emails_to_save)} new emails to database...")
                saved_count = await db.save_emails_batch("inbox", emails_to_save, batch_size=100)

                logger.info(
                    f"Successfully saved {saved_count} new email(s)."
                    f"({failed_count}) email(s) failed to fetch."
                )

                return saved_count
            else:
                logger.info("No new emails to save.")
                return 0

        except (IMAPError, NetworkError, NetworkTimeoutError):
            raise

        except Exception as e:
            logger.exception(f"Unexpected error fetching emails: {str(e)}")
            raise IMAPError(
                "Failed to fetch emails from server",
                details={"error": str(e)}
            ) from e

    async def _search_emails(self, client: aioimaplib.IMAP4_SSL, sync_mode: SyncMode, db) -> List[bytes]:
        """Search for new emails based on sync mode."""

        try:
            if sync_mode == SyncMode.FULL:
                response = await asyncio.wait_for(
                    client.uid_search("ALL"),
                    timeout=30.0
                )
            else:
                highest_uid = await db.get_highest_uid()
                if highest_uid:
                    response = await asyncio.wait_for(
                        client.uid_search(f"(UID {highest_uid + 1}:*)"),
                        timeout=30.0
                    )
                else:
                    response = await asyncio.wait_for(
                        client.uid_search("ALL"),
                        timeout=30.0
                    )
            
            self._check_response(response, "search emails")

            uid_data = response.lines[0] if response.lines else b""
            if not uid_data or uid_data == b'':
                return []

            uid_str = uid_data.decode() if isinstance(uid_data, bytes) else str(uid_data)
            email_uids = [int(uid) for uid in uid_str.split() if uid.strip()]

            return email_uids     
        
        except asyncio.TimeoutError as e:
            raise NetworkTimeoutError("IMAP search timeout") from e

        except Exception as e:
            raise IMAPError(f"Failed to search emails: {str(e)}") from e

    async def _fetch_email(self, client: aioimaplib.IMAP4_SSL, email_uid: int) -> Optional[bytes]:
        """Fetch a single email by UID from the server."""

        try:
            response = await asyncio.wait_for(
                client.uid("fetch", str(email_uid), "(RFC822)"),
                timeout=30.0
            )

            if response.result != self.RESONSE_OK:
                logger.warning(f"Failed to fetch email {email_uid}: {response.lines[0] if response.lines else 'No response'}")
                return None

            raw_email = None

            for line in response.lines:
                if isinstance(line, bytes) and len(line) > 100:
                    raw_email = line
                    break

            if not raw_email:
                logger.warning(f"Empty data for email {email_uid}")
                return None

            return raw_email

        except asyncio.TimeoutError as e:
            logger.error(f"Timeout fetching email {email_uid}: {str(e)}")
            return None
                
        except Exception as e:
            logger.error(f"Failed to fetch email {email_uid}: {str(e)}")
            return None
    

    ## Email Operations

    async def _store_flags(self, email_uid: str, operation: str, flags: str, add: bool = True) -> bool:
        """Generic flag store operation for emails."""
        
        try:
            client = await self._ensure_connection()
            await self._select_folder("INBOX")

            flag_op = "+FLAGS" if add else "-FLAGS"
            response = await asyncio.wait_for(
                client.uid("STORE", email_uid, flag_op, flags),
                timeout=10.0
            )

            self._check_response(response, f"{operation} for UID {email_uid}")
            logger.info(f"{operation.capitalize()} email UID {email_uid} successfully.")
            return True

        except IMAPError:
            raise

        except Exception as e:
            logger.exception(f"Error in {operation} for UID {email_uid}: {str(e)}")
            return False


    ## Email Deletion

    @async_log_call
    async def delete_email(self, email_uid: str) -> bool:
        """Delete an email by UID on the server."""

        try:
            if not await self._store_flags(email_uid, "mark for deletion", r"(\Deleted)"):
                return False

            client = await self._ensure_connection()
            response = await asyncio.wait_for(
                client.expunge(),
                timeout=10.0
            )

            self._check_response(response, f"expunge after delete UID {email_uid}")
            logger.info(f"Deleted email UID {email_uid} from IMAP server.")
            return True

        except Exception as e:
            logger.exception(f"Unexpected error deleting email UID {email_uid}: {str(e)}")
            return False


    ## Mark as Read/Unread

    @async_log_call
    async def update_read_status(self, email_uid: str, read: bool = True) -> bool:
        """Mark an email as read or unread by UID on the server."""

        return await self._store_flags(
            email_uid,
            f"mark as {'read' if read else 'unread'}",
            r"(\Seen)",
            add=read
        )


    ## Flag/Unflag Emails

    @async_log_call
    async def update_flag_status(self, email_uid: str, flagged: bool = True) -> bool:
        """Flag or unflag an email by UID on the server."""

        return await self._store_flags(
            email_uid,
            f"{'flag' if flagged else 'unflag'}",
            r"(\Flagged)",
            add=flagged
        )

    ## Move Emails

    @async_log_call
    async def move_email(self, email_uid: str, dest_folder: str) -> bool:
        """Move an email by UID to another folder on the server."""

        try:
            client = await self._ensure_connection()
            await self._select_folder("INBOX")

            # Copy email to destination folder
            response = await asyncio.wait_for(
                client.uid("copy", email_uid, dest_folder),
                timeout=10.0
            )

            self._check_response(response, f"copy email UID {email_uid} to {dest_folder}")

            # Mark original email as deleted using flag store operation
            if not await self._store_flags(email_uid, "mark for deletion in move", r"(\Deleted)"):
                logger.warning(f"Failed to mark source email UID {email_uid} for deletion after copy")
                return False

            # Expunge the marked email
            response = await asyncio.wait_for(
                client.expunge(),
                timeout=10.0
            )

            self._check_response(response, f"expunge after move UID {email_uid}")
            logger.info(f"Moved email UID {email_uid} to {dest_folder} on IMAP server.")
            return True

        except Exception as e:
            logger.exception(f"Unexpected error moving email UID {email_uid} to folder {dest_folder}: {str(e)}")
            return False
        
    
    ## Folder Management

    @async_log_call
    async def get_folder_list(self) -> List[str]:
        """Retrieve the list of folders from the IMAP server."""

        try:
            client = await self._ensure_connection()

            response = await asyncio.wait_for(
                client.list('""', '*'),
                timeout=10.0
            )

            self._check_response(response, "list folders")

            folders = []
            for line in response.lines:
                if isinstance(line, bytes):
                    line = line.decode("utf-8")
                
                if '""' in line:
                    parts = line.split('""')
                    if len(parts) >= 4:
                        folder_name = parts[3].strip().strip('"')
                        folders.append(folder_name)

            logger.info(f"Retrieved {len(folders)} folders from IMAP server.")
            return folders

        except Exception as e:
            logger.exception(f"Unexpected error retrieving folder list: {str(e)}")
            raise IMAPError(
                "Failed to retrieve folder list from server",
                details={"error": str(e)}
            ) from e

    @async_log_call
    async def get_folder_status(self, folder: str = "INBOX") -> dict:
        """Get status of a folder from the IMAP server."""

        try:
            client = await self._ensure_connection()

            response = await asyncio.wait_for(
                client.status(folder, "(MESSAGES UNSEEN RECENT)"),
                timeout=10.0
            )

            self._check_response(response, f"get status for folder '{folder}'")

            status = {}
            if response.lines:
                line = response.lines[0]
                if isinstance(line, bytes):
                    line = line.decode("utf-8")
                
                import re
                messages_match = re.search(r'MESSAGES (\d+)', line)
                unseen_match = re.search(r'UNSEEN (\d+)', line)
                recent_match = re.search(r'RECENT (\d+)', line)

                if messages_match:
                    status["messages"] = int(messages_match.group(1))
                if unseen_match:
                    status["unseen"] = int(unseen_match.group(1))
                if recent_match:
                    status["recent"] = int(recent_match.group(1))

            logger.info(f"Retrieved status for folder {folder}: {status}")
            return status
        
        except Exception as e:
            logger.exception(f"Unexpected error retrieving status for folder {folder}: {str(e)}")
            raise IMAPError(
                f"Failed to retrieve status for folder {folder}",
                details={"error": str(e)}
            ) from e


## IMAP Client Factory

def get_imap_client(config_manager) -> IMAPClient:
    """Get an IMAP client instance."""

    return IMAPClient(config_manager)
