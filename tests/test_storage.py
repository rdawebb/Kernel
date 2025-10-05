import unittest
import tempfile
import sqlite3
from pathlib import Path
from unittest.mock import patch

from src.quiet_mail.core.storage import (
    get_db_path, get_db_connection, initialize_db,
    save_email_metadata, save_email_body, get_inbox, get_email,
    search_emails, mark_email_flagged, search_emails_by_flag_status,
    search_emails_with_attachments, get_highest_uid, delete_email
)


class TestStorage(unittest.TestCase):
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.test_db_path = Path(self.temp_dir) / "test_emails.db"
        
        # Mock the config to use our test database
        self.config_patcher = patch('src.quiet_mail.core.storage.load_config')
        self.mock_config = self.config_patcher.start()
        self.mock_config.return_value = {
            'db_path': str(self.test_db_path)
        }
    
    def tearDown(self):
        self.config_patcher.stop()
        if self.test_db_path.exists():
            self.test_db_path.unlink()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_get_db_path(self):
        db_path = get_db_path()
        self.assertEqual(str(db_path), str(self.test_db_path))
    
    def test_get_db_connection(self):
        conn = get_db_connection()
        self.assertIsInstance(conn, sqlite3.Connection)
        self.assertEqual(conn.row_factory, sqlite3.Row)
        conn.close()
    
    def test_initialize_db(self):
        initialize_db()
        
        # Check the database was created via get_db_path() which uses our mocked config
        actual_db_path = get_db_path()
        self.assertTrue(actual_db_path.exists())
        
        conn = sqlite3.connect(actual_db_path)
        cursor = conn.cursor()
        
        cursor.execute("PRAGMA table_info(emails)")
        columns = cursor.fetchall()
        
        column_names = [col[1] for col in columns]
        expected_columns = ['id', 'uid', 'subject', 'sender', 'recipient', 'date', 'time', 'body', 'flagged']
        
        for col in expected_columns:
            self.assertIn(col, column_names)
        # Ensure fetched_at is NOT in the new schema
        self.assertNotIn('fetched_at', column_names)
        conn.close()
    
    def test_save_email_metadata(self):
        initialize_db()
        
        # Clear any existing data
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM emails")
        conn.commit()
        conn.close()
        
        # Use the new dict-based function signature
        test_email = {
            'uid': 'test_uid_123',
            'from': 'sender@example.com',
            'subject': 'Test Subject',
            'to': 'recipient@example.com',
            'date': '2025-10-02',
            'time': '10:30:00',
            'body': '',
            'flagged': False,
            'attachments': []
        }
        save_email_metadata(test_email)
        
        actual_db_path = get_db_path()
        conn = sqlite3.connect(actual_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM emails")
        rows = cursor.fetchall()
        
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row[1], 'test_uid_123')  # uid
        self.assertEqual(row[2], 'Test Subject')  # subject
        self.assertEqual(row[3], 'sender@example.com')  # sender
        self.assertEqual(row[4], 'recipient@example.com')  # recipient
        self.assertEqual(row[5], '2025-10-02')  # date
        self.assertEqual(row[6], '10:30:00')  # time
        
        conn.close()
    
    def test_save_email_body(self):
        initialize_db()
        
        # First save email metadata with new dict-based function signature
        test_email = {
            'uid': 'test_uid_123',
            'from': 'sender@example.com',
            'subject': 'Test Subject',
            'to': 'recipient@example.com',
            'date': '2025-10-02',
            'time': '10:30:00',
            'body': '',
            'flagged': False,
            'attachments': []
        }
        save_email_metadata(test_email)
        
        save_email_body('test_uid_123', 'This is the email body')
        
        actual_db_path = get_db_path()
        conn = sqlite3.connect(actual_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT body FROM emails WHERE uid = ?", ('test_uid_123',))
        result = cursor.fetchone()
        conn.close()
        
        self.assertIsNotNone(result)
        self.assertEqual(result[0], 'This is the email body')
    
    def test_get_inbox_empty(self):
        initialize_db()
        
        # Clear any existing data
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM emails")
        conn.commit()
        conn.close()
        
        emails = get_inbox()
        self.assertEqual(emails, [])
    
    def test_get_inbox_with_emails(self):
        initialize_db()
        
        # Clear any existing data
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM emails")
        conn.commit()
        conn.close()
        
        test_emails = [
            {
                'uid': 'test_uid_1',
                'subject': 'Email 1',
                'sender': 'sender1@example.com',
                'recipient': 'recipient@example.com',
                'date': '2025-10-02',
                'time': '10:30:00'
            },
            {
                'uid': 'test_uid_2', 
                'subject': 'Email 2',
                'sender': 'sender2@example.com',
                'recipient': 'recipient@example.com',
                'date': '2025-10-01',
                'time': '09:15:00'
            }
        ]
        
        for email in test_emails:
            # Convert to new format with required fields
            email_dict = {
                'uid': email['uid'],
                'from': email['sender'],
                'subject': email['subject'],
                'to': email['recipient'],
                'date': email['date'],
                'time': email['time'],
                'body': '',
                'flagged': False,
                'attachments': []
            }
            save_email_metadata(email_dict)
        
        inbox = get_inbox()
        
        self.assertEqual(len(inbox), 2)
        # Should be ordered by date DESC, so Email 1 should be first
        self.assertEqual(inbox[0]['subject'], 'Email 1')
        self.assertEqual(inbox[1]['subject'], 'Email 2')
    
    def test_get_inbox_with_limit(self):
        initialize_db()
        
        # Clear any existing data
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM emails")
        conn.commit()
        conn.close()
        
        # Add 5 test emails
        for i in range(5):
            email_dict = {
                'uid': f'test_uid_{i}',
                'from': f'sender{i}@example.com',
                'subject': f'Email {i}',
                'to': 'recipient@example.com',
                'date': f'2025-10-0{i+1}',
                'time': '10:30:00',
                'body': '',
                'flagged': False,
                'attachments': []
            }
            save_email_metadata(email_dict)
        
        inbox = get_inbox(limit=3)
        
        self.assertEqual(len(inbox), 3)
    
    def test_get_email_existing(self):
        initialize_db()
        
        # Clear any existing data
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM emails")
        conn.commit()
        conn.close()
        
        test_email = {
            'uid': 'test_uid_123',
            'from': 'sender@example.com',
            'subject': 'Test Email',
            'to': 'recipient@example.com',
            'date': '2025-10-02',
            'time': '10:30:00',
            'body': '',
            'flagged': False,
            'attachments': []
        }
        save_email_metadata(test_email)
        
        email = get_email('test_uid_123')
        
        self.assertIsNotNone(email)
        self.assertEqual(email['subject'], 'Test Email')
        self.assertEqual(email['from'], 'sender@example.com')
    
    def test_get_email_nonexistent(self):
        initialize_db()
        
        # Clear any existing data
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM emails")
        conn.commit()
        conn.close()
        
        email = get_email('nonexistent_uid')
        self.assertIsNone(email)
    
    def test_search_emails_by_keyword(self):
        initialize_db()
        
        # Clear any existing data
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM emails")
        conn.commit()
        conn.close()
        
        # Save test emails
        test_emails = [
            ('uid1', 'sender1@example.com', 'Important Meeting', 'recipient@example.com', '2025-10-03', '10:00:00'),
            ('uid2', 'sender2@example.com', 'Lunch Plans', 'recipient@example.com', '2025-10-03', '11:00:00'),
            ('uid3', 'important@example.com', 'Status Update', 'recipient@example.com', '2025-10-03', '12:00:00'),
        ]
        
        for uid, sender, subject, recipient, date, time in test_emails:
            email_dict = {
                'uid': uid,
                'from': sender,
                'subject': subject,
                'to': recipient,
                'date': date,
                'time': time,
                'body': '',
                'flagged': False,
                'attachments': []
            }
            save_email_metadata(email_dict)
            save_email_body(uid, f"Body content for {subject}")
        
        # Test search by subject keyword
        results = search_emails('Meeting')
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['subject'], 'Important Meeting')
        
        # Test search by sender keyword
        results = search_emails('important')
        self.assertEqual(len(results), 2)  # Should match subject "Important Meeting" and sender "important@example.com"
        
        # Test search by body keyword
        results = search_emails('Status Update')
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['subject'], 'Status Update')
        
        # Test no results
        results = search_emails('nonexistent')
        self.assertEqual(len(results), 0)
    
    def test_mark_email_flagged(self):
        initialize_db()
        
        # Clear any existing data
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM emails")
        conn.commit()
        conn.close()
        
        # Save test email
        test_email = {
            'uid': 'test_uid',
            'from': 'sender@example.com',
            'subject': 'Test Subject',
            'to': 'recipient@example.com',
            'date': '2025-10-03',
            'time': '10:00:00',
            'body': '',
            'flagged': False,
            'attachments': []
        }
        save_email_metadata(test_email)
        
        # Test flagging an email
        mark_email_flagged('test_uid', True)
        
        # Verify it's flagged
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT flagged FROM emails WHERE uid = ?", ('test_uid',))
        result = cursor.fetchone()
        conn.close()
        
        self.assertIsNotNone(result)
        self.assertEqual(result[0], 1)  # SQLite stores boolean as 1
        
        # Test unflagging an email
        mark_email_flagged('test_uid', False)
        
        # Verify it's unflagged
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT flagged FROM emails WHERE uid = ?", ('test_uid',))
        result = cursor.fetchone()
        conn.close()
        
        self.assertIsNotNone(result)
        self.assertEqual(result[0], 0)  # SQLite stores boolean as 0
    
    def test_search_emails_by_flag_status_flagged(self):
        initialize_db()
        
        # Clear any existing data
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM emails")
        conn.commit()
        conn.close()
        
        # Save test emails
        test_emails = [
            ('uid1', 'sender1@example.com', 'Flagged Email 1', 'recipient@example.com', '2025-10-03', '10:00:00'),
            ('uid2', 'sender2@example.com', 'Unflagged Email', 'recipient@example.com', '2025-10-03', '11:00:00'),
            ('uid3', 'sender3@example.com', 'Flagged Email 2', 'recipient@example.com', '2025-10-03', '12:00:00'),
        ]
        
        for uid, sender, subject, recipient, date, time in test_emails:
            email_dict = {
                'uid': uid,
                'from': sender,
                'subject': subject,
                'to': recipient,
                'date': date,
                'time': time,
                'body': '',
                'flagged': False,
                'attachments': []
            }
            save_email_metadata(email_dict)
        
        # Flag some emails
        mark_email_flagged('uid1', True)
        mark_email_flagged('uid3', True)
        # uid2 remains unflagged (default)
        
        # Test getting flagged emails
        flagged_emails = search_emails_by_flag_status(True)
        self.assertEqual(len(flagged_emails), 2)
        
        flagged_subjects = [email['subject'] for email in flagged_emails]
        self.assertIn('Flagged Email 1', flagged_subjects)
        self.assertIn('Flagged Email 2', flagged_subjects)
        self.assertNotIn('Unflagged Email', flagged_subjects)
        
        # Verify flagged column is included in results
        for email in flagged_emails:
            self.assertIn('flagged', email)
            self.assertEqual(email['flagged'], 1)
    
    def test_search_emails_by_flag_status_unflagged(self):
        initialize_db()
        
        # Clear any existing data
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM emails")
        conn.commit()
        conn.close()
        
        # Save test emails
        test_emails = [
            ('uid1', 'sender1@example.com', 'Flagged Email', 'recipient@example.com', '2025-10-03', '10:00:00'),
            ('uid2', 'sender2@example.com', 'Unflagged Email 1', 'recipient@example.com', '2025-10-03', '11:00:00'),
            ('uid3', 'sender3@example.com', 'Unflagged Email 2', 'recipient@example.com', '2025-10-03', '12:00:00'),
        ]
        
        for uid, sender, subject, recipient, date, time in test_emails:
            email_dict = {
                'uid': uid,
                'from': sender,
                'subject': subject,
                'to': recipient,
                'date': date,
                'time': time,
                'body': '',
                'flagged': False,
                'attachments': []
            }
            save_email_metadata(email_dict)
        
        # Flag one email
        mark_email_flagged('uid1', True)
        # uid2 and uid3 remain unflagged (default)
        
        # Test getting unflagged emails
        unflagged_emails = search_emails_by_flag_status(False)
        self.assertEqual(len(unflagged_emails), 2)
        
        unflagged_subjects = [email['subject'] for email in unflagged_emails]
        self.assertIn('Unflagged Email 1', unflagged_subjects)
        self.assertIn('Unflagged Email 2', unflagged_subjects)
        self.assertNotIn('Flagged Email', unflagged_subjects)
        
        # Verify flagged column is included in results
        for email in unflagged_emails:
            self.assertIn('flagged', email)
            self.assertEqual(email['flagged'], 0)
    
    def test_search_emails_by_flag_status_with_limit(self):
        initialize_db()
        
        # Clear any existing data
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM emails")
        conn.commit()
        conn.close()
        
        # Save multiple flagged emails
        for i in range(5):
            uid = f'uid{i}'
            email_dict = {
                'uid': uid,
                'from': 'sender@example.com',
                'subject': f'Email {i}',
                'to': 'recipient@example.com',
                'date': '2025-10-03',
                'time': f'1{i}:00:00',
                'body': '',
                'flagged': False,
                'attachments': []
            }
            save_email_metadata(email_dict)
            mark_email_flagged(uid, True)
        
        # Test limit functionality
        flagged_emails = search_emails_by_flag_status(True, limit=3)
        self.assertEqual(len(flagged_emails), 3)
        
        # Should be ordered by date DESC, time DESC (most recent first)
        self.assertEqual(flagged_emails[0]['subject'], 'Email 4')
        self.assertEqual(flagged_emails[1]['subject'], 'Email 3')
        self.assertEqual(flagged_emails[2]['subject'], 'Email 2')
    
    def test_search_emails_includes_flagged_column(self):
        initialize_db()
        
        # Clear any existing data
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM emails")
        conn.commit()
        conn.close()
        
        # Save test email and flag it
        test_email = {
            'uid': 'test_uid',
            'from': 'sender@example.com',
            'subject': 'Test Subject',
            'to': 'recipient@example.com',
            'date': '2025-10-03',
            'time': '10:00:00',
            'body': '',
            'flagged': False,
            'attachments': []
        }
        save_email_metadata(test_email)
        mark_email_flagged('test_uid', True)
        
        # Test that search_emails includes flagged column
        results = search_emails('Test')
        self.assertEqual(len(results), 1)
        self.assertIn('flagged', results[0])
        self.assertEqual(results[0]['flagged'], 1)

    def test_database_error_handling(self):
        # Mock a database connection that raises an exception
        with patch('src.quiet_mail.core.storage.get_db_connection') as mock_conn:
            mock_conn.side_effect = sqlite3.Error("Database error")
            
            with self.assertRaises(RuntimeError) as context:
                initialize_db()
            
            self.assertIn("Failed to initialize database", str(context.exception))

    # New tests for missing functionality
    def test_search_emails_with_attachments(self):
        initialize_db()
        
        # Create test emails with and without attachments
        email_with_attachments = {
            "uid": "1001",
            "subject": "Email with attachments",
            "from": "sender@example.com",
            "to": "recipient@example.com",
            "date": "2025-10-05",
            "time": "14:30:00",
            "body": "This email has attachments",
            "flagged": False,
            "attachments": "document.pdf,image.jpg"
        }
        
        email_without_attachments = {
            "uid": "1002", 
            "subject": "Email without attachments",
            "from": "sender2@example.com",
            "to": "recipient@example.com",
            "date": "2025-10-05",
            "time": "15:30:00",
            "body": "This email has no attachments",
            "flagged": False,
            "attachments": ""
        }
        
        save_email_metadata(email_with_attachments)
        save_email_metadata(email_without_attachments)
        
        # Test searching emails with attachments
        results = search_emails_with_attachments(limit=10)
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["subject"], "Email with attachments")
        self.assertTrue(results[0]["attachments"])

    def test_get_highest_uid(self):
        initialize_db()
        
        # Test with empty database
        highest_uid = get_highest_uid()
        self.assertIsNone(highest_uid)
        
        # Add some emails with different UIDs
        emails = [
            {"uid": "5", "subject": "Email 5", "from": "test@example.com", "to": "user@example.com", 
             "date": "2025-10-05", "time": "10:00:00", "body": "Test", "flagged": False, "attachments": ""},
            {"uid": "12", "subject": "Email 12", "from": "test@example.com", "to": "user@example.com",
             "date": "2025-10-05", "time": "11:00:00", "body": "Test", "flagged": False, "attachments": ""},
            {"uid": "8", "subject": "Email 8", "from": "test@example.com", "to": "user@example.com",
             "date": "2025-10-05", "time": "12:00:00", "body": "Test", "flagged": False, "attachments": ""}
        ]
        
        for email in emails:
            save_email_metadata(email)
        
        # Test getting highest UID
        highest_uid = get_highest_uid()
        self.assertEqual(highest_uid, 12)

    def test_delete_email(self):
        initialize_db()
        
        # Create test email
        test_email = {
            "uid": "delete_test_001",
            "subject": "Email to delete",
            "from": "sender@example.com",
            "to": "recipient@example.com",
            "date": "2025-10-05",
            "time": "16:00:00",
            "body": "This email will be deleted",
            "flagged": False,
            "attachments": ""
        }
        
        save_email_metadata(test_email)
        
        # Verify email exists
        retrieved_email = get_email("delete_test_001")
        self.assertIsNotNone(retrieved_email)
        self.assertEqual(retrieved_email["subject"], "Email to delete")
        
        # Delete the email
        delete_email("delete_test_001")
        
        # Verify email is deleted
        deleted_email = get_email("delete_test_001")
        self.assertIsNone(deleted_email)

    def test_delete_email_nonexistent(self):
        initialize_db()
        
        # Try to delete non-existent email - should not raise exception
        try:
            delete_email("nonexistent_uid")
        except Exception as e:
            self.fail(f"delete_email raised exception for non-existent email: {e}")


if __name__ == '__main__':
    unittest.main()
