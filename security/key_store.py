"""Key management for encryption and decryption of sensitive data."""

import json
import os
import subprocess
from contextlib import contextmanager
from enum import Enum
from typing import Callable, Dict, Optional

from src.utils.errors import (
    CorruptedSecretsError,
    EncryptionError,
    KeyringUnavailableError,
    KeyStoreError,
    safe_execute,
)
from src.utils.logging import get_logger, log_event
from src.utils.paths import CREDENTIALS_PATH, MASTER_KEY_PATH

logger = get_logger(__name__)


class KeyBackend(Enum):
    """Available key storage backends."""

    KEYRING = "keyring"
    ONEPASSWORD = "1password"
    BITWARDEN = "bitwarden"
    ENCRYPTED_FILE = "encrypted_file"


class KeyStore:
    """Manage encryption keys and encrypted secrets storage - supports multiple backends."""

    SECURITY_WARNING = """
    ⚠️  WARNING: Using fallback key storage method
    
    The preferred secure storage (system keyring or password manager) is not available.
    Your credentials will be stored using {backend}.
    
    For better security, consider:
    1. Installing keyring support for your system
    2. Using a password manager integration (1Password, Bitwarden)
    
    Continue with {backend}? (yes/no): """

    def __init__(self, service_name: str = "kernel"):
        """Initialize KeyStore with the most secure available backend."""

        self.service_name = service_name
        self.backend: Optional[KeyBackend] = None
        self._master_key: Optional[bytes] = None
        self._secrets_path = CREDENTIALS_PATH
        self._initialize_backend()

    def _initialize_backend(self) -> None:
        """Initialize the most secure available backend."""

        backends = [
            (KeyBackend.ONEPASSWORD, self._check_onepassword),
            (KeyBackend.BITWARDEN, self._check_bitwarden),
            (KeyBackend.KEYRING, self._check_keyring),
            (KeyBackend.ENCRYPTED_FILE, lambda: True),  # Always available
        ]

        for backend, check_func in backends:
            if check_func():
                self.backend = backend
                logger.info(f"Using key storage backend: {backend.value}")

                if backend == KeyBackend.ENCRYPTED_FILE:
                    self._show_security_warning(backend)

                log_event(
                    "keystore_initialized",
                    {"backend": backend.value, "service": self.service_name},
                )
                break

    ## Backend Detection

    def _check_cli_available(self, command: str) -> bool:
        """Check if a CLI tool is available (generic helper)."""
        result = safe_execute(
            subprocess.run,
            [command, "--version"],
            capture_output=True,
            timeout=2,
            default=None,
            context=f"check_{command}_cli",
        )
        return result is not None and result.returncode == 0

    def _check_onepassword(self) -> bool:
        """Check if 1Password CLI is available."""
        return self._check_cli_available("op")

    def _check_bitwarden(self) -> bool:
        """Check if Bitwarden CLI is available."""
        return self._check_cli_available("bw")

    def _check_keyring(self) -> bool:
        """Check if system keyring is available."""

        def test_keyring():
            import keyring

            keyring.get_keyring()
            return True

        return safe_execute(test_keyring, default=False, context="check_system_keyring")

    def _show_security_warning(self, backend: KeyBackend) -> None:
        """Show security warning and get user confirmation."""
        warning = self.SECURITY_WARNING.format(backend=backend.value)
        logger.warning(f"Using less secure backend: {backend.value}")

        # Non-interactive mode, log warning only
        if not os.isatty(0):
            logger.warning("Non-interactive mode: proceeding with fallback storage")
            return

        # Interactive mode: require confirmation
        try:
            response = input(warning).strip().lower()
            if response not in ("y", "yes"):
                raise KeyStoreError(
                    "User declined to use fallback key storage",
                    details={"backend": backend.value},
                )
        except EOFError:
            logger.warning("Cannot get user input, proceeding with fallback storage")

    ## Encryption Utilities

    def _get_master_key(self) -> bytes:
        """Get or create master encryption key for file backend."""
        if self._master_key:
            return self._master_key

        try:
            from cryptography.fernet import Fernet

            key_path = MASTER_KEY_PATH
            key_path.parent.mkdir(parents=True, exist_ok=True)

            if key_path.exists():
                self._master_key = key_path.read_bytes()
                logger.debug("Loaded existing master key")
            else:
                self._master_key = Fernet.generate_key()
                key_path.write_bytes(self._master_key)
                key_path.chmod(0o600)
                logger.info("Generated new master key")
                log_event("master_key_created", {"path": str(key_path)})

            return self._master_key

        except Exception as e:
            raise EncryptionError(
                "Failed to get or create master key", details={"error": str(e)}
            ) from e

    def _crypto_operation(self, value: str, operation: str) -> str:
        """Perform encryption or decryption (unified method)."""

        try:
            from cryptography.fernet import Fernet

            cipher = Fernet(self._get_master_key())

            if operation == "encrypt":
                result = cipher.encrypt(value.encode())
                return result.decode()
            else:
                result = cipher.decrypt(value.encode())
                return result.decode()

        except Exception as e:
            error_class = (
                CorruptedSecretsError if operation == "decrypt" else EncryptionError
            )
            message = (
                "Failed to decrypt data - may be corrupted or wrong key"
                if operation == "decrypt"
                else "Failed to encrypt data"
            )
            raise error_class(message, details={"error": str(e)}) from e

    def _encrypt(self, value: str) -> str:
        """Encrypt a value with master key."""
        return self._crypto_operation(value, "encrypt")

    def _decrypt(self, encrypted: str) -> str:
        """Decrypt a value with master key."""
        return self._crypto_operation(encrypted, "decrypt")

    ## Password Manager Operations (Generic)

    def _password_manager_operation(
        self, manager: str, operation: str, key: str, value: Optional[str] = None
    ) -> Optional[str]:
        """Generic password manager operation for 1Password ("op") and Bitwarden ("bw")."""

        item_name = f"{self.service_name}_{key}"

        try:
            if operation == "store":
                existing = safe_execute(
                    subprocess.run,
                    [manager, "item" if manager == "op" else "", "get", item_name],
                    capture_output=True,
                    default=None,
                    context=f"check_{manager}_item",
                )

                if existing and existing.returncode == 0:
                    if manager == "op":
                        subprocess.run(
                            ["op", "item", "edit", item_name, f"password={value}"],
                            check=True,
                            capture_output=True,
                        )
                    else:
                        item = json.loads(existing.stdout)
                        item["login"]["password"] = value
                        subprocess.run(
                            [
                                "bw",
                                "edit",
                                "item",
                                item["id"],
                                "--item",
                                json.dumps(item),
                            ],
                            check=True,
                            capture_output=True,
                        )
                else:
                    if manager == "op":
                        item_json = json.dumps(
                            {
                                "title": item_name,
                                "vault": "kernel",
                                "category": "password",
                                "fields": [{"id": "password", "value": value}],
                            }
                        )
                        subprocess.run(
                            ["op", "item", "create", "--template", item_json],
                            check=True,
                            capture_output=True,
                        )
                    else:
                        item_json = json.dumps(
                            {"type": 1, "name": item_name, "login": {"password": value}}
                        )
                        subprocess.run(
                            ["bw", "create", "item", item_json],
                            check=True,
                            capture_output=True,
                        )
                return None

            # retrieve
            else:
                if manager == "op":
                    result = subprocess.run(
                        ["op", "item", "get", item_name, "--fields", "label=password"],
                        capture_output=True,
                        text=True,
                        check=True,
                    )
                    return result.stdout.strip() or None
                else:
                    result = subprocess.run(
                        ["bw", "get", "item", item_name],
                        capture_output=True,
                        text=True,
                        check=True,
                    )
                    item = json.loads(result.stdout)
                    return item.get("login", {}).get("password")

        except subprocess.CalledProcessError:
            if operation == "retrieve":
                return None
            raise KeyStoreError(
                f"Failed to {operation} credential in {manager}", details={"key": key}
            )
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to parse {manager} response: {e}")
            return None if operation == "retrieve" else None

    ## 1Password Backend

    def _store_onepassword(self, key: str, value: str) -> None:
        """Store credential in 1Password."""
        self._password_manager_operation("op", "store", key, value)

    def _retrieve_onepassword(self, key: str) -> Optional[str]:
        """Retrieve credential from 1Password."""
        return self._password_manager_operation("op", "retrieve", key)

    ## Bitwarden Backend

    def _store_bitwarden(self, key: str, value: str) -> None:
        """Store credential in Bitwarden."""
        self._password_manager_operation("bw", "store", key, value)

    def _retrieve_bitwarden(self, key: str) -> Optional[str]:
        """Retrieve credential from Bitwarden."""
        return self._password_manager_operation("bw", "retrieve", key)

    ## Keyring Backend

    def _store_keyring(self, key: str, value: str) -> None:
        """Store credential in system keyring."""
        try:
            import keyring

            keyring.set_password(self.service_name, key, value)

        except Exception as e:
            raise KeyringUnavailableError(
                "Failed to access system keyring", details={"key": key, "error": str(e)}
            ) from e

    def _retrieve_keyring(self, key: str) -> Optional[str]:
        """Retrieve credential from system keyring."""
        try:
            import keyring

            return keyring.get_password(self.service_name, key)

        except Exception as e:
            logger.error(f"Failed to retrieve from keyring: {e}")
            return None

    ## Encrypted File Backend

    def _file_credentials_operation(
        self,
        operation: Callable[[Dict[str, str], str, Optional[str]], Optional[str]],
        key: str,
        value: Optional[str] = None,
    ) -> Optional[str]:
        """Generic file operation for encrypted credentials."""

        try:
            self._secrets_path.parent.mkdir(parents=True, exist_ok=True)

            # Load existing credentials
            credentials = {}
            if self._secrets_path.exists():
                encrypted_data = self._secrets_path.read_text()
                if encrypted_data:
                    decrypted_data = self._decrypt(encrypted_data)
                    credentials = json.loads(decrypted_data)

            result = operation(credentials, key, value)

            if operation.__name__ in ("store", "delete"):
                encrypted_data = self._encrypt(json.dumps(credentials))
                temp_path = self._secrets_path.with_suffix(".tmp")
                temp_path.write_text(encrypted_data)
                temp_path.chmod(0o600)
                temp_path.replace(self._secrets_path)

            return result

        except CorruptedSecretsError:
            raise
        except Exception as e:
            raise KeyStoreError(
                f"File operation failed for key '{key}'", details={"error": str(e)}
            ) from e

    def _store_encrypted_file(self, key: str, value: str) -> None:
        """Store encrypted credential in file."""

        def store(creds: Dict, k: str, v: str) -> None:
            creds[k] = v
            return None

        self._file_credentials_operation(store, key, value)

    def _retrieve_encrypted_file(self, key: str) -> Optional[str]:
        """Retrieve encrypted credential from file."""
        if not self._secrets_path.exists():
            return None

        def retrieve(creds: Dict, k: str, v: Optional[str]) -> Optional[str]:
            return creds.get(k)

        return self._file_credentials_operation(retrieve, key)

    def _delete_encrypted_file(self, key: str) -> None:
        """Delete credential from encrypted file."""

        def delete(creds: Dict, k: str, v: Optional[str]) -> None:
            creds.pop(k, None)
            return None

        self._file_credentials_operation(delete, key)

    ## Public API

    def store(self, key: str, value: str) -> None:
        """Store a credential using the configured backend."""

        backend_methods = {
            KeyBackend.ONEPASSWORD: self._store_onepassword,
            KeyBackend.BITWARDEN: self._store_bitwarden,
            KeyBackend.KEYRING: self._store_keyring,
            KeyBackend.ENCRYPTED_FILE: self._store_encrypted_file,
        }

        method = backend_methods[self.backend]
        method(key, value)

        logger.info(f"Stored credential '{key}' using {self.backend.value}")
        log_event("credential_stored", {"key": key, "backend": self.backend.value})

    def retrieve(self, key: str) -> Optional[str]:
        """Retrieve a credential using the configured backend."""

        backend_methods = {
            KeyBackend.ONEPASSWORD: self._retrieve_onepassword,
            KeyBackend.BITWARDEN: self._retrieve_bitwarden,
            KeyBackend.KEYRING: self._retrieve_keyring,
            KeyBackend.ENCRYPTED_FILE: self._retrieve_encrypted_file,
        }

        method = backend_methods[self.backend]
        value = method(key)

        if value:
            logger.debug(f"Retrieved credential '{key}' from {self.backend.value}")
        else:
            logger.debug(f"Credential '{key}' not found in {self.backend.value}")

        return value

    def delete(self, key: str) -> None:
        """Delete a credential."""

        if self.backend == KeyBackend.ENCRYPTED_FILE:
            self._delete_encrypted_file(key)
            logger.info(f"Deleted credential '{key}' from encrypted file")
            log_event("credential_deleted", {"key": key, "backend": self.backend.value})

        elif self.backend == KeyBackend.KEYRING:
            try:
                import keyring

                keyring.delete_password(self.service_name, key)
                logger.info(f"Deleted credential '{key}' from keyring")
                log_event(
                    "credential_deleted", {"key": key, "backend": self.backend.value}
                )

            except Exception as e:
                raise KeyStoreError(
                    "Failed to delete credential from keyring",
                    details={"key": key, "error": str(e)},
                ) from e

        else:
            logger.warning(
                f"Delete operation not supported for {self.backend.value} backend"
            )

    def validate(self) -> bool:
        """Validate that the keystore is operational."""

        if self.backend == KeyBackend.KEYRING:
            return True

        if self.backend == KeyBackend.ENCRYPTED_FILE:
            test_result = safe_execute(
                self._test_encryption, default=False, context="keystore_validation"
            )

            if not test_result:
                logger.error("Keystore validation failed")

            return test_result

        return True

    def _test_encryption(self) -> bool:
        """Test encryption/decryption cycle."""
        test_value = "test_validation_string"
        encrypted = self._encrypt(test_value)
        decrypted = self._decrypt(encrypted)
        return decrypted == test_value

    ## Utility Context Manager

    @contextmanager
    def temporary_credential(self, key: str, value: str):
        """Context manager for temporary credential storage for testing"""

        try:
            self.store(key, value)
            logger.debug(f"Temporary credential '{key}' stored")
            yield

        finally:
            try:
                self.delete(key)
                logger.debug(f"Temporary credential '{key}' deleted")
            except KeyStoreError as e:
                logger.warning(f"Failed to delete temporary credential: {e.message}")


## Singleton instance
_keystore_instance = None


def get_keystore(service_name: str = "kernel") -> KeyStore:
    """Get or create singleton KeyStore instance."""

    global _keystore_instance

    if _keystore_instance is None:
        _keystore_instance = KeyStore(service_name)

    return _keystore_instance
