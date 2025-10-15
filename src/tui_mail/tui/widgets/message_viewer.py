from textual.containers import Vertical, VerticalScroll
from textual.widgets import Static
from tui.message_actions import MessageActions

MOCK_BODIES = {
    "Project Update": """Hi team,

Quick update on the project — milestones are on track.
We’ll review next steps on Monday.

Best,
Alice""",
    "Lunch tomorrow?": """Hey!

Are we still on for lunch at 12:30?
Let me know if that works.

- Bob""",
    "Your receipt": """Thank you for your purchase.
Order #34291 has been processed successfully.""",
    "Re: Meeting notes": """Thanks for sending over the notes. I’ve attached the
slides for the next meeting.""",
    "(draft) Proposal": """Draft proposal content goes here...""",
}

class MessageViewer(Vertical):
    """Displays full content of the selected message."""

    def __init__(self):
        super().__init__(id="message-viewer")
        self.body_container = VerticalScroll()
        self.actions = MessageActions()

    async def on_mount(self):
        await self.mount(self.body_container)
        await self.mount(self.actions)

    async def show_message(self, message):
        """Render the full selected message."""
        self.body_container.clear()
        if not message:
            await self.body_container.mount(Static("No message selected.", classes="empty-view"))
            return

        body = MOCK_BODIES.get(message["subject"], "(No content)")
        header = (
            f"[b]From:[/b] {message['from']}\n"
            f"[b]Subject:[/b] {message['subject']}\n"
            f"[b]Date:[/b] {message['date']}\n\n"
        )
        await self.body_container.mount(Static(header + body, classes="message-body"))
