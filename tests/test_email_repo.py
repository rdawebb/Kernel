"""Tests for EmailRepository with SQLAlchemy Core."""

import asyncio
from datetime import datetime
from pathlib import Path
import pytest
import tempfile

from src.core.database import (
    EngineManager,
    EmailRepository,
    create_engine,
    metadata,
)
from src.core.models.email import Email, EmailAddress, EmailId, FolderName
from src.core.models.attachment import Attachment


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
async def repo(test_db):
    """Create EmailRepository with test database."""
    engine_mgr = EngineManager(test_db)
    repo = EmailRepository(engine_mgr)
    
    yield repo
    
    await engine_mgr.close()


@pytest.fixture
def sample_email():
    """Create sample email for testing."""
    return Email(
        id=EmailId("test-123"),
        subject="Test Email",
        sender=EmailAddress.parse("sender@example.com"),
        recipients=[EmailAddress.parse("recipient@example.com")],
        received_at=datetime(2024, 1, 15, 10, 30, 0),
        body="Test body",
        attachments=[],
        folder=FolderName.INBOX,
        is_read=False,
        is_flagged=False,
    )


@pytest.mark.asyncio
async def test_save_and_find(repo, sample_email):
    """Test saving and retrieving email."""
    # Save
    await repo.save(sample_email)
    
    # Find
    found = await repo.find_by_id(sample_email.id, FolderName.INBOX)
    
    assert found is not None
    assert found.id == sample_email.id
    assert found.subject == sample_email.subject
    assert found.sender == sample_email.sender
    assert found.folder == FolderName.INBOX


@pytest.mark.asyncio
async def test_save_batch(repo):
    """Test batch save with progress tracking."""
    # Create 50 test emails
    emails = []
    for i in range(50):
        email = Email(
            id=EmailId(f"batch-{i}"),
            subject=f"Email {i}",
            sender=EmailAddress.parse("sender@example.com"),
            recipients=[EmailAddress.parse("recipient@example.com")],
            received_at=datetime(2024, 1, 15, 10, i, 0),
            body=f"Body {i}",
            attachments=[],
            folder=FolderName.INBOX,
            is_read=False,
        )
        emails.append(email)
    
    # Track progress
    progress_calls = []
    
    def track_progress(current, total):
        progress_calls.append((current, total))
    
    # Save batch
    result = await repo.save_batch(
        emails,
        batch_size=10,
        progress=track_progress,
    )
    
    # Verify result
    assert result.total == 50
    assert result.succeeded == 50
    assert result.failed == 0
    assert result.success_rate == 100.0
    
    # Verify progress was tracked
    assert len(progress_calls) > 0
    assert progress_calls[-1] == (50, 50)
    
    # Verify emails were saved
    count = await repo.count(FolderName.INBOX)
    assert count == 50


@pytest.mark.asyncio
async def test_save_batch_with_cancellation(repo):
    """Test batch save with cancellation."""
    # Create 100 emails
    emails = []
    for i in range(100):
        email = Email(
            id=EmailId(f"cancel-{i}"),
            subject=f"Email {i}",
            sender=EmailAddress.parse("sender@example.com"),
            recipients=[EmailAddress.parse("recipient@example.com")],
            received_at=datetime(2024, 1, 15, 10, 0, 0),
            body=f"Body {i}",
            attachments=[],
            folder=FolderName.INBOX,
            is_read=False,
        )
        emails.append(email)
    
    # Create cancellation token
    cancel_token = asyncio.Event()
    
    # Cancel after first batch
    def track_progress(current, total):
        if current >= 10:
            cancel_token.set()
    
    # Save batch (should be cancelled)
    result = await repo.save_batch(
        emails,
        batch_size=10,
        progress=track_progress,
        cancel_token=cancel_token,
    )
    
    # Verify partial completion
    assert result.succeeded < 100
    assert result.succeeded >= 10


@pytest.mark.asyncio
async def test_find_all_with_pagination(repo):
    """Test finding all emails with pagination."""
    # Create 30 emails
    for i in range(30):
        email = Email(
            id=EmailId(f"page-{i}"),
            subject=f"Email {i}",
            sender=EmailAddress.parse("sender@example.com"),
            recipients=[EmailAddress.parse("recipient@example.com")],
            received_at=datetime(2024, 1, 15, 10, 0, i),
            body=f"Body {i}",
            attachments=[],
            folder=FolderName.INBOX,
            is_read=False,
        )
        await repo.save(email)
    
    # Get first page
    page1 = await repo.find_all(FolderName.INBOX, limit=10, offset=0)
    assert len(page1) == 10
    
    # Get second page
    page2 = await repo.find_all(FolderName.INBOX, limit=10, offset=10)
    assert len(page2) == 10
    
    # Verify no overlap
    page1_ids = {e.id for e in page1}
    page2_ids = {e.id for e in page2}
    assert len(page1_ids & page2_ids) == 0


@pytest.mark.asyncio
async def test_delete(repo, sample_email):
    """Test deleting email."""
    # Save
    await repo.save(sample_email)
    assert await repo.exists(sample_email.id, FolderName.INBOX)
    
    # Delete
    await repo.delete(sample_email.id, FolderName.INBOX)
    
    # Verify deleted
    assert not await repo.exists(sample_email.id, FolderName.INBOX)


@pytest.mark.asyncio
async def test_move(repo, sample_email):
    """Test moving email between folders."""
    # Save to inbox
    await repo.save(sample_email)
    
    # Move to trash
    await repo.move(sample_email.id, FolderName.INBOX, FolderName.TRASH)
    
    # Verify move
    assert not await repo.exists(sample_email.id, FolderName.INBOX)
    assert await repo.exists(sample_email.id, FolderName.TRASH)
    
    # Verify email updated
    moved = await repo.find_by_id(sample_email.id, FolderName.TRASH)
    assert moved is not None
    assert moved.folder == FolderName.TRASH


@pytest.mark.asyncio
async def test_flag(repo, sample_email):
    """Test flagging email."""
    # Save
    await repo.save(sample_email)
    
    # Flag
    await repo.flag(sample_email.id, FolderName.INBOX, True)
    
    # Verify flagged
    email = await repo.find_by_id(sample_email.id, FolderName.INBOX)
    assert email.is_flagged is True
    
    # Unflag
    await repo.flag(sample_email.id, FolderName.INBOX, False)
    
    # Verify unflagged
    email = await repo.find_by_id(sample_email.id, FolderName.INBOX)
    assert email.is_flagged is False


@pytest.mark.asyncio
async def test_count(repo):
    """Test counting emails."""
    # Initially empty
    assert await repo.count(FolderName.INBOX) == 0
    
    # Add 5 emails
    for i in range(5):
        email = Email(
            id=EmailId(f"count-{i}"),
            subject=f"Email {i}",
            sender=EmailAddress.parse("sender@example.com"),
            recipients=[EmailAddress.parse("recipient@example.com")],
            received_at=datetime(2024, 1, 15, 10, 0, 0),
            body=f"Body {i}",
            attachments=[],
            folder=FolderName.INBOX,
            is_read=False,
        )
        await repo.save(email)
    
    # Verify count
    assert await repo.count(FolderName.INBOX) == 5
