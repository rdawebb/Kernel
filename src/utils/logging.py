"""Logging utility for Kernel application"""

import json
import logging
import re
from datetime import datetime, timezone
from functools import wraps
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict, Optional

from rich.logging import RichHandler

from .paths import LOGS_DIR

_LOG_DIR: Optional[Path] = None


def _get_log_dir() -> Path:
    """Get log directory, creating it on first access."""

    from .errors import FileSystemError

    global _LOG_DIR

    if _LOG_DIR is None:
        _LOG_DIR = LOGS_DIR
        try:
            _LOG_DIR.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise FileSystemError(f"Failed to create log directory: {_LOG_DIR}") from e

    return _LOG_DIR


## Custom JSON Formatter


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for log records."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
            "level": record.levelname,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "message": record.getMessage(),
        }

        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        if hasattr(record, "context"):
            log_entry["context"] = record.context

        return json.dumps(log_entry)


class ContextAdapter(logging.LoggerAdapter):
    """Logger adapter to add contextual information."""

    from typing import Any, MutableMapping

    def process(
        self, msg: Any, kwargs: MutableMapping[str, Any]
    ) -> tuple[Any, MutableMapping[str, Any]]:
        if "extra" not in kwargs:
            kwargs["extra"] = {}

        kwargs["extra"].update(self.extra)
        return msg, kwargs


## Log Masking


