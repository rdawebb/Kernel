from textual.containers import Vertical, Horizontal
from textual.widgets import Input, TextArea, Button, Static
from textual.message import Message
from .animated_modal import AnimatedModal


class ReplySent(Message):
    """Emitted when a reply is 'sent'."""
    def __init__(self, to_addr: str, subject: str, body: str):
        super().__init__()
        self.to_addr = to_addr
        self.subject = subject
        self.body = body


class ReplyModal(AnimatedModal):
    """Modal for composing and sending replies."""

    def __init__(self):
        super().__init__(id="reply-modal")
        self.to_input = Input(placeholder="To")
        self.subject_input = Input(placeholder="Subject")
        self.body_input = TextArea(placeholder="Type your reply here...")
        self.send_button = Button("Send", variant="primary")
        self.cancel_button = Button("Cancel", variant="secondary")

    def compose(self):
        yield Vertical(
            Static("✉️ Compose Reply", classes="modal-title"),
            self.to_input,
            self.subject_input,
            self.body_input,
            Horizontal(self.send_button, self.cancel_button, classes="modal-actions"),
        )

    async def on_button_pressed(self, event: Button.Pressed):
        if event.button == self.cancel_button:
            await self.dismiss()
        elif event.button == self.send_button:
            await self.emit(
                ReplySent(
                    to_addr=self.to_input.value.strip(),
                    subject=self.subject_input.value.strip(),
                    body=self.body_input.value.strip(),
                )
            )
            await self.dismiss()

    async def on_mount(self):
        await self.to_input.focus()
