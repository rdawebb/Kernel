from textual.containers import Horizontal
from textual.widgets import Tabs
from quiet_mail.tui.widgets.modals.animated_modal import AnimatedModal
class SettingsModal(AnimatedModal):
    def compose(self):
        yield Tabs("General", "Appearance", "Email", "Backup")
        yield Horizontal(id="settings-content")
