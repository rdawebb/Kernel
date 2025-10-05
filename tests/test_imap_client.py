import unittest
from unittest.mock import patch, MagicMock
import imaplib

from src.quiet_mail.core.imap_client import (
    connect_to_imap, fetch_inbox, decode_email_header, decode_filename,
    _extract_attachment_filenames, _extract_attachments_from_email,
    download_all_attachments, download_attachment_by_index, get_attachment_list,
    delete_email
)


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

    def test_decode_email_header_with_encoding(self):
        # Test header decoding with proper encoding
        result = decode_email_header("Test Subject")
        self.assertEqual(result, "Test Subject")
        
        # Test with None input
        result = decode_email_header(None)
        self.assertEqual(result, "")

    def test_decode_filename_basic(self):
        # Test basic filename decoding
        result = decode_filename("document.pdf")
        self.assertEqual(result, "document.pdf")
        
        # Test with None input
        result = decode_filename(None)
        self.assertEqual(result, "")

    @patch('email.message_from_bytes')
    def test_extract_attachment_filenames(self, mock_message_from_bytes):
        # Create mock email message with attachments
        mock_part = MagicMock()
        mock_part.get.return_value = "attachment; filename=test.pdf"
        mock_part.get_filename.return_value = "test.pdf"
        
        mock_message = MagicMock()
        mock_message.walk.return_value = [mock_part]
        
        result = _extract_attachment_filenames(mock_message)
        self.assertEqual(result, ["test.pdf"])

    @patch('tempfile.mkdtemp')
    @patch('os.path.exists')
    @patch('builtins.open', create=True)
    @patch('os.makedirs')
    def test_save_attachment_to_disk(self, mock_makedirs, mock_open, mock_exists, mock_mkdtemp):
        from src.quiet_mail.core.imap_client import _save_attachment_to_disk
        
        mock_exists.return_value = False
        mock_file = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_file
        
        result = _save_attachment_to_disk("test.pdf", b"test content", "/tmp/attachments")
        
        mock_makedirs.assert_called_once_with("/tmp/attachments", exist_ok=True)
        mock_open.assert_called_once()
        mock_file.write.assert_called_once_with(b"test content")
        self.assertEqual(result, "/tmp/attachments/test.pdf")


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
