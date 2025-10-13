from textual.widget import Widget
from textual.app import ComposeResult
from textual.reactive import reactive
from textual import events
from tui_mail.tui.widgets.modals.animated_modal import AnimatedModal


class ModalManager(Widget):
    """Manages modals: open, close, stacking, and background dimming."""

    DEFAULT_CSS = """
    ModalManager {
        layer: overlay;
        align: center middle;
        background: rgba(0, 0, 0, 0.4);
        opacity: 0;
        transition: opacity 200ms ease-in-out;
    }

    ModalManager.-visible {
        opacity: 1;
    }
    """

    visible = reactive(False)
    _stack: list[AnimatedModal] = []

    def compose(self) -> ComposeResult:
        # Modals will be mounted dynamically here
        yield

    async def push(self, modal: AnimatedModal) -> None:
        """Show a modal, dimming background and pausing input below."""
        if not self.visible:
            self.add_class("-visible")
            self.visible = True

        self._stack.append(modal)
        await self.mount(modal)
        modal.focus()

    async def pop(self) -> None:
        """Close the topmost modal."""
        if not self._stack:
            return

        modal = self._stack.pop()
        await modal.close()

        if not self._stack:
            self.remove_class("-visible")
            self.visible = False

    async def replace(self, modal: AnimatedModal) -> None:
        """Replace the current modal (e.g. switching between Settings panels)."""
        if self._stack:
            await self._stack[-1].close()
            self._stack.pop()
        await self.push(modal)

    async def on_key(self, event: events.Key) -> None:
        """Press Escape to close the topmost modal."""
        if event.key == "escape" and self._stack:
            await self.pop()

    async def close_all(self) -> None:
        """Close all modals immediately."""
        while self._stack:
            await self.pop()
