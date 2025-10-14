from textual.widgets import DataTable
from textual.message import Message

class FolderView(DataTable):
    class MessageSelected(Message):
        def __init__(self, message_id: int) -> None:
            self.message_id = message_id
            super().__init__()

    DEFAULT_CSS = "FolderView { width: 1fr; }"

    def __init__(self):
        super().__init__()
        self.messages = []

    def on_mount(self):
        self.add_columns("From", "Subject", "Date")

    def load_messages(self, messages):
        self.clear()
        self.messages = messages
        if messages:
            self.add_rows([[m["from"], m["subject"], m["date"]] for m in messages])

    def on_data_table_row_selected(self, event):
        row_index = event.row_key
        if 0 <= row_index < len(self.messages):
            msg = self.messages[row_index]
            self.post_message(self.MessageSelected(msg["id"]))
