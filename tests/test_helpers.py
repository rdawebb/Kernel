"""
Test helper functions and utilities for reducing duplicate code across test modules
"""
from unittest.mock import MagicMock, patch


class DatabaseTestHelper:
    """Helper methods for database testing"""
    
    @staticmethod
    def create_mock_email(**kwargs):
        """Create a mock email dictionary with default values"""
        defaults = {
            'uid': 'test_uid_123',
            'from': 'sender@example.com',  # Use aliased name as in SELECT results
            'to': 'recipient@example.com',  # Use aliased name as in SELECT results
            'subject': 'Test Subject',
            'date': '2025-10-02',
            'time': '10:30:00',
            'body': 'Test body',
            'flagged': False,
            'attachments': []
        }
        defaults.update(kwargs)
        return defaults
    
    @staticmethod
    def create_mock_emails(count=2, **kwargs):
        """Create multiple mock emails"""
        emails = []
        for i in range(count):
            email = DatabaseTestHelper.create_mock_email(
                uid=f'test_uid_{i}',
                subject=f'Test Subject {i}',
                date=f'2025-10-{i:02d}',
                **kwargs
            )
            emails.append(email)
        return emails


class IMAPTestHelper:
    """Helper methods for IMAP testing"""
    
    @staticmethod
    def create_mock_imap():
        """Create a properly configured mock IMAP connection"""
        mock_mail = MagicMock()
        mock_mail.login.return_value = ('OK', [b'Login successful'])
        mock_mail.select.return_value = ('OK', [b'10'])
        mock_mail.search.return_value = ('OK', [b'1 2 3'])
        mock_mail.close.return_value = ('OK', [])
        mock_mail.logout.return_value = ('OK', [])
        mock_mail.fetch.return_value = ('OK', [(b'1 (RFC822 ...)', b'email data')])
        return mock_mail
    
    @staticmethod
    def setup_imap_connection_patch(mock_connect, mock_mail=None):
        """Setup a patched IMAP connection"""
        if mock_mail is None:
            mock_mail = IMAPTestHelper.create_mock_imap()
        mock_connect.return_value = mock_mail
        return mock_mail


class SMTPTestHelper:
    """Helper methods for SMTP testing"""
    
    @staticmethod
    def create_mock_smtp():
        """Create a properly configured mock SMTP connection"""
        mock_server = MagicMock()
        mock_server.send_message.return_value = None
        mock_server.quit.return_value = None
        mock_server.login.return_value = None
        mock_server.starttls.return_value = (220, b'Ready to start TLS')
        return mock_server
    
    @staticmethod
    def setup_smtp_connection_patch(mock_context, mock_server=None):
        """Setup a patched SMTP connection context manager"""
        if mock_server is None:
            mock_server = SMTPTestHelper.create_mock_smtp()
        mock_context.return_value.__enter__.return_value = mock_server
        mock_context.return_value.__exit__.return_value = None
        return mock_server


class ConfigTestHelper:
    """Helper methods for configuration testing"""
    
    @staticmethod
    def create_test_config(**kwargs):
        """Create a test configuration dictionary"""
        defaults = {
            'db_path': '/tmp/test_emails.db',
            'database_path': '/tmp/test_emails.db',
            'imap_server': 'imap.test.com',
            'imap_port': 993,
            'imap_use_ssl': True,
            'smtp_server': 'smtp.test.com',
            'smtp_port': 465,
            'smtp_use_ssl': True,
            'email': 'test@example.com',
            'password': 'testpass'
        }
        defaults.update(kwargs)
        return defaults
    
    @staticmethod
    def patch_config(config=None):
        """Create a patcher for config manager"""
        if config is None:
            config = ConfigTestHelper.create_test_config()
        return patch('src.core.config_manager.ConfigManager', return_value=config)


class ConsoleTestHelper:
    """Helper methods for console/UI testing"""
    
    @staticmethod
    def capture_console_output(func, *args, **kwargs):
        """Capture and return console output from a function"""
        import io
        import contextlib
        
        f = io.StringIO()
        with contextlib.redirect_stdout(f):
            result = func(*args, **kwargs)
        return f.getvalue(), result
    
    @staticmethod
    def assert_text_in_output(output, expected_texts):
        """Assert multiple text items are in output"""
        for text in expected_texts:
            assert text in output, f"Expected '{text}' not found in output:\n{output}"


class MockBuilder:
    """Builder for creating complex mock objects"""
    
    def __init__(self):
        self.specs = {}
    
    def with_email(self, **kwargs):
        """Add email spec"""
        self.specs['email'] = DatabaseTestHelper.create_mock_email(**kwargs)
        return self
    
    def with_imap(self):
        """Add IMAP connection spec"""
        self.specs['imap'] = IMAPTestHelper.create_mock_imap()
        return self
    
    def with_smtp(self):
        """Add SMTP connection spec"""
        self.specs['smtp'] = SMTPTestHelper.create_mock_smtp()
        return self
    
    def with_config(self, **kwargs):
        """Add config spec"""
        self.specs['config'] = ConfigTestHelper.create_test_config(**kwargs)
        return self
    
    def build(self):
        """Build and return specs"""
        return self.specs
