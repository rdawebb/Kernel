"""Model manager for handling model installation, selection, and tracking."""

import subprocess
import sys

from .config_manager import ConfigManager
from .error_handling import (
    ConfigurationError,
    KernelError,
    ValidationError,
)
from .log_manager import get_logger, log_call

logger = get_logger(__name__)


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
        self.config_manager = ConfigManager()
        self.load_config()

    @log_call
    def load_config(self):
        """Load configuration from config file"""
        self.current_model = getattr(self.config_manager.config, "default_summariser", "sumy")

    @log_call
    def reload_config(self):
        """Reload configuration and model status"""
        self.load_config()

    @staticmethod
    @log_call
    def install(package):
        """Install a package using pip."""
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])
            logger.info(f"Successfully installed {package}")
        except subprocess.CalledProcessError as e:
            raise ValidationError(f"Failed to install package {package}: {str(e)}") from e
        except Exception as e:
            raise ValidationError(f"Unexpected error installing {package}: {str(e)}") from e

    @staticmethod
    @log_call
    def uninstall(package):
        """Uninstall a package using pip."""
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "uninstall", "-y", package])
            logger.info(f"Successfully uninstalled {package}")
        except subprocess.CalledProcessError as e:
            raise ValidationError(f"Failed to uninstall package {package}: {str(e)}") from e
        except Exception as e:
            raise ValidationError(f"Unexpected error uninstalling {package}: {str(e)}") from e

    def is_installed(self, model_name):
        """Check if a model is marked as installed."""
        return self.installed_models.get(model_name, False)

    def set_installed(self, model_name, installed=True):
        """Mark a model as installed or not."""
        if model_name in self.installed_models:
            self.installed_models[model_name] = installed
            logger.debug(f"Model {model_name} marked as {'installed' if installed else 'not installed'}")

    @log_call
    def choose_model(self, choice):
        """Select and configure a model by choice number."""
        try:
            selected_model = self.MODEL_MAP.get(choice)

            if not selected_model:
                raise ValidationError(f"Invalid model choice: {choice}. Valid choices are 1-7.")

            if selected_model == self.current_model:
                logger.info(f"Model {selected_model} is already selected.")
                return selected_model

            self.current_model = selected_model
            self.config_manager.set_config("default_summariser", selected_model)

            if not self.is_installed(selected_model):
                logger.info(f"Installing model: {selected_model}...")
                self.install(selected_model)
                self.set_installed(selected_model, True)

            self._cleanup_unused_models(selected_model)
            logger.info(f"Selected summarization model: {selected_model}")

            return selected_model
        
        except KernelError:
            raise
        except Exception as e:
            raise ConfigurationError(f"Failed to choose model {choice}: {str(e)}") from e

    @log_call
    def _cleanup_unused_models(self, keep_model):
        """Uninstall unused models to save space."""
        try:
            for model_name in self.installed_models:
                if model_name != keep_model and self.is_installed(model_name):
                    logger.info(f"Uninstalling unused model: {model_name}")
                    self.uninstall(model_name)
                    self.set_installed(model_name, False)
        except KernelError:
            raise
        except Exception as e:
            raise ConfigurationError(f"Failed to cleanup unused models: {str(e)}") from e

    def get_current_model(self):
        """Get the currently selected model."""
        return self.current_model

    def get_available_models(self):
        """Get list of available models."""
        return self.MODEL_MAP.copy()

    def get_installed_models(self):
        """Get list of installed models."""
        return [model for model, installed in self.installed_models.items() if installed]
