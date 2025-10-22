"""Configuration manager for persistent settings stored as JSON."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from pydantic import BaseModel, Field, ValidationError
from .log_manager import get_logger, log_call

logger = get_logger(__name__)

CONFIG_DIR = Path.home() / ".kernel"
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

class AppConfig(BaseModel):
    """Pydantic model for overall application configuration."""

    version: str = "0.1.0"
    account: AccountConfig = Field(default_factory=AccountConfig)
    features: FeaturesConfig = Field(default_factory=FeaturesConfig)
    ui: UIConfig = Field(default_factory=UIConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

class ConfigManager:
    """Manages persistent application configuration."""

    def __init__(self, config_path: Optional[Path] = None):
        self.path = config_path or CONFIG_PATH
        self.config = self._load_or_create_config()
        logger.info(f"Configuration loaded from {self.path}")

    def _load_or_create_config(self) -> AppConfig:
        """Load configuration from file or create default if not present."""
        
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
        
        except (json.JSONDecodeError, ValidationError) as e:
            logger.error(f"Failed to load config file: {e}")
            logger.warning("Creating backup and resetting to default configuration.")

            backup_path = self.path.with_suffix(".backup.json")
            self.path.rename(backup_path)
            logger.info(f"Backup created at {backup_path}")

            config = AppConfig()
            self._save_config(config)
            return config
        
    def _save_config(self, config: Optional[AppConfig] = None):
        """Save the current configuration to file."""
        
        config = config or self.config
        
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(
                config.model_dump(),
                f,
                indent=2,
                ensure_ascii=False
            )
        logger.debug("Configuration successfully saved.")

    @log_call
    def get_config(self, key_path: str, default: Any = None) -> Any:
        """Get a configuration value using dot-separated key path."""
        
        keys = key_path.split(".")
        value = self.config.model_dump()

        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                logger.debug(f"Config key '{key_path}' not found, returning default: {default}")
                return default
            
            if value is None:
                return default

        return value

    @log_call
    def set_config(self, key_path: str, value: Any, persist: bool = True):
        """Set a configuration value using dot-separated key path."""
        
        keys = key_path.split(".")
        obj = self.config

        for key in keys:
            obj = getattr(obj, key)

        setattr(obj, keys[-1], value)

        if persist:
            self._save_config()
        
        logger.info(f"Config key '{key_path}' updated and saved.")

    @log_call
    def reset_to_defaults(self):
        """Reset configuration to default values."""
        
        logger.warning("Resetting configuration to default values.")
        self.config = AppConfig()
        self._save_config()
        logger.info("Configuration reset to default values.")

    @log_call
    def backup_config(self) -> Path:
        """Create a backup of the current configuration file."""
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.path.with_name(f"config_backup_{timestamp}.json")

        with open(backup_path, "w", encoding="utf-8") as f:
            json.dump(self.config.model_dump(), f, indent=2)

        logger.info(f"Configuration backup created at {backup_path}")

        return backup_path