class SensitiveDataMasker:
    """Utility to mask sensitive data in log messages."""

    PATTERNS = {
        "password": re.compile(
            r'(password["\']?\s*[:=]\s*["\']?)([^"\'}\s]+)', re.IGNORECASE
        ),
        "token": re.compile(
            r'(token["\']?\s*[:=]\s*["\']?)([^"\'}\s]+)', re.IGNORECASE
        ),
        "api_key": re.compile(
            r'(api[_-]?key["\']?\s*[:=]\s*["\']?)([^"\'}\s]+)', re.IGNORECASE
        ),
        "secret": re.compile(
            r'(secret["\']?\s*[:=]\s*["\']?)([^"\'}\s]+)', re.IGNORECASE
        ),
        "authorization": re.compile(
            r'(authorization["\']?\s*[:=]\s*["\']?)([^"\'}\s]+)', re.IGNORECASE
        ),
        "email": re.compile(
            r"([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})", re.IGNORECASE
        ),
        "credit_card": re.compile(
            r"(\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b)", re.IGNORECASE
        ),
    }

    SENSITIVE_FIELDS = {
        "password",
        "passwd",
        "pwd",
        "secret",
        "token",
        "api_key",
        "apikey",
        "authorization",
        "auth",
        "credential",
        "private_key",
        "access_token",
        "refresh_token",
        "session_id",
        "cookie",
    }

    MASK_STRATEGIES = {
        "full": lambda x: "[REDACTED]",
        "partial": lambda x: x[:3] + "*" * (len(x) - 6) + x[-3:]
        if len(x) > 6
        else "[REDACTED]",
        "hash": lambda x: f"[HASHED:{hash(x) & 0xFFFFFFFF:08X}]",
    }

    def __init__(self, strategy: str = "full"):
        """Initialize masker with specified strategy."""

        self.strategy = strategy
        self.mask_func = self.MASK_STRATEGIES[strategy]

    @staticmethod
    def _validate_credit_card(card_number: str) -> bool:
        """Validate credit card number using Luhn algorithm."""

        digits = card_number.replace(" ", "").replace("-", "")

        if not digits.isdigit() or len(digits) < 13 or len(digits) > 19:
            return False

        total = 0
        for i, digit in enumerate(reversed(digits)):
            n = int(digit)

            if i % 2 == 1:
                n *= 2
                if n > 9:
                    n -= 9

            total += n

        return total % 10 == 0

    def mask_string(self, text: str) -> str:
        """Mask sensitive data in a string message."""

        if not text:
            return text

        masked = text

        for name, pattern in self.PATTERNS.items():
            if name == "email":
                masked = pattern.sub(lambda m: self._mask_email(m.group(0)), masked)
            elif name == "credit_card":
                masked = pattern.sub(
                    lambda m: self.mask_func(m.group(1))
                    if self._validate_credit_card(m.group(1))
                    else m.group(1),
                    masked,
                )
            else:
                masked = pattern.sub(
                    lambda m: m.group(1) + self.mask_func(m.group(2)), masked
                )

        return masked

    def mask_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Mask sensitive data in a dictionary."""

        if not isinstance(data, dict):
            return data

        masked = {}

        for key, value in data.items():
            try:
                if key.lower() in self.SENSITIVE_FIELDS:
                    masked[key] = self.mask_func(str(value))
                elif isinstance(value, dict):
                    masked[key] = self.mask_dict(value)
                elif isinstance(value, str):
                    masked[key] = self.mask_string(value)
                else:
                    masked[key] = value

            except Exception:
                masked[key] = self.mask_func(str(value))

        return masked

    def _mask_email(self, email: str) -> str:
        """Mask an email address while preserving domain."""

        try:
            username, domain = email.split("@")
            masked_username = username[0] + "***" if len(username) > 1 else "***"
            masked_domain = domain[0] + ("***" if len(domain) > 1 else "*")

            return f"{masked_username}@{masked_domain}"

        except Exception:
            return self.mask_func(email)


class SensitiveDataFilter(logging.Filter):
    """Logging filter to mask sensitive data in log records."""

    def __init__(self, strategy: str = "full"):
        """Initialize filter with specified masking strategy."""

        super().__init__()
        self.masker = SensitiveDataMasker(strategy)

    def filter(self, record) -> bool:
        """Filter log record to mask sensitive data."""

        if hasattr(record, "msg"):
            record.msg = self.masker.mask_string(record.msg)

        if hasattr(record, "__dict__"):
            for key, value in record.__dict__.items():
                if key.lower() in self.masker.SENSITIVE_FIELDS:
                    setattr(record, key, self.masker.mask_func(str(value)))
                elif isinstance(value, str):
                    setattr(record, key, self.masker.mask_string(value))
                elif isinstance(value, dict):
                    setattr(record, key, self.masker.mask_dict(value))

        return True


## Main Log Manager


class LogManager:
    """Manages logging configuration and provides logger instances."""

    def __init__(self, log_level: str = "INFO"):
        self.log_level = getattr(logging, log_level.upper())
        self.root_logger = logging.getLogger("kernel")
        self.root_logger.setLevel(logging.DEBUG)
        self._setup_handlers()

    def _setup_handlers(self) -> None:
        """Setup console and file handlers with sensitive data filtering."""

        from .errors import FileSystemError, KernelError

        sensitive_filter = SensitiveDataFilter(strategy="full")

        try:
            self.root_logger.handlers.clear()

            console_handler = RichHandler(
                show_time=True,
                show_path=False,
                markup=True,
                rich_tracebacks=True,
            )

            console_handler.setLevel(logging.WARNING)
            console_formatter = logging.Formatter("%(message)s", datefmt="[%X]")

            console_handler.setFormatter(console_formatter)
            console_handler.addFilter(sensitive_filter)

            try:
                log_dir = _get_log_dir()
                app_handler = RotatingFileHandler(
                    log_dir / "app.log",
                    maxBytes=5_242_880,
                    backupCount=5,
                    encoding="utf-8",
                )

            except IOError as e:
                raise FileSystemError(
                    f"Failed to create app.log handler: {str(e)}"
                ) from e

            app_handler.setLevel(logging.DEBUG)
            app_handler.setFormatter(JSONFormatter())
            app_handler.addFilter(sensitive_filter)

            try:
                event_handler = RotatingFileHandler(
                    log_dir / "events.log",
                    maxBytes=2_048_000,
                    backupCount=3,
                    encoding="utf-8",
                )

            except IOError as e:
                raise FileSystemError(
                    f"Failed to create events.log handler: {str(e)}"
                ) from e

            event_handler.setLevel(logging.INFO)
            event_handler.setFormatter(JSONFormatter())
            event_handler.addFilter(lambda record: hasattr(record, "event_type"))
            event_handler.addFilter(sensitive_filter)

            self.root_logger.addHandler(console_handler)
            self.root_logger.addHandler(app_handler)
            self.root_logger.addHandler(event_handler)

        except KernelError:
            raise

        except Exception as e:
            raise FileSystemError(f"Failed to setup logging handlers: {str(e)}") from e

    def get_logger(
        self, name: Optional[str] = None, **context
    ) -> logging.Logger | ContextAdapter:
        """Get a logger with optional context.

        Returns:
            logging.Logger or ContextAdapter: Logger instance, possibly wrapped with context.
        """

        if _log_manager is None:
            init_logging()

        logger = logging.getLogger(f"kernel.{name}" if name else "kernel")

        if context:
            return ContextAdapter(logger, context)

        return logger

    def set_level(self, level: str):
        """Set logging level at runtime"""

        from .errors import FileSystemError

        try:
            self.log_level = getattr(logging, level.upper())

            for handler in self.root_logger.handlers:
                handler.setLevel(self.log_level)

        except AttributeError as e:
            raise ValueError(f"Invalid logging level: {level}") from e
        except Exception as e:
            raise FileSystemError(f"Failed to set logging level: {str(e)}") from e

    def log_event(self, event_type: str, message: str, level: str = "INFO", **extra):
        """Log an event with specific type and extra context."""

        logger = self.root_logger
        extra_dict = {"event_type": event_type}
        extra_dict.update(extra)

        try:
            log_level = getattr(logging, level.upper())
            logger.log(log_level, message, extra=extra_dict)

        except AttributeError as e:
            raise ValueError(f"Invalid logging level: {level}") from e


## Decorators for Logging


def log_call(func):
    """Decorator to log function calls with arguments and return values."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        logger = logging.getLogger("kernel")
        func_name = f"{func.__module__}.{func.__qualname__}"
        logger.debug(f"-> Entering {func_name}")
        start_time = datetime.now()

        try:
            result = func(*args, **kwargs)
            duration = (datetime.now() - start_time).total_seconds()
            logger.debug(f"<- Exiting {func_name} (Duration: {duration:.3f}s)")
            return result

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.exception(f"<- Error in {func_name} after {duration:.3f}s: {e}")
            raise

    return wrapper


