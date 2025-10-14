from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.binding import Binding
from data.mock_data import MOCK_MESSAGES
from .layout.sidebar import Sidebar
from .layout.folder_view import FolderView
from .layout.message_view import MessageView
from .widgets.status_bar import StatusBar
from .widgets.modals.modal_manager import ModalManager
from .theme.theme_manager import ThemeManager
from tui_mail.core.config_manager import ConfigManager

class TuiMailApp(App):
    CSS_PATH = "styles.tcss"
    TITLE = "TuiMail - Minimal Email Client"

    BINDINGS = [
        Binding("ctrl+s", "open_settings", "Settings"),
        Binding("ctrl+i", "open_info", "Info"),
        Binding("ctrl+q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        self.modal_manager = ModalManager(self)
        self.sidebar = Sidebar()
        self.folder_view = FolderView()
        self.message_view = MessageView()
        yield Horizontal(self.sidebar, self.folder_view, self.message_view)
        yield StatusBar()

    async def action_open_settings(self):
        await self.modal_manager.push("settings")

    async def action_open_info(self):
        await self.modal_manager.push("info")

    # --- Event Handlers ---
    def on_mount(self) -> None:
        # Initialize Theme Manager and apply saved theme
        self.config = ConfigManager()
        self.theme_manager = ThemeManager(app=self)
        appearance = self.config.section("appearance")
        self.theme_manager.apply_theme(appearance.get("theme", "dark"))
        self.theme_manager.apply_layout(appearance.get("layout", "comfortable"))

    def on_sidebar_folder_selected(self, message: Sidebar.FolderSelected):
        folder_name = message.folder
        messages = MOCK_MESSAGES.get(folder_name, [])
        self.folder_view.load_messages(messages)
        self.message_view.show_blank()

    def on_folder_view_message_selected(self, message: FolderView.MessageSelected):
        for folder_msgs in MOCK_MESSAGES.values():
            for m in folder_msgs:
                if m["id"] == message.message_id:
                    self.message_view.show_message(m)
                    return

if __name__ == "__main__":
    TuiMailApp().run()
