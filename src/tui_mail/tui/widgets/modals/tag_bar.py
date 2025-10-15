from textual.containers import Horizontal
from textual.widgets import Button
from textual.message import Message


class TagFilter(Message):
    """Emitted when a tag filter is toggled."""
    def __init__(self, tag: str):
        super().__init__()
        self.tag = tag


class TagBar(Horizontal):
    """Quick tag buttons for filtering."""
    TAGS = ["All", "Important", "Work", "Personal", "Drafts"]

    def __init__(self):
        super().__init__(id="tag-bar")

    def compose(self):
        for tag in self.TAGS:
            yield Button(tag, id=f"tag-{tag.lower()}", variant="default")

    async def on_button_pressed(self, event: Button.Pressed):
        tag_name = event.button.label
        await self.emit(TagFilter(tag_name))
