from textual.containers import Vertical
from textual.widgets import Static, Input, Button


class BackupSettingsPanel(Vertical):
    """App backup and storage options."""

    def compose(self):
        yield Static("Backup & Data", classes="panel-title")
        yield Input(placeholder="Backup folder path")
        yield Input(placeholder="Auto-backup interval (days)")
        yield Button("Save Backup Settings", id="save-backup")
