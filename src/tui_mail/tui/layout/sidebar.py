from textual.containers import Vertical
from textual.widgets import Button, Static


class Sidebar(Vertical):
    """App sidebar with navigation and actions."""

    def compose(self):
        yield Static("📫 Kernel", classes="sidebar-title")
        yield Button("Inbox", id="inbox-btn")
        yield Button("Sent", id="sent-btn")
        yield Button("Drafts", id="drafts-btn")
        yield Button("Trash", id="trash-btn")
        yield Button("⚙ Settings", id="settings-btn")
        yield Button("Quit", id="quit-btn", variant="error")
