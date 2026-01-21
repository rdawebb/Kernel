"""Database backup service with progress tracking and compression."""

import asyncio
import csv
import gzip
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional

from src.core.database.repositories.email import EmailRepository
from src.core.models.email import Email, FolderName
from src.utils.errors import BackupError
from src.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class BackupResult:
    """Result of backup operation."""

    backup_path: Path
    size_bytes: int
    compressed: bool
    duration_seconds: float
    success: bool = True
    error: Optional[str] = None

    @property
    def size_mb(self) -> float:
        """Get size in megabytes."""
        return round(self.size_bytes / 1024 / 1024, 2)


@dataclass
class ExportResult:
    """Result of CSV export operation."""

    exported_files: List[Path] = field(default_factory=list)
    total_emails: int = 0
    duration_seconds: float = 0.0
    errors: List[tuple[str, str]] = field(default_factory=list)

    @property
    def success(self) -> bool:
        """Check if export was successful."""
        return len(self.errors) == 0


class BackupService:
    """Service for database backup and export operations.

    Features:
    - Full database file backup with compression
    - CSV export with progress tracking
    - Cancellation support for long exports
    - Automatic cleanup of old backups
    - Verification of backup integrity
    """

    def __init__(
        self,
        db_path: Path,
        email_repository: EmailRepository,
    ):
        """Initialize backup service.

        Args:
            db_path: Path to database file
            email_repository: Repository for email access
        """
        self.db_path = db_path
        self.email_repo = email_repository

    async def create_backup(
        self,
        backup_path: Optional[Path] = None,
        compress: bool = True,
        progress: Optional[Callable[[int, int], None]] = None,
    ) -> BackupResult:
        """Create backup of database file.

        Args:
            backup_path: Custom backup path (auto-generated if None)
            compress: Whether to compress backup with gzip
            progress: Optional progress callback(bytes_copied, total_bytes)

        Returns:
            BackupResult with backup details

        Raises:
            BackupError: If backup fails
        """
        start_time = asyncio.get_event_loop().time()

        try:
            # Generate backup path if not provided
            if backup_path is None:
                backup_path = self._generate_backup_path(compress)

            # Ensure backup directory exists
            backup_path.parent.mkdir(parents=True, exist_ok=True)

            # Get source file size
            if not self.db_path.exists():
                raise BackupError(f"Database file not found: {self.db_path}")

            source_size = self.db_path.stat().st_size

            # Copy file with optional compression
            if compress:
                await self._copy_compressed(
                    self.db_path,
                    backup_path,
                    progress,
                    source_size,
                )
            else:
                await self._copy_uncompressed(
                    self.db_path,
                    backup_path,
                    progress,
                    source_size,
                )

            # Get backup size
            backup_size = backup_path.stat().st_size

            duration = asyncio.get_event_loop().time() - start_time

            logger.info(
                f"Database backup created: {backup_path} "
                f"({backup_size / 1024 / 1024:.2f} MB, "
                f"compression={'on' if compress else 'off'}, "
                f"duration={duration:.2f}s)"
            )

            return BackupResult(
                backup_path=backup_path,
                size_bytes=backup_size,
                compressed=compress,
                duration_seconds=duration,
            )

        except Exception as e:
            logger.error(f"Backup failed: {e}")
            return BackupResult(
                backup_path=backup_path or Path("unknown"),
                size_bytes=0,
                compressed=compress,
                duration_seconds=asyncio.get_event_loop().time() - start_time,
                success=False,
                error=str(e),
            )

    async def export_to_csv(
        self,
        export_dir: Path,
        folders: Optional[List[FolderName]] = None,
        progress: Optional[Callable[[str, int, int], None]] = None,
        cancel_token: Optional[asyncio.Event] = None,
    ) -> ExportResult:
        """Export folders to CSV files.

        Args:
            export_dir: Directory for CSV files
            folders: Folders to export (default: all)
            progress: Optional callback(folder_name, current, total)
            cancel_token: Optional cancellation token

        Returns:
            ExportResult with export details
        """
        start_time = asyncio.get_event_loop().time()
        result = ExportResult()

        try:
            export_dir.mkdir(parents=True, exist_ok=True)

            if folders is None:
                folders = list(FolderName)

            for folder in folders:
                # Check cancellation
                if cancel_token and cancel_token.is_set():
                    logger.info("Export cancelled")
                    break

                try:
                    # Export folder
                    csv_path, email_count = await self._export_folder_to_csv(
                        folder=folder,
                        export_dir=export_dir,
                        progress=progress,
                        cancel_token=cancel_token,
                    )

                    if csv_path:
                        result.exported_files.append(csv_path)
                        result.total_emails += email_count

                except Exception as e:
                    error_msg = f"Failed to export {folder.value}: {e}"
                    logger.error(error_msg)
                    result.errors.append((folder.value, str(e)))

            result.duration_seconds = asyncio.get_event_loop().time() - start_time

            logger.info(
                f"CSV export complete: {result.total_emails} emails "
                f"in {len(result.exported_files)} files "
                f"({result.duration_seconds:.2f}s)"
            )

            return result

        except Exception as e:
            logger.error(f"Export failed: {e}")
            result.errors.append(("general", str(e)))
            result.duration_seconds = asyncio.get_event_loop().time() - start_time
            return result

    async def verify_backup(self, backup_path: Path) -> bool:
        """Verify backup file integrity.

        Args:
            backup_path: Path to backup file

        Returns:
            True if backup is valid, False otherwise
        """
        try:
            if not backup_path.exists():
                logger.error(f"Backup file not found: {backup_path}")
                return False

            # Check if compressed
            is_compressed = backup_path.suffix == ".gz"

            # Try to read file
            if is_compressed:

                async def test_read():
                    with gzip.open(backup_path, "rb") as f:
                        # Read first 1KB to verify
                        f.read(1024)

                await asyncio.to_thread(test_read)
            else:
                # For uncompressed, just check size
                size = backup_path.stat().st_size
                if size == 0:
                    logger.error("Backup file is empty")
                    return False

            logger.info(f"Backup verification passed: {backup_path}")
            return True

        except Exception as e:
            logger.error(f"Backup verification failed: {e}")
            return False

    async def cleanup_old_backups(
        self,
        backup_dir: Path,
        keep_count: int = 5,
        max_age_days: Optional[int] = None,
    ) -> int:
        """Clean up old backup files.

        Args:
            backup_dir: Directory containing backups
            keep_count: Number of most recent backups to keep
            max_age_days: Delete backups older than this (optional)

        Returns:
            Number of backups deleted
        """
        if not backup_dir.exists():
            return 0

        try:
            # Find all backup files
            backup_files = []
            for pattern in ["kernel_backup_*.db", "kernel_backup_*.db.gz"]:
                backup_files.extend(backup_dir.glob(pattern))

            if not backup_files:
                return 0

            # Sort by modification time (newest first)
            backup_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)

            deleted_count = 0
            now = datetime.now().timestamp()

            for i, backup_file in enumerate(backup_files):
                should_delete = False

                # Keep most recent backups
                if i >= keep_count:
                    should_delete = True

                # Check age if specified
                if max_age_days is not None:
                    age_days = (now - backup_file.stat().st_mtime) / 86400
                    if age_days > max_age_days:
                        should_delete = True

                if should_delete:
                    await asyncio.to_thread(backup_file.unlink)
                    deleted_count += 1
                    logger.info(f"Deleted old backup: {backup_file}")

            logger.info(f"Cleaned up {deleted_count} old backups")
            return deleted_count

        except Exception as e:
            logger.error(f"Backup cleanup failed: {e}")
            return 0

    async def restore_from_backup(
        self,
        backup_path: Path,
        target_path: Optional[Path] = None,
    ) -> bool:
        """Restore database from backup.

        Args:
            backup_path: Path to backup file
            target_path: Target database path (uses original if None)

        Returns:
            True if restore successful, False otherwise
        """
        try:
            if not await self.verify_backup(backup_path):
                raise BackupError("Backup verification failed")

            target = target_path or self.db_path

            # Create backup of current database
            if target.exists():
                temp_backup = target.with_suffix(".db.pre_restore")
                await asyncio.to_thread(lambda: shutil.copy2(target, temp_backup))
                logger.info(f"Created pre-restore backup: {temp_backup}")

            # Restore from backup
            is_compressed = backup_path.suffix == ".gz"

            if is_compressed:
                await self._restore_compressed(backup_path, target)
            else:
                await asyncio.to_thread(lambda: shutil.copy2(backup_path, target))

            logger.info(f"Database restored from: {backup_path}")
            return True

        except Exception as e:
            logger.error(f"Restore failed: {e}")
            return False

    # Helper methods

    def _generate_backup_path(self, compress: bool) -> Path:
        """Generate backup file path with timestamp."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = self.db_path.parent / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)

        filename = f"kernel_backup_{timestamp}.db"
        if compress:
            filename += ".gz"

        return backup_dir / filename

    async def _copy_compressed(
        self,
        source: Path,
        dest: Path,
        progress: Optional[Callable[[int, int], None]],
        total_size: int,
    ) -> None:
        """Copy file with gzip compression."""

        def compress_file():
            with open(source, "rb") as f_in:
                with gzip.open(dest, "wb", compresslevel=6) as f_out:
                    bytes_copied = 0
                    chunk_size = 1024 * 1024  # 1MB chunks

                    while True:
                        chunk = f_in.read(chunk_size)
                        if not chunk:
                            break

                        f_out.write(chunk)
                        bytes_copied += len(chunk)

                        if progress:
                            progress(bytes_copied, total_size)

        await asyncio.to_thread(compress_file)

    async def _copy_uncompressed(
        self,
        source: Path,
        dest: Path,
        progress: Optional[Callable[[int, int], None]],
        total_size: int,
    ) -> None:
        """Copy file without compression."""

        def copy_file():
            with open(source, "rb") as f_in:
                with open(dest, "wb") as f_out:
                    bytes_copied = 0
                    chunk_size = 1024 * 1024  # 1MB chunks

                    while True:
                        chunk = f_in.read(chunk_size)
                        if not chunk:
                            break

                        f_out.write(chunk)
                        bytes_copied += len(chunk)

                        if progress:
                            progress(bytes_copied, total_size)

        await asyncio.to_thread(copy_file)

    async def _restore_compressed(self, backup_path: Path, target: Path) -> None:
        """Restore from compressed backup."""

        def decompress():
            with gzip.open(backup_path, "rb") as f_in:
                with open(target, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)

        await asyncio.to_thread(decompress)

    async def _export_folder_to_csv(
        self,
        folder: FolderName,
        export_dir: Path,
        progress: Optional[Callable[[str, int, int], None]],
        cancel_token: Optional[asyncio.Event],
    ) -> tuple[Optional[Path], int]:
        """Export single folder to CSV.

        Returns:
            Tuple of (csv_path, email_count)
        """
        # Get all emails from folder
        from src.core.database.config import get_config

        config = get_config()
        emails = await self.email_repo.find_all(
            folder,
            limit=config.max_export_limit,
        )

        if not emails:
            logger.info(f"No emails to export in {folder.value}")
            return None, 0

        # Generate CSV path
        csv_path = export_dir / f"{folder.value}.csv"

        # Write CSV
        await self._write_csv(
            path=csv_path,
            emails=emails,
            folder_name=folder.value,
            progress=progress,
            cancel_token=cancel_token,
        )

        logger.info(f"Exported {len(emails)} emails from {folder.value} to {csv_path}")
        return csv_path, len(emails)

    async def _write_csv(
        self,
        path: Path,
        emails: List[Email],
        folder_name: str,
        progress: Optional[Callable[[str, int, int], None]],
        cancel_token: Optional[asyncio.Event],
    ) -> None:
        """Write emails to CSV file with progress tracking."""

        def write():
            with open(path, "w", newline="", encoding="utf-8") as f:
                if not emails:
                    return

                # Use first email to determine fieldnames
                fieldnames = list(emails[0].to_dict().keys())

                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()

                for i, email in enumerate(emails):
                    # Check cancellation
                    if cancel_token and cancel_token.is_set():
                        logger.info(f"CSV export cancelled at {i}/{len(emails)}")
                        break

                    writer.writerow(email.to_dict())

                    # Report progress every 100 emails
                    if progress and i % 100 == 0:
                        progress(folder_name, i + 1, len(emails))

                # Final progress update
                if progress:
                    progress(folder_name, len(emails), len(emails))

        await asyncio.to_thread(write)
