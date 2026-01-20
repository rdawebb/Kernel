"""Email repository with SQLAlchemy Core queries."""

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, List, Optional

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.sqlite import insert

from src.core.database.engine_manager import EngineManager
from src.core.database.models import get_table
from src.core.database.query import QueryBuilder
from src.core.database.transaction import TransactionManager
from src.core.models.email import Email, EmailId, FolderName
from src.utils.errors import EmailNotFoundError
from src.utils.logging import get_logger

from .base import Repository
from .batch_result import BatchResult
from ..utils import row_to_email

logger = get_logger(__name__)


@dataclass
class EmailRepository(Repository[Email, EmailId, FolderName]):
    """Repository for Email entities using SQLAlchemy Core.

    Provides CRUD operations with:
    - Type-safe queries (no SQL injection)
    - Batch operations with progress callbacks
    - Cancellation support for long operations
    - Automatic retry on transient failures
    - Domain model conversion (Email objects, not dicts)
    """

    def __init__(self, engine_manager: EngineManager):
        """Initialize repository.

        Args:
            engine_manager: Engine manager for database access
        """
        self.engine_mgr = engine_manager
        self._query_builder = QueryBuilder()

    async def save(self, entity: Email) -> None:
        """Save single email to database.

        Args:
            email: Email domain object to save

        Raises:
            DatabaseError: If save operation fails
        """
        engine = await self.engine_mgr.get_engine()
        table = get_table(entity.folder.value)

        # Convert domain model to database row
        values = self._email_to_row(entity)

        query = insert(table).values(**values)
        query = query.on_conflict_do_update(
            index_elements=["uid"],
            set_=values,
        )

        async with engine.begin() as conn:
            await conn.execute(query)

        logger.debug(f"Saved email {entity.id.value} to {entity.folder.value}")

    async def save_batch(
        self,
        entities: List[Email],
        batch_size: int = 100,
        progress: Optional[Callable[[int, int], None]] = None,
        cancel_token: Optional[asyncio.Event] = None,
    ) -> BatchResult:
        """Save multiple emails in batches with progress tracking.

        Args:
            emails: List of emails to save
            batch_size: Number of emails per batch
            progress: Optional callback(current, total) for progress updates
            cancel_token: Optional event to signal cancellation

        Returns:
            BatchResult with operation statistics
        """
        if not entities:
            return BatchResult(total=0, succeeded=0, failed=0)

        start_time = asyncio.get_event_loop().time()
        result = BatchResult(total=len(entities), succeeded=0, failed=0)

        # Group by folder for efficiency
        by_folder: dict[FolderName, List[Email]] = {}
        for entity in entities:
            if entity.folder not in by_folder:
                by_folder[entity.folder] = []
            by_folder[entity.folder].append(entity)

        engine = await self.engine_mgr.get_engine()

        # Process each folder's emails
        for folder, folder_entities in by_folder.items():
            table = get_table(folder.value)

            # Process in batches
            for i in range(0, len(folder_entities), batch_size):
                # Check cancellation
                if cancel_token and cancel_token.is_set():
                    logger.info(
                        f"Batch operation cancelled at {result.succeeded}/{result.total}"
                    )
                    break

                batch = folder_entities[i : i + batch_size]
                batch_values = [self._email_to_row(e) for e in batch]

                try:
                    # Use transaction for atomic batch insert
                    async with TransactionManager(engine) as tx:
                        for values in batch_values:
                            query = insert(table).values(**values)
                            query = query.on_conflict_do_update(
                                index_elements=["uid"],
                                set_=values,
                            )
                            await tx.connection.execute(query)

                    result.succeeded += len(batch)

                except Exception as e:
                    result.failed += len(batch)
                    for email in batch:
                        result.errors.append((email.id, str(e)))
                    logger.error(f"Batch insert failed for {len(batch)} emails: {e}")

                # Report progress
                if progress:
                    progress(result.succeeded + result.failed, result.total)

        result.duration_seconds = asyncio.get_event_loop().time() - start_time
        logger.info(
            f"Batch save complete: {result.succeeded}/{result.total} succeeded "
            f"({result.success_rate:.1f}%) in {result.duration_seconds:.2f}s"
        )

        return result

    async def find_by_id(self, id: EmailId, context: FolderName) -> Optional[Email]:
        """Find email by ID in specific folder.

        Args:
            id: Email ID
            context: Folder to search in

        Returns:
            Email if found, None otherwise
        """
        engine = await self.engine_mgr.get_engine()

        query = self._query_builder.select_emails(
            folder=context,
            include_body=True,
            conditions={"uid": id.value},
            limit=1,
        )

        async with engine.connect() as conn:
            result = await conn.execute(query)
            row = result.fetchone()

            if not row:
                return None

            return row_to_email(row, context)

    async def find_all(
        self,
        context: FolderName,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Email]:
        """Find all emails in folder with pagination.

        Args:
            folder: Folder to query
            limit: Maximum number of emails to return
            offset: Number of emails to skip

        Returns:
            List of Email objects
        """
        engine = await self.engine_mgr.get_engine()

        query = self._query_builder.select_emails(
            folder=context,
            include_body=True,
            limit=limit,
            offset=offset,
            order_by_date_desc=True,
        )

        async with engine.connect() as conn:
            result = await conn.execute(query)
            rows = result.fetchall()

            return [row_to_email(row, context) for row in rows]

    async def delete(self, id: EmailId, context: FolderName) -> None:
        """Delete email from folder.

        Args:
            id: Email ID
            context: Folder to delete from

        Raises:
            EmailNotFoundError: If email doesn't exist
        """
        engine = await self.engine_mgr.get_engine()
        table = get_table(context.value)

        query = delete(table).where(table.c.uid == id.value)

        async with engine.begin() as conn:
            result = await conn.execute(query)

            if result.rowcount == 0:
                raise EmailNotFoundError(
                    f"Email {id.value} not found in {context.value}"
                )

        logger.debug(f"Deleted email {id.value} from {context.value}")

    async def exists(self, id: EmailId, context: FolderName) -> bool:
        """Check if email exists in folder.

        Args:
            id: Email ID
            context: Folder to check

        Returns:
            True if exists, False otherwise
        """
        engine = await self.engine_mgr.get_engine()
        table = get_table(context.value)

        query = select(func.count()).select_from(table).where(table.c.uid == id.value)

        async with engine.connect() as conn:
            result = await conn.execute(query)
            count = result.scalar()

            return count > 0

    async def exists_batch(self, ids: List[str], context: FolderName) -> dict:
        """Check which UIDs exist in folder (batch operation).

        Args:
            ids: List of email UIDs to check
            context: Folder to check

        Returns:
            Dictionary mapping UID -> bool (True if exists)
        """
        if not ids:
            return {}

        engine = await self.engine_mgr.get_engine()
        table = get_table(context.value)

        # Single query to get all existing UIDs
        query = select(table.c.uid).select_from(table).where(table.c.uid.in_(ids))

        async with engine.connect() as conn:
            result = await conn.execute(query)
            existing_uids = {row.uid for row in result}

        # Return dict mapping each ID to whether it exists
        return {uid: uid in existing_uids for uid in ids}

    async def move(
        self, id: EmailId, from_folder: FolderName, to_folder: FolderName
    ) -> None:
        """Move email between folders atomically.

        Args:
            id: Email ID
            from_folder: Source folder
            to_folder: Destination folder

        Raises:
            EmailNotFoundError: If email not found in source folder
        """
        email = await self.find_by_id(id, from_folder)

        if not email:
            raise EmailNotFoundError(
                f"Email {id.value} not found in {from_folder.value}"
            )

        engine = await self.engine_mgr.get_engine()

        # Use transaction for atomicity
        async with TransactionManager(engine) as tx:
            # Update folder in domain model
            email.move_to(to_folder)

            # Insert into destination folder
            dest_table = get_table(to_folder.value)
            values = self._email_to_row(email)

            insert_query = insert(dest_table).values(**values)
            insert_query = insert_query.on_conflict_do_update(
                index_elements=["uid"],
                set_=values,
            )
            await tx.connection.execute(insert_query)

            # Delete from source folder
            src_table = get_table(from_folder.value)
            delete_query = delete(src_table).where(src_table.c.uid == id.value)
            await tx.connection.execute(delete_query)

        logger.info(
            f"Moved email {id.value} from {from_folder.value} to {to_folder.value}"
        )

    async def count(self, folder: FolderName) -> int:
        """Count total emails in folder.

        Args:
            folder: Folder to count

        Returns:
            Number of emails
        """
        engine = await self.engine_mgr.get_engine()

        query = self._query_builder.count_emails(folder)

        async with engine.connect() as conn:
            result = await conn.execute(query)
            return result.scalar() or 0

    async def flag(self, id: EmailId, folder: FolderName, flagged: bool) -> None:
        """Toggle flagged status on email.

        Args:
            id: Email ID
            folder: Folder containing email
            flagged: New flagged status

        Raises:
            EmailNotFoundError: If email not found
            ValueError: If folder doesn't support flagging
        """
        if folder not in (FolderName.INBOX, FolderName.TRASH):
            raise ValueError(f"Folder {folder.value} does not support flagging")

        engine = await self.engine_mgr.get_engine()
        table = get_table(folder.value)

        query = self._query_builder.update_email(
            folder=folder,
            uid=id.value,
            values={"flagged": flagged},
        )

        async with engine.begin() as conn:
            result = await conn.execute(query)

            if result.rowcount == 0:
                raise EmailNotFoundError(
                    f"Email {id.value} not found in {folder.value}"
                )

        logger.debug(f"Set flagged={flagged} for {id.value} in {folder.value}")

    async def get_highest_uid(self, folder: FolderName) -> int:
        """Get the highest UID in a folder for incremental sync.

        Args:
            folder: Folder to check

        Returns:
            Highest UID as integer, or 0 if no emails in folder

        Raises:
            DatabaseError: If query fails
        """
        try:
            from sqlalchemy import cast, Integer

            engine = await self.engine_mgr.get_engine()
            table = get_table(folder.value)

            # Cast UID to integer for proper numeric comparison
            query = select(func.max(cast(table.c.uid, Integer))).select_from(table)

            async with engine.connect() as conn:
                result = await conn.execute(query)
                max_uid = result.scalar()

                if max_uid is None:
                    return 0

                return int(max_uid)

        except Exception as e:
            logger.error(f"Failed to get highest UID from {folder.value}: {e}")
            return 0

    # Helper methods for domain model <-> database row conversion

    def _email_to_row(self, email: Email) -> dict:
        """Convert Email domain object to database row dict.

        Args:
            email: Email domain object

        Returns:
            Dictionary of column values
        """
        row = {
            "uid": email.id.value,
            "subject": email.subject,
            "sender": str(email.sender),
            "recipient": ", ".join(str(r) for r in email.recipients),
            "date": email.received_at.strftime("%Y-%m-%d"),
            "time": email.received_at.strftime("%H:%M:%S"),
            "body": email.body or "",
            "attachments": ", ".join(a.filename for a in email.attachments),
            "is_read": email.is_read,
        }

        # Folder-specific columns
        if email.folder == FolderName.INBOX:
            row["flagged"] = email.is_flagged
        elif email.folder == FolderName.TRASH:
            row["flagged"] = email.is_flagged
            row["deleted_at"] = datetime.now().isoformat()
        elif email.folder == FolderName.SENT:
            # TODO: sent-specific columns
            pass

        return row
