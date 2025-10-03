import unittest
import io
import contextlib
from unittest.mock import patch, MagicMock

from src.quiet_mail.ui.inbox_viewer import display_inbox
from src.quiet_mail.ui.email_viewer import display_email


class TestInboxViewer(unittest.TestCase):
    
    def setUp(self):
        self.test_emails = [
            {
                'id': 1,
                'from': 'alice@example.com',
                'subject': 'Test Email 1',
                'date': '2025-10-02'
            },
            {
                'id': 2,
                'from': 'bob@example.com',
                'subject': 'Test Email 2',
                'date': '2025-10-01'
            }
        ]
    
    def test_display_inbox_with_emails_table_structure(self):
        """Test display_inbox shows proper table structure with emails"""
        f = io.StringIO()
        with contextlib.redirect_stdout(f):
            display_inbox(self.test_emails)
        
        output = f.getvalue()
        # Verify that table structure and data are displayed
        self.assertIn("Inbox", output)
        self.assertIn("alice@example.com", output)
        self.assertIn("Test Email 1", output)
        self.assertIn("bob@example.com", output)
        self.assertIn("Test Email 2", output)
    
    def test_display_inbox_empty(self):
        """Test display_inbox with empty list - should show empty table structure"""
        # Capture stdout to verify the table is displayed
        import io
        import contextlib
        
        f = io.StringIO()
        with contextlib.redirect_stdout(f):
            display_inbox([])
        
        output = f.getvalue()
        # Verify that a table structure is displayed
        self.assertIn("Inbox", output)
        self.assertIn("ID", output) 
        self.assertIn("From", output)
        self.assertIn("Subject", output)

    def test_display_inbox_with_emails(self):
        """Test display_inbox with email data - should show populated table"""
        import io
        import contextlib
        
        f = io.StringIO()
        with contextlib.redirect_stdout(f):
            display_inbox(self.test_emails)
        
        output = f.getvalue()
        # Verify that table structure and data are displayed
        self.assertIn("Inbox", output)
        self.assertIn("alice@example.com", output)
        self.assertIn("Test Email 1", output)
        self.assertIn("bob@example.com", output)
        self.assertIn("Test Email 2", output)
    
    def test_display_inbox_with_missing_fields(self):
        incomplete_emails = [
            {
                'id': 1,
                'from': 'alice@example.com',
                # Missing subject and date
            },
            {
                'id': 2,
                'subject': 'Test Email 2',
                # Missing from and date
            }
        ]
        
        try:
            display_inbox(incomplete_emails)
        except Exception as e:
            self.fail(f"display_inbox should handle missing fields: {e}")


class TestEmailViewer(unittest.TestCase):
    
    def setUp(self):
        self.test_email = {
            'id': 1,
            'from': 'sender@example.com',
            'subject': 'Test Email Subject',
            'date': '2025-10-02',
            'body': 'This is the email body content.'
        }
    
    def test_display_email_complete(self):
        """Test display_email with complete email data"""
        f = io.StringIO()
        with contextlib.redirect_stdout(f):
            display_email(self.test_email)
        
        output = f.getvalue()
        self.assertIn('sender@example.com', output)
        self.assertIn('Test Email Subject', output)
        self.assertIn('2025-10-02', output)
        self.assertIn('This is the email body content.', output)
    
    def test_display_email_missing_body(self):
        """Test display_email with missing body"""
        email_no_body = self.test_email.copy()
        email_no_body['body'] = None
        
        f = io.StringIO()
        with contextlib.redirect_stdout(f):
            display_email(email_no_body)
        
        output = f.getvalue()
        self.assertIn('sender@example.com', output)
        self.assertIn('Test Email Subject', output)
    
    def test_display_email_missing_fields(self):
        """Test display_email with minimal fields"""
        minimal_email = {
            'from': 'sender@example.com',
            'subject': 'Test Subject'
            # Missing date and body
        }
        
        f = io.StringIO()
        with contextlib.redirect_stdout(f):
            display_email(minimal_email)
        
        output = f.getvalue()
        self.assertIn('sender@example.com', output)
        self.assertIn('Test Subject', output)
    
    def test_display_email_data_integrity(self):
        try:
            display_email(self.test_email)
        except Exception as e:
            self.fail(f"display_email raised an exception: {e}")
    
    def test_display_email_none_values(self):
        email_with_nones = {
            'from': 'sender@example.com',
            'subject': None,
            'date': None,
            'body': None
        }
        
        try:
            display_email(email_with_nones)
        except Exception as e:
            self.fail(f"display_email should handle None values: {e}")
    
    def test_display_email_data_integrity(self):
        original_email = self.test_email.copy()
        
        display_email(self.test_email)
        
        self.assertEqual(self.test_email, original_email)


class TestUIIntegration(unittest.TestCase):
    
    def test_inbox_to_email_workflow(self):
        emails = [
            {
                'id': 1,
                'from': 'alice@example.com',
                'subject': 'Test Email',
                'date': '2025-10-02',
                'body': 'Email content'
            }
        ]
        
        try:
            display_inbox(emails)
            display_email(emails[0])
        except Exception as e:
            self.fail(f"UI workflow failed: {e}")
    
    def test_display_functions_handle_empty_data(self):
        try:
            display_inbox([])
            display_email({})
        except Exception as e:
            self.fail(f"UI functions should handle empty data: {e}")
    
    def test_ui_components_dont_interfere(self):
        """Test that both UI components can be used together without issues"""
        emails = [{'id': 1, 'from': 'test@example.com', 'subject': 'Test', 'date': '2025-10-02'}]
        
        f = io.StringIO()
        with contextlib.redirect_stdout(f):
            display_inbox(emails)
            display_email(emails[0])
        
        output = f.getvalue()
        # Check that both components produced output
        self.assertIn('test@example.com', output)
        self.assertIn('Test', output)


if __name__ == '__main__':
    unittest.main()
