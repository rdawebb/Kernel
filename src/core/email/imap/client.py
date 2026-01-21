"""IMAP client for high-level email operations."""

from typing import Dict, List

from src.core.email.imap.protocol import IMAPProtocol
from src.utils.logging import async_log_call, get_logger

logger = get_logger(__name__)


class IMAPClient:
    """High-level IMAP email operations."""

    def __init__(self, protocol: IMAPProtocol):
        """Initialise IMAP client.

        Args:
            protocol: IMAPProtocol instance for low-level operations
        """
        self.protocol = protocol

    @async_log_call
    async def delete_email(self, email_uid: str, folder: str = "INBOX") -> bool:
        """Delete an email by UID.

        This permanently deletes the email by:
        1. Marking it with the \\Deleted flag
        2. Expunging to remove it from the server

        Args:
            email_uid: UID of the email to delete
            folder: Folder containing the email (default: INBOX)

        Returns:
            True if deletion succeeded, False otherwise
        """
        try:
            await self.protocol.select_folder(folder)

            # Mark as deleted
            if not await self.protocol.set_flags(email_uid, ["\\Deleted"], add=True):
                logger.warning(f"Failed to mark email {email_uid} as deleted")
                return False

            # Permanently remove
            if not await self.protocol.expunge():
                logger.warning(f"Failed to expunge deleted email {email_uid}")
                return False

            logger.info(f"Successfully deleted email {email_uid}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete email {email_uid}: {e}")
            return False

    @async_log_call
    async def mark_as_read(self, email_uid: str, folder: str = "INBOX") -> bool:
        """Mark an email as read.

        Args:
            email_uid: UID of the email
            folder: Folder containing the email (default: INBOX)

        Returns:
            True if successful, False otherwise
        """
        try:
            await self.protocol.select_folder(folder)
            result = await self.protocol.set_flags(email_uid, ["\\Seen"], add=True)

            if result:
                logger.debug(f"Marked email {email_uid} as read")

            return result

        except Exception as e:
            logger.error(f"Failed to mark email {email_uid} as read: {e}")
            return False

    @async_log_call
    async def mark_as_unread(self, email_uid: str, folder: str = "INBOX") -> bool:
        """Mark an email as unread.

        Args:
            email_uid: UID of the email
            folder: Folder containing the email (default: INBOX)

        Returns:
            True if successful, False otherwise
        """
        try:
            await self.protocol.select_folder(folder)
            result = await self.protocol.set_flags(email_uid, ["\\Seen"], add=False)

            if result:
                logger.debug(f"Marked email {email_uid} as unread")

            return result

        except Exception as e:
            logger.error(f"Failed to mark email {email_uid} as unread: {e}")
            return False

    @async_log_call
    async def flag_email(self, email_uid: str, folder: str = "INBOX") -> bool:
        """Flag an email for follow-up.

        Args:
            email_uid: UID of the email
            folder: Folder containing the email (default: INBOX)

        Returns:
            True if successful, False otherwise
        """
        try:
            await self.protocol.select_folder(folder)
            result = await self.protocol.set_flags(email_uid, ["\\Flagged"], add=True)

            if result:
                logger.debug(f"Flagged email {email_uid}")

            return result

        except Exception as e:
            logger.error(f"Failed to flag email {email_uid}: {e}")
            return False

    @async_log_call
    async def unflag_email(self, email_uid: str, folder: str = "INBOX") -> bool:
        """Remove flag from an email.

        Args:
            email_uid: UID of the email
            folder: Folder containing the email (default: INBOX)

        Returns:
            True if successful, False otherwise
        """
        try:
            await self.protocol.select_folder(folder)
            result = await self.protocol.set_flags(email_uid, ["\\Flagged"], add=False)

            if result:
                logger.debug(f"Unflagged email {email_uid}")

            return result

        except Exception as e:
            logger.error(f"Failed to unflag email {email_uid}: {e}")
            return False

    @async_log_call
    async def move_to_folder(
        self,
        email_uid: str,
        dest_folder: str,
        source_folder: str = "INBOX",
    ) -> bool:
        """Move an email to another folder.

        This operation:
        1. Copies the email to the destination folder
        2. Deletes the original from the source folder

        Args:
            email_uid: UID of the email to move
            dest_folder: Destination folder name
            source_folder: Source folder name (default: INBOX)

        Returns:
            True if move succeeded, False otherwise
        """
        try:
            await self.protocol.select_folder(source_folder)

            # Copy to destination
            if not await self.protocol.copy_message(email_uid, dest_folder):
                logger.warning(f"Failed to copy email {email_uid} to {dest_folder}")
                return False

            # Delete from source
            if not await self.protocol.set_flags(email_uid, ["\\Deleted"], add=True):
                logger.warning(
                    f"Copied email {email_uid} but failed to mark original as deleted"
                )
                return False

            if not await self.protocol.expunge():
                logger.warning(
                    f"Copied email {email_uid} but failed to expunge original"
                )
                return False

            logger.info(
                f"Successfully moved email {email_uid} from {source_folder} to {dest_folder}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to move email {email_uid}: {e}")
            return False

    @async_log_call
    async def get_folders(self, pattern: str = "*") -> List[str]:
        """Get list of available folders.

        Args:
            pattern: Pattern to match folder names (default: "*" for all)

        Returns:
            List of folder names
        """
        try:
            folders = await self.protocol.get_folder_list(pattern)
            logger.debug(f"Retrieved {len(folders)} folders")

            return folders

        except Exception as e:
            logger.error(f"Failed to get folder list: {e}")
            return []

    @async_log_call
    async def get_folder_info(self, folder: str = "INBOX") -> Dict[str, int]:
        """Get folder statistics.

        Args:
            folder: Folder name to query (default: INBOX)

        Returns:
            Dictionary with folder statistics:
            - MESSAGES: Total message count
            - RECENT: Recent message count
            - UNSEEN: Unread message count
        """
        try:
            status = await self.protocol.get_folder_status(folder)
            logger.debug(f"Retrieved status for folder {folder}", extra=status)

            return status

        except Exception as e:
            logger.error(f"Failed to get folder status for {folder}: {e}")
            return {}

    @async_log_call
    async def archive_email(self, email_uid: str, source_folder: str = "INBOX") -> bool:
        """Archive an email (move to archive folder).

        Args:
            email_uid: UID of the email to archive
            source_folder: Source folder (default: INBOX)

        Returns:
            True if successful, False otherwise
        """
        archive_folder = "[Gmail]/All Mail"

        result = await self.move_to_folder(email_uid, archive_folder, source_folder)

        if not result:
            # Try generic archive folder
            archive_folder = "Archive"
            result = await self.move_to_folder(email_uid, archive_folder, source_folder)

        return result

    @async_log_call
    async def trash_email(self, email_uid: str, source_folder: str = "INBOX") -> bool:
        """Move an email to trash.

        Args:
            email_uid: UID of the email to trash
            source_folder: Source folder (default: INBOX)

        Returns:
            True if successful, False otherwise
        """
        trash_folder = "[Gmail]/Trash"

        result = await self.move_to_folder(email_uid, trash_folder, source_folder)

        if not result:
            # Try generic trash folder
            trash_folder = "Trash"
            result = await self.move_to_folder(email_uid, trash_folder, source_folder)

        return result
