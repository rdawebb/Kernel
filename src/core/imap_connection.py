"""IMAP connection management - handles connection setup and cleanup."""

import imaplib
from contextlib import contextmanager
from typing import Optional
from security.key_store import KeyStore
from ..utils.config_manager import ConfigManager
from ..utils.log_manager import get_logger

logger = get_logger(__name__)


def _prompt_for_config(config_key: str, prompt_text: str, default_value: str = "") -> Optional[str]:
    """Prompt user for missing config value and save it."""
    config_manager = ConfigManager()
    config_value = config_manager.get_config(config_key)
    
    if not config_value or config_value == "":
        logger.info(f"{config_key} not configured, prompting user")
        user_input = input(prompt_text).strip()
        
        if user_input:
            config_manager.set_config(config_key, user_input)
            return user_input
        elif default_value:
            config_manager.set_config(config_key, default_value)
            return default_value
        else:
            logger.error(f"{config_key} not provided")
            return None
    
    return config_value


def get_account_info(email: str = "") -> Optional[dict]:
    """Retrieve all required account information, prompting for missing values."""
    try:
        config_manager = ConfigManager()
        key_store = KeyStore()
        
        imap_server = _prompt_for_config(
            'account.imap_server',
            "Enter IMAP server address (e.g., imap.gmail.com): "
        )
        if not imap_server:
            print("IMAP server is required. Please configure it and try again.")
            return None
        
        if not email:
            email = _prompt_for_config(
                'account.email',
                "Enter your email address: "
            )
            if not email:
                print("Email address is required. Please configure it and try again.")
                return None
        
        username = _prompt_for_config(
            'account.username',
            "Enter your username (or press Enter to use your email address): ",
            default_value=email
        )
        if not username:
            print("Username is required. Please configure it and try again.")
            return None
        
        if not key_store:
            logger.warning("KeyStore unavailable, cannot securely retrieve password")
            print("Warning: Password storage not available. Please reconfigure your system.")
            return None
        
        password = key_store.get_password("kernel_imap", username, prompt_if_missing=True)
        if not password:
            print("Password is required. Please configure it and try again.")
            return None
        
        imap_port = config_manager.get_config('account.imap_port', default=993)
        
        return {
            "imap_server": imap_server,
            "imap_port": imap_port,
            "username": username,
            "email": email,
            "password": password,
        }
    except Exception as e:
        logger.error(f"Error retrieving account information: {e}")
        print("Error retrieving account information. Please check your settings and try again.")
        return None


def connect_to_imap(account_config: dict) -> Optional[imaplib.IMAP4_SSL]:
    """Establish connection to IMAP server."""

    import getpass

    try:
        mail = imaplib.IMAP4_SSL(account_config["imap_server"], account_config["imap_port"])
        try:
            mail.login(account_config["username"], account_config["password"])
            logger.info(f"Connected to IMAP server: {account_config['imap_server']}")
            return mail
        
        except imaplib.IMAP4.error as e:
            logger.error(f"Error logging in to IMAP server: {e}")
            print("Login failed - please enter your password again.")
            password = getpass.getpass(f"Password for {account_config['username']}: ")

            if password:
                KeyStore().set_password("kernel_imap", account_config["username"], password)

                try:
                    mail.login(account_config["username"], password)
                    logger.info(f"Connected to IMAP server after re-prompt: {account_config['imap_server']}")
                    return mail
                
                except Exception as e:
                    logger.error(f"Error logging in to IMAP server after re-prompt: {e}")
                    print("Unable to login to your email server. Please check your settings and try again.")
                    return None
            
    except Exception as e:
        logger.error(f"Error connecting to IMAP server: {e}")
        print("Unable to connect to your email server. Please check your settings and try again.")
        return None


@contextmanager
def imap_connection(account_config: dict):
    """Context manager for IMAP connection with automatic cleanup."""
    mail = connect_to_imap(account_config)
    if not mail:
        logger.error("Failed to establish IMAP connection")
        print("Unable to connect to your email server. Please check your settings and try again.")
        yield None
        return
    try:
        yield mail
    finally:
        try:
            mail.close()
            mail.logout()
        except Exception:
            pass
