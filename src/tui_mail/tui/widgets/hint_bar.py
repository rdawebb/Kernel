from textual.widgets import Static

class HintBar(Static):
    """Displays keyboard shortcuts or contextual hints."""

    def __init__(self):
        super().__init__("Press [b]S[/b] for Settings · [b]Q[/b] to Quit", id="hint-bar")
