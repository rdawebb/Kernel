"""Key management for encryption and decryption of sensitive data."""

import keyring
import getpass
import json
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Optional, Dict
from src.utils.log_manager import get_logger, log_call

logger = get_logger(__name__)

SECRETS_DIR = Path.home() / '.kernel' / 'secrets'
SECRETS_DIR.mkdir(parents=True, exist_ok=True)
SECRETS_FILE = SECRETS_DIR / "secrets.enc.json"
KEY_ENV = "KERNEL_SECRETS_KEY"


class KeyStore:
    """Manage encryption keys and encrypted secrets storage."""

    def __init__(self):
        self.backend = self._detect_backend()
        self.cipher = None
        logger.info(f"KeyStore initialised using backend: {self.backend}")


    def _detect_backend(self) -> str:
        """Detect available key storage backend."""
        
        try:
            backend = keyring.get_keyring()
            if backend and backend.priority > 0:
                return "keyring"

        except Exception as e:
            logger.warning(f"Keyring unavailable ({e}), using encrypted file")
        
        return "file"


    def _get_cipher(self):
        """Initialize encryption cipher for file backend."""
        
        if self.cipher is None and self.backend == "file":
            from cryptography.fernet import Fernet

            key = os.environ.get(KEY_ENV)
            if not key:
                key = Fernet.generate_key().decode()
                os.environ[KEY_ENV] = key
                logger.warning("Generated new encryption key for file backend.")

            self.cipher = Fernet(key.encode())

        return self.cipher
    

    @log_call
    def set_password(self, service: str, username: str, password: str):
        """Store password securely."""
        
        try:
            if self.backend == "keyring":
                keyring.set_password(service, username, password)
                logger.info(f"Stored password for {username}@{service} in keyring.")
            else:
                self._store_in_file(service, username, password)
                logger.info(f"Stored password for {username}@{service} in encrypted file.")

        except Exception as e:
            logger.error(f"Failed to store password: {e}")
            raise


    @log_call
    def get_password(self, service: str, username: str, prompt_if_missing: bool = False) -> Optional[str]:
        """Retrieve stored password."""
        
        try:
            if self.backend == "keyring":
                password = keyring.get_password(service, username)
            else:
                password = self._load_from_file(service, username)

            if password:
                logger.debug(f"Retrieved password for {username}@{service}.")
                return password
            
            if prompt_if_missing:
                logger.info(f"Password for {username}@{service} not found, prompting user.")
                password = getpass.getpass(f"Enter password for {username}: ")
                if password:
                    self.set_password(service, username, password)
                    return password
                else:
                    logger.warning(f"No password provided for {username}@{service}")
                    return None
            
            return None

        except Exception as e:
            logger.error(f"Failed to retrieve password: {e}")
            raise


    @log_call
    def delete_password(self, service: str, username: str):
        """Delete stored password."""
        
        try:
            if self.backend == "keyring":
                keyring.delete_password(service, username)
            else:
                self._delete_from_file(service, username)

            logger.info(f"Deleted password for {username}@{service}.")

        except Exception as e:
            logger.error(f"Failed to delete password: {e}")
            raise


    @log_call
    def rotate_key(self):
        """Rotate encryption key for file backend."""
        
        if self.backend != "file":
            logger.warning("Key rotation is only applicable for file backend.")
            return
        
        from cryptography.fernet import Fernet

        logger.info("Rotating encryption key for file backend.")

        all_creds = self._load_all()
        new_key = Fernet.generate_key().decode()
        os.environ[KEY_ENV] = new_key
        self.cipher = Fernet(new_key.encode())
        self._save_all(all_creds)

        logger.info("Encryption key rotated successfully.")


    @log_call
    def validate_keystore(self) -> bool:
        """Validate that the keystore is operational."""
        
        if self.backend == "keyring":
            return True

        if not SECRETS_FILE.exists():
            return True
        
        try:
            self._load_all()
            return True
        
        except Exception as e:
            logger.error(f"Keystore validation failed: {e}")
            return False


    ## Context Managers

    @contextmanager
    def file_operation(self):
        """Context manager for file backend operations."""
        
        try:
            yield

        except OSError as e:
            logger.error(f"File operation error: {e}")
            raise

        except Exception as e:
            logger.error(f"Unexpected error during file operation: {e}")
            raise

    
    @contextmanager
    def temp_password(self, service: str, username: str, password: str):
        """Context manager for temporary password storage."""
        
        try:
            self.set_password(service, username, password)
            logger.debug(f"Temporary password set for {username}@{service}.")
            yield

        finally:
            try:
                self.delete_password(service, username)
                logger.debug(f"Temporary password deleted for {username}@{service}.")

            except Exception as e:
                logger.warning(f"Failed to delete temporary password: {e}")


    ## File Backend Methods

    def _store_in_file(self, service: str, username: str, password: str):
        """Store password in encrypted file."""

        with self.file_operation():
            data = self._load_all()
            key = f"{service}:{username}"
            data[key] = password
            self._save_all(data)


    def _load_from_file(self, service: str, username: str) -> Optional[str]:
        """Load password from encrypted file."""

        with self.file_operation():
            data = self._load_all()
            key = f"{service}:{username}"
            return data.get(key)


    def _delete_from_file(self, service: str, username: str):
        """Delete password from encrypted file."""

        with self.file_operation():
            data = self._load_all()
            key = f"{service}:{username}"
            data.pop(key, None)
            self._save_all(data)


    def _load_all(self) -> Dict[str, str]:
        """Load all credentials from encrypted file."""
        
        if not SECRETS_FILE.exists():
            return {}
        
        with open(SECRETS_FILE, "rb") as f:
            encrypted_data = f.read()

        if not encrypted_data:
            return {}
        
        cipher = self._get_cipher()
        decrypted_data = cipher.decrypt(encrypted_data)

        return json.loads(decrypted_data.decode())
    

    def _save_all(self, data: Dict[str, str]):
        """Save all credentials to encrypted file."""

        cipher = self._get_cipher()
        json_data = json.dumps(data).encode()
        encrypted_data = cipher.encrypt(json_data)

        with open(SECRETS_FILE, "wb") as f:
            f.write(encrypted_data)
