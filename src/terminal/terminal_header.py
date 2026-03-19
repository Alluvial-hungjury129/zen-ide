"""Shared terminal header bar builder — used by both TerminalView and TerminalStack."""

from gi.repository import Gtk, Pango

from constants import (
    TERMINAL_HEADER_MARGIN_BOTTOM,
    TERMINAL_HEADER_MARGIN_TOP,
)
from icons import Icons
from shared.ui import ZenButton


class TerminalHeader:
    """Standard terminal panel header bar with action buttons.

    Builds: [Terminal btn] --- [trash btn] [+ btn] [⛶ btn] [× btn?]

    Attributes exposed:
        box          – the Gtk.Box container
        header_btn   – "Terminal" label button
        add_btn      – add/split button
        clear_btn    – clear button
        maximize_btn – maximize button
        close_btn    – close button (None when *include_close* is False)
    """

    def __init__(self, include_close=False):
        self.box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.box.set_margin_start(8)
        self.box.set_margin_end(8)
        self.box.set_margin_top(TERMINAL_HEADER_MARGIN_TOP)
        self.box.set_margin_bottom(TERMINAL_HEADER_MARGIN_BOTTOM)

        # Clickable header label
        self.header_btn = ZenButton(label="Terminal", tooltip="Click to switch workspace folder")
        self.header_btn.set_halign(Gtk.Align.START)
        self.header_btn.add_css_class("terminal-header-btn")
        self.box.append(self.header_btn)

        # Spacer
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        self.box.append(spacer)

        # Clear button
        self.clear_btn = ZenButton(icon=Icons.TRASH, tooltip="Clear terminal")
        self.box.append(self.clear_btn)

        # Add button
        self.add_btn = ZenButton(icon=Icons.PLUS, tooltip="Split terminal")
        self.box.append(self.add_btn)

        # Maximize button
        self.maximize_btn = ZenButton(icon=Icons.MAXIMIZE, tooltip="Maximize")
        self.box.append(self.maximize_btn)

        # Close button (optional, hidden by default)
        self.close_btn = None
        if include_close:
            self.close_btn = ZenButton(icon=Icons.CLOSE, tooltip="Close terminal")
            self.close_btn.set_visible(False)
            self.box.append(self.close_btn)

        self.apply_header_font()

    def apply_header_font(self):
        """Apply terminal font to the header button."""
        from fonts import get_font_settings

        font_settings = get_font_settings("terminal")
        family = font_settings["family"]
        size = font_settings.get("size", 12)

        label = self.header_btn.get_child()
        if label and hasattr(label, "set_attributes"):
            attr_list = Pango.AttrList()
            attr_list.insert(Pango.attr_family_new(family))
            attr_list.insert(Pango.attr_underline_new(Pango.Underline.NONE))
            label.set_attributes(attr_list)
