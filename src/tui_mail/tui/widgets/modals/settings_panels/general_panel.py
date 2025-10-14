from textual.containers import Vertical, Horizontal
from textual.widgets import Label, Input, Switch, Static, Button
from textual.app import ComposeResult
from tui_mail.core.config_manager import ConfigManager


class GeneralSettingsPanel(Vertical):
    """Panel for general app settings."""

    def __init__(self) -> None:
        super().__init__()
        self.config = ConfigManager()

    DEFAULT_CSS = """
    GeneralSettingsPanel {
        padding: 2;
        overflow: auto;
    }

    GeneralSettingsPanel > Horizontal {
        margin-bottom: 1;
        align: center middle;
    }

    GeneralSettingsPanel Label {
        width: 40%;
    }

    GeneralSettingsPanel Input {
        width: 60%;
    }

    GeneralSettingsPanel Switch {
        width: 10;
    }
    """

    def compose(self) -> ComposeResult:
        yield Label("General Settings", id="panel-title")

        with Horizontal():
            yield Label("Default Inbox Refresh (min):")
            yield Input(placeholder="e.g. 10", id="refresh-interval")

        with Horizontal():
            yield Label("Enable Notifications:")
            yield Switch(value=True, id="notifications-toggle")

        with Horizontal():
            yield Label("Auto-Save Drafts:")
            yield Switch(value=True, id="auto-save-toggle")

        yield Static("")
        yield Button("Save Changes", id="save-general")

    def get_settings(self) -> dict:
        """Return settings as a dictionary."""
        return {
            "refresh_interval": self.query_one("#refresh-interval", Input).value,
            "notifications": self.query_one("#notifications-toggle", Switch).value,
            "auto_save": self.query_one("#auto-save-toggle", Switch).value,
        }
