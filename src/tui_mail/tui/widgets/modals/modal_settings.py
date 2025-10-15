from textual.containers import Container, Horizontal
from textual.widgets import Button, Static
from textual.reactive import reactive

from .modal_base import Modal
from .settings_panels.general_settings import GeneralSettingsPanel
from .settings_panels.appearance_settings import AppearanceSettingsPanel
from .settings_panels.email_settings import EmailSettingsPanel
from .settings_panels.backup_settings import BackupSettingsPanel


class SettingsModal(Modal):
    """Settings modal with tabbed panels."""

    current_panel = reactive("general")

    def __init__(self):
        super().__init__(title="Settings", width=80, height=35)
        self.panels = {
            "general": GeneralSettingsPanel(),
            "appearance": AppearanceSettingsPanel(),
            "email": EmailSettingsPanel(),
            "backup": BackupSettingsPanel(),
        }

    def compose(self):
        yield Container(
            id="modal-backdrop",
            classes="modal-backdrop",
        )
        yield Horizontal(
            id="settings-window",
            classes="modal-window",
            children=[
                self._build_nav(),
                Container(id="settings-panel-container"),
            ],
        )

    def _build_nav(self) -> Container:
        """Sidebar navigation inside settings modal."""
        nav_items = [
            ("general", "General"),
            ("appearance", "Appearance"),
            ("email", "Email"),
            ("backup", "Backup"),
        ]
        return Container(
            id="settings-nav",
            classes="settings-nav",
            children=[
                Static("⚙️  Settings", classes="settings-title"),
                *[Button(label, id=key, classes="nav-btn") for key, label in nav_items],
                Button("Close", id="close-settings", variant="error"),
            ],
        )

    async def on_mount(self):
        await self._load_panel("general")

    async def _load_panel(self, panel_name: str):
        """Swap current panel inside the modal."""
        container = self.query_one("#settings-panel-container")
        container.remove_children()
        panel = self.panels.get(panel_name)
        if panel:
            await container.mount(panel)
            self.current_panel = panel_name

    async def on_button_pressed(self, event: Button.Pressed):
        button_id = event.button.id
        if button_id == "close-settings":
            self.hide()
        elif button_id in self.panels:
            await self._load_panel(button_id)
