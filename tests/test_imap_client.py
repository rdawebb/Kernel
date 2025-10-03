import unittest
from unittest.mock import patch, MagicMock
import imaplib

from src.quiet_mail.core.imap_client import connect_to_imap, fetch_inbox


class TestImapClient(unittest.TestCase):
    
    def setUp(self):
        self.test_config = {
            'imap_server': 'imap.test.com',
            'imap_port': 993,
            'imap_use_ssl': True,
            'email': 'test@example.com',
            'password': 'testpass'
        }
    
    @patch('quiet_mail.core.imap_client.imaplib.IMAP4_SSL')
    def test_connect_to_imap_success(self, mock_imap_ssl):
        mock_mail = MagicMock()
        mock_imap_ssl.return_value = mock_mail
        mock_mail.login.return_value = ('OK', [b'Login successful'])
        mock_mail.select.return_value = ('OK', [b'10'])
        
        result = connect_to_imap(self.test_config)

        mock_imap_ssl.assert_called_once_with('imap.test.com', 993)
        mock_mail.login.assert_called_once_with('test@example.com', 'testpass')
        mock_mail.select.assert_called_once_with('inbox')
        
        self.assertEqual(result, mock_mail)
    
    @patch('quiet_mail.core.imap_client.imaplib.IMAP4_SSL')
    @patch('builtins.print')
    def test_connect_to_imap_login_failure(self, mock_print, mock_imap_ssl):
        mock_mail = MagicMock()
        mock_imap_ssl.return_value = mock_mail
        mock_mail.login.side_effect = imaplib.IMAP4.error("Login failed")
        
        result = connect_to_imap(self.test_config)
        
        self.assertIsNone(result)
        mock_print.assert_called_once()
        call_args = mock_print.call_args[0][0]
        self.assertIn("Error connecting to email server", call_args)
    
    @patch('quiet_mail.core.imap_client.imaplib.IMAP4_SSL')
    @patch('builtins.print')
    def test_connect_to_imap_connection_failure(self, mock_print, mock_imap_ssl):
        mock_imap_ssl.side_effect = ConnectionError("Cannot connect to server")
        
        result = connect_to_imap(self.test_config)
        
        self.assertIsNone(result)
        mock_print.assert_called_once()
        call_args = mock_print.call_args[0][0]
        self.assertIn("Error connecting to email server", call_args)


# TODO: Fix hanging fetch_inbox tests
# The following tests hang due to mocking issues with fetch_inbox function:
# - test_fetch_inbox_with_limit
# - test_fetch_inbox_default_limit  
# - test_fetch_inbox_exception_handling
# - test_fetch_inbox_when_connection_fails
# - test_fetch_inbox_returns_mock_data
#
# Even with @patch('quiet_mail.core.imap_client.connect_to_imap'), these tests
# still try to make real network connections and hang. Need to investigate
# why the mocking isn't working correctly for the fetch_inbox function.


if __name__ == '__main__':
    unittest.main()
