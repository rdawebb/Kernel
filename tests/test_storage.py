import unittest
import tempfile
import sqlite3
from pathlib import Path
from unittest.mock import patch

from src.quiet_mail.core.storage import (
    get_db_path, get_db_connection, initialize_db,
    save_email_metadata, save_email_body, get_inbox, get_email
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
        expected_columns = ['id', 'uid', 'subject', 'sender', 'recipient', 'date', 'time', 'body']
        
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
        
        # Use the correct function signature: uid, sender, subject, recipient, date, time
        save_email_metadata(
            uid='test_uid_123',
            sender='sender@example.com',
            subject='Test Subject',
            recipient='recipient@example.com',
            date='2025-10-02',
            time='10:30:00'
        )
        
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
        
        # First save email metadata with correct function signature
        save_email_metadata(
            uid='test_uid_123',
            sender='sender@example.com', 
            subject='Test Subject',
            recipient='recipient@example.com',
            date='2025-10-02',
            time='10:30:00'
        )
        
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
            save_email_metadata(
                uid=email['uid'],
                sender=email['sender'], 
                subject=email['subject'],
                recipient=email['recipient'],
                date=email['date'],
                time=email['time']
            )
        
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
            save_email_metadata(
                uid=f'test_uid_{i}',
                sender=f'sender{i}@example.com', 
                subject=f'Email {i}',
                recipient='recipient@example.com',
                date=f'2025-10-0{i+1}',
                time='10:30:00'
            )
        
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
        
        save_email_metadata(
            uid='test_uid_123',
            sender='sender@example.com', 
            subject='Test Email',
            recipient='recipient@example.com',
            date='2025-10-02',
            time='10:30:00'
        )
        
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
    
    def test_database_error_handling(self):
        # Mock a database connection that raises an exception
        with patch('src.quiet_mail.core.storage.get_db_connection') as mock_conn:
            mock_conn.side_effect = sqlite3.Error("Database error")
            
            with self.assertRaises(RuntimeError) as context:
                initialize_db()
            
            self.assertIn("Failed to initialize database", str(context.exception))


if __name__ == '__main__':
    unittest.main()
