import unittest
from unittest.mock import patch, MagicMock
import imaplib
import smtplib
import pytest

from src.tui_mail.utils.config import load_config
from src.tui_mail.core.imap_client import connect_to_imap, imap_connection
from src.tui_mail.core.smtp_client import smtp_connection


class TestIMAPConnection(unittest.TestCase):
    """Test IMAP connection functionality"""
    
    def setUp(self):
        self.test_config = {
            'imap_server': 'imap.test.com',
            'imap_port': 993,
            'imap_use_ssl': True,
            'email': 'test@example.com',
            'password': 'testpass'
        }
    
    @patch('src.tui_mail.core.imap_client.imaplib.IMAP4_SSL')
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
    
    @patch('src.tui_mail.core.imap_client.imaplib.IMAP4_SSL')
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
    
    @patch('src.tui_mail.core.imap_client.imaplib.IMAP4_SSL')
    @patch('builtins.print')
    def test_connect_to_imap_connection_failure(self, mock_print, mock_imap_ssl):
        mock_imap_ssl.side_effect = ConnectionError("Cannot connect to server")
        
        result = connect_to_imap(self.test_config)
        
        self.assertIsNone(result)
        mock_print.assert_called_once()
        call_args = mock_print.call_args[0][0]
        self.assertIn("Error connecting to email server", call_args)

    @patch('src.tui_mail.core.imap_client.connect_to_imap')
    def test_imap_connection_context_manager_success(self, mock_connect):
        mock_mail = MagicMock()
        mock_connect.return_value = mock_mail
        
        with imap_connection(self.test_config) as mail:
            self.assertEqual(mail, mock_mail)
        
        mock_mail.close.assert_called_once()
        mock_mail.logout.assert_called_once()
    
    @patch('src.tui_mail.core.imap_client.connect_to_imap')
    def test_imap_connection_context_manager_failure(self, mock_connect):
        mock_connect.return_value = None
        
        with self.assertRaises(RuntimeError, msg="Failed to connect to IMAP server"):
            with imap_connection(self.test_config):
                pass


class TestSMTPConnection(unittest.TestCase):
    """Test SMTP connection functionality"""
    
    @patch('src.tui_mail.core.smtp_client.load_config')
    @patch('src.tui_mail.core.smtp_client.smtplib.SMTP_SSL')
    def test_smtp_connection_ssl_success(self, mock_smtp_ssl, mock_config):
        """Test successful SSL SMTP connection"""
        mock_config.return_value = {
            'smtp_server': 'smtp.test.com',
            'smtp_port': 465,
            'smtp_use_ssl': True,
            'email': 'test@example.com',
            'password': 'testpass'
        }
        
        mock_server = MagicMock()
        mock_smtp_ssl.return_value = mock_server
        mock_server.login.return_value = None
        
        with smtp_connection() as server:
            self.assertEqual(server, mock_server)
        
        mock_smtp_ssl.assert_called_once_with('smtp.test.com', 465)
        mock_server.login.assert_called_once_with('test@example.com', 'testpass')
        mock_server.quit.assert_called_once()

    @patch('src.tui_mail.core.smtp_client.load_config')
    @patch('src.tui_mail.core.smtp_client.smtplib.SMTP')
    def test_smtp_connection_starttls_success(self, mock_smtp, mock_config):
        """Test successful STARTTLS SMTP connection"""
        mock_config.return_value = {
            'smtp_server': 'smtp.test.com',
            'smtp_port': 587,
            'smtp_use_ssl': False,
            'email': 'test@example.com',
            'password': 'testpass'
        }
        
        mock_server = MagicMock()
        mock_smtp.return_value = mock_server
        mock_server.starttls.return_value = (220, b'Ready to start TLS')
        mock_server.login.return_value = None
        
        with smtp_connection() as server:
            self.assertEqual(server, mock_server)
        
        mock_smtp.assert_called_once_with('smtp.test.com', 587)
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with('test@example.com', 'testpass')
        mock_server.quit.assert_called_once()

    @patch('src.tui_mail.core.smtp_client.load_config')
    @patch('src.tui_mail.core.smtp_client.smtplib.SMTP_SSL')
    def test_smtp_connection_login_failure(self, mock_smtp_ssl, mock_config):
        """Test SMTP connection with login failure"""
        mock_config.return_value = {
            'smtp_server': 'smtp.test.com',
            'smtp_port': 465,
            'smtp_use_ssl': True,
            'email': 'test@example.com',
            'password': 'wrongpass'
        }
        
        mock_server = MagicMock()
        mock_smtp_ssl.return_value = mock_server
        mock_server.login.side_effect = smtplib.SMTPAuthenticationError(535, b'Invalid credentials')
        
        with pytest.raises(RuntimeError, match="Failed to connect to SMTP server"):
            with smtp_connection():
                pass

    @patch('src.tui_mail.core.smtp_client.load_config')
    @patch('src.tui_mail.core.smtp_client.smtplib.SMTP_SSL')
    def test_smtp_connection_server_error(self, mock_smtp_ssl, mock_config):
        """Test SMTP connection with server connection error"""
        mock_config.return_value = {
            'smtp_server': 'smtp.test.com',
            'smtp_port': 465,
            'smtp_use_ssl': True,
            'email': 'test@example.com',
            'password': 'testpass'
        }
        
        mock_smtp_ssl.side_effect = smtplib.SMTPServerDisconnected("Connection lost")
        
        with pytest.raises(RuntimeError, match="Failed to connect to SMTP server"):
            with smtp_connection():
                pass


def test_imap_connection():
    """Legacy test IMAP connection function for manual testing"""
    
    print("🔌 Testing IMAP connection...")
    
    try:
        # Load configuration
        config = load_config()
        
        # Test connection
        server = connect_to_imap(config)
        if server:
            print("✅ Successfully connected to IMAP server!")
            print(f"   Server: {config['imap_server']}:{config['imap_port']}")
            print(f"   Email: {config['email']}")
            print(f"   SSL: {'Yes' if config['imap_use_ssl'] else 'No'}")
            
            # Test authentication by selecting INBOX
            try:
                status, _ = server.select('INBOX')
                if status == 'OK':
                    print("✅ Successfully authenticated and selected INBOX!")
                else:
                    print("⚠️  Connected but failed to select INBOX")
            except Exception as e:
                print(f"⚠️  Connected but authentication issue: {e}")
            
            # Clean up
            try:
                server.logout()
            except Exception:
                pass
                
            # Use assert instead of return for pytest
            assert True, "IMAP connection successful"
            
        else:
            print("❌ Connection failed!")
            assert False, "IMAP connection failed"
            
    except Exception as e:
        print(f"❌ Connection test failed: {e}")
        assert False, f"IMAP connection test failed: {e}"


if __name__ == "__main__":
    import sys
    try:
        test_imap_connection()
        print("\n🎉 IMAP connection test passed!")
        print("You can now use 'python cli.py list' to fetch emails.")
        sys.exit(0)
    except AssertionError as e:
        print(f"\n💥 IMAP connection test failed: {e}")
        print("Please check your .env file settings.")
        sys.exit(1)
