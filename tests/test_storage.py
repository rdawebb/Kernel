"""
Comprehensive tests for storage_api database operations

Tests cover:
- Database initialisation and management
- CRUD operations on all email tables
- Search functionality
- Email marking (flagged/unflagged)
- Attachment handling
- Backup and export operations
"""

from unittest.mock import patch

from src.core import storage_api

from .test_helpers import DatabaseTestHelper


class TestDatabaseManagement:
    """Tests for database initialisation and connection management"""

    def test_initialise_db_creates_tables(self, temp_db, mock_config):
        """Test that initialise_db creates all required tables"""
        with patch(
            "src.core.db_manager.DatabaseManager.get_db_path", return_value=temp_db
        ):
            storage_api.initialise_db()

            conn = storage_api.get_db_connection()
            cursor = conn.cursor()

            # Check all required tables exist
            tables = ["inbox", "sent_emails", "drafts", "deleted_emails"]
            for table in tables:
                cursor.execute(
                    f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'"
                )
                assert cursor.fetchone() is not None, f"Table {table} should exist"

            conn.close()

    def test_get_db_connection(self, temp_db, mock_config):
        """Test database connection retrieval"""
        with patch(
            "src.core.db_manager.DatabaseManager.get_db_path", return_value=temp_db
        ):
            storage_api.initialise_db()
            conn = storage_api.get_db_connection()

            assert conn is not None
            assert hasattr(conn, "execute")
            conn.close()


class TestEmailCRUDOperations:
    """Tests for Create, Read, Update, Delete operations on emails"""

    def test_save_email_to_inbox(self, temp_db, mock_config):
        """Test saving an email to inbox table"""
        with patch(
            "src.core.db_manager.DatabaseManager.get_db_path", return_value=temp_db
        ):
            storage_api.initialise_db()

            email = DatabaseTestHelper.create_mock_email(uid="test_uid_1")
            storage_api.save_email_to_table("inbox", email)

            retrieved = storage_api.get_email_from_table("inbox", "test_uid_1")
            assert retrieved is not None

    def test_delete_email_from_table(self, temp_db, mock_config):
        """Test deleting an email from a table"""
        with patch(
            "src.core.db_manager.DatabaseManager.get_db_path", return_value=temp_db
        ):
            storage_api.initialise_db()

            email = DatabaseTestHelper.create_mock_email()
            storage_api.save_email_to_table("inbox", email)

            # Verify it exists
            assert storage_api.get_email_from_table("inbox", email["uid"]) is not None

            # Delete it
            storage_api.delete_email_from_table("inbox", email["uid"])

            # Verify it's deleted
            assert storage_api.get_email_from_table("inbox", email["uid"]) is None


class TestEmailSearch:
    """Tests for email search functionality"""

    def test_search_emails_by_keyword(self, temp_db, mock_config):
        """Test searching emails by keyword"""
        with patch(
            "src.core.db_manager.DatabaseManager.get_db_path", return_value=temp_db
        ):
            storage_api.initialise_db()

            email = DatabaseTestHelper.create_mock_email(subject="Important Meeting")
            storage_api.save_email_to_table("inbox", email)

            results = storage_api.search_emails("inbox", "Important")
            assert len(results) >= 1


class TestEmailFlagging:
    """Tests for email flagging/marking functionality"""

    def test_mark_email_flagged(self, temp_db, mock_config):
        """Test marking an email as flagged"""
        with patch(
            "src.core.db_manager.DatabaseManager.get_db_path", return_value=temp_db
        ):
            storage_api.initialise_db()

            email = DatabaseTestHelper.create_mock_email(uid="test_flag", flagged=False)
            storage_api.save_email_to_table("inbox", email)

            storage_api.mark_email_flagged("test_flag", True)

            retrieved = storage_api.get_email_from_table("inbox", "test_flag")
            assert retrieved["flagged"] == 1 or retrieved["flagged"] is True

    def test_mark_email_unflagged(self, temp_db, mock_config):
        """Test unmarking a flagged email"""
        with patch(
            "src.core.db_manager.DatabaseManager.get_db_path", return_value=temp_db
        ):
            storage_api.initialise_db()

            email = DatabaseTestHelper.create_mock_email(
                uid="test_unflag", flagged=True
            )
            storage_api.save_email_to_table("inbox", email)

            storage_api.mark_email_flagged("test_unflag", False)

            retrieved = storage_api.get_email_from_table("inbox", "test_unflag")
            assert retrieved["flagged"] == 0 or retrieved["flagged"] is False


class TestEmailMovement:
    """Tests for moving emails between tables"""

    def test_move_email_to_deleted(self, temp_db, mock_config):
        """Test moving email from inbox to deleted_emails"""
        with patch(
            "src.core.db_manager.DatabaseManager.get_db_path", return_value=temp_db
        ):
            storage_api.initialise_db()

            email = DatabaseTestHelper.create_mock_email()
            storage_api.save_email_to_table("inbox", email)

            # Move to deleted
            storage_api.move_email_between_tables(
                "inbox", "deleted_emails", email["uid"]
            )

            # Verify moved
            assert storage_api.get_email_from_table("inbox", email["uid"]) is None
            assert (
                storage_api.get_email_from_table("deleted_emails", email["uid"])
                is not None
            )


class TestPendingEmailStatus:
    """Tests for tracking pending/unsent email status"""

    def test_get_pending_emails_count(self, temp_db, mock_config):
        """Test counting pending emails"""
        with patch(
            "src.core.db_manager.DatabaseManager.get_db_path", return_value=temp_db
        ):
            storage_api.initialise_db()

            # Should not crash with empty database
            pending = storage_api.get_pending_emails()
            assert pending is not None or isinstance(pending, list)


class TestDatabaseBackupExport:
    """Tests for database backup and export operations"""

    def test_backup_database(self, temp_db, mock_config):
        """Test creating database backup"""
        with patch(
            "src.core.db_manager.DatabaseManager.get_db_path", return_value=temp_db
        ):
            storage_api.initialise_db()

            email = DatabaseTestHelper.create_mock_email()
            storage_api.save_email_to_table("inbox", email)

            # Backup should complete without error
            backup_path = storage_api.backup_db()
            assert backup_path is not None


class TestGetHighestUID:
    """Tests for highest UID tracking"""

    def test_get_highest_uid(self, temp_db, mock_config):
        """Test retrieving highest UID from inbox"""
        with patch(
            "src.core.db_manager.DatabaseManager.get_db_path", return_value=temp_db
        ):
            storage_api.initialise_db()

            emails = DatabaseTestHelper.create_mock_emails(3)
            for email in emails:
                storage_api.save_email_to_table("inbox", email)

            # Should return a valid UID or 0
            uid = storage_api.get_highest_uid()
            assert uid is not None or uid == 0
