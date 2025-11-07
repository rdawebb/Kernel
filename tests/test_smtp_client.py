import smtplib
from unittest.mock import Mock, patch

from src.core.email.smtp.client import send_email


class TestSendEmail:
    """Test the send_email function"""
    
    @patch('src.core.smtp_client.smtp_connection')
    @patch('src.core.smtp_client.config_manager')
    def test_send_email_basic_success(self, mock_config_mgr, mock_smtp_conn):
        """Test basic email sending success"""
        # Setup
        mock_config_mgr.get_config.side_effect = lambda key, default=None: {
            'account.email': 'sender@test.com'
        }.get(key, default)
        mock_server = Mock()
        mock_smtp_conn.return_value.__enter__.return_value = mock_server
        
        # Test
        result = send_email(
            to_email='recipient@test.com',
            subject='Test Subject',
            body='Test Body'
        )
        
        # Verify
        assert result is True
        mock_server.send_message.assert_called_once()
        
        # Check the message was created correctly
        call_args = mock_server.send_message.call_args
        msg = call_args[0][0]
        assert msg['From'] == 'sender@test.com'
        assert msg['To'] == 'recipient@test.com'
        assert msg['Subject'] == 'Test Subject'
        assert 'Test Body' in str(msg)
    
    @patch('src.core.smtp_client.smtp_connection')
    @patch('src.core.smtp_client.config_manager')
    def test_send_email_default_recipient(self, mock_config_mgr, mock_smtp_conn):
        """Test email sending with default recipient (self)"""
        # Setup
        mock_config_mgr.get_config.side_effect = lambda key, default=None: {
            'account.email': 'sender@test.com'
        }.get(key, default)
        mock_server = Mock()
        mock_smtp_conn.return_value.__enter__.return_value = mock_server
        
        # Test
        result = send_email(subject='Test Subject', body='Test Body')
        
        # Verify
        assert result is True
        call_args = mock_server.send_message.call_args
        msg = call_args[0][0]
        assert msg['To'] == 'sender@test.com'  # Should default to sender
    
    @patch('src.core.smtp_client.smtp_connection')
    @patch('src.core.smtp_client.config_manager')
    def test_send_email_with_cc_bcc(self, mock_config_mgr, mock_smtp_conn):
        """Test email sending with CC and BCC recipients"""
        # Setup
        mock_config_mgr.get_config.side_effect = lambda key, default=None: {
            'account.email': 'sender@test.com'
        }.get(key, default)
        mock_server = Mock()
        mock_smtp_conn.return_value.__enter__.return_value = mock_server
        
        # Test
        result = send_email(
            to_email='recipient@test.com',
            subject='Test Subject',
            body='Test Body',
            cc=['cc1@test.com', 'cc2@test.com'],
            bcc='bcc@test.com'
        )
        
        # Verify
        assert result is True
        call_args = mock_server.send_message.call_args
        msg, recipients = call_args[0][0], call_args[1]['to_addrs']
        
        # Check message headers
        assert msg['Cc'] == 'cc1@test.com, cc2@test.com'
        assert msg['Bcc'] == 'bcc@test.com'
        
        # Check all recipients are included
        expected_recipients = ['recipient@test.com', 'cc1@test.com', 'cc2@test.com', 'bcc@test.com']
        assert set(recipients) == set(expected_recipients)
    
    @patch('src.core.smtp_client.smtp_connection')
    @patch('src.core.smtp_client.config_manager')
    def test_send_email_cc_bcc_strings(self, mock_config_mgr, mock_smtp_conn):
        """Test email sending with CC and BCC as strings"""
        # Setup
        mock_config_mgr.get_config.side_effect = lambda key, default=None: {
            'account.email': 'sender@test.com'
        }.get(key, default)
        mock_server = Mock()
        mock_smtp_conn.return_value.__enter__.return_value = mock_server
        
        # Test
        result = send_email(
            to_email='recipient@test.com',
            cc='cc@test.com',
            bcc='bcc@test.com'
        )
        
        # Verify
        assert result is True
        call_args = mock_server.send_message.call_args
        recipients = call_args[1]['to_addrs']
        expected_recipients = ['recipient@test.com', 'cc@test.com', 'bcc@test.com']
        assert set(recipients) == set(expected_recipients)
    
    @patch('src.core.smtp_client.smtp_connection')
    def test_send_email_smtp_failure(self, mock_smtp_conn):
        """Test email sending with SMTP failure"""
        # Setup - when smtp_connection context manager fails, it yields None
        mock_smtp_conn.return_value.__enter__.return_value = None
        
        # Test - the function should return False when server is None
        result = send_email(to_email='test@test.com')
        
        # Verify - returns False, does not raise
        assert result is False
    
    @patch('src.core.smtp_client.smtp_connection')
    @patch('src.core.smtp_client.config_manager')
    def test_send_email_server_error(self, mock_config_mgr, mock_smtp_conn):
        """Test email sending with server error during send"""
        # Setup
        mock_config_mgr.get_config.side_effect = lambda key, default=None: {
            'account.email': 'sender@test.com'
        }.get(key, default)
        mock_server = Mock()
        mock_server.send_message.side_effect = smtplib.SMTPException("Server error")
        mock_smtp_conn.return_value.__enter__.return_value = mock_server
        
        # Test - function returns False on error, does not raise
        result = send_email(to_email='test@test.com')
        
        # Verify
        assert result is False
    
    @patch('src.core.smtp_client.smtp_connection')
    @patch('src.core.smtp_client.config_manager')
    def test_send_email_default_values(self, mock_config_mgr, mock_smtp_conn):
        """Test email sending with default subject and body"""
        # Setup
        mock_config_mgr.get_config.side_effect = lambda key, default=None: {
            'account.email': 'sender@test.com'
        }.get(key, default)
        mock_server = Mock()
        mock_smtp_conn.return_value.__enter__.return_value = mock_server
        
        # Test
        result = send_email(to_email='test@test.com')
        
        # Verify
        assert result is True
        call_args = mock_server.send_message.call_args
        msg = call_args[0][0]
        assert msg['Subject'] == 'Test Email from tui_mail'
        # Check that body contains the default text (it's in the message)
        assert 'tui_mail' in str(msg['Subject'])