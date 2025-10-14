from textual import on
from textual.containers import Vertical, Horizontal
from textual.widgets import Label, Select, Switch, Button, Static
from textual.app import ComposeResult
from tui_mail.tui.theme.theme_manager import ThemeManager
from tui_mail.core.config_manager import ConfigManager


class AppearanceSettingsPanel(Vertical):
    """Panel for theme and layout appearance settings."""

    def __init__(self, app=None) -> None:
        super().__init__()
        self.config = ConfigManager()
        self.app_ref = app or self.app

    DEFAULT_CSS = """
    AppearanceSettingsPanel {
        padding: 2;
        overflow: auto;
    }

    AppearanceSettingsPanel > Horizontal {
        margin-bottom: 1;
        align: center middle;
    }

    AppearanceSettingsPanel Label {
        width: 40%;
    }

    AppearanceSettingsPanel Select {
        width: 60%;
    }
    """

    THEMES = [
        ("Light", "light"),
        ("Dark", "dark"),
        ("Solarized", "solarized"),
    ]

    LAYOUTS = [
        ("Compact", "compact"),
        ("Comfortable", "comfortable"),
    ]

    def compose(self) -> ComposeResult:
        yield Label("Appearance Settings", id="panel-title")

        with Horizontal():
            yield Label("Theme:")
            yield Select(options=self.THEMES, id="theme-select")

        with Horizontal():
            yield Label("Layout Density:")
            yield Select(options=self.LAYOUTS, id="layout-select")

        with Horizontal():
            yield Label("Show Avatars:")
            yield Switch(value=True, id="avatars-toggle")

        yield Static("")
        yield Button("Apply Theme", id="apply-theme")

    def get_settings(self) -> dict:
        """Return appearance settings as a dictionary."""
        return {
            "theme": self.query_one("#theme-select", Select).value,
            "layout": self.query_one("#layout-select", Select).value,
            "avatars": self.query_one("#avatars-toggle", Switch).value,
        }
    
    @on (Button.Pressed, "#apply-theme")
    def save_appearance_settings(self, _: Button.Pressed) -> None:
        """Apply and save appearance settings."""
        new_settings = self.get_settings()
        self.config.update_settings("appearance", new_settings)

        theme_manager = ThemeManager(app=self.app_ref)
        theme_manager.apply_theme(new_settings.get("theme", "dark"))
        theme_manager.apply_layout(new_settings.get("layout", "comfortable"))
