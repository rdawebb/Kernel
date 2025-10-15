"""Logging utility for Kernel application"""

import logging
import json
import datetime
import inspect
from logging.handlers import RotatingFileHandler
from pathlib import Path
from utils.config import load_config

config = load_config()
log_path = Path(config.get("log_path"))
log_file = log_path / config.get("log_file")
log_config_file = log_path / config.get("log_config")

def load_log_config():
    """Load logging configuration from JSON file if it exists"""
    try:
        if log_config_file.exists():
            cfg = json.loads(log_config_file.read_text())
            level = cfg.get("log_level", "INFO").upper()
            return getattr(logging, level, logging.INFO)
    except Exception:
        pass
    return logging.INFO

def get_logger(
        name: str = "kernel",
        level = None,
        max_bytes: int = 5 * 1024 * 1024,
        backup_count: int = 5,
        console: bool = True,
        session: bool = True,
):
    """Create a configured logger with rotation and optional session file and console handlers"""
    log_path.mkdir(parents=True, exist_ok=True)
    level = level or load_log_config()

    logger = logging.getLogger(name)
    logger.setLevel(level)

    if not any(isinstance(handler, RotatingFileHandler) for handler in logger.handlers):
        file_handler = RotatingFileHandler(
            log_file, maxBytes=max_bytes, backupCount=backup_count, encoding='utf-8'
        )

        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))

        logger.addHandler(file_handler)

    if session and not any(isinstance(handler, logging.FileHandler) and handler.baseFilename != str(log_file) for handler in logger.handlers):
        time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        session_file = log_path / f"session_{time.replace(' ', '_').replace(':', '-')}.log"
        session_handler = logging.FileHandler(session_file, encoding='utf-8')
        session_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
        logger.addHandler(session_handler)

    if console and not any(isinstance(handler, logging.StreamHandler) for handler in logger.handlers):
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter('%(levelname)s - %(message)s'))
        logger.addHandler(console_handler)

    return logger

def get_component_logger(component: object, level=None):
    """Get a logger from a component's module and class"""
    module = inspect.getmodule(component).__name__
    name = getattr(component, '__class__', type(component)).__name__
    logger_name = f"{module}.{name.lower()}"

    logger = get_logger(name=logger_name, level=level)
    return logger