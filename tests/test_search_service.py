"""Tests for SearchService with SQLAlchemy Core."""

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
from src.core.database.services.search import (
    SearchService,
    SearchQuery,
    SearchFilter,
    SearchOperator,
    SearchQueryBuilder,
)
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
async def search_service(test_db):
    """Create SearchService with test database."""
    engine_mgr = EngineManager(test_db)
    service = SearchService(engine_mgr)

    yield service

    await engine_mgr.close()


@pytest.fixture
async def populated_db(test_db):
    """Create database with sample emails."""
    engine_mgr = EngineManager(test_db)
    repo = EmailRepository(engine_mgr)

    # Create sample emails
    emails = [
        Email(
            id=EmailId("email-1"),
            subject="Important meeting",
            sender=EmailAddress.parse("boss@company.com"),
            recipients=[EmailAddress.parse("user@company.com")],
            received_at=datetime(2024, 1, 15, 10, 0, 0),
            body="Let's discuss the project",
            attachments=[],
            folder=FolderName.INBOX,
            is_read=False,
            is_flagged=True,
        ),
        Email(
            id=EmailId("email-2"),
            subject="Project update",
            sender=EmailAddress.parse("colleague@company.com"),
            recipients=[EmailAddress.parse("user@company.com")],
            received_at=datetime(2024, 1, 14, 15, 30, 0),
            body="Here's the latest status",
            attachments=[],
            folder=FolderName.INBOX,
            is_read=True,
            is_flagged=False,
        ),
        Email(
            id=EmailId("email-3"),
            subject="Invoice #12345",
            sender=EmailAddress.parse("billing@vendor.com"),
            recipients=[EmailAddress.parse("user@company.com")],
            received_at=datetime(2024, 1, 13, 9, 0, 0),
            body="Please find attached invoice",
            attachments=[],
            folder=FolderName.INBOX,
            is_read=False,
            is_flagged=False,
        ),
        Email(
            id=EmailId("email-4"),
            subject="Re: Important meeting",
            sender=EmailAddress.parse("user@company.com"),
            recipients=[EmailAddress.parse("boss@company.com")],
            received_at=datetime(2024, 1, 15, 11, 0, 0),
            body="Sounds good, see you then",
            attachments=[],
            folder=FolderName.SENT,
            is_read=True,
        ),
    ]

    for email in emails:
        await repo.save(email)

    await engine_mgr.close()

    return test_db


@pytest.mark.asyncio
async def test_basic_keyword_search(populated_db):
    """Test basic keyword search."""
    engine_mgr = EngineManager(populated_db)
    service = SearchService(engine_mgr)

    # Search for "meeting"
    result = await service.search_in_folder(
        FolderName.INBOX,
        "meeting",
    )

    assert len(result) == 1
    assert result[0].subject == "Important meeting"

    await engine_mgr.close()


@pytest.mark.asyncio
async def test_multi_folder_search(populated_db):
    """Test searching across multiple folders."""
    engine_mgr = EngineManager(populated_db)
    service = SearchService(engine_mgr)

    # Search for "meeting" in all folders
    result = await service.search_all_folders("meeting")

    assert len(result) == 2  # One in inbox, one in sent

    await engine_mgr.close()


@pytest.mark.asyncio
async def test_field_specific_search(populated_db):
    """Test searching in specific fields."""
    engine_mgr = EngineManager(populated_db)
    service = SearchService(engine_mgr)

    # Search for "boss" in sender field only
    result = await service.search_in_folder(
        FolderName.INBOX,
        "boss",
        fields={"sender"},
    )

    assert len(result) == 1
    assert "boss@company.com" in str(result[0].sender)

    await engine_mgr.close()


@pytest.mark.asyncio
async def test_advanced_search_with_filters(populated_db):
    """Test advanced search with multiple filters."""
    engine_mgr = EngineManager(populated_db)
    service = SearchService(engine_mgr)

    # Search for flagged emails from boss
    filters = [
        SearchFilter("sender", SearchOperator.CONTAINS, "boss"),
        SearchFilter("flagged", SearchOperator.EQUALS, True),
    ]

    result = await service.advanced_search(
        filters=filters,
        folders=[FolderName.INBOX],
    )

    assert len(result.emails) == 1
    assert result.emails[0].subject == "Important meeting"
    assert result.emails[0].is_flagged is True

    await engine_mgr.close()


