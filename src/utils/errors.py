"""Centralized email handling module."""

import asyncio
from enum import Enum
from functools import wraps
from typing import Any, Callable, Dict, Optional

from src.utils.logging import get_logger

_logger = None


def _get_logger():
    """Get logger with lazy initialisation."""
    global _logger
    if _logger is None:
        _logger = get_logger(__name__)
    return _logger


## Error Categories


class ErrorCategory(Enum):
    """Categories of errors for better handling."""

    DATABASE = "database"
    NETWORK = "network"
    AUTHENTICATION = "authentication"
    VALIDATION = "validation"
    FILE_SYSTEM = "file_system"
    CONFIGURATION = "configuration"
    UNKNOWN = "unknown"


## Custom Exceptions


class KernelError(Exception):
    """Base exception for all Kernel errors."""

    category = ErrorCategory.UNKNOWN
    user_message = "An error occurred"

    def __init__(
        self, message: str | None = None, details: Dict[str, Any] | None = None
    ):
        """Initialise KernelError with optional message and details."""
        self.message = message or self.user_message
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        """Convert error details to a dictionary."""
        return {
            "error_type": self.__class__.__name__,
            "category": self.category.value,
            "message": self.message,
            "details": self.details,
        }


## Database Errors


class DatabaseError(KernelError):
    """Base exception for database-related errors."""

    category = ErrorCategory.DATABASE
    user_message = "A database error occurred"


class BackupError(DatabaseError):
    """Base exception for backup-related errors."""

    user_message = "A backup error occurred"


class DatabaseConnectionError(DatabaseError):
    """Exception for database connection failures."""

    user_message = "Failed to connect to the database"


class DatabaseTransactionError(DatabaseError):
    """Exception for database transaction failures."""

    user_message = "A database transaction error occurred"


class EmailNotFoundError(DatabaseError):
    """Exception when an email is not found in the database."""

    user_message = "Email not found"


class InvalidTableError(DatabaseError):
    """Exception for invalid database table operations."""

    user_message = "Invalid email folder specified"


## Network Errors


class NetworkError(KernelError):
    """Base exception for network-related errors."""

    category = ErrorCategory.NETWORK
    user_message = "A network error occurred"


class IMAPError(NetworkError):
    """Exception for IMAP protocol errors."""

    user_message = "Failed to connect to email server"


class SMTPError(NetworkError):
    """Exception for SMTP protocol errors."""

    user_message = "Failed to send email"


class NetworkTimeoutError(NetworkError):
    """Exception for network timeout errors."""

    user_message = "The connection timed out"


## Authentication Errors


class AuthenticationError(KernelError):
    """Base exception for authentication-related errors."""

    category = ErrorCategory.AUTHENTICATION
    user_message = "An authentication error occurred"


class InvalidCredentialsError(AuthenticationError):
    """Exception for invalid login credentials."""

    user_message = "Invalid email or password"


class MissingCredentialsError(AuthenticationError):
    """Exception for missing login credentials."""

    user_message = "Email credentials not configured"


## Validation Errors


class ValidationError(KernelError):
    """Base exception for validation-related errors."""

    category = ErrorCategory.VALIDATION
    user_message = "Invalid input"


class InvalidEmailAddressError(ValidationError):
    """Exception for invalid email addresses."""

    user_message = "Invalid email address"


class MissingRequiredFieldError(ValidationError):
    """Exception for missing required fields."""

    user_message = "A required field is missing"


## File System Errors


class FileSystemError(KernelError):
    """Base exception for file system-related errors."""

    category = ErrorCategory.FILE_SYSTEM
    user_message = "A file system error occurred"


class AttachmentNotFoundError(FileSystemError):
    """Exception when an email attachment is not found."""

    user_message = "Attachment not found"


class AttachmentDownloadError(FileSystemError):
    """Exception for failures during attachment download."""

    user_message = "Failed to download attachment"


class InvalidPathError(FileSystemError):
    """Exception for invalid file paths."""

    user_message = "Invalid file path"


