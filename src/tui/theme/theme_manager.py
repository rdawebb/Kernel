from textual.reactive import reactive
from textual.css.query import NoMatches
from textual.app import App
from typing import Optional


class ThemeManager:
    """Manages dynamic appearance settings across the Tui Mail application."""

    THEMES = {
        "dark": {
            "background": "#1e1e1e",
            "foreground": "#ffffff",
            "accent": "#569cd6",
        },
        "light": {
            "background": "#ffffff",
            "foreground": "#1e1e1e",
            "accent": "#007acc",
        },
        "solarized": {
            "background": "#002b36",
            "foreground": "#93a1a1",
            "accent": "#b58900",
        },
    }

    LAYOUTS = {
        "compact": {
            "padding": "0 1",
            "margin": "0",
        },
        "comfortable": {
            "padding": "1 2",
            "margin": "0 1",
        },
    }

    current_theme: reactive[str] = reactive("dark")
    layout_density: reactive[str] = reactive("comfortable")

    def __init__(self, app: Optional[App] = None):
        self.app = app

    def apply_theme(self, theme_name: str) -> None:
        """Apply a theme across the app."""
        if theme_name not in self.THEMES:
            return
        self.current_theme = theme_name
        theme = self.THEMES[theme_name]

        if self.app:
            self.app.styles.background = theme["background"]
            self.app.styles.color = theme["foreground"]
            try:
                self.app.set_variable("accent", theme["accent"])
            except Exception:
                pass
            self.app.refresh(layout=True)

    def apply_layout(self, layout_name: str) -> None:
        """Apply compact or comfortable density globally."""
        if layout_name not in self.LAYOUTS:
            return
        self.layout_density = layout_name

        layout = self.LAYOUTS[layout_name]
        if self.app:
            try:
                self.app.styles.padding = layout["padding"]
                self.app.styles.margin = layout["margin"]
                self.app.refresh(layout=True)
            except NoMatches:
                pass
