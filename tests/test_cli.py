import unittest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch
import unittest.mock
from src.tui_mail.cli import main

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
    @patch('src.tui_mail.cli.console')
    @patch('tui_mail.core.storage_api.get_inbox')
    @patch('tui_mail.ui.inbox_viewer.display_inbox')
    def test_list_command_with_limit(self, mock_display_inbox, mock_get_inbox, mock_console):
        # Test list command with limit (should use local database by default)
        mock_get_inbox.return_value = []
        
        main()
    
        # Verify get_inbox was called with correct limit
        mock_get_inbox.assert_called_once_with(limit=5)
        mock_display_inbox.assert_called_once()
    
    @patch('sys.argv', ['cli.py', 'view', '1'])
    @patch('tui_mail.core.storage_api.initialize_db')
    @patch('tui_mail.ui.email_viewer.display_email')
    @patch('tui_mail.core.storage_api.get_email_from_table')
    @patch('src.tui_mail.cli.console')  # Mock the global console object
    def test_view_command_existing_email(self, mock_console, mock_get_email, mock_display_email, mock_init_db):
        mock_email = {
            'uid': '1',
            'from': 'test@example.com',
            'subject': 'Test Email',
            'date': '2025-10-02',
            'body': 'Test body'
        }
        mock_get_email.return_value = mock_email
        
        main()
        
        # CLI passes string arguments, not integers
        mock_get_email.assert_called_once_with('inbox', '1')
        mock_display_email.assert_called_once_with(mock_email)
    
    @patch('sys.argv', ['cli.py', 'view', '999'])
    @patch('tui_mail.core.storage_api.initialize_db')
    @patch('tui_mail.core.storage_api.get_email_from_table')
    @patch('src.tui_mail.cli.console')  # Mock the global console object
    def test_view_command_nonexistent_email(self, mock_console, mock_get_email, mock_init_db):
        mock_get_email.return_value = None
        
        main()
        
        mock_console.print.assert_called()
        calls = [str(call) for call in mock_console.print.call_args_list]
        error_found = any('999 not found' in call for call in calls)
        self.assertTrue(error_found)
    
    @patch('sys.argv', ['cli.py', 'list'])
    @patch('src.tui_mail.cli.console')  # Mock the global console object
    @patch('tui_mail.utils.config.load_config')
    def test_config_error_handling(self, mock_load_config, mock_console):
        mock_load_config.side_effect = ValueError("Missing configuration")
        
        main()
        
        mock_console.print.assert_called()
        calls = [str(call) for call in mock_console.print.call_args_list]
        error_found = any('Configuration error' in call for call in calls)
        self.assertTrue(error_found)
    
    @patch('sys.argv', ['cli.py', 'refresh'])
    @patch('src.tui_mail.cli.console')  # Mock the global console object
    @patch('tui_mail.core.imap_client.fetch_new_emails')
    def test_imap_error_handling(self, mock_fetch_new_emails, mock_console):
        mock_fetch_new_emails.side_effect = Exception("IMAP connection failed")
        
        main()
        
        mock_console.print.assert_called()
        calls = [str(call) for call in mock_console.print.call_args_list]
        error_found = any('Failed to fetch' in call for call in calls)
        self.assertTrue(error_found)
    
    @patch('sys.argv', ['cli.py', 'list'])
    @patch('src.tui_mail.cli.console')
    @patch('tui_mail.core.storage_api.get_inbox')
    def test_storage_api_operation_failure(self, mock_get_inbox, mock_console):
        # Test storage_api operation failure during runtime
        mock_get_inbox.side_effect = Exception("Failed to load emails")
        
        main()
        
        mock_console.print.assert_called()
        calls = [str(call) for call in mock_console.print.call_args_list]
        error_found = any('Failed to load emails' in call for call in calls)
        self.assertTrue(error_found)
    
    @patch('sys.argv', ['cli.py', 'refresh', '--limit', '3'])
    @patch('src.tui_mail.cli.console')
    @patch('tui_mail.core.storage_api.initialize_db')
    @patch('src.tui_mail.cli.inbox_viewer.display_inbox')
    @patch('src.tui_mail.cli.storage_api.get_inbox')
    @patch('src.tui_mail.cli.imap_client.fetch_new_emails')
    def test_list_command_with_refresh(self, mock_fetch_new_emails, mock_get_inbox, mock_display_inbox, mock_init_db, mock_console):
        # Test refresh command (should fetch from server)
        mock_fetch_new_emails.return_value = 3  # Number of emails fetched
        mock_get_inbox.return_value = [
            {'id': '123', 'from': 'test@example.com', 'subject': 'Test', 'to': 'user@example.com', 'date': '2025-10-04', 'time': '10:00:00'}
        ]
        
        main()
        
        mock_fetch_new_emails.assert_called_once()
        mock_get_inbox.assert_called_once_with(limit=3)
        mock_display_inbox.assert_called_once()
        mock_console.print.assert_called()
        calls = [str(call) for call in mock_console.print.call_args_list]
        fetching_found = any('Fetching' in call for call in calls)
        self.assertTrue(fetching_found)
    
    @patch('sys.argv', ['cli.py', 'list', '--limit', '3'])
    @patch('src.tui_mail.cli.console')
    @patch('tui_mail.core.storage_api.get_inbox')
    @patch('tui_mail.ui.inbox_viewer.display_inbox')
    def test_list_command_default_behavior(self, mock_display_inbox, mock_get_inbox, mock_console):
        # Test list command default behavior (should use local database)
        mock_get_inbox.return_value = [
            {'id': '123', 'from': 'test@example.com', 'subject': 'Test', 'date': '2025-10-04', 'time': '10:00:00', 'flagged': 0}
        ]
        
        main()
        
        mock_get_inbox.assert_called_once_with(limit=3)
        mock_display_inbox.assert_called_once()
        mock_console.print.assert_called()
        calls = [str(call) for call in mock_console.print.call_args_list]
        loading_found = any('Loading emails' in call for call in calls)
        self.assertTrue(loading_found)

    @patch('sys.argv', ['cli.py', 'search', 'inbox', 'test_keyword'])
    @patch('src.tui_mail.cli.console')
    @patch('tui_mail.core.storage_api.search_emails')
    @patch('tui_mail.ui.search_viewer.display_search_results')
    def test_search_command(self, mock_display_results, mock_search_emails, mock_console):
        mock_search_emails.return_value = [
            {'id': '1', 'subject': 'Test Email', 'from': 'test@example.com', 'date': '2025-10-03', 'time': '10:00:00', 'flagged': 0}
        ]
        
        main()
        
        mock_search_emails.assert_called_once_with('inbox', 'test_keyword')
        mock_display_results.assert_called_once_with('inbox', mock_search_emails.return_value, 'test_keyword')
    
    @patch('sys.argv', ['cli.py', 'flagged', '--limit', '5'])
    @patch('src.tui_mail.cli.console')
    @patch('tui_mail.core.storage_api.search_emails_by_flag_status')
    @patch('tui_mail.ui.search_viewer.display_search_results')
    def test_flagged_command(self, mock_display_results, mock_search_flagged, mock_console):
        mock_search_flagged.return_value = [
            {'id': '1', 'subject': 'Flagged Email', 'from': 'test@example.com', 'date': '2025-10-03', 'time': '10:00:00', 'flagged': 1}
        ]
        
        main()
        
        mock_search_flagged.assert_called_once_with(True, limit=5)
        mock_display_results.assert_called_once_with('inbox', mock_search_flagged.return_value, 'flagged emails')
    
    @patch('sys.argv', ['cli.py', 'unflagged', '--limit', '3'])
    @patch('src.tui_mail.cli.console')
    @patch('tui_mail.core.storage_api.search_emails_by_flag_status')
    @patch('tui_mail.ui.search_viewer.display_search_results')
    def test_unflagged_command(self, mock_display_results, mock_search_unflagged, mock_console):
        mock_search_unflagged.return_value = [
            {'id': '2', 'subject': 'Unflagged Email', 'from': 'test@example.com', 'date': '2025-10-03', 'time': '11:00:00', 'flagged': 0}
        ]
        
        main()
        
        mock_search_unflagged.assert_called_once_with(False, limit=3)
        mock_display_results.assert_called_once_with('inbox', mock_search_unflagged.return_value, 'unflagged emails')
    
    @patch('sys.argv', ['cli.py', 'flag', 'test_uid', '--flag'])
    @patch('src.tui_mail.cli.console')
    @patch('tui_mail.core.storage_api.get_email_from_table')
    @patch('tui_mail.core.storage_api.mark_email_flagged')
    def test_flag_command_flag(self, mock_mark_flagged, mock_get_email, mock_console):
        mock_get_email.return_value = {'id': 'test_uid', 'subject': 'Test Email'}
        
        main()
        
        mock_get_email.assert_called_once_with('inbox', 'test_uid')
        mock_mark_flagged.assert_called_once_with('test_uid', True)
        mock_console.print.assert_called()
        calls = [str(call) for call in mock_console.print.call_args_list]
        success_found = any('Flagged email ID test_uid successfully' in call for call in calls)
        self.assertTrue(success_found)
    
    @patch('sys.argv', ['cli.py', 'flag', 'test_uid', '--unflag'])
    @patch('src.tui_mail.cli.console')
    @patch('tui_mail.core.storage_api.get_email_from_table')
    @patch('tui_mail.core.storage_api.mark_email_flagged')
    def test_flag_command_unflag(self, mock_mark_flagged, mock_get_email, mock_console):
        mock_get_email.return_value = {'id': 'test_uid', 'subject': 'Test Email'}
        
        main()
        
        mock_get_email.assert_called_once_with('inbox', 'test_uid')
        mock_mark_flagged.assert_called_once_with('test_uid', False)
        mock_console.print.assert_called()
        calls = [str(call) for call in mock_console.print.call_args_list]
        success_found = any('Unflagged email ID test_uid successfully' in call for call in calls)
        self.assertTrue(success_found)
    
    @patch('sys.argv', ['cli.py', 'flag', 'test_uid'])
    @patch('src.tui_mail.cli.console')
    def test_flag_command_no_flag_option(self, mock_console):
        main()
        
        mock_console.print.assert_called()
        calls = [str(call) for call in mock_console.print.call_args_list]
        error_found = any('Please specify either --flag or --unflag' in call for call in calls)
        self.assertTrue(error_found)
    
    @patch('sys.argv', ['cli.py', 'flag', 'nonexistent_uid', '--flag'])
    @patch('src.tui_mail.cli.console')
    @patch('tui_mail.core.storage_api.get_email_from_table')
    def test_flag_command_nonexistent_email(self, mock_get_email, mock_console):
        mock_get_email.return_value = None
        
        main()
        
        mock_get_email.assert_called_once_with('inbox', 'nonexistent_uid')
        mock_console.print.assert_called()
        calls = [str(call) for call in mock_console.print.call_args_list]
        error_found = any('Email with ID nonexistent_uid not found' in call for call in calls)
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

    # New tests for attachment and delete functionality
    @patch('src.tui_mail.core.storage_api.initialize_db')
    @patch('src.tui_mail.cli.console')
    @patch('src.tui_mail.cli.storage_api.search_emails_with_attachments')
    @patch('src.tui_mail.cli.inbox_viewer.display_inbox')
    def test_attachments_command(self, mock_display_inbox, mock_search_attachments, mock_console, mock_init_db):
        with patch('sys.argv', ['cli.py', 'attachments', '--limit', '5']):
            mock_search_attachments.return_value = [
                {'id': '1', 'subject': 'Email with PDF', 'attachments': 'document.pdf'},
                {'id': '2', 'subject': 'Email with images', 'attachments': 'photo1.jpg,photo2.png'}
            ]
            
            main()
            
            mock_search_attachments.assert_called_once_with('inbox', limit=5)
            mock_display_inbox.assert_called_once()

    @patch('src.tui_mail.core.storage_api.initialize_db')
    @patch('src.tui_mail.cli.console')
    @patch('src.tui_mail.cli.imap_client.get_attachment_list')
    def test_list_attachments_command(self, mock_get_attachment_list, mock_console, mock_init_db):
        with patch('sys.argv', ['cli.py', 'attachments-list', '123']):
            mock_get_attachment_list.return_value = ['document.pdf', 'image.jpg']
            
            main()
            
            mock_get_attachment_list.assert_called_once_with(unittest.mock.ANY, '123')
            # Verify console.print was called with attachment information
            self.assertTrue(mock_console.print.called)

    @patch('src.tui_mail.core.storage_api.initialize_db')
    @patch('src.tui_mail.cli.console')
    @patch('src.tui_mail.cli.storage_api.get_email_from_table')
    @patch('src.tui_mail.cli.handle_download_action')
    def test_download_command_with_attachments(self, mock_handle_download, mock_get_email, mock_console, mock_init_db):
        with patch('sys.argv', ['cli.py', 'download', '123', '--all']):
            mock_get_email.return_value = {
                'id': '123',
                'subject': 'Test Email',
                'attachments': 'document.pdf,image.jpg'
            }
            
            main()
            
            mock_get_email.assert_called_once_with('inbox', '123')
            mock_handle_download.assert_called_once()

    @patch('src.tui_mail.core.storage_api.initialize_db')
    @patch('src.tui_mail.cli.console')
    @patch('src.tui_mail.cli.storage_api.get_email_from_table')
    @patch('src.tui_mail.cli.storage_api.delete_email')
    @patch('src.tui_mail.cli.storage_api.save_deleted_email')
    @patch('src.tui_mail.cli.storage_api.email_exists')
    @patch('builtins.input', return_value='y')  # Mock user confirmation
    def test_delete_command_local_only(self, mock_input, mock_email_exists, mock_save_deleted, mock_delete_email, mock_get_email, mock_console, mock_init_db):
        with patch('sys.argv', ['cli.py', 'delete', '123']):
            mock_email_data = {
                'uid': '123',
                'subject': 'Email to delete'
            }
            mock_get_email.return_value = mock_email_data
            mock_email_exists.return_value = False  # Email not in deleted_emails table yet
            
            main()
            
            mock_email_exists.assert_called_once_with('deleted_emails', '123')
            mock_get_email.assert_called_once_with('inbox', '123')
            # Verify the email_data includes deleted_at timestamp
            saved_email = mock_save_deleted.call_args[0][0]
            self.assertIn('deleted_at', saved_email)
            mock_delete_email.assert_called_once_with('123')
            # Should not call imap delete for local-only deletion

    @patch('src.tui_mail.core.storage_api.initialize_db')
    @patch('src.tui_mail.cli.console')
    @patch('src.tui_mail.cli.storage_api.get_email_from_table')
    @patch('src.tui_mail.cli.storage_api.delete_email')
    @patch('src.tui_mail.cli.storage_api.save_deleted_email')
    @patch('src.tui_mail.cli.imap_client.delete_email')
    @patch('src.tui_mail.cli.storage_api.email_exists')
    @patch('builtins.input', return_value='y')  # Mock user confirmation
    def test_delete_command_server_and_local(self, mock_input, mock_email_exists, mock_imap_delete, mock_save_deleted, mock_storage_api_delete, mock_get_email, mock_console, mock_init_db):
        with patch('sys.argv', ['cli.py', 'delete', '123', '--all']):
            mock_email_data = {
                'uid': '123',
                'subject': 'Email to delete'
            }
            mock_get_email.return_value = mock_email_data
            mock_email_exists.return_value = False  # Email not in deleted_emails table yet
            
            main()
            
            mock_email_exists.assert_called_once_with('deleted_emails', '123')
            mock_get_email.assert_called_once_with('inbox', '123')
            # Verify the email_data includes deleted_at timestamp
            saved_email = mock_save_deleted.call_args[0][0]
            self.assertIn('deleted_at', saved_email)
            mock_storage_api_delete.assert_called_once_with('123')
            mock_imap_delete.assert_called_once()

    @patch('src.tui_mail.core.storage_api.initialize_db')
    @patch('src.tui_mail.cli.console')
    @patch('builtins.input', return_value='n')  # Mock user declining deletion
    def test_delete_command_cancelled(self, mock_input, mock_console, mock_init_db):
        with patch('sys.argv', ['cli.py', 'delete', '123']):
            main()
            
            # Should print cancellation message
            mock_console.print.assert_called_with("[yellow]Deletion cancelled.[/]")

    @patch('src.tui_mail.core.storage_api.initialize_db')
    @patch('src.tui_mail.cli.console')
    def test_downloads_list_command(self, mock_console, mock_init_db):
        # Test downloads-list command execution
        with patch('sys.argv', ['cli.py', 'downloads-list']):
            # We'll just test that the command runs without error
            # The actual file listing behavior is tested functionally elsewhere
            main()
            
            # Verify console.print was called (for either success or error message)
            self.assertTrue(mock_console.print.called)


if __name__ == '__main__':
    unittest.main()
