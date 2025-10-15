from textual.containers import Container
from textual.widget import Widget
from textual.reactive import reactive
from textual import events

class Modal(Container):
    """Base modal window with backdrop and escape-close support."""

    visible = reactive(False)

    def __init__(self, title: str = "Modal", width: int = 60, height: int = 20):
        super().__init__()
        self.title = title
        self.width = width
        self.height = height
        self._content: Widget | None = None

    def compose(self):
        yield Container(
            id="modal-backdrop",
            classes="modal-backdrop",
        )
        yield Container(
            id="modal-window",
            classes="modal-window",
            children=[
                Container(id="modal-title", classes="modal-title", content=self.title),
                Container(id="modal-content", classes="modal-content"),
            ],
        )

    def on_mount(self):
        self.set_class(False, "visible")
        self.set_class(True, "hidden")

    def show(self):
        """Display modal and optionally replace its content."""
        self.visible = True
        backdrop = self.query_one("#modal-backdrop")
        window = self.query_one("#modal-window")
        backdrop.styles.opacity = 1
        window.add_class("visible")
        self.display = True
        
    def hide(self):
        """Hide modal and clear its content."""
        self.visible = False
        backdrop = self.query_one("#modal-backdrop")
        window = self.query_one("#modal-window")
        backdrop.styles.opacity = 0
        window.remove_class("visible")
        self.display = False

    async def on_key(self, event: events.Key) -> None:
        """Press Escape to close modal."""
        if event.key == "escape" and self.visible:
            self.hide()
            event.stop()
