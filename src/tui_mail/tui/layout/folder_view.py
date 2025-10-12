from textual.widgets import DataTable

class FolderView(DataTable):
    DEFAULT_CSS = "FolderView { width: 1fr; }"

    def on_mount(self):
        self.add_columns("From", "Subject", "Date")
        # Placeholder messages
        self.add_rows([
            ["Alice", "Meeting update", "Today"],
            ["Bob", "Invoice attached", "Yesterday"],
        ])
