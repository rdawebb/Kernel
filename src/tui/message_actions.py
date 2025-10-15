from textual.containers import Horizontal
from textual.widgets import Button
from textual.message import Message

class MessageAction(Message):
    """Emitted when a message action is triggered."""
    def __init__(self, action_name: str):
        super().__init__()
        self.action_name = action_name


class MessageActions(Horizontal):
    """Action bar for common mail operations."""
    def __init__(self):
        super().__init__(id="message-actions")

    def compose(self):
        yield Button("Reply", id="reply", variant="primary")
        yield Button("Archive", id="archive", variant="default")
        yield Button("Delete", id="delete", variant="error")
        yield Button("Mark Read", id="mark", variant="secondary")

    async def on_button_pressed(self, event: Button.Pressed):
        action_id = event.button.id
        await self.emit(MessageAction(action_id))