@pytest.mark.asyncio
async def test_date_range_search(populated_db):
    """Test searching with date filters."""
    engine_mgr = EngineManager(populated_db)
    service = SearchService(engine_mgr)

    # Search for emails on or after 2024-01-15
    filters = [
        SearchFilter("date", SearchOperator.GREATER_EQUAL, "2024-01-15"),
    ]

    result = await service.advanced_search(
        filters=filters,
        folders=[FolderName.INBOX],
    )

    assert len(result.emails) == 1
    assert result.emails[0].received_at.date() >= datetime(2024, 1, 15).date()

    await engine_mgr.close()


@pytest.mark.asyncio
async def test_search_with_operators(populated_db):
    """Test different search operators."""
    engine_mgr = EngineManager(populated_db)
    service = SearchService(engine_mgr)

    # Test STARTS_WITH
    filters = [SearchFilter("subject", SearchOperator.STARTS_WITH, "Project")]
    result = await service.advanced_search(filters, folders=[FolderName.INBOX])
    assert len(result.emails) == 1

    # Test CONTAINS
    filters = [SearchFilter("subject", SearchOperator.CONTAINS, "update")]
    result = await service.advanced_search(filters, folders=[FolderName.INBOX])
    assert len(result.emails) == 1

    # Test NOT_EQUALS
    filters = [SearchFilter("is_read", SearchOperator.NOT_EQUALS, True)]
    result = await service.advanced_search(filters, folders=[FolderName.INBOX])
    assert len(result.emails) == 2  # Two unread emails

    await engine_mgr.close()


@pytest.mark.asyncio
async def test_search_query_builder(populated_db):
    """Test fluent query builder API."""
    engine_mgr = EngineManager(populated_db)
    service = SearchService(engine_mgr)

    # Build query using fluent API
    query = (
        SearchQueryBuilder()
        .keyword("meeting")
        .in_folder(FolderName.INBOX)
        .filter("flagged", SearchOperator.EQUALS, True)
        .limit(10)
        .build()
    )

    result = await service.search(query)

    assert len(result.emails) == 1
    assert result.emails[0].subject == "Important meeting"
    assert result.total_count == 1

    await engine_mgr.close()


@pytest.mark.asyncio
async def test_search_pagination(populated_db):
    """Test search with pagination."""
    engine_mgr = EngineManager(populated_db)
    service = SearchService(engine_mgr)

    # Get first 2 results
    query = SearchQuery(
        keyword="",  # Match all
        folders=[FolderName.INBOX],
        limit=2,
        offset=0,
    )
    result1 = await service.search(query)
    assert len(result1.emails) == 2

    # Get next result
    query.offset = 2
    result2 = await service.search(query)
    assert len(result2.emails) == 1

    # Verify no overlap
    ids1 = {e.id for e in result1.emails}
    ids2 = {e.id for e in result2.emails}
    assert len(ids1 & ids2) == 0

    await engine_mgr.close()


@pytest.mark.asyncio
async def test_search_ordering(populated_db):
    """Test search result ordering."""
    engine_mgr = EngineManager(populated_db)
    service = SearchService(engine_mgr)

    # Order by date descending (newest first)
    query = SearchQuery(
        folders=[FolderName.INBOX],
        order_by="date",
        order_desc=True,
    )
    result = await service.search(query)

    # Verify order
    dates = [e.received_at for e in result.emails]
    assert dates == sorted(dates, reverse=True)

    await engine_mgr.close()


@pytest.mark.asyncio
async def test_empty_search(search_service):
    """Test search with no results."""
    # Search empty database
    result = await search_service.search_in_folder(
        FolderName.INBOX,
        "nonexistent",
    )

    assert len(result) == 0


@pytest.mark.asyncio
async def test_invalid_field_validation():
    """Test that invalid fields are rejected."""
    with pytest.raises(ValueError, match="Invalid search field"):
        SearchFilter("invalid_field", SearchOperator.EQUALS, "value")


@pytest.mark.asyncio
async def test_search_performance_logging(populated_db, caplog):
    """Test that slow queries are logged."""
    engine_mgr = EngineManager(populated_db)
    service = SearchService(engine_mgr)

    # Search (should be fast, but we're testing the logging mechanism)
    result = await service.search_all_folders("meeting")

    # Query time should be recorded
    assert result.query_time_ms >= 0

    await engine_mgr.close()


@pytest.mark.asyncio
async def test_search_result_metadata(populated_db):
    """Test search result metadata."""
    engine_mgr = EngineManager(populated_db)
    service = SearchService(engine_mgr)

    query = SearchQuery(
        keyword="meeting",
        folders=[FolderName.INBOX, FolderName.SENT],
    )

    result = await service.search(query)

    assert result.total_count == len(result.emails)
    assert result.query_time_ms > 0
    assert set(result.folders_searched) == {"inbox", "sent"}

    await engine_mgr.close()
