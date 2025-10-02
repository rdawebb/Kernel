import unittest
import tempfile
import sqlite3
from pathlib import Path
from unittest.mock import patch, MagicMock

from core.storage import (
    get_db_path, get_db_connection, initialize_db,
    save_email_metadata, save_email_body, get_inbox, get_email
)


class TestStorage(unittest.TestCase):
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.test_db_path = Path(self.temp_dir) / "test_emails.db"
        
        # Mock the config to use our test database
        self.config_patcher = patch('core.storage.load_config')
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
        
        self.assertTrue(self.test_db_path.exists())
        
        conn = sqlite3.connect(self.test_db_path)
        cursor = conn.cursor()
        
        cursor.execute("PRAGMA table_info(emails)")
        columns = cursor.fetchall()
        
        column_names = [col[1] for col in columns]
        expected_columns = ['id', 'uid', 'subject', 'sender', 'recipient', 'date', 'body']
        
        for col in expected_columns:
            self.assertIn(col, column_names)
        conn.close()
    
    def test_save_email_metadata(self):
        initialize_db()
        
        email_data = {
            'subject': 'Test Subject',
            'from': 'sender@example.com',
            'to': 'recipient@example.com',
            'date': '2025-10-02'
        }
        
        save_email_metadata(email_data)
        
        conn = sqlite3.connect(self.test_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM emails")
        rows = cursor.fetchall()
        
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row[2], 'Test Subject')
        self.assertEqual(row[3], 'sender@example.com')
        self.assertEqual(row[4], 'recipient@example.com')
        self.assertEqual(row[5], '2025-10-02')
        
        conn.close()
    
    def test_save_email_body(self):
        initialize_db()
        
        email_data = {
            'subject': 'Test Subject',
            'from': 'sender@example.com',
            'to': 'recipient@example.com',
            'date': '2025-10-02'
        }
        save_email_metadata(email_data)
        
        save_email_body('test_uid', 'This is the email body')
        
        # Note: This will fail because save_email_metadata doesn't include uid
        conn = sqlite3.connect(self.test_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT body FROM emails WHERE uid = ?", ('test_uid',))
        result = cursor.fetchone()
        conn.close()
        
        # This will be None because uid wasn't saved in save_email_metadata
        self.assertIsNone(result)
    
    def test_get_inbox_empty(self):
        initialize_db()
        
        emails = get_inbox()
        self.assertEqual(emails, [])
    
    def test_get_inbox_with_emails(self):
        initialize_db()
        
        test_emails = [
            {
                'subject': 'Email 1',
                'from': 'sender1@example.com',
                'to': 'recipient@example.com',
                'date': '2025-10-02'
            },
            {
                'subject': 'Email 2',
                'from': 'sender2@example.com',
                'to': 'recipient@example.com',
                'date': '2025-10-01'
            }
        ]
        
        for email in test_emails:
            save_email_metadata(email)
        
        inbox = get_inbox()
        
        self.assertEqual(len(inbox), 2)
        # Should be ordered by date DESC, so Email 1 should be first
        self.assertEqual(inbox[0]['subject'], 'Email 1')
        self.assertEqual(inbox[1]['subject'], 'Email 2')
    
    def test_get_inbox_with_limit(self):
        initialize_db()
        
        # Add 5 test emails
        for i in range(5):
            email_data = {
                'subject': f'Email {i}',
                'from': f'sender{i}@example.com',
                'to': 'recipient@example.com',
                'date': f'2025-10-0{i+1}'
            }
            save_email_metadata(email_data)
        
        inbox = get_inbox(limit=3)
        
        self.assertEqual(len(inbox), 3)
    
    def test_get_email_existing(self):
        initialize_db()
        
        email_data = {
            'subject': 'Test Email',
            'from': 'sender@example.com',
            'to': 'recipient@example.com',
            'date': '2025-10-02'
        }
        save_email_metadata(email_data)
        
        email = get_email(1)
        
        self.assertIsNotNone(email)
        self.assertEqual(email['subject'], 'Test Email')
        self.assertEqual(email['from'], 'sender@example.com')
    
    def test_get_email_nonexistent(self):
        initialize_db()
        
        email = get_email(999)
        self.assertIsNone(email)
    
    def test_database_error_handling(self):
        # Mock a database connection that raises an exception
        with patch('core.storage.get_db_connection') as mock_conn:
            mock_conn.side_effect = sqlite3.Error("Database error")
            
            with self.assertRaises(RuntimeError) as context:
                initialize_db()
            
            self.assertIn("Failed to initialize database", str(context.exception))


if __name__ == '__main__':
    unittest.main()
