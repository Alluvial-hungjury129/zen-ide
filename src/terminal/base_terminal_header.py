"""Base terminal header bar — shared logic for TerminalHeader and AITerminalHeader."""

from gi.repository import Gtk, Pango

from constants import (
    TERMINAL_HEADER_MARGIN_BOTTOM,
    TERMINAL_HEADER_MARGIN_TOP,
)
from icons import IconsManager
from shared.ui import ZenButton


class BaseTerminalHeader:
    """Common terminal header layout and font handling.

    Subclasses should call ``super().__init__()`` then append any extra
    widgets between ``self.header_btn`` and the right-side buttons by
    inserting into ``self.box`` before the spacer (use ``_insert_after_header``).

    Attributes exposed:
        box          – the Gtk.Box container
        header_btn   – clickable label button on the left
        clear_btn    – trash / clear button
        add_btn      – plus / new button
        maximize_btn – maximize button
    """

    def __init__(self, label: str, tooltip: str, add_tooltip: str):
        self.box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.box.set_margin_start(8)
        self.box.set_margin_end(8)
        self.box.set_margin_top(TERMINAL_HEADER_MARGIN_TOP)
        self.box.set_margin_bottom(TERMINAL_HEADER_MARGIN_BOTTOM)

        self.header_btn = ZenButton(label=label, tooltip=tooltip)
        self.header_btn.set_halign(Gtk.Align.START)
        self.header_btn.add_css_class("terminal-header-btn")
        self.box.append(self.header_btn)

        # Subclasses insert extra widgets here via _insert_after_header
        self._spacer = Gtk.Box()
        self._spacer.set_hexpand(True)
        self.box.append(self._spacer)

        self.clear_btn = ZenButton(icon=IconsManager.TRASH, tooltip="Clear")
        self.box.append(self.clear_btn)

        self.add_btn = ZenButton(icon=IconsManager.PLUS, tooltip=add_tooltip)
        self.box.append(self.add_btn)

        self.maximize_btn = ZenButton(icon=IconsManager.MAXIMIZE, tooltip="Maximize")
        self.box.append(self.maximize_btn)

        self.apply_header_font()

    def _insert_after_header(self, widget):
        """Insert a widget between the header button and the spacer."""
        self.box.insert_child_after(widget, self.header_btn)

    def apply_header_font(self):
        """Apply terminal font to the header button label."""
        from fonts import get_font_settings

        font_settings = get_font_settings("terminal")
        family = font_settings["family"]

        label = self.header_btn.get_child()
        if label and hasattr(label, "set_attributes"):
            attr_list = Pango.AttrList()
            attr_list.insert(Pango.attr_family_new(family))
            attr_list.insert(Pango.attr_underline_new(Pango.Underline.NONE))
            label.set_attributes(attr_list)
