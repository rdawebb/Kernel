"""Model manager for handling model installation, selection, and tracking."""

import subprocess
import sys
from src.utils import log_manager
from src.utils.config import load_config

log_manager = log_manager.get_logger()


class ModelManager:
    """Manages model installation, selection, and tracking"""

    # Mapping of model choices to model names
    MODEL_MAP = {
        1: "sumy",
        2: "minibart",
        3: "t5",
        4: "bart",
        5: "openai",
        6: "cohere",
        7: "ollama"
    }

    def __init__(self):
        """Initialize model manager with installed models state"""
        self.installed_models = {
            "sumy": False,
            "minibart": False,
            "t5": False,
            "bart": False,
            "openai": False,
            "cohere": False,
            "ollama": False
        }
        self.current_model = None
        self.config = load_config()
        self.load_config()

    def load_config(self):
        """Load configuration from config file"""
        self.config = load_config()
        self.current_model = self.config.get("default_summariser", "sumy")

    def reload_config(self):
        """Reload configuration and model status"""
        self.load_config()

    @staticmethod
    def install(package):
        """Install a package using pip."""
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])
            log_manager.info(f"Successfully installed {package}")
        except Exception as e:
            log_manager.error(f"Error installing {package}: {e}")

    @staticmethod
    def uninstall(package):
        """Uninstall a package using pip."""
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "uninstall", "-y", package])
            log_manager.info(f"Successfully uninstalled {package}")
        except Exception as e:
            log_manager.error(f"Error uninstalling {package}: {e}")

    def is_installed(self, model_name):
        """Check if a model is marked as installed."""
        return self.installed_models.get(model_name, False)

    def set_installed(self, model_name, installed=True):
        """Mark a model as installed or not."""
        if model_name in self.installed_models:
            self.installed_models[model_name] = installed
            log_manager.debug(f"Model {model_name} marked as {'installed' if installed else 'not installed'}")

    def choose_model(self, choice):
        """Select and configure a model by choice number."""
        selected_model = self.MODEL_MAP.get(choice)

        if not selected_model:
            log_manager.error(f"Invalid model choice: {choice}. Valid choices are 1-7.")
            return None

        if selected_model == self.current_model:
            log_manager.info(f"Model {selected_model} is already selected.")
            return selected_model

        self.current_model = selected_model
        self.config["default_summariser"] = selected_model

        if not self.is_installed(selected_model):
            log_manager.info(f"Installing model: {selected_model}...")
            self.install(selected_model)
            self.set_installed(selected_model, True)

        self._cleanup_unused_models(selected_model)
        log_manager.info(f"Selected summarization model: {selected_model}")

        return selected_model

    def _cleanup_unused_models(self, keep_model):
        """Uninstall unused models to save space."""
        for model_name in self.installed_models:
            if model_name != keep_model and self.is_installed(model_name):
                log_manager.info(f"Uninstalling unused model: {model_name}")
                self.uninstall(model_name)
                self.set_installed(model_name, False)

    def get_current_model(self):
        """Get the currently selected model."""
        return self.current_model

    def get_available_models(self):
        """Get list of available models."""
        return self.MODEL_MAP.copy()

    def get_installed_models(self):
        """Get list of installed models."""
        return [model for model, installed in self.installed_models.items() if installed]
