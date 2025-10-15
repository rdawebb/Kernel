from textual.containers import VerticalScroll
from textual.widgets import Static
from textual import events, message
from data.mock_data import MOCK_EMAILS

class MessageSelected(message.Message):
    """Custom message for message selection."""
    def __init__(self, message_data):
        super().__init__()
        self.message_data = message_data

class MessageList(VerticalScroll):
    """Displays messages for the selected folder."""

    def __init__(self):
        super().__init__(id="message-list")
        self.folder_name = "Inbox"
        self.messages = []

    async def on_mount(self):
        await self.load_folder("Inbox")

    async def load_folder(self, folder_name: str):
        """Replace message list with contents of selected folder."""
        self.folder_name = folder_name
        self.clear()
        self.messages = MOCK_EMAILS.get(folder_name, [])
        if not self.messages:
            await self.mount(Static(f"No messages in {folder_name}", classes="empty-folder"))
            return
        
        for mail in self.messages:
            preview = f"[b]{mail['from']}[/b]  •  {mail['subject']}  •  {mail['date']}"
            await self.mount(Static(preview, classes="message-preview"))

    async def on_click(self, event: events.Click):
        widgets = self.query(".message-preview")
        for i, widget in enumerate(widgets):
            if widget == event.widget:
                selected_message = self.messages[i]
                await self.emit(MessageSelected(selected_message))
                break
