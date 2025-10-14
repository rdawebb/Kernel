from textual.widgets import Static

class MessageView(Static):
    DEFAULT_CSS = """
    MessageView {
        width: 2fr;
        border-left: solid $surface;
        padding: 1 2;
    }
    """

    def show_message(self, msg):
        content = (
            f"[b]From:[/b] {msg['from']}\n"
            f"[b]Date:[/b] {msg['date']}\n\n"
            f"[b]Time:[/b] {msg['time']}\n\n"
            f"[b]Subject:[/b] {msg['subject']}\n\n"
            f"{msg['body']}"
        )
        self.update(content)

    def show_blank(self):
        self.update("[dim]No message selected[/dim]")
