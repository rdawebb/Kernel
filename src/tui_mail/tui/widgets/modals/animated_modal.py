from textual.widget import Widget
from textual.containers import Vertical
from textual import events
from textual.reactive import reactive

class AnimatedModal(Widget):
    """A custom modal base with fade-in/out animation and background dimming."""

    DEFAULT_CSS = """
    AnimatedModal {
        layer: overlay;
        align: center middle;
        background: rgba(0, 0, 0, 0.6);
    }

    AnimatedModal > Vertical {
        background: $panel;
        border: solid $accent;
        width: 60%;
        height: auto;
        min-height: 10;
        padding: 2;
        animation: fade_in 150ms ease-in;
    }

    @keyframes fade_in {
        0% { opacity: 0; transform: scale(0.9); }
        100% { opacity: 1; transform: scale(1); }
    }
    """

    visible = reactive(False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.container = Vertical(classes="modal-container")

    def compose(self):
        yield self.container

    def on_mount(self):
        # Dim background + grab focus
        self.visible = True
        self.focus()

    async def close(self):
        self.visible = False
        await self.remove()

    async def on_key(self, event: events.Key) -> None:
        """Press Escape to close."""
        if event.key == "escape":
            await self.close()
