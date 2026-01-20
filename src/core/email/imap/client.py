"""IMAP client for fetching emails from Gmail."""

import asyncio
import re
import time
from typing import List
from concurrent.futures import ThreadPoolExecutor

from src.core.email.parser import EmailParser
from src.core.email.imap.connection import IMAPConnection
from src.core.models.email import Email, EmailId, EmailAddress, FolderName
from src.core.models.attachment import Attachment
from src.utils.errors import IMAPError
from src.utils.logging import get_logger
from src.utils.config import ConfigManager
from enum import Enum

logger = get_logger(__name__)


class SyncMode(Enum):
    """Email synchronization mode."""

    INCREMENTAL = "incremental"
    FULL = "full"


class BatchSizes:
    """Batch size constants for email operations."""

    IMAP_FETCH_BATCH = 10
    IMAP_FETCH_DELAY = 0.5  # seconds


class IMAPClient:
    """Client for IMAP email operations using standard imaplib wrapped in async."""

    def __init__(self, config_manager: ConfigManager):
        """Initialize IMAP client.

        Args:
            config_manager: Configuration manager instance
        """
        self._connection = IMAPConnection(config_manager)
        self._selected_folder = None
        self._executor = ThreadPoolExecutor(max_workers=1)

    async def _run_in_executor(self, func, *args):
        """Run a synchronous function in the thread executor.

        Args:
            func: Function to run
            *args: Arguments to pass to the function

        Returns:
            Result from the function
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, func, *args)

    async def _select_folder(self, folder: str = "INBOX") -> None:
        """Select IMAP folder.

        Args:
            folder: Folder name to select

        Raises:
            IMAPError: If folder selection fails
        """
        if self._selected_folder != folder:
            imap_client = await self._connection._ensure_connection()
            try:
                # Use the aioimaplib client's select
                response = await imap_client.select(folder)
                if response.result != "OK":
                    raise IMAPError(f"Failed to select folder {folder}")
                self._selected_folder = folder
                logger.debug(f"Selected IMAP folder: {folder}")
            except Exception as e:
                raise IMAPError(f"IMAP error selecting folder {folder}: {e}")

    @staticmethod
    def _extract_email_address(email_str: str) -> str:
        """Extract email address from a field that may contain display name.

        Args:
            email_str: Email field that may contain "Display Name <email@domain.com>"

        Returns:
            Just the email address part, or the original string if no angle brackets
        """
        if not email_str:
            return ""

        # Handle "Display Name <email@domain.com>" format
        if "<" in email_str and ">" in email_str:
            start = email_str.rfind("<")
            end = email_str.rfind(">")
            if start < end:
                return email_str[start + 1 : end].strip()

        # Handle plain email address
        return email_str.strip()

    async def fetch_new_emails(self, sync_mode: SyncMode = SyncMode.INCREMENTAL) -> int:
        """Fetch new emails from the IMAP server.

        Args:
            sync_mode: Synchronization mode (incremental or full)

        Returns:
            Number of new emails fetched and saved
        """
        start_time = time.time()
        logger.info(
            "Starting email fetch from IMAP server",
            extra={"sync_mode": sync_mode.value},
        )

        try:
            imap_client = await self._connection._ensure_connection()
            await self._select_folder("INBOX")

            from src.core.database import EngineManager, EmailRepository
            from src.utils.paths import DATABASE_PATH

            engine_mgr = EngineManager(DATABASE_PATH)
            repo = EmailRepository(engine_mgr)

            # Search for emails
            search_start = time.time()
            try:
                if sync_mode == SyncMode.FULL:
                    response = await imap_client.uid_search("ALL")
                else:
                    highest_uid = await repo.get_highest_uid(FolderName.INBOX)
                    search_criteria = f"UID {highest_uid + 1}:*"
                    response = await imap_client.uid_search(search_criteria)

                # Parse response - aioimaplib returns space-separated UIDs in first line
                uid_data = response.lines[0] if response.lines else b""
                uid_list = uid_data.split() if uid_data else []
                email_uids = [int(uid) for uid in uid_list if uid]

            except Exception as e:
                logger.error(f"Search failed: {e}")
                await engine_mgr.close()
                return 0

            search_duration = time.time() - search_start

            if not email_uids:
                logger.info(
                    "No new emails found",
                    extra={
                        "sync_mode": sync_mode.value,
                        "search_duration": round(search_duration, 2),
                    },
                )
                await engine_mgr.close()
                return 0

            logger.info(
                "Found new emails to fetch",
                extra={
                    "email_count": len(email_uids),
                    "sync_mode": sync_mode.value,
                },
            )

            emails_to_save = []
            failed_count = 0
            parse_failures = 0

            # Fetch emails in batches
            for i in range(0, len(email_uids), BatchSizes.IMAP_FETCH_BATCH):
                batch = email_uids[i : i + BatchSizes.IMAP_FETCH_BATCH]

                for email_uid in batch:
                    try:
                        # Fetch raw email using aioimaplib
                        response = await imap_client.uid(
                            "fetch", str(email_uid), "(RFC822)"
                        )

                        if response.result != "OK" or not response.lines:
                            failed_count += 1
                            continue

                        # Extract email bytes - aioimaplib returns it in a specific format
                        raw_email = None
                        for line in response.lines:
                            if isinstance(line, bytearray):
                                raw_email = bytes(line)
                                break
                            elif isinstance(line, bytes):
                                line_str = line.decode("utf-8", errors="ignore").strip()
                                if not (
                                    line_str.startswith("*")
                                    or "FETCH" in line_str
                                    or line_str == ")"
                                    or line_str.startswith("{")
                                ):
                                    raw_email = line
                                    break

                        if not raw_email:
                            failed_count += 1
                            continue

                        # Parse email
                        email_dict = EmailParser.parse_from_bytes(
                            raw_email, str(email_uid), strict=False
                        )

                        if email_dict is None:
                            logger.warning(f"Skipping malformed email UID {email_uid}")
                            parse_failures += 1
                            failed_count += 1
                            continue

                        # Check for sender
                        sender_str = email_dict.get("sender", "")
                        if not sender_str or not sender_str.strip():
                            logger.warning(
                                f"Skipping email {email_uid} - no sender address"
                            )
                            parse_failures += 1
                            failed_count += 1
                            continue

                        emails_to_save.append(email_dict)

                    except Exception as e:
                        logger.error(
                            "Failed to process email UID",
                            extra={
                                "email_uid": email_uid,
                                "error": str(e),
                            },
                        )
                        failed_count += 1
                        continue

                # Small delay between batches
                if i + BatchSizes.IMAP_FETCH_BATCH < len(email_uids):
                    await asyncio.sleep(BatchSizes.IMAP_FETCH_DELAY)

            # Save emails
            saved_count = 0
            updated_count = 0
            if emails_to_save:
                # Batch check which UIDs already exist (single DB query instead of N queries)
                uids_to_check = [email_dict.get("uid") for email_dict in emails_to_save]
                exists_map = await repo.exists_batch(uids_to_check, FolderName.INBOX)

                for email_dict in emails_to_save:
                    try:
                        email_uid = email_dict.get("uid")
                        already_exists = exists_map.get(email_uid, False)

                        sender_str = email_dict.get("sender", "")
                        # Extract just the email address if it contains display name
                        sender_email = self._extract_email_address(sender_str)
                        sender = EmailAddress(sender_email)

                        recipient_str = email_dict.get("recipient", "")
                        recipients = []
                        if recipient_str and recipient_str.strip():
                            for addr in recipient_str.split(","):
                                addr = addr.strip()
                                if addr:
                                    try:
                                        # Extract just the email address if it contains display name
                                        recipient_email = self._extract_email_address(
                                            addr
                                        )
                                        recipients.append(EmailAddress(recipient_email))
                                    except Exception:
                                        pass

                        # Parse attachments
                        attachments = []
                        attachments_str = email_dict.get("attachments", "")
                        if attachments_str and attachments_str.strip():
                            for filename in attachments_str.split(","):
                                filename = filename.strip()
                                if filename:
                                    # Create minimal attachment object (ID and content to be filled later)
                                    try:
                                        attach = Attachment(
                                            id=f"{email_dict['uid']}-{filename}",
                                            filename=filename,
                                            content=b"",
                                        )
                                        attachments.append(attach)
                                    except Exception:
                                        pass

                        # Create Email object
                        email = Email(
                            id=EmailId(email_dict["uid"]),
                            sender=sender,
                            recipients=recipients if recipients else [sender],
                            subject=email_dict.get("subject", ""),
                            body=email_dict.get("body", ""),
                            received_at=email_dict.get("received_at"),
                            attachments=attachments,
                            folder=FolderName.INBOX,
                        )

                        await repo.save(email)

                        # Count only truly new emails, not updates
                        if already_exists:
                            updated_count += 1
                        else:
                            saved_count += 1

                    except Exception as e:
                        logger.error(
                            f"Failed to save email: {e}",
                            extra={"email_uid": email_dict.get("uid")},
                        )
                        failed_count += 1

                total_duration = time.time() - start_time
                logger.info(
                    "Fetched and saved new emails",
                    extra={
                        "new": saved_count,
                        "updated": updated_count,
                        "failed": failed_count,
                        "parse_failures": parse_failures,
                        "total_duration": round(total_duration, 2),
                    },
                )
            else:
                logger.info(
                    "No new emails to save",
                    extra={
                        "total_found": len(email_uids),
                        "failed": failed_count,
                    },
                )

            await engine_mgr.close()
            return saved_count

        except Exception as e:
            logger.exception(
                "Unexpected error fetching emails",
                extra={
                    "error": str(e),
                    "duration": round(time.time() - start_time, 2),
                },
            )
            raise IMAPError(f"Failed to fetch emails: {str(e)}") from e

    async def delete_email(self, email_uid: str) -> bool:
        """Delete an email by UID."""
        try:
            imap_client = await self._connection._ensure_connection()
            await self._select_folder("INBOX")
            response = await imap_client.uid(
                "store", str(email_uid), "+FLAGS", "(\\Deleted)"
            )
            if response.result == "OK":
                await imap_client.expunge()
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to delete email: {e}")
            return False

    async def update_read_status(self, email_uid: str, read: bool = True) -> bool:
        """Update email read status."""
        try:
            imap_client = await self._connection._ensure_connection()
            flag = "(\\Seen)" if read else ""
            response = await imap_client.uid(
                "store",
                str(email_uid),
                "+FLAGS" if read else "-FLAGS",
                flag if flag else "(\\Seen)",
            )
            return response.result == "OK"
        except Exception as e:
            logger.error(f"Failed to update read status: {e}")
            return False

    async def update_flag_status(self, email_uid: str, flagged: bool = True) -> bool:
        """Update email flag status."""
        try:
            imap_client = await self._connection._ensure_connection()
            response = await imap_client.uid(
                "store",
                str(email_uid),
                "+FLAGS" if flagged else "-FLAGS",
                "(\\Flagged)",
            )
            return response.result == "OK"
        except Exception as e:
            logger.error(f"Failed to update flag status: {e}")
            return False

    async def move_email(self, email_uid: str, dest_folder: str) -> bool:
        """Move email to another folder."""
        try:
            imap_client = await self._connection._ensure_connection()
            await self._select_folder("INBOX")

            response = await imap_client.uid("copy", str(email_uid), dest_folder)
            if response.result != "OK":
                return False

            response = await imap_client.uid(
                "store", str(email_uid), "+FLAGS", "(\\Deleted)"
            )
            if response.result == "OK":
                await imap_client.expunge()
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to move email: {e}")
            return False

    async def get_folder_list(self) -> List[str]:
        """Get list of available folders."""
        try:
            imap_client = await self._connection._ensure_connection()
            # aioimaplib.list() expects a compiled regex pattern
            response = await imap_client.list("", re.compile(".*"))
            if response.result != "OK":
                return []

            folders = []
            for mailbox in response.lines:
                if isinstance(mailbox, bytes):
                    parts = mailbox.decode().split(' "/" ')
                    if len(parts) >= 2:
                        folder_name = parts[1].strip('"')
                        folders.append(folder_name)
            return folders
        except Exception as e:
            logger.error(f"Failed to get folder list: {e}")
            return []

    async def get_folder_status(self, folder: str = "INBOX") -> dict:
        """Get status of a folder."""
        try:
            imap_client = await self._connection._ensure_connection()
            response = await imap_client.status(folder, "(MESSAGES RECENT UNSEEN)")
            if response.result != "OK":
                return {}

            status_dict = {}
            if response.lines:
                status_line = (
                    response.lines[0].decode()
                    if isinstance(response.lines[0], bytes)
                    else response.lines[0]
                )
                for part in status_line.split():
                    if part.isdigit():
                        status_dict[
                            status_line.split()[status_line.split().index(part) - 1]
                        ] = int(part)

            return status_dict
        except Exception as e:
            logger.error(f"Failed to get folder status: {e}")
            return {}
