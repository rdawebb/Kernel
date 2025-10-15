from textual.containers import Horizontal
from textual.widgets import Input, Button
from textual.message import Message


class SearchUpdated(Message):
    """Emitted when the search text changes."""
    def __init__(self, query: str):
        super().__init__()
        self.query = query


class SearchBar(Horizontal):
    """Search input and clear button for filtering messages."""

    def __init__(self):
        super().__init__(id="search-bar")
        self.search_input = Input(placeholder="Search mail (sender, subject, body)...", id="search-input")
        self.clear_button = Button("Clear", id="clear-search", variant="secondary")

    def compose(self):
        yield self.search_input
        yield self.clear_button

    async def on_input_changed(self, event: Input.Changed):
        await self.emit(SearchUpdated(event.value.strip()))

    async def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "clear-search":
            self.search_input.value = ""
            await self.emit(SearchUpdated(""))
