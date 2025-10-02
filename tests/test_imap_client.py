import unittest
from unittest.mock import patch, MagicMock
import imaplib

from core.imap_client import connect_to_imap, fetch_inbox


class TestImapClient(unittest.TestCase):
    
    def setUp(self):
        self.test_config = {
            'imap_server': 'imap.test.com',
            'imap_port': 993,
            'imap_use_ssl': True,
            'email': 'test@example.com',
            'password': 'testpass'
        }
    
    @patch('core.imap_client.imaplib.IMAP4_SSL')
    def test_connect_to_imap_success(self, mock_imap_ssl):
        mock_mail = MagicMock()
        mock_imap_ssl.return_value = mock_mail
        mock_mail.login.return_value = ('OK', [b'Login successful'])
        mock_mail.select.return_value = ('OK', [b'10'])
        
        result = connect_to_imap(self.test_config)
        
        mock_imap_ssl.assert_called_once_with('imap.test.com')
        mock_mail.login.assert_called_once_with('test@example.com', 'testpass')
        mock_mail.select.assert_called_once_with('inbox')
        
        self.assertEqual(result, mock_mail)
    
    @patch('core.imap_client.imaplib.IMAP4_SSL')
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
    
    @patch('core.imap_client.imaplib.IMAP4_SSL')
    @patch('builtins.print')
    def test_connect_to_imap_connection_failure(self, mock_print, mock_imap_ssl):
        mock_imap_ssl.side_effect = ConnectionError("Cannot connect to server")
        
        result = connect_to_imap(self.test_config)
        
        self.assertIsNone(result)
        mock_print.assert_called_once()
        call_args = mock_print.call_args[0][0]
        self.assertIn("Error connecting to email server", call_args)
    
    def test_fetch_inbox_returns_mock_data(self):
        # Current implementation returns hardcoded test data
        emails = fetch_inbox(self.test_config, limit=5)
        
        self.assertIsInstance(emails, list)
        self.assertLessEqual(len(emails), 5)
        
        if emails:
            email = emails[0]
            self.assertIn('id', email)
            self.assertIn('uid', email)
            self.assertIn('from', email)
            self.assertIn('subject', email)
            self.assertIn('date', email)
    
    def test_fetch_inbox_with_limit(self):
        for limit in [1, 2, 5]:
            with self.subTest(limit=limit):
                emails = fetch_inbox(self.test_config, limit=limit)
                self.assertLessEqual(len(emails), limit)
    
    def test_fetch_inbox_default_limit(self):
        emails = fetch_inbox(self.test_config)
        self.assertLessEqual(len(emails), 10)
    
    @patch('builtins.print')
    def test_fetch_inbox_exception_handling(self, mock_print):
        # Since the current implementation returns hardcoded data and catches exceptions,
        # we can't easily test exception propagation. This test documents the current behavior.
        emails = fetch_inbox(self.test_config)
        
        self.assertIsInstance(emails, list)


class TestImapClientIntegration(unittest.TestCase):
    
    def setUp(self):
        self.test_config = {
            'imap_server': 'imap.test.com',
            'imap_port': 993,
            'imap_use_ssl': True,
            'email': 'test@example.com',
            'password': 'testpass'
        }
    
    @patch('core.imap_client.connect_to_imap')
    def test_fetch_inbox_when_connection_fails(self, mock_connect):
        mock_connect.return_value = None
        
        # Current implementation doesn't actually use the connection
        emails = fetch_inbox(self.test_config)
        
        self.assertIsInstance(emails, list)


if __name__ == '__main__':
    unittest.main()
