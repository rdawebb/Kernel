"""Logging utility for Kernel application"""

import logging
import json
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from functools import wraps
from pathlib import Path
from typing import Optional
from rich.logging import RichHandler
from rich.console import Console

console = Console()

LOG_DIR = Path("logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)


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

    def process(self, msg: str, kwargs: dict) -> tuple[str, dict]:
        if "extra" not in kwargs:
            kwargs["extra"] = {}

        kwargs["extra"].update(self.extra)
        return msg, kwargs

class LogManager:
    """Manages logging configuration and provides logger instances."""
    
    def __init__(self, log_level: str = "INFO"):
        self.log_level = getattr(logging, log_level.upper())
        self.root_logger = logging.getLogger("kernel")
        self.root_logger.setLevel(logging.DEBUG)
        self._setup_handlers()

    def _setup_handlers(self) -> None:
        """Setup console and file handlers."""

        self.root_logger.handlers.clear()

        console_handler = RichHandler(
            console=console,
            show_time=True,
            show_path=False,
            markup=True,
            rich_tracebacks=True,
        )

        console_handler.setLevel(logging.WARNING)
        console_formatter = logging.Formatter(
            "%(message)s",
            datefmt="[%X]"
        )

        console_handler.setFormatter(console_formatter)

        app_handler = RotatingFileHandler(
            LOG_DIR / "app.log",
            maxBytes=5_242_880,
            backupCount=5,
            encoding="utf-8"
        )

        app_handler.setLevel(logging.DEBUG)
        app_handler.setFormatter(JSONFormatter())

        event_handler = RotatingFileHandler(
            LOG_DIR / "events.log",
            maxBytes=2_048_000,
            backupCount=3,
            encoding="utf-8"
        )

        event_handler.setLevel(logging.INFO)
        event_handler.setFormatter(JSONFormatter())
        event_handler.addFilter(lambda record: hasattr(record, "event_type"))

        self.root_logger.addHandler(console_handler)
        self.root_logger.addHandler(app_handler)
        self.root_logger.addHandler(event_handler)

    def get_logger(self, name: Optional[str] = None, **context) -> logging.Logger:
        """Get a logger with optional context."""
        
        logger = self.root_logger if name else self.root_logger

        if context:
            return ContextAdapter(logger, context)
        
        return logger

    def set_level(self, level: str):
        """Set logging level at runtime"""

        self.log_level = getattr(logging, level.upper())
        
        for handler in self.root_logger.handlers:
            if isinstance(handler, RichHandler):
                handler.setLevel(self.log_level)

    def log_event(self, event_type: str, message: str, **extra):
        """Log an event with specific type and extra context."""
        
        logger = self.root_logger
        extra["event_type"] = event_type
        logger.info(message, extra=extra)

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

_log_manager: Optional[LogManager] = None

def init_logging(log_level: str = "INFO") -> LogManager:
    """Initialize logging system and return LogManager instance."""
    
    global _log_manager
    _log_manager = LogManager(log_level)

    return _log_manager

def get_logger(name: Optional[str] = None, **context) -> logging.Logger:
    """Get a logger instance with optional context."""

    if _log_manager is None:
        init_logging()

    return _log_manager.get_logger(name, **context)

def log_event(event_type: str, message: str, **extra):
    """Log an event with specific type and extra context (module-level wrapper)."""
    
    if _log_manager is None:
        init_logging()
    
    return _log_manager.log_event(event_type, message, **extra)
