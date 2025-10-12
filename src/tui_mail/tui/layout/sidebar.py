from textual.widgets import ListView, ListItem, Label
from textual.containers import Vertical

class Sidebar(Vertical):
    DEFAULT_CSS = """
    Sidebar {
        width: 24;
        background: $boost;
        border-right: solid $primary;
    }
    """

    def compose(self):
        folders = ["Inbox", "Sent", "Drafts", "Archive", "Trash"]
        yield Label("Folders", classes="title")
        yield ListView(*[ListItem(Label(f)) for f in folders])
