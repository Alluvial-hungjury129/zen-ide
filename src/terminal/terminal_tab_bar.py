"""Terminal Tab Bar mixin — tab bar UI and management logic for TerminalStack."""

import os

from gi.repository import Gtk

from constants import (
    TERMINAL_TAB_BAR_MARGIN_BOTTOM,
)


class TerminalTabBarMixin:
    """Mixin: tab bar construction and tab management for TerminalStack (tab mode only)."""

    # ── Tab bar (tab mode only) ───────────────────────────────────────

    def _build_tab_bar(self):
        """Create header row and tab bar for tab mode (matches AI chat layout)."""
        from terminal.terminal_header import TerminalHeader

        hdr = TerminalHeader(include_close=False)
        hdr.add_btn.set_tooltip_text("New terminal tab")

        # Wire up signal handlers
        hdr.header_btn.connect("clicked", self._on_header_click)
        hdr.add_btn.connect("clicked", lambda b: self._on_add_request())
        hdr.clear_btn.connect("clicked", lambda b: self.clear())
        hdr.maximize_btn.connect("clicked", self._on_stack_maximize_clicked)

        # Expose widgets for external access
        self._terminal_header = hdr
        self._header_box = hdr.box
        self._header_btn = hdr.header_btn
        self._stack_add_btn = hdr.add_btn
        self._stack_clear_btn = hdr.clear_btn
        self._stack_maximize_btn = hdr.maximize_btn

        self.append(hdr.box)

        # Tab bar row: [◀] [scrollable tabs] [▶]
        self._tab_bar_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self._tab_bar_row.set_margin_start(8)
        self._tab_bar_row.set_margin_end(8)
        self._tab_bar_row.set_margin_bottom(TERMINAL_TAB_BAR_MARGIN_BOTTOM)
        self._tab_bar_row.set_visible(False)

        self._scroll_left_btn = Gtk.Button.new_from_icon_name("pan-start-symbolic")
        self._scroll_left_btn.add_css_class("flat")
        self._scroll_left_btn.add_css_class("tab-scroll-btn")
        self._scroll_left_btn.connect("clicked", lambda _b: self._scroll_tab_bar(-1))
        self._tab_bar_row.append(self._scroll_left_btn)

        self._tab_bar_scroll = Gtk.ScrolledWindow()
        self._tab_bar_scroll.set_policy(Gtk.PolicyType.EXTERNAL, Gtk.PolicyType.NEVER)
        self._tab_bar_scroll.set_propagate_natural_width(False)
        self._tab_bar_scroll.set_hexpand(True)

        self._tab_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self._tab_bar_scroll.set_child(self._tab_bar)
        self._tab_bar_row.append(self._tab_bar_scroll)

        self._scroll_right_btn = Gtk.Button.new_from_icon_name("pan-end-symbolic")
        self._scroll_right_btn.add_css_class("flat")
        self._scroll_right_btn.add_css_class("tab-scroll-btn")
        self._scroll_right_btn.connect("clicked", lambda _b: self._scroll_tab_bar(1))
        self._tab_bar_row.append(self._scroll_right_btn)

        self.append(self._tab_bar_row)

    def _add_tab_button(self, index, title):
        """Add a tab button for a terminal at *index*."""
        from terminal.terminal_tab_button import TerminalTabButton

        btn = TerminalTabButton(
            index=index,
            title=title,
            on_select=self._switch_to_tab,
            on_close=self._close_tab,
            show_close=len(self._terminals) > 1,
        )
        self._tab_buttons.append(btn)
        self._tab_bar.append(btn)

    def _rebuild_tab_indices(self):
        """Re-index tab buttons after a removal."""
        for i, btn in enumerate(self._tab_buttons):
            btn.index = i

    def _switch_to_tab(self, index):
        """Switch the visible terminal in tab mode."""
        if index < 0 or index >= len(self._terminals):
            return
        self._active_idx = index
        self._content_stack.set_visible_child_name(f"term_{id(self._terminals[index])}")
        self._update_tab_selection()
        self._scroll_tab_into_view(index)
        self._update_header_title()
        # Focus the terminal
        self._terminals[index].grab_focus()

    def _close_tab(self, index):
        """Close a terminal tab."""
        if index < 0 or index >= len(self._terminals):
            return
        self._remove_terminal(self._terminals[index])

    def _update_tab_selection(self):
        """Highlight only the active tab."""
        for i, btn in enumerate(self._tab_buttons):
            btn.set_selected(i == self._active_idx)

    def _update_tab_close_buttons(self):
        """Show close buttons only when there are multiple tabs."""
        show = len(self._tab_buttons) > 1
        for btn in self._tab_buttons:
            btn.set_show_close(show)

    def _scroll_tab_bar(self, direction: int) -> None:
        """Scroll the tab bar left (-1) or right (+1) by one tab width."""
        hadj = self._tab_bar_scroll.get_hadjustment()
        if not hadj:
            return
        step = 120
        if self._tab_buttons:
            step = max(self._tab_buttons[0].get_width(), 60)
        new_val = hadj.get_value() + direction * step
        new_val = max(0, min(new_val, hadj.get_upper() - hadj.get_page_size()))
        hadj.set_value(new_val)

    def _scroll_tab_into_view(self, index: int) -> None:
        """Ensure the tab button at *index* is visible in the scroll area."""
        if index < 0 or index >= len(self._tab_buttons):
            return
        btn = self._tab_buttons[index]
        hadj = self._tab_bar_scroll.get_hadjustment()
        if not hadj:
            return
        offset = 0
        for i in range(index):
            offset += self._tab_buttons[i].get_width() + 4
        btn_w = btn.get_width()
        cur = hadj.get_value()
        page = hadj.get_page_size()
        if offset < cur:
            hadj.set_value(offset)
        elif offset + btn_w > cur + page:
            hadj.set_value(offset + btn_w - page)

    def _update_tab_bar_visibility(self) -> None:
        """Show the tab bar row only when there are multiple tabs."""
        self._tab_bar_row.set_visible(len(self._terminals) > 1)

    def _update_header_title(self):
        """Update the header label to show the active terminal's folder name."""
        if not self._vertical_mode and hasattr(self, "_header_btn"):
            self._header_btn.set_label("Terminal")

    def _update_active_tab_title(self):
        """Update the active tab button's title to match its terminal's cwd."""
        if 0 <= self._active_idx < len(self._tab_buttons):
            t = self._active
            if t:
                self._tab_buttons[self._active_idx].set_title(os.path.basename(t.get_cwd()))
