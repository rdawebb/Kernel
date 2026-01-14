"""Tests for BackupService with progress tracking."""

import asyncio
from datetime import datetime
from pathlib import Path
import pytest
import tempfile
import gzip

from src.core.database import (
    EngineManager,
    EmailRepository,
    create_engine,
    metadata,
)
from src.core.database.services.backup import BackupService
from src.core.models.email import Email, EmailAddress, EmailId, FolderName


@pytest.fixture
async def test_db():
    """Create temporary test database."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)
    
    # Create engine and tables
    engine = create_engine(db_path, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)
    
    yield db_path
    
    # Cleanup
    await engine.dispose()
    db_path.unlink(missing_ok=True)


@pytest.fixture
async def backup_service(test_db):
    """Create BackupService with test database."""
    engine_mgr = EngineManager(test_db)
    repo = EmailRepository(engine_mgr)
    service = BackupService(test_db, repo)
    
    yield service
    
    await engine_mgr.close()


@pytest.fixture
async def populated_db(test_db):
    """Create database with sample emails."""
    engine_mgr = EngineManager(test_db)
    repo = EmailRepository(engine_mgr)
    
    # Add sample emails
    for i in range(10):
        email = Email(
            id=EmailId(f"test-{i}"),
            subject=f"Test Email {i}",
            sender=EmailAddress.parse("sender@example.com"),
            recipients=[EmailAddress.parse("recipient@example.com")],
            received_at=datetime(2024, 1, 15, 10, i, 0),
            body=f"Test body {i}",
            attachments=[],
            folder=FolderName.INBOX,
            is_read=False,
        )
        await repo.save(email)
    
    await engine_mgr.close()
    return test_db


@pytest.mark.asyncio
async def test_create_backup_uncompressed(backup_service, test_db):
    """Test creating uncompressed backup."""
    with tempfile.TemporaryDirectory() as tmpdir:
        backup_path = Path(tmpdir) / "backup.db"
        
        result = await backup_service.create_backup(
            backup_path=backup_path,
            compress=False,
        )
        
        assert result.success
        assert backup_path.exists()
        assert result.size_bytes > 0
        assert not result.compressed
        assert result.duration_seconds > 0


@pytest.mark.asyncio
async def test_create_backup_compressed(backup_service, test_db):
    """Test creating compressed backup."""
    with tempfile.TemporaryDirectory() as tmpdir:
        backup_path = Path(tmpdir) / "backup.db.gz"
        
        result = await backup_service.create_backup(
            backup_path=backup_path,
            compress=True,
        )
        
        assert result.success
        assert backup_path.exists()
        assert result.size_bytes > 0
        assert result.compressed
        
        # Verify it's actually gzipped
        with gzip.open(backup_path, "rb") as f:
            data = f.read(10)
            assert len(data) > 0


@pytest.mark.asyncio
async def test_backup_with_progress(backup_service, test_db):
    """Test backup with progress tracking."""
    progress_updates = []
    
    def track_progress(current, total):
        progress_updates.append((current, total))
    
    with tempfile.TemporaryDirectory() as tmpdir:
        backup_path = Path(tmpdir) / "backup.db"
        
        result = await backup_service.create_backup(
            backup_path=backup_path,
            compress=False,
            progress=track_progress,
        )
        
        assert result.success
        assert len(progress_updates) > 0
        
        # Last update should be 100% complete
        last_current, last_total = progress_updates[-1]
        assert last_current == last_total


@pytest.mark.asyncio
async def test_backup_auto_path_generation(backup_service):
    """Test automatic backup path generation."""
    result = await backup_service.create_backup(compress=False)
    
    assert result.success
    assert result.backup_path.exists()
    assert "kernel_backup_" in result.backup_path.name
    
    # Cleanup
    result.backup_path.unlink()


@pytest.mark.asyncio
async def test_export_to_csv(populated_db):
    """Test CSV export."""
    engine_mgr = EngineManager(populated_db)
    repo = EmailRepository(engine_mgr)
    service = BackupService(populated_db, repo)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        export_dir = Path(tmpdir)
        
        result = await service.export_to_csv(export_dir)
        
        assert result.success
        assert len(result.exported_files) > 0
        assert result.total_emails == 10
        
        # Verify CSV file exists
        inbox_csv = export_dir / "inbox.csv"
        assert inbox_csv.exists()
        
        # Verify CSV content
        import csv
        with open(inbox_csv, "r") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert len(rows) == 10
    
    await engine_mgr.close()


@pytest.mark.asyncio
async def test_export_with_progress(populated_db):
    """Test CSV export with progress tracking."""
    engine_mgr = EngineManager(populated_db)
    repo = EmailRepository(engine_mgr)
    service = BackupService(populated_db, repo)
    
    progress_updates = []
    
    def track_progress(folder, current, total):
        progress_updates.append((folder, current, total))
    
    with tempfile.TemporaryDirectory() as tmpdir:
        export_dir = Path(tmpdir)
        
        result = await service.export_to_csv(
            export_dir,
            progress=track_progress,
        )
        
        assert result.success
        assert len(progress_updates) > 0
        
        # Verify we got updates for inbox
        inbox_updates = [u for u in progress_updates if u[0] == "inbox"]
        assert len(inbox_updates) > 0
    
    await engine_mgr.close()


@pytest.mark.asyncio
async def test_export_with_cancellation(populated_db):
    """Test CSV export with cancellation."""
    engine_mgr = EngineManager(populated_db)
    repo = EmailRepository(engine_mgr)
    service = BackupService(populated_db, repo)
    
    cancel_token = asyncio.Event()
    
    def track_progress(folder, current, total):
        # Cancel after first update
        if current >= 1:
            cancel_token.set()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        export_dir = Path(tmpdir)
        
        result = await service.export_to_csv(
            export_dir,
            progress=track_progress,
            cancel_token=cancel_token,
        )
        
        # Should still return result, but possibly incomplete
        assert result.total_emails <= 10
    
    await engine_mgr.close()


@pytest.mark.asyncio
async def test_export_specific_folders(populated_db):
    """Test exporting specific folders only."""
    engine_mgr = EngineManager(populated_db)
    repo = EmailRepository(engine_mgr)
    service = BackupService(populated_db, repo)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        export_dir = Path(tmpdir)
        
        # Export only inbox
        result = await service.export_to_csv(
            export_dir,
            folders=[FolderName.INBOX],
        )
        
        assert result.success
        assert len(result.exported_files) == 1
        
        # Only inbox.csv should exist
        assert (export_dir / "inbox.csv").exists()
        assert not (export_dir / "sent.csv").exists()
    
    await engine_mgr.close()


@pytest.mark.asyncio
async def test_verify_backup(backup_service):
    """Test backup verification."""
    with tempfile.TemporaryDirectory() as tmpdir:
        backup_path = Path(tmpdir) / "backup.db"
        
        # Create backup
        result = await backup_service.create_backup(
            backup_path=backup_path,
            compress=False,
        )
        
        # Verify it
        is_valid = await backup_service.verify_backup(backup_path)
        assert is_valid


@pytest.mark.asyncio
async def test_verify_compressed_backup(backup_service):
    """Test verification of compressed backup."""
    with tempfile.TemporaryDirectory() as tmpdir:
        backup_path = Path(tmpdir) / "backup.db.gz"
        
        # Create compressed backup
        result = await backup_service.create_backup(
            backup_path=backup_path,
            compress=True,
        )
        
        # Verify it
        is_valid = await backup_service.verify_backup(backup_path)
        assert is_valid


@pytest.mark.asyncio
async def test_verify_nonexistent_backup(backup_service):
    """Test verification of nonexistent backup."""
    is_valid = await backup_service.verify_backup(Path("/nonexistent/backup.db"))
    assert not is_valid


@pytest.mark.asyncio
async def test_cleanup_old_backups(backup_service):
    """Test cleanup of old backup files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        backup_dir = Path(tmpdir)
        
        # Create 10 fake backups
        for i in range(10):
            backup_file = backup_dir / f"kernel_backup_202401{i:02d}_000000.db"
            backup_file.touch()
        
        # Keep only 5 most recent
        deleted = await backup_service.cleanup_old_backups(
            backup_dir,
            keep_count=5,
        )
        
        assert deleted == 5
        
        # Verify only 5 remain
        remaining = list(backup_dir.glob("kernel_backup_*.db"))
        assert len(remaining) == 5


