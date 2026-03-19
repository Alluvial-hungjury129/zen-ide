"""Terminal Tab Button — individual tab for the terminal tab bar."""

from constants import TAB_BUTTON_FONT_SIZE
from shared.ui.tab_button import TabButton


class TerminalTabButton(TabButton):
    """Tab button for terminal tab bar with terminal font styling."""

    def __init__(self, index, title, on_select, on_close, show_close=True):
        self._font_family = self._load_font_family()
        super().__init__(index, title, on_select, on_close, show_close)

    @property
    def index(self):
        return self.tab_id

    @index.setter
    def index(self, value):
        self.tab_id = value

    def _load_font_family(self):
        """Load terminal font family."""
        from fonts import get_font_settings

        font_settings = get_font_settings("terminal")
        return font_settings["family"]

    def _get_font_css(self):
        return f"font-family: '{self._font_family}'; font-size: {TAB_BUTTON_FONT_SIZE}pt;"

    def apply_font_settings(self):
        """Re-read terminal font settings and re-apply styling."""
        self._font_family = self._load_font_family()
        self._apply_theme()
