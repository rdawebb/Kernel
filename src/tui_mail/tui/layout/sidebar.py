from textual.widgets import ListView, ListItem, Label
from textual.message import Message
from textual.containers import Vertical

class Sidebar(Vertical):
    class FolderSelected(Message):
        def __init__(self, folder: str) -> None:
            self.folder = folder
            super().__init__()

    DEFAULT_CSS = """
    Sidebar {
        width: 24;
        background: $boost;
        border-right: solid $accent;
    }
    """

    def compose(self):
        folders = ["Inbox", "Sent", "Drafts", "Trash"]
        yield Label("📁 Folders", classes="title")
        self.list = ListView(*[ListItem(Label(f)) for f in folders])
        yield self.list

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        folder = event.item.label.plain
        self.post_message(self.FolderSelected(folder))
