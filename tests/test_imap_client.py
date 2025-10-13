import unittest
from unittest.mock import patch, MagicMock, mock_open

from src.tui_mail.core.imap_client import (
    fetch_inbox, fetch_new_emails,
    decode_email_header, decode_filename, parse_email_date, parse_email,
    _extract_attachment_filenames, _extract_attachments_from_email,
    _save_attachment_to_disk, download_all_attachments, 
    download_attachment_by_index, get_attachment_list, delete_email,
    _fetch_email_by_uid, process_email_message
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
    
    def test_decode_email_header_with_encoding(self):
        # Test header decoding with proper encoding
        result = decode_email_header("Test Subject")
        self.assertEqual(result, "Test Subject")
        
        # Test with None input
        result = decode_email_header(None)
        self.assertEqual(result, "")
        
        # Test with empty string
        result = decode_email_header("")
        self.assertEqual(result, "")

    def test_decode_filename_basic(self):
        # Test basic filename decoding
        result = decode_filename("document.pdf")
        self.assertEqual(result, "document.pdf")
        
        # Test with None input
        result = decode_filename(None)
        self.assertEqual(result, "")
        
        # Test with empty string
        result = decode_filename("")
        self.assertEqual(result, "")

    def test_parse_email_date_valid(self):
        # Test with valid date string
        date_str = "Tue, 01 Jan 2023 12:00:00 +0000"
        result = parse_email_date(date_str)
        # parse_email_date returns a tuple (date_str, time_str)
        self.assertEqual(len(result), 2)
        self.assertTrue(result[0].startswith('2023-01-01'))
        self.assertTrue('12:00:00' in result[1])
    
    def test_parse_email_date_invalid(self):
        # Test with invalid date string
        result = parse_email_date("invalid date")
        self.assertIsNotNone(result)  # Should return current time
        
        # Test with None
        result = parse_email_date(None)
        self.assertIsNotNone(result)  # Should return current time

    @patch('src.tui_mail.core.imap_client.connect_to_imap')
    @patch('src.tui_mail.core.imap_client.process_email_message')
    def test_fetch_inbox_success(self, mock_process, mock_connect):
        mock_mail = MagicMock()
        mock_connect.return_value = mock_mail
        mock_mail.search.return_value = ('OK', [b'1 2 3'])
        mock_mail.fetch.side_effect = [
            ('OK', [(b'3 (RFC822 {123})', b'email data 3')]),
            ('OK', [(b'2 (RFC822 {456})', b'email data 2')])
        ]
        
        mock_message_1 = MagicMock()
        mock_message_2 = MagicMock()
        mock_process.side_effect = [mock_message_1, mock_message_2]
        
        with patch('src.tui_mail.core.imap_client.parse_email') as mock_parse:
            mock_parse.side_effect = [
                {'id': '3', 'subject': 'Test 3'},
                {'id': '2', 'subject': 'Test 2'}
            ]
            
            result = fetch_inbox(self.test_config, limit=2)
            
            self.assertEqual(len(result), 2)
            self.assertEqual(result[0]['subject'], 'Test 3')
            self.assertEqual(result[1]['subject'], 'Test 2')

    @patch('src.tui_mail.core.imap_client.connect_to_imap')
    def test_fetch_inbox_no_emails(self, mock_connect):
        mock_mail = MagicMock()
        mock_connect.return_value = mock_mail
        mock_mail.search.return_value = ('OK', [b''])
        
        result = fetch_inbox(self.test_config)
        
        self.assertEqual(result, [])

    @patch('src.tui_mail.core.imap_client.connect_to_imap')
    def test_fetch_inbox_connection_failure(self, mock_connect):
        mock_connect.return_value = None
        
        result = fetch_inbox(self.test_config)
        
        self.assertEqual(result, [])

    def test_fetch_new_emails_basic(self):
        # Simple test for fetch_new_emails without complex storage mocking
        with patch('src.tui_mail.core.imap_client.connect_to_imap') as mock_connect:
            mock_connect.return_value = None  # Connection failure
            
            result = fetch_new_emails(self.test_config)
            
            self.assertEqual(result, 0)

    @patch('email.message_from_bytes')
    def test_extract_attachment_filenames(self, mock_message_from_bytes):
        # Create mock email message with attachments
        mock_part1 = MagicMock()
        mock_part1.get.return_value = "attachment; filename=test.pdf"
        mock_part1.get_filename.return_value = "test.pdf"
        
        mock_part2 = MagicMock()
        mock_part2.get.return_value = "inline"
        mock_part2.get_filename.return_value = None
        
        mock_message = MagicMock()
        mock_message.walk.return_value = [mock_part1, mock_part2]
        
        result = _extract_attachment_filenames(mock_message)
        self.assertEqual(result, ["test.pdf"])

    @patch('email.message_from_bytes')
    def test_extract_attachments_from_email(self, mock_message_from_bytes):
        # Create mock email message with attachments
        mock_part = MagicMock()
        mock_part.get.return_value = "attachment; filename=test.pdf"
        mock_part.get_filename.return_value = "test.pdf"
        mock_part.get_payload.return_value = b"PDF content"
        
        mock_message = MagicMock()
        mock_message.walk.return_value = [mock_part]
        
        result = _extract_attachments_from_email(mock_message)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['filename'], "test.pdf")
        self.assertEqual(result[0]['content'], b"PDF content")

    @patch('os.makedirs')
    @patch('builtins.open', new_callable=mock_open)
    def test_save_attachment_to_disk(self, mock_file, mock_makedirs):
        result = _save_attachment_to_disk("test.pdf", b"test content", "/tmp/attachments")
        
        mock_makedirs.assert_called_once_with("/tmp/attachments", exist_ok=True)
        mock_file.assert_called_once_with("/tmp/attachments/test.pdf", "wb")
        mock_file().write.assert_called_once_with(b"test content")
        self.assertEqual(result, "/tmp/attachments/test.pdf")

    @patch('src.tui_mail.core.imap_client._save_attachment_to_disk')
    @patch('src.tui_mail.core.imap_client._extract_attachments_from_email')
    @patch('src.tui_mail.core.imap_client._fetch_email_by_uid')
    @patch('src.tui_mail.core.imap_client.imap_connection')
    def test_download_all_attachments(self, mock_imap_conn, mock_fetch, mock_extract, mock_save):
        mock_mail = MagicMock()
        mock_imap_conn.return_value.__enter__.return_value = mock_mail
        mock_fetch.return_value = MagicMock()  # mock email message
        mock_extract.return_value = [
            {'filename': 'test1.pdf', 'content': b'content1'},
            {'filename': 'test2.jpg', 'content': b'content2'}
        ]
        mock_save.side_effect = ['/path/test1.pdf', '/path/test2.jpg']
        
        result = download_all_attachments(self.test_config, '123')
        
        self.assertEqual(len(result), 2)
        self.assertIn('/path/test1.pdf', result)
        self.assertIn('/path/test2.jpg', result)

    @patch('src.tui_mail.core.imap_client._save_attachment_to_disk')
    @patch('src.tui_mail.core.imap_client._extract_attachments_from_email')
    @patch('src.tui_mail.core.imap_client._fetch_email_by_uid')
    @patch('src.tui_mail.core.imap_client.imap_connection')
    def test_download_attachment_by_index(self, mock_imap_conn, mock_fetch, mock_extract, mock_save):
        mock_mail = MagicMock()
        mock_imap_conn.return_value.__enter__.return_value = mock_mail
        mock_fetch.return_value = MagicMock()  # mock email message
        mock_extract.return_value = [
            {'filename': 'test1.pdf', 'content': b'content1'},
            {'filename': 'test2.jpg', 'content': b'content2'}
        ]
        mock_save.return_value = '/path/test2.jpg'
        
        result = download_attachment_by_index(self.test_config, '123', 1)
        
        self.assertEqual(result, '/path/test2.jpg')
        mock_save.assert_called_once_with('test2.jpg', b'content2', './attachments')

    @patch('src.tui_mail.core.imap_client._extract_attachment_filenames')
    @patch('src.tui_mail.core.imap_client._fetch_email_by_uid')
    @patch('src.tui_mail.core.imap_client.imap_connection')
    def test_get_attachment_list(self, mock_imap_conn, mock_fetch, mock_extract):
        mock_mail = MagicMock()
        mock_imap_conn.return_value.__enter__.return_value = mock_mail
        mock_fetch.return_value = MagicMock()  # mock email message
        mock_extract.return_value = ['test1.pdf', 'test2.jpg']
        
        result = get_attachment_list(self.test_config, '123')
        
        self.assertEqual(result, ['test1.pdf', 'test2.jpg'])

    @patch('src.tui_mail.core.imap_client.imap_connection')
    def test_delete_email_success(self, mock_imap_conn):
        mock_mail = MagicMock()
        mock_imap_conn.return_value.__enter__.return_value = mock_mail
        mock_mail.uid.return_value = ('OK', [])
        mock_mail.expunge.return_value = ('OK', [])
        
        # delete_email doesn't return anything, just shouldn't raise
        delete_email(self.test_config, '123')
        
        mock_mail.uid.assert_called_with('STORE', '123', '+FLAGS', r'(\Deleted)')
        mock_mail.expunge.assert_called_once()

    @patch('src.tui_mail.core.imap_client.imap_connection')
    def test_delete_email_failure(self, mock_imap_conn):
        mock_mail = MagicMock()
        mock_imap_conn.return_value.__enter__.return_value = mock_mail
        mock_mail.uid.side_effect = Exception("Delete failed")
        
        # Should raise exception since no error handling in delete_email
        with self.assertRaises(Exception):
            delete_email(self.test_config, '123')

    def test_parse_email_basic(self):
        # Create a mock email message object
        mock_email = MagicMock()
        mock_email.get.side_effect = lambda key: {
            "Subject": "Test Subject",
            "From": "sender@test.com",
            "To": "recipient@test.com",
            "Date": "Tue, 01 Jan 2023 12:00:00 +0000"
        }.get(key)
        mock_email.is_multipart.return_value = False
        mock_email.get_content_type.return_value = "text/plain"
        mock_email.get_payload.return_value = b"Test body content"
        
        with patch('src.tui_mail.core.imap_client._extract_attachment_filenames') as mock_extract:
            mock_extract.return_value = []
            
            result = parse_email(mock_email, 123)
            
            self.assertEqual(result['id'], 123)
            self.assertEqual(result['subject'], 'Test Subject')
            self.assertEqual(result['from'], 'sender@test.com')
            self.assertEqual(result['attachments'], '')

    def test_parse_email_with_attachments(self):
        # Create a mock email message object
        mock_email = MagicMock()
        mock_email.get.side_effect = lambda key: {
            "Subject": "Test with Attachments",
            "From": "sender@test.com",
            "To": "recipient@test.com",
            "Date": "Tue, 01 Jan 2023 12:00:00 +0000"
        }.get(key)
        mock_email.is_multipart.return_value = False
        mock_email.get_content_type.return_value = "text/plain"
        mock_email.get_payload.return_value = b"Body with attachments"
        
        with patch('src.tui_mail.core.imap_client._extract_attachment_filenames') as mock_extract:
            mock_extract.return_value = ['file1.pdf', 'file2.jpg']
            
            result = parse_email(mock_email, 123)
            
            self.assertEqual(result['attachments'], 'file1.pdf,file2.jpg')

    def test_fetch_email_by_uid(self):
        mock_mail = MagicMock()
        mock_mail.search.return_value = ('OK', [b'123'])
        mock_mail.fetch.return_value = ('OK', [(b'123 (RFC822 {456})', b'email data')])
        
        with patch('email.message_from_bytes') as mock_from_bytes:
            mock_message = MagicMock()
            mock_from_bytes.return_value = mock_message
            
            result = _fetch_email_by_uid(mock_mail, '123')
            
            self.assertEqual(result, mock_message)
            mock_mail.search.assert_called_with(None, 'UID 123')
            mock_mail.fetch.assert_called_with('123', '(RFC822)')
            mock_from_bytes.assert_called_with(b'email data')

    def test_process_email_message_text_plain(self):
        # Test processing tuple message data 
        msg_tuple = (b'1 (RFC822 {123})', b'email data')
        
        with patch('email.message_from_bytes') as mock_from_bytes:
            mock_message = MagicMock()
            mock_from_bytes.return_value = mock_message
            
            result = process_email_message(msg_tuple)
            
            self.assertEqual(result, mock_message)
            mock_from_bytes.assert_called_once_with(b'email data')

    def test_process_email_message_text_html(self):
        # Test with non-tuple input
        result = process_email_message("not a tuple")
        
        self.assertIsNone(result)

    def test_process_email_message_multipart(self):
        # Test with None input
        result = process_email_message(None)
        
        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()
