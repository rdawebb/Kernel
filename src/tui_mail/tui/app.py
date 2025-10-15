from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.binding import Binding
from textual.widgets import Static
from textual import events
from data.mock_data import MOCK_MESSAGES
from .layout.sidebar import Sidebar
from .layout.folder_list import FolderList
from .layout.message_list import MessageList, MessageSelected
from .widgets.message_viewer import MessageViewer
from .widgets.status_bar import StatusBar
from .widgets.hint_bar import HintBar
from .widgets.modals.modal_manager import ModalManager
from .widgets.modals.settings_modal import SettingsModal
from .theme.theme_manager import ThemeManager
from tui_mail.core.config_manager import ConfigManager

class KernelApp(App):
    CSS_PATH = "styles.tcss"
    TITLE = "TuiMail - Minimal Email Client"

    BINDINGS = [
        Binding("ctrl+s", "open_settings", "Settings"),
        Binding("ctrl+i", "open_info", "Info"),
        Binding("ctrl+q", "quit", "Quit"),
    ]

    def __init__(self):
        super().__init__()
        self.config = None
        self.theme_manager = None
        self.modal_manager = None
        self.settings_modal = SettingsModal()
        self.sidebar = Sidebar()
        self.folder_list = FolderList()
        self.message_list = MessageList()
        self.message_viewer = MessageViewer()

    def compose(self) -> ComposeResult:
        self.modal_manager = ModalManager(self)
        yield Horizontal(self.sidebar, self.folder_list, self.message_list, self.message_viewer)
        yield StatusBar()
        yield HintBar()

    async def action_open_settings(self):
        await self.modal_manager.push("settings")

    async def action_open_info(self):
        await self.modal_manager.push("info")

    # --- Event Handlers ---
    async def on_mount(self) -> None:
        # Initialize Theme Manager and apply saved theme
        self.config = ConfigManager()
        self.theme_manager = ThemeManager(app=self)
        appearance = self.config.section("appearance")
        self.theme_manager.apply_theme(appearance.get("theme", "dark"))
        self.theme_manager.apply_layout(appearance.get("layout", "comfortable"))
        await self.settings_modal.hide()

    async def action_open_settings(self):
        await self.show_modal()

    async def show_modal(self):
        self.settings_modal.show()

    async def on_button_pressed(self, event):
        button_id = event.button.id
        if button_id == "settings-btn":
            await self.action_open_settings()
        elif button_id == "quit-btn":
            await self.action_quit()
        
    async def _on_key(self, event: events.Key):
        if event.key == "escape" and self.settings_modal.visible:
            self.settings_modal.hide()
            event.stop()

    async def on_folder_selected(self, event: FolderList.FolderSelected) -> None:
        await self.folder_list.load_folder(event.folder_name)
        await self.message_viewer.show_message(None)  # Clear message viewer

    async def message_selected(self, event: MessageSelected) -> None:
        await self.message_viewer.show_message(event.message_data)

if __name__ == "__main__":
    KernelApp().run()
