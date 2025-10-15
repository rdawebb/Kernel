import json
import threading
from pathlib import Path
from typing import Any, Dict


class ConfigManager:
    """Handles persistent settings configuration stored as JSON."""

    _lock = threading.Lock()

    DEFAULT_CONFIG = {
        "general": {
            "refresh_interval": "10",
            "notifications": True,
            "auto_save": True,
        },
        "appearance": {
            "theme": "dark",
            "layout": "comfortable",
            "avatars": True,
        },
    }

    def __init__(self, config_path: str | Path = "config/settings.json"):
        self.config_path = Path(config_path)
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self._data = self.DEFAULT_CONFIG.copy()
        self.load()

    def load(self) -> Dict[str, Any]:
        """Load settings from file or create defaults."""
        with self._lock:
            if self.config_path.exists():
                try:
                    with open(self.config_path, "r", encoding="utf-8") as f:
                        file_data = json.load(f)
                        self._data.update(file_data)
                except (json.JSONDecodeError, OSError):
                    # fallback to defaults
                    pass
            else:
                self.save()
        return self._data

    def save(self) -> None:
        """Save current settings to file."""
        with self._lock:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=4)

    def get(self, section: str, key: str, default: Any = None) -> Any:
        """Retrieve a setting value."""
        return self._data.get(section, {}).get(key, default)

    def set(self, section: str, key: str, value: Any) -> None:
        """Set a setting value and save immediately."""
        if section not in self._data:
            self._data[section] = {}
        self._data[section][key] = value
        self.save()

    def section(self, section: str) -> Dict[str, Any]:
        """Return an entire section (e.g. 'general')."""
        return self._data.get(section, {})

    def update_section(self, section: str, values: Dict[str, Any]) -> None:
        """Update a section with a dict of values."""
        self._data[section] = values
        self.save()
