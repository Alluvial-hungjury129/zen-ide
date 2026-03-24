"""Header bar for AI Terminal — shows the active CLI name with a picker trigger."""

from gi.repository import Gtk, Pango

from terminal.base_terminal_header import BaseTerminalHeader


class AITerminalHeader(BaseTerminalHeader):
    """Header for the AI Terminal panel.

    Builds: [<CLI name>] [spinner] [title] --- [trash btn] [+ btn] [⛶ btn]

    Attributes exposed (in addition to BaseTerminalHeader):
        spinner_widget – Gtk.Spinner for activity indication
        title_label    – Gtk.Label for conversation title
    """

    def __init__(self, label: str = "AI"):
        super().__init__(
            label=label,
            tooltip="Click to switch AI CLI",
            add_tooltip="New AI chat",
        )

        # Extra widgets between header button and spacer (inserted right-to-left)
        self.title_label = Gtk.Label(label="")
        self.title_label.set_margin_start(6)
        self.title_label.set_ellipsize(Pango.EllipsizeMode.END)
        self.title_label.set_visible(False)
        self.title_label.add_css_class("dim-label")
        self._insert_after_header(self.title_label)

        self.spinner_widget = Gtk.Spinner()
        self.spinner_widget.set_size_request(16, 16)
        self.spinner_widget.set_margin_start(6)
        self.spinner_widget.set_visible(False)
        self._insert_after_header(self.spinner_widget)

    def set_label(self, label: str) -> None:
        """Update the CLI name shown in the header button."""
        child = self.header_btn.get_child()
        if child and hasattr(child, "set_text"):
            child.set_text(label)
