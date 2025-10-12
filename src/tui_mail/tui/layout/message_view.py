from textual.widgets import Static

class MessageView(Static):
    DEFAULT_CSS = "MessageView { width: 2fr; border-left: solid $surface; }"

    def on_mount(self):
        self.update("[b]No message selected[/b]")
