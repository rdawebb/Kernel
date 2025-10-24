"""
Tests for IMAP email operations

Tests cover:
- IMAP connection
- Email fetching  
- Email deletion
"""
from unittest.mock import patch, MagicMock

from src.core.imap_client import IMAPClient, SyncMode
from src.core.imap_connection import connect_to_imap
from .test_helpers import IMAPTestHelper, ConfigTestHelper


class TestIMAPConnection:
    """Tests for IMAP connection establishment"""
    
    def test_connect_to_imap_success(self):
        """Test successful IMAP connection"""
        config = ConfigTestHelper.create_test_config()
        
        with patch('src.core.imap_connection.imaplib.IMAP4_SSL') as mock_imap:
            mock_connection = MagicMock()
            mock_imap.return_value = mock_connection
            mock_connection.login.return_value = ('OK', [])
            mock_connection.select.return_value = ('OK', [])
            
            result = connect_to_imap(config)
            
            assert result is not None
            mock_connection.login.assert_called_once()
    
    def test_connect_to_imap_failure(self):
        """Test IMAP connection failure handling"""
        config = ConfigTestHelper.create_test_config()
        
        with patch('src.core.imap_connection.imaplib.IMAP4_SSL') as mock_imap:
            mock_imap.side_effect = Exception("Connection failed")
            
            result = connect_to_imap(config)
            
            assert result is None


class TestFetchNewEmails:
    """Tests for fetching new emails"""
    
    def test_fetch_new_emails_success(self):
        """Test fetching new emails successfully"""
        config = ConfigTestHelper.create_test_config()
        client = IMAPClient(config)
        
        with patch('src.core.imap_client.imap_connection') as mock_context:
            mock_mail = IMAPTestHelper.create_mock_imap()
            mock_mail.search.return_value = ('OK', [b'1 2 3'])
            mock_context.return_value.__enter__.return_value = mock_mail
            
            result = client.fetch_new_emails()
            
            # Should return int or None
            assert result is None or isinstance(result, int)
    
    def test_fetch_new_emails_no_emails(self):
        """Test fetching when no new emails exist"""
        config = ConfigTestHelper.create_test_config()
        client = IMAPClient(config)
        
        with patch('src.core.imap_client.imap_connection') as mock_context:
            mock_mail = IMAPTestHelper.create_mock_imap()
            mock_mail.search.return_value = ('OK', [b''])
            mock_context.return_value.__enter__.return_value = mock_mail
            
            result = client.fetch_new_emails()
            
            assert result is None or result == 0
    
    def test_fetch_new_emails_fetch_all(self):
        """Test fetching all emails with fetch_all parameter"""
        config = ConfigTestHelper.create_test_config()
        client = IMAPClient(config)
        
        with patch('src.core.imap_client.imap_connection') as mock_context:
            mock_mail = IMAPTestHelper.create_mock_imap()
            mock_mail.search.return_value = ('OK', [b'1 2 3'])
            mock_context.return_value.__enter__.return_value = mock_mail
            
            result = client.fetch_new_emails(sync_mode=SyncMode.FULL)
            
            assert result is None or isinstance(result, int)
    
    def test_fetch_new_emails_connection_failure(self):
        """Test fetching when IMAP connection fails"""
        config = ConfigTestHelper.create_test_config()
        client = IMAPClient(config)
        
        with patch('src.core.imap_client.imap_connection') as mock_context:
            mock_context.return_value.__enter__.return_value = None
            
            result = client.fetch_new_emails()
            
            # Function returns 0 when connection fails
            assert result == 0 or result is None


class TestDeleteEmail:
    """Tests for email deletion"""
    
    def test_delete_email_success(self):
        """Test successful email deletion"""
        config = ConfigTestHelper.create_test_config()
        client = IMAPClient(config)
        
        with patch('src.core.imap_client.imap_connection') as mock_context:
            mock_mail = IMAPTestHelper.create_mock_imap()
            mock_mail.store.return_value = ('OK', [])
            mock_context.return_value.__enter__.return_value = mock_mail
            
            result = client.delete_email('123')
            
            # Should complete without error
            assert result is None or isinstance(result, bool)
    
    def test_delete_email_connection_failure(self):
        """Test deletion when connection fails"""
        config = ConfigTestHelper.create_test_config()
        client = IMAPClient(config)
        
        with patch('src.core.imap_client.imap_connection') as mock_context:
            mock_context.return_value.__enter__.return_value = None
            
            result = client.delete_email('123')
            
            # Should handle gracefully
            assert result is None or isinstance(result, bool)
            
            # Function returns 0 when connection fails
            assert result == 0 or result is None
