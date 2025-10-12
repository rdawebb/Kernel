from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.binding import Binding
from quiet_mail.tui.layout.sidebar import Sidebar
from quiet_mail.tui.layout.folder_view import FolderView
from quiet_mail.tui.layout.message_view import MessageView
from quiet_mail.tui.widgets.status_bar import StatusBar
from quiet_mail.tui.widgets.modals.modal_manager import ModalManager

class TuiMail(App):
    CSS_PATH = "styles.tcss"
    TITLE = "Minimal TUI Mail Client"

    BINDINGS = [
        Binding("ctrl+s", "open_settings", "Settings"),
        Binding("ctrl+i", "open_info", "Info"),
        Binding("ctrl+q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        self.modal_manager = ModalManager()
        yield Horizontal(
            Sidebar(),
            FolderView(),
            MessageView(),
        )
        yield StatusBar()

    async def action_open_settings(self):
        await self.modal_manager.push("settings")

    async def action_open_info(self):
        await self.modal_manager.push("info")

if __name__ == "__main__":
    TuiMail().run()
