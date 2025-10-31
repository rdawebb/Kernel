"""
Shared test fixtures and configuration for pytest
"""
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def temp_db():
    """Create a temporary database for testing"""
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "test_emails.db"
        yield db_path
        if db_path.exists():
            db_path.unlink()


@pytest.fixture
def mock_config(temp_db):
    """Mock configuration with test database path"""
    config = {
        'db_path': str(temp_db),
        'database_path': str(temp_db),
        'imap_server': 'imap.test.com',
        'imap_port': 993,
        'imap_use_ssl': True,
        'smtp_server': 'smtp.test.com',
        'smtp_port': 465,
        'smtp_use_ssl': True,
        'email': 'test@example.com',
        'password': 'testpass'
    }
    with patch('src.utils.config_manager.ConfigManager') as mock_cm:
        manager = MagicMock()
        manager.get_config.side_effect = lambda key, default=None: config.get(key, default)
        mock_cm.return_value = manager
        yield config


@pytest.fixture
def test_email():
    """Sample test email dictionary"""
    return {
        'uid': 'test_uid_123',
        'from': 'sender@example.com',
        'to': 'recipient@example.com',
        'subject': 'Test Subject',
        'date': '2025-10-02',
        'time': '10:30:00',
        'body': 'Test email body',
        'flagged': False,
        'attachments': []
    }


@pytest.fixture
def test_emails():
    """Multiple sample test emails"""
    return [
        {
            'uid': 'test_uid_1',
            'from': 'sender1@example.com',
            'to': 'recipient@example.com',
            'subject': 'Email 1',
            'date': '2025-10-02',
            'time': '10:30:00',
            'body': 'Body 1',
            'flagged': False,
            'attachments': []
        },
        {
            'uid': 'test_uid_2',
            'from': 'sender2@example.com',
            'to': 'recipient@example.com',
            'subject': 'Email 2',
            'date': '2025-10-01',
            'time': '09:15:00',
            'body': 'Body 2',
            'flagged': True,
            'attachments': [{'filename': 'test.pdf'}]
        }
    ]


@pytest.fixture
def mock_imap_connection():
    """Mock IMAP connection"""
    mock_mail = MagicMock()
    mock_mail.login.return_value = ('OK', [b'Login successful'])
    mock_mail.select.return_value = ('OK', [b'10'])
    mock_mail.search.return_value = ('OK', [b'1 2 3'])
    mock_mail.close.return_value = ('OK', [])
    mock_mail.logout.return_value = ('OK', [])
    return mock_mail


@pytest.fixture
def mock_smtp_connection():
    """Mock SMTP connection"""
    mock_server = MagicMock()
    mock_server.send_message.return_value = None
    mock_server.quit.return_value = None
    mock_server.login.return_value = None
    mock_server.starttls.return_value = (220, b'Ready to start TLS')
    return mock_server


@pytest.fixture(autouse=True)
def clear_env_vars():
    """Clear test environment variables before each test"""
    env_vars = [
        'IMAP_SERVER', 'IMAP_PORT', 'IMAP_USE_SSL',
        'SMTP_SERVER', 'SMTP_PORT', 'SMTP_USE_SSL',
        'EMAIL', 'PASSWORD', 'DB_PATH'
    ]
    original = {}
    for var in env_vars:
        original[var] = os.environ.get(var)
        if var in os.environ:
            del os.environ[var]
    
    yield
    
    # Restore original environment
    for var, value in original.items():
        if value is not None:
            os.environ[var] = value
        elif var in os.environ:
            del os.environ[var]
