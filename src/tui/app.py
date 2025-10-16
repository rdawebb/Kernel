from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.binding import Binding
from textual import events
from .layout.sidebar import Sidebar
from .layout.folder_list import FolderList
from .layout.message_list import MessageList, MessageSelected
from .message_actions import MessageAction
from .widgets.search_bar import SearchBar, SearchUpdated
from .widgets.message_viewer import MessageViewer
from .widgets.status_bar import StatusBar
from .widgets.hint_bar import HintBar
from .widgets.modals.modal_manager import ModalManager
from .widgets.modals.settings_modal import SettingsModal
from .widgets.modals.reply_modal import ReplyModal, ReplySent
from .theme.theme_manager import ThemeManager
from core.config_manager import ConfigManager
from data.mock_data import MOCK_BODIES

class KernelApp(App):
    CSS_PATH = "styles.tcss"
    TITLE = "Kernel - Minimal Email Client"

    BINDINGS = [
        Binding("s", "open_settings", "Settings"),
        Binding("i", "open_info", "Info"),
        Binding("r", "reply", "Reply"),
        Binding("a", "archive", "Archive"),
        Binding("f", "flag", "Flag"),
        Binding("m", "mark_read", "Mark Read"),
        Binding("d", "delete", "Delete"),
        Binding("h", "open_help", "Help"),
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
        self.search_bar = SearchBar()
        self.reply_modal = ReplyModal()
        self.selected_message = None

    def compose(self) -> ComposeResult:
        self.modal_manager = ModalManager(self)
        yield Horizontal(self.sidebar,
                         self.folder_list, 
                         Vertical(self.search_bar, self.message_list, self.message_viewer))
        yield StatusBar()
        yield HintBar()
        yield self.settings_modal
        yield self.reply_modal

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

    async def on_search_updated(self, event: SearchUpdated) -> None:
        await self.message_list.set_query(event.query)

    async def on_folder_selected(self, event: FolderList.FolderSelected) -> None:
        await self.folder_list.load_folder(event.folder_name)
        self.selected_message = None
        await self.message_viewer.show_message(None)  # Clear message viewer

    async def message_selected(self, event: MessageSelected) -> None:
        self.selected_message = event.message_data
        await self.message_viewer.show_message(event.message_data)

    async def on_message_action(self, event: MessageAction):
        await self.handle_message_action(event.action_name)

    async def handle_message_action(self, action_name: str):
        if not self.selected_message:
            return
        subject = self.selected_message["subject"]
        
        match action_name:
            case "reply":
                await self.show_reply_modal()
            case "archive":
                await self.message_list.archicve_message(self.selected_message)
                await self.message_viewer.show_message(None)
                self.log(f"Archived message: {subject}")
            case "flag":
                self.log(f"Flagged message: {subject}")
            case "mark":
                await self.message_list.mark_as_read(self.selected_message)
                self.log(f"Marked as read: {subject}")
            case "delete":
                await self.message_list.delete_message(self.selected_message)
                await self.message_viewer.show_message(None)
                self.log(f"Deleted message: {subject}")

    async def show_reply_modal(self):
        if not self.selected_message:
            return
        message = self.selected_message
        self.reply_modal.to_input.value = message["from"]
        self.reply_modal.subject_input.value = f"Re: {message['subject']}"
        self.reply_modal.body_input.value = f"\n\n--- On {message['date'], message['from']} wrote: ---\n{MOCK_BODIES.get(message['subject'], '')}"
        await self.reply_modal.show()

    async def on_reply_sent(self, event: ReplySent):
        self.log(f"Reply sent to {event.to_addr} - '{event.subject}'")

    async def action_reply(self):
        await self.handle_message_action("reply")

    async def action_archive(self):
        await self.handle_message_action("archive")

    async def action_flag(self):
        await self.handle_message_action("flag")

    async def action_mark_read(self):
        await self.handle_message_action("mark")

    async def action_delete(self):
        await self.handle_message_action("delete")

if __name__ == "__main__":
    KernelApp().run()
