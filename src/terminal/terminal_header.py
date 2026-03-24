"""Shared terminal header bar builder — used by both TerminalView and TerminalStack."""

from icons import Icons
from shared.ui import ZenButton
from terminal.base_terminal_header import BaseTerminalHeader


class TerminalHeader(BaseTerminalHeader):
    """Standard terminal panel header bar with action buttons.

    Builds: [Terminal btn] --- [trash btn] [+ btn] [⛶ btn] [× btn?]

    Attributes exposed (in addition to BaseTerminalHeader):
        close_btn – close button (None when *include_close* is False)
    """

    def __init__(self, include_close=False):
        super().__init__(
            label="Terminal",
            tooltip="Click to switch workspace folder",
            add_tooltip="Split terminal",
        )

        self.close_btn = None
        if include_close:
            self.close_btn = ZenButton(icon=Icons.CLOSE, tooltip="Close terminal")
            self.close_btn.set_visible(False)
            self.box.append(self.close_btn)