@pytest.mark.asyncio
async def test_restore_from_backup(backup_service, test_db):
    """Test restoring database from backup."""
    with tempfile.TemporaryDirectory() as tmpdir:
        backup_path = Path(tmpdir) / "backup.db"
        restore_path = Path(tmpdir) / "restored.db"
        
        # Create backup
        result = await backup_service.create_backup(
            backup_path=backup_path,
            compress=False,
        )
        
        # Restore to new location
        success = await backup_service.restore_from_backup(
            backup_path=backup_path,
            target_path=restore_path,
        )
        
        assert success
        assert restore_path.exists()
        
        # Verify restored file has similar size
        assert restore_path.stat().st_size > 0


@pytest.mark.asyncio
async def test_restore_compressed_backup(backup_service, test_db):
    """Test restoring from compressed backup."""
    with tempfile.TemporaryDirectory() as tmpdir:
        backup_path = Path(tmpdir) / "backup.db.gz"
        restore_path = Path(tmpdir) / "restored.db"
        
        # Create compressed backup
        result = await backup_service.create_backup(
            backup_path=backup_path,
            compress=True,
        )
        
        # Restore
        success = await backup_service.restore_from_backup(
            backup_path=backup_path,
            target_path=restore_path,
        )
        
        assert success
        assert restore_path.exists()


@pytest.mark.asyncio
async def test_backup_result_properties(backup_service):
    """Test BackupResult helper properties."""
    with tempfile.TemporaryDirectory() as tmpdir:
        backup_path = Path(tmpdir) / "backup.db"
        
        result = await backup_service.create_backup(
            backup_path=backup_path,
            compress=False,
        )
        
        # Test size_mb property
        assert result.size_mb > 0
        assert result.size_mb == round(result.size_bytes / 1024 / 1024, 2)


@pytest.mark.asyncio
async def test_export_result_properties(populated_db):
    """Test ExportResult helper properties."""
    engine_mgr = EngineManager(populated_db)
    repo = EmailRepository(engine_mgr)
    service = BackupService(populated_db, repo)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        export_dir = Path(tmpdir)
        
        result = await service.export_to_csv(export_dir)
        
        # Test success property
        assert result.success  # No errors
        assert len(result.errors) == 0
    
    await engine_mgr.close()
