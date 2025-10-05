import unittest
import io
import contextlib

from src.quiet_mail.ui.inbox_viewer import display_inbox
from src.quiet_mail.ui.email_viewer import display_email
from src.quiet_mail.ui.search_viewer import display_search_results


class TestInboxViewer(unittest.TestCase):
    
    def setUp(self):
        self.test_emails = [
            {
                'id': 1,
                'from': 'alice@example.com',
                'subject': 'Test Email 1',
                'date': '2025-10-02',
                'time': '10:00:00',
                'flagged': 1
            },
            {
                'id': 2,
                'from': 'bob@example.com',
                'subject': 'Test Email 2',
                'date': '2025-10-01',
                'time': '11:00:00',
                'flagged': 0
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
        # Verify flag emoji appears for flagged email (no header since columns are headerless)
        self.assertIn("🚩", output)
    
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
        """Test display_inbox gracefully handles missing optional fields like flagged"""
        emails_missing_fields = [
            {
                'id': 1,
                'from': 'test@example.com',
                'subject': 'Test',
                'date': '2025-10-02'
                # Note: missing 'time' and 'flagged' fields
            }
        ]
        
        try:
            f = io.StringIO()
            with contextlib.redirect_stdout(f):
                display_inbox(emails_missing_fields)
            
            output = f.getvalue()
            self.assertIn("test@example.com", output)
            self.assertIn("Test", output)
        except Exception as e:
            self.fail(f"display_inbox should handle missing fields gracefully: {e}")


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
        original_email = self.test_email.copy()
        
        display_email(self.test_email)
        
        self.assertEqual(self.test_email, original_email)


class TestSearchViewer(unittest.TestCase):
    
    def setUp(self):
        self.test_emails_with_flags = [
            {
                'id': 1,
                'from': 'alice@example.com',
                'subject': 'Flagged Email',
                'date': '2025-10-02',
                'time': '10:00:00',
                'flagged': 1
            },
            {
                'id': 2,
                'from': 'bob@example.com',
                'subject': 'Unflagged Email',
                'date': '2025-10-01',
                'time': '11:00:00',
                'flagged': 0
            }
        ]
    
    def test_display_search_results_with_emails(self):
        """Test display_search_results shows proper table with flagged status"""
        f = io.StringIO()
        with contextlib.redirect_stdout(f):
            display_search_results(self.test_emails_with_flags, "test")
        
        output = f.getvalue()
        # Verify that table structure and data are displayed
        self.assertIn("Search Results for 'test'", output)
        self.assertIn("alice@example.com", output)
        self.assertIn("Flagged Email", output)
        self.assertIn("bob@example.com", output)
        self.assertIn("Unflagged Email", output)
        # Check for flagged column header
        self.assertIn("Flagged", output)
        # Check for flag emoji (flagged email)
        self.assertIn("🚩", output)
    
    def test_display_search_results_empty(self):
        """Test display_search_results with empty results"""
        f = io.StringIO()
        with contextlib.redirect_stdout(f):
            display_search_results([], "nonexistent")
        
        output = f.getvalue()
        self.assertIn("No emails found matching 'nonexistent'", output)
    
    def test_display_search_results_flagged_only(self):
        """Test display of only flagged emails"""
        flagged_emails = [email for email in self.test_emails_with_flags if email['flagged']]
        
        f = io.StringIO()
        with contextlib.redirect_stdout(f):
            display_search_results(flagged_emails, "flagged emails")
        
        output = f.getvalue()
        self.assertIn("Search Results for 'flagged emails'", output)
        self.assertIn("Flagged Email", output)
        self.assertNotIn("Unflagged Email", output)
        self.assertIn("🚩", output)
    
    def test_display_search_results_unflagged_only(self):
        """Test display of only unflagged emails"""
        unflagged_emails = [email for email in self.test_emails_with_flags if not email['flagged']]
        
        f = io.StringIO()
        with contextlib.redirect_stdout(f):
            display_search_results(unflagged_emails, "unflagged emails")
        
        output = f.getvalue()
        self.assertIn("Search Results for 'unflagged emails'", output)
        self.assertIn("Unflagged Email", output)
        self.assertNotIn("Flagged Email", output)
        # Should not contain flag emoji for unflagged emails
        flag_count = output.count("🚩")
        self.assertEqual(flag_count, 0)


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
