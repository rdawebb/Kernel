"""Email fetch service - orchestrates email synchronisation"""

import asyncio
import time
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional

from src.core.database import EmailRepository
from src.core.email.imap.client import IMAPClient
from src.core.email.imap.protocol import IMAPProtocol
from src.core.email.parser import EmailParser
from src.core.models.email import Email, FolderName
from src.utils.logging import async_log_call, get_logger

logger = get_logger(__name__)


class SyncMode(Enum):
    """Email synchronization mode."""

    INCREMENTAL = "incremental"  # Fetch only new emails since last sync
    FULL = "full"  # Fetch all emails from server


@dataclass
class FetchStats:
    """Statistics for email fetch operation."""

    saved_count: int = 0
    updated_count: int = 0
    failed_count: int = 0
    parse_failures: int = 0
    total_duration: float = 0.0
    emails_fetched: int = 0

    def total_processed(self) -> int:
        """Total emails processed (saved + updated + failed)."""
        return self.saved_count + self.updated_count + self.failed_count

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        total = self.total_processed()
        if total == 0:
            return 0.0
        return (self.saved_count + self.updated_count) / total * 100


class EmailFetchService:
    """Service for fetching and syncing emails from IMAP server."""

    def __init__(
        self,
        protocol: IMAPProtocol,
        repository: EmailRepository,
        batch_size: int = 50,
        batch_delay: float = 0.0,
    ):
        """Initialise email fetch service.

        Args:
            protocol: IMAPProtocol instance for IMAP operations
            repository: EmailRepository for database operations
            batch_size: Number of emails to fetch per batch (default: 50)
            batch_delay: Delay in seconds between batches (default: 0.0)
        """
        self._protocol = protocol
        self._repository = repository
        self.batch_size = batch_size
        self.batch_delay = batch_delay

        self._imap_client = IMAPClient(protocol)

    @property
    def client(self) -> IMAPClient:
        """Get IMAP client for direct email operations.

        Provides access to user-facing operations like
        delete, flag, move, etc.

        Returns:
            IMAPClient instance
        """
        return self._imap_client

    @async_log_call
    async def fetch_new_emails(
        self,
        folder: FolderName = FolderName.INBOX,
        sync_mode: SyncMode = SyncMode.INCREMENTAL,
        cancel_token: Optional[asyncio.Event] = None,
    ) -> FetchStats:
        """Fetch new emails from server and save to database.

        Args:
            folder: Folder to sync (default: INBOX)
            sync_mode: Synchronization mode (INCREMENTAL or FULL)
            cancel_token: Optional event to signal cancellation

        Returns:
            FetchStats with operation statistics
        """
        stats = FetchStats()
        start_time = time.time()

        logger.info(
            "Starting email fetch",
            extra={
                "folder": folder.value,
                "sync_mode": sync_mode.value,
            },
        )

        try:
            uids = await self._get_uids_to_fetch(folder, sync_mode)

            if not uids:
                logger.info(
                    "No new emails found",
                    extra={"folder": folder.value, "sync_mode": sync_mode.value},
                )
                stats.total_duration = time.time() - start_time
                return stats

            logger.info(
                f"Found {len(uids)} emails to fetch",
                extra={"folder": folder.value, "count": len(uids)},
            )

            for batch_start in range(0, len(uids), self.batch_size):
                if cancel_token and cancel_token.is_set():
                    logger.info("Email fetch cancelled by user")
                    break

                batch_uids = uids[batch_start : batch_start + self.batch_size]

                logger.debug(
                    f"Processing batch {batch_start // self.batch_size + 1}",
                    extra={
                        "batch_size": len(batch_uids),
                        "progress": f"{batch_start + len(batch_uids)}/{len(uids)}",
                    },
                )

                raw_emails = await self._protocol.fetch_messages(batch_uids)
                stats.emails_fetched += len(raw_emails)

                parsed_emails = self._parse_batch(raw_emails, stats)

                await self._save_batch(parsed_emails, folder, stats)

                # Delay between batches if configured
                if batch_start + self.batch_size < len(uids) and self.batch_delay > 0:
                    await asyncio.sleep(self.batch_delay)

            stats.total_duration = time.time() - start_time

            logger.info(
                "Email fetch completed",
                extra={
                    "folder": folder.value,
                    "new": stats.saved_count,
                    "updated": stats.updated_count,
                    "failed": stats.failed_count,
                    "parse_failures": stats.parse_failures,
                    "duration": round(stats.total_duration, 2),
                    "success_rate": round(stats.success_rate, 1),
                },
            )

            return stats

        except Exception as e:
            logger.exception(
                "Unexpected error during email fetch",
                extra={
                    "folder": folder.value,
                    "error": str(e),
                    "duration": round(time.time() - start_time, 2),
                },
            )
            raise

    async def _get_uids_to_fetch(
        self,
        folder: FolderName,
        sync_mode: SyncMode,
    ) -> List[int]:
        """Determine which UIDs to fetch based on sync mode.

        Args:
            folder: Folder to search in
            sync_mode: Synchronization mode

        Returns:
            List of UIDs to fetch (sorted ascending)
        """
        search_start = time.time()

        await self._protocol.select_folder(folder.value.upper())

        # Determine search criteria
        if sync_mode == SyncMode.FULL:
            criteria = "ALL"
        else:
            highest_uid = await self._repository.get_highest_uid(folder)

            if highest_uid == 0:
                # No emails in database, fetch all
                criteria = "ALL"
            else:
                # Fetch only emails after the highest UID
                criteria = f"UID {highest_uid + 1}:*"

        uids = await self._protocol.search_uids(criteria)

        search_duration = time.time() - search_start
        logger.info(
            "UID search completed",
            extra={
                "folder": folder.value,
                "criteria": criteria,
                "count": len(uids),
                "duration": round(search_duration, 2),
            },
        )

        return uids

    def _parse_batch(
        self,
        raw_emails: Dict[int, bytes],
        stats: FetchStats,
    ) -> List[Email]:
        """Parse raw emails into Email domain objects.

        Args:
            raw_emails: Dictionary mapping UID -> raw email bytes
            stats: Statistics tracker (updated in-place)

        Returns:
            List of successfully parsed Email objects
        """
        parsed_emails = []

        for uid, raw_bytes in raw_emails.items():
            try:
                # Parse with lenient mode (returns None for malformed emails)
                email = EmailParser.parse_from_bytes(
                    raw_bytes,
                    str(uid),
                    strict=False,
                )

                if email is None:
                    logger.warning(
                        "Skipping malformed email",
                        extra={"uid": uid},
                    )
                    stats.parse_failures += 1
                    stats.failed_count += 1
                    continue

                parsed_emails.append(email)

            except Exception as e:
                logger.error(
                    "Unexpected error parsing email",
                    extra={"uid": uid, "error": str(e)},
                )
                stats.parse_failures += 1
                stats.failed_count += 1

        logger.debug(
            "Parsed email batch",
            extra={
                "total": len(raw_emails),
                "success": len(parsed_emails),
                "failures": stats.parse_failures,
            },
        )

        return parsed_emails

    async def _save_batch(
        self,
        emails: List[Email],
        folder: FolderName,
        stats: FetchStats,
    ) -> None:
        """Save emails to database, tracking new vs updated.

        Args:
            emails: List of Email objects to save
            folder: Folder to save emails to
            stats: Statistics tracker (updated in-place)
        """
        if not emails:
            logger.debug("No emails to save in batch")
            return

        try:
            uids = [email.id.value for email in emails]
            exists_map = await self._repository.exists_batch(uids, folder)

            for email in emails:
                try:
                    email.folder = folder

                    already_exists = exists_map.get(email.id.value, False)

                    await self._repository.save(email)

                    if already_exists:
                        stats.updated_count += 1
                    else:
                        stats.saved_count += 1

                except Exception as e:
                    logger.error(
                        "Failed to save individual email",
                        extra={"uid": email.id.value, "error": str(e)},
                    )
                    stats.failed_count += 1

            logger.debug(
                "Saved email batch",
                extra={
                    "new": stats.saved_count,
                    "updated": stats.updated_count,
                    "failed": stats.failed_count,
                },
            )

        except Exception as e:
            logger.error(f"Failed to save email batch: {e}")
            # If batch save fails completely, count all as failed
            stats.failed_count += len(emails)

    async def get_folder_stats(self, folder: FolderName) -> Dict[str, int]:
        """Get statistics for a folder (both server and local).

        Args:
            folder: Folder to get statistics for

        Returns:
            Dictionary with statistics:
            - server_total: Total emails on server
            - server_unread: Unread emails on server
            - local_total: Total emails in local database
            - local_unread: Unread emails in local database
            - sync_needed: Approximate number of emails to sync
        """
        try:
            server_status = await self._protocol.get_folder_status(folder.value.upper())
            server_total = server_status.get("MESSAGES", 0)
            server_unread = server_status.get("UNSEEN", 0)

            local_total = await self._repository.count(folder)
            local_unread = await self._repository.count(
                folder,
                conditions={"is_read": False},
            )

            # Estimate sync needed
            sync_needed = max(0, server_total - local_total)

            return {
                "server_total": server_total,
                "server_unread": server_unread,
                "local_total": local_total,
                "local_unread": local_unread,
                "sync_needed": sync_needed,
            }

        except Exception as e:
            logger.error(f"Failed to get folder stats: {e}")
            return {
                "server_total": 0,
                "server_unread": 0,
                "local_total": 0,
                "local_unread": 0,
                "sync_needed": 0,
            }
