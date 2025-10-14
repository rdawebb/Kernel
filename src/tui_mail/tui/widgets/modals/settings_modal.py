from textual import on
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, Label, Static
from textual.app import ComposeResult
from .animated_modal import AnimatedModal
from .settings_panels.general_panel import GeneralSettingsPanel
from .settings_panels.appearance_panel import AppearanceSettingsPanel



class SettingsModal(AnimatedModal):
    """Settings modal with multiple tabbed panels."""

    DEFAULT_CSS = """
    SettingsModal {
        width: 80%;
        height: 70%;
        border: solid $accent 1px;
        border-radius: 2;
        background: $surface;
        padding: 2;
        shadow: 0 0 20px rgba(0, 0, 0, 0.4);
        transition: opacity 250ms ease-in-out, scale 250ms ease-in-out;
    }

    SettingsModal:focus {
        outline: none;
    }

    #settings-header {
        dock: top;
        height: 3;
        align-horizontal: center;
        content-align: center middle;
        text-style: bold;
        border-bottom: solid $accent 1px;
    }

    #settings-tabs {
        dock: left;
        width: 25%;
        border-right: solid $accent 1px;
        padding: 1;
    }

    #settings-content {
        dock: right;
        width: 75%;
        padding: 2;
        overflow: auto;
    }

    #settings-footer {
        dock: bottom;
        height: 3;
        border-top: solid $accent 1px;
        align-horizontal: right;
        padding: 0 2;
    }

    Button.tab {
        width: 100%;
        margin-bottom: 1;
    }
    """

    def compose(self) -> ComposeResult:
        yield Label("Settings", id="settings-header")
        with Horizontal():
            with Vertical(id="settings-tabs"):
                yield Button("General", id="tab-general", classes="tab")
                yield Button("Appearance", id="tab-appearance", classes="tab")
                yield Button("Email", id="tab-email", classes="tab")
                yield Button("Backup", id="tab-backup", classes="tab")
            yield Container(Static("Select a tab from the left."), id="settings-content")
        with Horizontal(id="settings-footer"):
            yield Button("Close", id="close-btn")

    @on(Button.Pressed, "#close-btn")
    async def on_close_pressed(self, _: Button.Pressed) -> None:
        await self.close()

    @on(Button.Pressed)
    async def on_tab_pressed(self, event: Button.Pressed) -> None:
        tab_id = event.button.id
        if tab_id and tab_id.startswith("tab-"):
            content = self.query_one("#settings-content", Container)
            content.remove_children()

            if tab_id == "tab-general":
                content.mount(GeneralSettingsPanel())
            elif tab_id == "tab-appearance":
                content.mount(AppearanceSettingsPanel())
            else:
                panel_name = tab_id.split("-")[1].capitalize()
                content.mount(Static(f"{panel_name} Settings Panel"))
                