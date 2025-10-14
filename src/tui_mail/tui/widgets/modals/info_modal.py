from textual import on
from textual.widgets import Button, Label, Static
from textual.containers import Vertical
from textual.app import ComposeResult
from .animated_modal import AnimatedModal


class InfoModal(AnimatedModal):
    """Simple modal showing app information / about screen."""

    DEFAULT_CSS = """
    InfoModal {
        width: 60%;
        height: auto;
        border: solid $accent 1px;
        border-radius: 2;
        background: $surface;
        padding: 2;
        shadow: 0 0 15px rgba(0, 0, 0, 0.4);
        transition: opacity 250ms ease-in-out, scale 250ms ease-in-out;
    }

    InfoModal:focus {
        outline: none;
    }

    #info-content {
        align: center middle;
        text-align: center;
        padding: 2;
    }

    #info-footer {
        align-horizontal: center;
        padding-top: 1;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="info-content"):
            yield Label("TuiMail - Minimal Email Client", id="app-name")
            yield Static("Version 0.1.0\nBuilt with Python + Textual\n© 2025", id="app-info")
            with Vertical(id="info-footer"):
                yield Button("Close", id="close-btn")

    @on(Button.Pressed, "#close-btn")
    async def on_close_pressed(self, _: Button.Pressed) -> None:
        await self.close()
