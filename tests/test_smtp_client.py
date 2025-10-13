import pytest
import smtplib
from unittest.mock import Mock, patch
from src.tui_mail.core.smtp_client import send_email


class TestSendEmail:
    """Test the send_email function"""
    
    @patch('src.tui_mail.core.smtp_client.smtp_connection')
    @patch('src.tui_mail.core.smtp_client.load_config')
    def test_send_email_basic_success(self, mock_config, mock_smtp_conn):
        """Test basic email sending success"""
        # Setup
        mock_config.return_value = {'email': 'sender@test.com'}
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
    
    @patch('src.tui_mail.core.smtp_client.smtp_connection')
    @patch('src.tui_mail.core.smtp_client.load_config')
    def test_send_email_default_recipient(self, mock_config, mock_smtp_conn):
        """Test email sending with default recipient (self)"""
        # Setup
        mock_config.return_value = {'email': 'sender@test.com'}
        mock_server = Mock()
        mock_smtp_conn.return_value.__enter__.return_value = mock_server
        
        # Test
        result = send_email(subject='Test Subject', body='Test Body')
        
        # Verify
        assert result is True
        call_args = mock_server.send_message.call_args
        msg = call_args[0][0]
        assert msg['To'] == 'sender@test.com'  # Should default to sender
    
    @patch('src.tui_mail.core.smtp_client.smtp_connection')
    @patch('src.tui_mail.core.smtp_client.load_config')
    def test_send_email_with_cc_bcc(self, mock_config, mock_smtp_conn):
        """Test email sending with CC and BCC recipients"""
        # Setup
        mock_config.return_value = {'email': 'sender@test.com'}
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
    
    @patch('src.tui_mail.core.smtp_client.smtp_connection')
    @patch('src.tui_mail.core.smtp_client.load_config')
    def test_send_email_cc_bcc_strings(self, mock_config, mock_smtp_conn):
        """Test email sending with CC and BCC as strings"""
        # Setup
        mock_config.return_value = {'email': 'sender@test.com'}
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
    
    @patch('src.tui_mail.core.smtp_client.smtp_connection')
    def test_send_email_smtp_failure(self, mock_smtp_conn):
        """Test email sending with SMTP failure"""
        # Setup
        mock_smtp_conn.side_effect = RuntimeError("SMTP connection failed")
        
        # Test
        with pytest.raises(RuntimeError, match="Failed to send email"):
            send_email(to_email='test@test.com')
    
    @patch('src.tui_mail.core.smtp_client.smtp_connection')
    @patch('src.tui_mail.core.smtp_client.load_config')
    def test_send_email_server_error(self, mock_config, mock_smtp_conn):
        """Test email sending with server error during send"""
        # Setup
        mock_config.return_value = {'email': 'sender@test.com'}
        mock_server = Mock()
        mock_server.send_message.side_effect = smtplib.SMTPException("Server error")
        mock_smtp_conn.return_value.__enter__.return_value = mock_server
        
        # Test
        with pytest.raises(RuntimeError, match="Failed to send email"):
            send_email(to_email='test@test.com')
    
    @patch('src.tui_mail.core.smtp_client.smtp_connection')
    @patch('src.tui_mail.core.smtp_client.load_config')
    def test_send_email_default_values(self, mock_config, mock_smtp_conn):
        """Test email sending with default subject and body"""
        # Setup
        mock_config.return_value = {'email': 'sender@test.com'}
        mock_server = Mock()
        mock_smtp_conn.return_value.__enter__.return_value = mock_server
        
        # Test
        result = send_email(to_email='test@test.com')
        
        # Verify
        assert result is True
        call_args = mock_server.send_message.call_args
        msg = call_args[0][0]
        assert msg['Subject'] == 'Test Email from tui_mail'
        assert 'This is a test email sent from the tui_mail SMTP client.' in str(msg)