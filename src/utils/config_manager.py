"""Configuration manager for persistent settings stored as JSON."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field

from .error_handling import (
    ConfigurationError,
    FileSystemError,
    InvalidConfigError,
    KernelError,
    MissingConfigError,
)
from .log_manager import get_logger, log_call
from .paths import (
    ATTACHMENTS_DIR,
    BACKUP_DB_PATH,
    DATABASE_PATH,
    EXPORTS_DIR,
    KERNEL_DIR,
)

logger = get_logger(__name__)

CONFIG_DIR = KERNEL_DIR
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_PATH = CONFIG_DIR / "config.json"


class AccountConfig(BaseModel):
    """Pydantic model for account configuration."""
    
    imap_server: str = ""
    imap_port: int = 993
    smtp_server: str = ""
    smtp_port: int = 587
    username: str = ""
    email: str = ""
    use_tls: bool = True
    network_timeout: int = 30  # in seconds
    connection_ttl: int = 3600  # in seconds

class FeaturesConfig(BaseModel):
    """Pydantic model for feature toggles."""
    
    auto_sync: bool = True
    auto_sync_interval: int = 5  # in minutes
    auto_backup: bool = True
    auto_backup_interval: int = 1440  # 24 hours
    notifications: bool = True
    email_summarisation: bool = True
    send_later: bool = True

class UIConfig(BaseModel):
    """Pydantic model for UI settings."""
    
    theme: str = "dark"
    show_status_bar: bool = True
    compact_mode: bool = False
    show_preview_pane: bool = True
    default_folder: str = "inbox"
    manage_list_columns: list[str] = Field(default_factory=lambda: ["from", "subject", "date"])

class LoggingConfig(BaseModel):
    """Pydantic model for logging settings."""
    
    log_level: str = "INFO"
    console_level: str = "INFO"
    file_level: str = "DEBUG"
    max_file_size: int = 5_242_880 # 5 MB
    backup_count: int = 5

class DatabaseConfig(BaseModel):
    """Pydantic model for database settings."""
    database_path: str = str(DATABASE_PATH.parent / "data" / "kernel.db")
    backup_path: str = str(BACKUP_DB_PATH)
    export_path: str = str(EXPORTS_DIR)
    attachments_path: str = str(ATTACHMENTS_DIR)

class AppConfig(BaseModel):
    """Pydantic model for overall application configuration."""

    version: str = "0.1.0"
    account: AccountConfig = Field(default_factory=AccountConfig)
    features: FeaturesConfig = Field(default_factory=FeaturesConfig)
    ui: UIConfig = Field(default_factory=UIConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)

class ConfigManager:
    """Manages persistent application configuration."""

    _instance = None
    _initialized = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
        return cls._instance

    def __init__(self, config_path: Optional[Path] = None):
        if not ConfigManager._initialized:
            self.path = config_path or CONFIG_PATH
            self.config = self._load_or_create_config()
            logger.info(f"Configuration loaded from {self.path}")
            ConfigManager._initialized = True

    def _load_or_create_config(self) -> AppConfig:
        """Load configuration from file or create default if not present."""

        from pydantic import ValidationError
        
        if not self.path.exists():
            logger.info("No config file found, creating default configuration.")
            config = AppConfig()
            self._save_config(config)
            return config
        
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            config = AppConfig(**data)
            logger.debug("Configuration successfully loaded and validated.")
            return config
        
        except FileNotFoundError as e:
            raise FileSystemError(f"Configuration file not found: {self.path}") from e
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse config file: {e}")
            raise InvalidConfigError(f"Configuration file is not valid JSON: {str(e)}") from e
        except ValidationError as e:
            logger.error(f"Failed to validate config file: {e}")
            raise InvalidConfigError(f"Configuration data does not match expected schema: {str(e)}") from e
        except KernelError:
            raise
        except Exception as e:
            logger.exception(f"Unexpected error loading config: {e}")
            raise ConfigurationError(f"Failed to load configuration: {str(e)}") from e
        
    def _save_config(self, config: Optional[AppConfig] = None):
        """Save the current configuration to file."""

        config = config or self.config
            
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(
                    config.model_dump(),
                    f,
                    indent=2,
                    ensure_ascii=False
                )
            logger.debug("Configuration successfully saved.")
        except FileNotFoundError as e:
            raise FileSystemError(f"Configuration directory does not exist: {self.path.parent}") from e
        except IOError as e:
            raise FileSystemError(f"Failed to write configuration file: {str(e)}") from e
        except Exception as e:
            raise ConfigurationError(f"Failed to save configuration: {str(e)}") from e
    
    @log_call
    def get_account_config(self) -> dict:
        """Retrieve account configuration as a dictionary."""
        try:
            return self.config.account.model_dump()
        except Exception as e:
            raise ConfigurationError(f"Failed to retrieve account configuration: {str(e)}") from e

    @log_call
    def set_config(self, key_path: str, value: Any, persist: bool = True):
        """Set a configuration value using dot-separated key path."""
        
        try:
            keys = key_path.split(".")
            obj = self.config

            for key in keys[:-1]:
                if not hasattr(obj, key):
                    raise MissingConfigError(f"Configuration path '{key_path}' is invalid: '{key}' not found")
                obj = getattr(obj, key)

            if not hasattr(obj, keys[-1]):
                raise MissingConfigError(f"Configuration key '{keys[-1]}' does not exist in path '{key_path}'")
            
            setattr(obj, keys[-1], value)

            if persist:
                self._save_config()
            
            logger.info(f"Config key '{key_path}' updated and saved.")
        
        except KernelError:
            raise
        except Exception as e:
            raise ConfigurationError(f"Failed to set configuration key '{key_path}': {str(e)}") from e

    @log_call
    def reset_to_defaults(self):
        """Reset configuration to default values."""
        
        try:
            logger.warning("Resetting configuration to default values.")
            self.config = AppConfig()
            self._save_config()
            logger.info("Configuration reset to default values.")
        except KernelError:
            raise
        except Exception as e:
            raise ConfigurationError(f"Failed to reset configuration to defaults: {str(e)}") from e

    @log_call
    def backup_config(self) -> Path:
        """Create a backup of the current configuration file."""
        
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = self.path.with_name(f"config_backup_{timestamp}.json")

            backup_path.parent.mkdir(parents=True, exist_ok=True)
            with open(backup_path, "w", encoding="utf-8") as f:
                json.dump(self.config.model_dump(), f, indent=2)

            logger.info(f"Configuration backup created at {backup_path}")
            return backup_path
        
        except FileNotFoundError as e:
            raise FileSystemError(f"Cannot create backup: directory not found {backup_path.parent}") from e
        except IOError as e:
            raise FileSystemError(f"Failed to write backup file: {str(e)}") from e
        except Exception as e:
            raise ConfigurationError(f"Failed to backup configuration: {str(e)}") from e
