from textual.containers import Vertical
from textual.widgets import Static, ListView, ListItem

FOLDERS = ["Inbox", "Sent", "Drafts", "Trash"]

class FolderList(Vertical):
    """Displays mail folders in a vertical list."""

    def compose(self):
        yield Static("Folders", classes="section-title")
        folder_items = [ListItem(Static(f)) for f in FOLDERS]
        yield ListView(*folder_items, id="folder-list")

    async def on_list_view_selected(self, event: ListView.Selected):
        """Broadcast selected folder name."""
        folder = event.item.query_one(Static).renderable
        await self.emit(self.FolderSelected(folder))

    class FolderSelected(Static.Message):
        """Custom message for folder selection."""
        def __init__(self, folder_name: str) -> None:
            super().__init__()
            self.folder_name = folder_name
