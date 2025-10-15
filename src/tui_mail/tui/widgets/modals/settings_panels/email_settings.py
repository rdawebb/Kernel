from textual.containers import Vertical
from textual.widgets import Static, Input, Button


class EmailSettingsPanel(Vertical):
    """Email account and sync settings."""

    def compose(self):
        yield Static("Email Settings", classes="panel-title")
        yield Input(placeholder="IMAP server")
        yield Input(placeholder="SMTP server")
        yield Input(placeholder="Sync frequency (minutes)")
        yield Button("Save Email Settings", id="save-email")
