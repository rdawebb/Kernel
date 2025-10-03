import unittest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys

from src.quiet_mail.cli import main

class TestCLI(unittest.TestCase):
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.test_db_path = Path(self.temp_dir) / "test_emails.db"
        
        self.test_env = {
            'IMAP_SERVER': 'imap.test.com',
            'IMAP_PORT': '993',
            'IMAP_USE_SSL': 'true',
            'EMAIL': 'test@example.com',
            'PASSWORD': 'testpass',
            'DB_PATH': str(self.test_db_path)
        }
        self.original_env = {}
        for key in self.test_env:
            self.original_env[key] = os.environ.get(key)
            os.environ[key] = self.test_env[key]
    
    def tearDown(self):
        for key, value in self.original_env.items():
            if value is not None:
                os.environ[key] = value
            elif key in os.environ:
                del os.environ[key]
        
        if self.test_db_path.exists():
            self.test_db_path.unlink()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    # TODO: Fix console mocking for Rich Console integration
    pass
    
    @patch('sys.argv', ['cli.py', 'list', '--limit', '5'])
    @patch('src.quiet_mail.cli.console')
    @patch('quiet_mail.core.storage.initialize_db')
    @patch('quiet_mail.ui.inbox_viewer.display_inbox')
    @patch('quiet_mail.core.imap_client.fetch_inbox')
    @patch('quiet_mail.core.storage.save_email_metadata')
    def test_list_command_with_limit(self, mock_save_email, mock_fetch_inbox, mock_display_inbox, mock_init_db, mock_console):
        mock_fetch_inbox.return_value = []
        
        main()
        
        # Verify fetch_inbox was called with correct limit
        args, kwargs = mock_fetch_inbox.call_args
        self.assertEqual(kwargs.get('limit'), 5)
    
    @patch('sys.argv', ['cli.py', 'view', '1'])
    @patch('quiet_mail.core.storage.initialize_db')
    @patch('quiet_mail.ui.email_viewer.display_email')
    @patch('quiet_mail.core.storage.get_email')
    @patch('src.quiet_mail.cli.console')  # Mock the global console object
    def test_view_command_existing_email(self, mock_console, mock_get_email, mock_display_email, mock_init_db):
        mock_email = {
            'id': 1,
            'from': 'test@example.com',
            'subject': 'Test Email',
            'date': '2025-10-02',
            'body': 'Test body'
        }
        mock_get_email.return_value = mock_email
        
        main()
        
        # CLI passes string arguments, not integers
        mock_get_email.assert_called_once_with('1')
        mock_display_email.assert_called_once_with(mock_email)
    
    @patch('sys.argv', ['cli.py', 'view', '999'])
    @patch('quiet_mail.core.storage.initialize_db')
    @patch('quiet_mail.core.storage.get_email')
    @patch('src.quiet_mail.cli.console')  # Mock the global console object
    def test_view_command_nonexistent_email(self, mock_console, mock_get_email, mock_init_db):
        mock_get_email.return_value = None
        
        main()
        
        mock_console.print.assert_called()
        calls = [str(call) for call in mock_console.print.call_args_list]
        error_found = any('999 not found' in call for call in calls)
        self.assertTrue(error_found)
    
    @patch('sys.argv', ['cli.py', 'list'])
    @patch('src.quiet_mail.cli.console')  # Mock the global console object
    @patch('quiet_mail.utils.config.load_config')
    def test_config_error_handling(self, mock_load_config, mock_console):
        mock_load_config.side_effect = ValueError("Missing configuration")
        
        main()
        
        mock_console.print.assert_called()
        calls = [str(call) for call in mock_console.print.call_args_list]
        error_found = any('Configuration error' in call for call in calls)
        self.assertTrue(error_found)
    
    @patch('sys.argv', ['cli.py', 'list'])
    @patch('src.quiet_mail.cli.console')  # Mock the global console object
    @patch('quiet_mail.core.imap_client.fetch_inbox')
    def test_imap_error_handling(self, mock_fetch_inbox, mock_console):
        mock_fetch_inbox.side_effect = Exception("IMAP connection failed")
        
        main()
        
        mock_console.print.assert_called()
        calls = [str(call) for call in mock_console.print.call_args_list]
        error_found = any('Failed to fetch' in call for call in calls)
        self.assertTrue(error_found)
    
    @patch('sys.argv', ['cli.py', 'list', '--cached'])
    @patch('src.quiet_mail.cli.console')
    @patch('quiet_mail.core.storage.get_inbox')
    def test_storage_operation_failure(self, mock_get_inbox, mock_console):
        # Test storage operation failure during runtime
        mock_get_inbox.side_effect = Exception("Failed to load emails")
        
        main()
        
        mock_console.print.assert_called()
        calls = [str(call) for call in mock_console.print.call_args_list]
        error_found = any('Failed to load emails' in call for call in calls)
        self.assertTrue(error_found)


class TestCLIArgumentParsing(unittest.TestCase):
    """Test CLI argument parsing separately"""
    
    def test_help_command(self):
        with patch('sys.argv', ['cli.py', '--help']):
            with patch('sys.exit'):
                try:
                    main()
                except SystemExit:
                    pass  # Help command causes SystemExit, which is expected
    
    def test_invalid_command(self):
        with patch('sys.argv', ['cli.py', 'invalid_command']):
            with patch('sys.exit'):
                try:
                    main()
                except SystemExit:
                    pass  # Invalid command causes SystemExit, which is expected


if __name__ == '__main__':
    unittest.main()