def async_log_call(func):
    """Async decorator to log function calls with arguments and return values."""

    @wraps(func)
    async def wrapper(*args, **kwargs):
        logger = logging.getLogger("kernel")
        func_name = f"{func.__module__}.{func.__qualname__}"
        logger.debug(f"-> Entering {func_name} (async)")
        start_time = datetime.now()

        try:
            result = await func(*args, **kwargs)
            duration = (datetime.now() - start_time).total_seconds()
            logger.debug(f"<- Exiting {func_name} (Duration: {duration:.3f}s)")
            return result

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.exception(f"<- Error in {func_name} after {duration:.3f}s: {e}")
            raise

    return wrapper


## Module-level LogManager Instance and Helper Functions

_log_manager: Optional[LogManager] = None


def init_logging(log_level: str = "INFO") -> LogManager:
    """Initialize logging system and return LogManager instance."""

    global _log_manager

    if _log_manager is None:
        _log_manager = LogManager(log_level)

    return _log_manager


def get_logger(
    name: Optional[str] = None, **context
) -> logging.Logger | ContextAdapter:
    """Get a logger instance with optional context."""

    global _log_manager
    if _log_manager is None:
        _log_manager = init_logging()

    # _log_manager is guaranteed to be LogManager here
    return _log_manager.get_logger(name, **context)


def log_event(event_type: str, message, **extra):
    """Log an event with specific type and extra context (module-level wrapper)."""

    global _log_manager
    if _log_manager is None:
        _log_manager = init_logging()

    # Handle both string messages and dict-based messages
    if isinstance(message, dict):
        # If message is a dict, merge it with extra and create a string message
        extra.update(message)
        message = f"Event: {event_type}"

    return _log_manager.log_event(event_type, message, **extra)