## Configuration Errors


class ConfigurationError(KernelError):
    """Base exception for configuration-related errors."""

    category = ErrorCategory.CONFIGURATION
    user_message = "A configuration error occurred"


class MissingConfigError(ConfigurationError):
    """Exception for missing configuration settings."""

    user_message = "Missing configuration settings"


class InvalidConfigError(ConfigurationError):
    """Exception for invalid configuration settings."""

    user_message = "Invalid configuration settings"


## Key Store Errors


class KeyStoreError(KernelError):
    """Base exception for key store-related errors."""

    category = ErrorCategory.AUTHENTICATION
    user_message = "A key store error occurred"


class EncryptionError(KeyStoreError):
    """Exception for encryption/decryption failures."""

    user_message = "Failed to encrypt/decrypt data"


class CorruptedSecretsError(KeyStoreError):
    """Exception for corrupted key store data."""

    user_message = "Key store data is corrupted"


class KeyringUnavailableError(KeyStoreError):
    """Exception when keyring service is unavailable."""

    user_message = "Keyring service is unavailable"


## Error Handler


class ErrorHandler:
    """Centralized error handling and logging."""

    @staticmethod
    def handle(
        error: Exception, context: str = "", log_traceback: bool = True
    ) -> Dict[str, Any]:
        """Handle errors with logging and user-friendly message."""
        if isinstance(error, KernelError):
            _get_logger().error(f"{context}: {error.message}", extra=error.details)
            if log_traceback:
                _get_logger().exception(error)
            return error.to_dict()
        else:
            _get_logger().error(f"{context}: {str(error)}")
            if log_traceback:
                _get_logger().exception(error)
            return {
                "error_type": "UnknownError",
                "category": ErrorCategory.UNKNOWN.value,
                "message": str(error),
                "details": {"context": context},
            }

    @staticmethod
    def wrap(func):
        """Decorator to wrap functions with error handling."""
        if asyncio.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                try:
                    return await func(*args, **kwargs)

                except KernelError:
                    raise

                except Exception as e:
                    _get_logger().exception(f"Unexpected error in {func.__name__}")
                    raise KernelError(
                        message=f"Unexpected error: {str(e)}",
                        details={"function": func.__name__},
                    ) from e

            return async_wrapper
        else:

            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                try:
                    return func(*args, **kwargs)

                except KernelError:
                    raise

                except Exception as e:
                    _get_logger().exception(f"Unexpected error in {func.__name__}")
                    raise KernelError(
                        message=f"Unexpected error: {str(e)}",
                        details={"function": func.__name__},
                    ) from e

            return sync_wrapper


## Context Manager for Error Handling


class error_context:
    """Context manager for error handling."""

    def __init__(
        self,
        context: str = "",
        user_message: Optional[str] = None,
        reraise: bool = True,
    ):
        """initialise error context manager."""

        self.context = context
        self.user_message = user_message
        self.reraise = reraise
        self.error = None

    def __enter__(self):
        """Enter the context."""
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        """Exit the context and handle exceptions."""
        if exc_type is None:
            return False

        self.error = ErrorHandler.handle(exc_value, self.context)

        return not self.reraise


## Utility Functions


def safe_execute(func: Callable, *args, default=None, context: str = "", **kwargs):
    """Execute a function safely with error handling."""
    if asyncio.iscoroutinefunction(func):
        return _safe_execute_async(
            func, *args, default=default, context=context, **kwargs
        )
    else:
        try:
            return func(*args, **kwargs)

        except Exception as e:
            ErrorHandler.handle(e, context, log_traceback=False)
            return default


async def _safe_execute_async(func, *args, default, context, **kwargs):
    """Internal async safe execute helper."""
    try:
        return await func(*args, **kwargs)

    except Exception as e:
        ErrorHandler.handle(e, context, log_traceback=False)
        return default


def format_error_message(error: Exception) -> str:
    """Format an error message for display."""
    if isinstance(error, KernelError):
        return error.message
    else:
        return "An unexpected error occurred - check logs for details."
