import unittest
import os
from unittest.mock import patch

from src.tui_mail.utils.config import load_config

class TestConfig(unittest.TestCase):
    
    def setUp(self):
        self.env_vars_to_clear = [
            'IMAP_SERVER', 'IMAP_PORT', 'IMAP_USE_SSL',
            'EMAIL', 'PASSWORD', 'DB_PATH'
        ]
        self.original_env_values = {}
        for var in self.env_vars_to_clear:
            self.original_env_values[var] = os.environ.get(var)
            if var in os.environ:
                del os.environ[var]
        
        # Mock load_dotenv to prevent loading actual .env file
        self.dotenv_patcher = patch('src.tui_mail.utils.config.load_dotenv')
        self.mock_dotenv = self.dotenv_patcher.start()
    
    def tearDown(self):
        self.dotenv_patcher.stop()
        
        for var, value in self.original_env_values.items():
            if value is not None:
                os.environ[var] = value
            elif var in os.environ:
                del os.environ[var]
    
    def test_load_config_with_valid_env_vars(self):
        os.environ.update({
            'IMAP_SERVER': 'imap.gmail.com',
            'IMAP_PORT': '993',
            'IMAP_USE_SSL': 'true',
            'EMAIL': 'test@example.com',
            'PASSWORD': 'testpass',
            'DB_PATH': '~/.test_mail/emails.db'
        })
        
        config = load_config()
        
        self.assertEqual(config['imap_server'], 'imap.gmail.com')
        self.assertEqual(config['imap_port'], 993)
        self.assertTrue(config['imap_use_ssl'])
        self.assertEqual(config['email'], 'test@example.com')
        self.assertEqual(config['password'], 'testpass')
        self.assertTrue(config['db_path'].endswith('emails.db'))
    
    def test_load_config_missing_required_vars(self):
        os.environ['IMAP_SERVER'] = 'imap.gmail.com'
        # EMAIL and PASSWORD are already cleared in setUp
        
        with self.assertRaises(RuntimeError) as context:
            load_config()
        
        self.assertIn("IMAP_SERVER, SMTP_SERVER, EMAIL, and PASSWORD must be set", str(context.exception))
    
    def test_load_config_invalid_port(self):
        os.environ.update({
            'IMAP_SERVER': 'imap.gmail.com',
            'IMAP_PORT': 'invalid_port',
            'EMAIL': 'test@example.com',
            'PASSWORD': 'testpass'
        })
        
        with self.assertRaises(RuntimeError) as context:
            load_config()
        
        self.assertIn("IMAP_PORT must be a valid integer", str(context.exception))
    
    def test_load_config_defaults(self):
        os.environ.update({
            'IMAP_SERVER': 'imap.gmail.com',
            'EMAIL': 'test@example.com',
            'PASSWORD': 'testpass'
        })
        
        config = load_config()
        
        self.assertEqual(config['imap_port'], 993)
        self.assertTrue(config['imap_use_ssl'])
        self.assertTrue(config['db_path'].endswith('emails.db'))
    
    def test_ssl_flag_parsing(self):
        test_cases = [
            ('true', True),
            ('TRUE', True),
            ('True', True),
            ('false', False),
            ('FALSE', False),
            ('False', False),
            ('anything_else', False)
        ]
        
        for ssl_value, expected in test_cases:
            with self.subTest(ssl_value=ssl_value):
                os.environ.update({
                    'IMAP_SERVER': 'imap.gmail.com',
                    'IMAP_USE_SSL': ssl_value,
                    'EMAIL': 'test@example.com',
                    'PASSWORD': 'testpass'
                })
                
                config = load_config()
                self.assertEqual(config['imap_use_ssl'], expected)


if __name__ == '__main__':
    unittest.main()
