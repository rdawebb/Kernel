"""IMAP connection management - handles connection setup and cleanup."""

import imaplib
from contextlib import contextmanager
from typing import Optional
from security.key_store import KeyStore
from ..utils.config_manager import ConfigManager
from ..utils.log_manager import get_logger
from ..utils.error_handling import (
    IMAPError,
    NetworkTimeoutError,
    MissingCredentialsError,
    InvalidCredentialsError,
)

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
            raise MissingCredentialsError("IMAP server is required")
        
        if not email:
            email = _prompt_for_config(
                'account.email',
                "Enter your email address: "
            )
            if not email:
                raise MissingCredentialsError("Email address is required")
        
        username = _prompt_for_config(
            'account.username',
            "Enter your username (or press Enter to use your email address): ",
            default_value=email
        )
        if not username:
            raise MissingCredentialsError("Username is required")
        
        if not key_store:
            raise MissingCredentialsError("KeyStore unavailable - cannot securely retrieve password")
        
        password = key_store.get_password("kernel_imap", username, prompt_if_missing=True)
        if not password:
            raise MissingCredentialsError("Password is required")
        
        imap_port = config_manager.get_config('account.imap_port', default=993)
        
        return {
            "imap_server": imap_server,
            "imap_port": imap_port,
            "username": username,
            "email": email,
            "password": password,
        }
    except MissingCredentialsError:
        raise
    except Exception as e:
        raise IMAPError("Error retrieving account information") from e


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
            password = getpass.getpass(f"Password for {account_config['username']}: ")

            if password:
                KeyStore().set_password("kernel_imap", account_config["username"], password)

                try:
                    mail.login(account_config["username"], password)
                    logger.info(f"Connected to IMAP server after re-prompt: {account_config['imap_server']}")
                    return mail
                
                except Exception as e:
                    raise InvalidCredentialsError("Invalid credentials for IMAP server") from e
            else:
                raise MissingCredentialsError("Password required for IMAP authentication")
            
    except (InvalidCredentialsError, MissingCredentialsError):
        raise
    except imaplib.IMAP4.abort:
        raise NetworkTimeoutError("IMAP connection timeout") 
    except Exception as e:
        raise IMAPError("Failed to connect to IMAP server") from e


@contextmanager
def imap_connection(account_config: dict):
    """Context manager for IMAP connection with automatic cleanup."""
    try:
        mail = connect_to_imap(account_config)
        if not mail:
            raise IMAPError("Failed to establish IMAP connection")
        try:
            yield mail
        finally:
            try:
                mail.close()
                mail.logout()
            except Exception:
                pass
    except (IMAPError, InvalidCredentialsError, MissingCredentialsError, NetworkTimeoutError):
        raise
    except Exception as e:
        raise IMAPError("IMAP connection error") from e
