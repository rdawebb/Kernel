import unittest
from unittest.mock import patch, MagicMock

from ui.inbox_viewer import display_inbox
from ui.email_viewer import display_email


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
    
    @patch('ui.inbox_viewer.console')
    def test_display_inbox_with_emails(self, mock_console):
        display_inbox(self.test_emails)
        
        mock_console.print.assert_called_once()
        
        call_args = mock_console.print.call_args[0][0]
        
        from rich.table import Table
        self.assertIsInstance(call_args, Table)
    
    @patch('ui.inbox_viewer.console')
    def test_display_inbox_empty(self, mock_console):
        display_inbox([])
        
        mock_console.print.assert_called_once()
        
        call_args = mock_console.print.call_args[0][0]
        from rich.table import Table
        self.assertIsInstance(call_args, Table)
    
    def test_display_inbox_data_integrity(self):
        # Test ensures the function doesn't crash with real data
        try:
            display_inbox(self.test_emails)
        except Exception as e:
            self.fail(f"display_inbox raised an exception: {e}")
    
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
    
    @patch('ui.email_viewer.console')
    def test_display_email_complete(self, mock_console):
        display_email(self.test_email)
        
        self.assertTrue(mock_console.print.called)
        
        all_calls = str(mock_console.print.call_args_list)
        self.assertIn('sender@example.com', all_calls)
        self.assertIn('Test Email Subject', all_calls)
        self.assertIn('2025-10-02', all_calls)
        self.assertIn('This is the email body content.', all_calls)
    
    @patch('ui.email_viewer.console')
    def test_display_email_missing_body(self, mock_console):
        email_no_body = self.test_email.copy()
        email_no_body['body'] = None
        
        display_email(email_no_body)
        
        all_calls = str(mock_console.print.call_args_list)
        self.assertIn('sender@example.com', all_calls)
        self.assertIn('Test Email Subject', all_calls)
    
    @patch('ui.email_viewer.console')
    def test_display_email_missing_fields(self, mock_console):
        minimal_email = {
            'from': 'sender@example.com',
            'subject': 'Test Subject'
            # Missing date and body
        }
        
        display_email(minimal_email)
        
        self.assertTrue(mock_console.print.called)
    
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
    
    @patch('ui.inbox_viewer.console')
    @patch('ui.email_viewer.console')
    def test_ui_components_dont_interfere(self, mock_email_console, mock_inbox_console):
        emails = [{'id': 1, 'from': 'test@example.com', 'subject': 'Test', 'date': '2025-10-02'}]
        
        display_inbox(emails)
        display_email(emails[0])
        
        self.assertTrue(mock_inbox_console.print.called)
        self.assertTrue(mock_email_console.print.called)


if __name__ == '__main__':
    unittest.main()
