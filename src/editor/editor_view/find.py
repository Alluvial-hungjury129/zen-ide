"""Find & replace bar for EditorView."""

from gi.repository import GLib, Gtk, GtkSource

from fonts import get_font_settings, subscribe_font_change
from icons import Icons
from shared.ui import ZenButton
from shared.ui.zen_entry import ZenEntry, ZenSearchEntry
from themes import get_theme, subscribe_theme_change


class EditorViewFindMixin:
    """Mixin providing find & replace bar methods for EditorView."""

    def _create_find_bar(self):
        """Create the find & replace bar."""
        self.find_bar = Gtk.SearchBar()
        self.find_bar.set_show_close_button(True)

        container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)

        # Find row
        find_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)

        self.find_entry = ZenSearchEntry(placeholder="Find...")
        self.find_entry.set_hexpand(True)
        self.find_entry.connect("search-changed", self._on_find_changed)
        self.find_entry.connect("activate", self._on_find_next)

        # Add Escape key handler to close find bar
        find_key_controller = Gtk.EventControllerKey()
        find_key_controller.connect("key-pressed", self._on_find_entry_key)
        self.find_entry.add_controller(find_key_controller)

        find_row.append(self.find_entry)

        self.find_count_label = Gtk.Label(label="")
        self.find_count_label.add_css_class("dim-label")
        find_row.append(self.find_count_label)

        prev_btn = ZenButton(icon=Icons.ARROW_UP, tooltip="Previous (Shift+Enter)")
        prev_btn.connect("clicked", lambda b: self._on_find_prev())
        find_row.append(prev_btn)

        next_btn = ZenButton(icon=Icons.ARROW_DOWN, tooltip="Next (Enter)")
        next_btn.connect("clicked", lambda b: self._on_find_next())
        find_row.append(next_btn)

        # Toggle replace row button
        self._replace_toggle = ZenButton(icon=Icons.CHEVRON_DOWN, tooltip="Toggle Replace", toggle=True)
        self._replace_toggle.connect("toggled", self._on_replace_toggled)
        find_row.append(self._replace_toggle)

        container.append(find_row)

        # Replace row (hidden by default)
        self._replace_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self._replace_row.set_visible(False)

        self.replace_entry = ZenEntry(placeholder="Replace...")
        self.replace_entry.set_hexpand(True)
        replace_key_controller = Gtk.EventControllerKey()
        replace_key_controller.connect("key-pressed", self._on_replace_entry_key)
        self.replace_entry.add_controller(replace_key_controller)
        self._replace_row.append(self.replace_entry)

        replace_btn = ZenButton(label="Replace")
        replace_btn.connect("clicked", lambda b: self._on_replace())
        self._replace_row.append(replace_btn)

        replace_all_btn = ZenButton(label="All")
        replace_all_btn.connect("clicked", lambda b: self._on_replace_all())
        self._replace_row.append(replace_all_btn)

        container.append(self._replace_row)

        self.find_bar.set_child(container)
        self.find_bar.connect_entry(self.find_entry)
        self.prepend(self.find_bar)

        # Apply editor font to labels that aren't covered by ZenSearchEntry/ZenEntry
        self._find_bar_font_widgets = [
            self.find_count_label,
            replace_btn,
            replace_all_btn,
        ]
        self._find_bar_css = Gtk.CssProvider()
        for w in self._find_bar_font_widgets:
            w.get_style_context().add_provider(self._find_bar_css, Gtk.STYLE_PROVIDER_PRIORITY_USER + 1)
        self._apply_find_bar_font()
        subscribe_font_change(lambda comp, _s: self._apply_find_bar_font() if comp == "editor" else None)
        subscribe_theme_change(lambda _t: self._apply_find_bar_font())

    def _apply_find_bar_font(self):
        """Refresh editor font CSS on find-bar labels/buttons."""
        theme = get_theme()
        settings = get_font_settings("editor")
        css = f'label {{ font-family: "{settings["family"]}"; font-size: {settings["size"]}pt; color: {theme.fg_dim}; }}'
        self._find_bar_css.load_from_data(css.encode())

    def show_find_bar(self, replace: bool = False):
        """Show the find bar."""
        if not self._find_bar_created:
            self._create_find_bar()
            self._find_bar_created = True
        self.find_bar.set_search_mode(True)
        self.find_entry.grab_focus()
        # Select all text so re-pressing Cmd+F highlights existing query
        pos = len(self.find_entry.get_text())
        if pos > 0:
            self.find_entry.select_region(0, pos)
        if replace:
            self._replace_toggle.set_active(True)

    def _on_replace_toggled(self, button):
        """Toggle replace row visibility."""
        self._replace_row.set_visible(button.get_active())

    def _on_find_entry_key(self, controller, keyval, keycode, state):
        """Handle key press in find entry - Escape closes the find bar."""
        from gi.repository import Gdk

        if keyval == Gdk.KEY_Escape:
            self.find_bar.set_search_mode(False)
            # Return focus to editor
            tab = self._get_current_tab()
            if tab:
                tab.view.grab_focus()
            return True

        # Cmd+Backspace: clear the entire search entry
        meta = Gdk.ModifierType.META_MASK
        if keyval == Gdk.KEY_BackSpace and (state & meta):
            self.find_entry.set_text("")
            return True

        return False

    def _on_replace_entry_key(self, controller, keyval, keycode, state):
        """Handle key press in replace entry - Cmd+Backspace clears text."""
        from gi.repository import Gdk

        meta = Gdk.ModifierType.META_MASK
        if keyval == Gdk.KEY_BackSpace and (state & meta):
            self.replace_entry.set_text("")
            return True
        return False

    def _on_find_changed(self, entry):
        """Handle find text change."""
        text = entry.get_text()
        self._ensure_search_context(text)
        if text:
            self._find_text(text, forward=True)
        else:
            self.find_count_label.set_label("")

    def _on_find_next(self, *args):
        """Find next occurrence."""
        text = self.find_entry.get_text()
        if text:
            self._find_text(text, forward=True)

    def _on_find_prev(self, *args):
        """Find previous occurrence."""
        text = self.find_entry.get_text()
        if text:
            self._find_text(text, forward=False)

    def _ensure_search_context(self, text: str):
        """Create or update the search context for the current buffer."""
        tab = self._get_current_tab()
        if not tab:
            self._search_context = None
            return

        if self._search_settings is None:
            self._search_settings = GtkSource.SearchSettings()
            self._search_settings.set_case_sensitive(False)
            self._search_settings.set_wrap_around(True)

        self._search_settings.set_search_text(text if text else None)

        # Recreate context if buffer changed
        if self._search_context is None or self._search_context.get_buffer() != tab.buffer:
            self._search_context = GtkSource.SearchContext(buffer=tab.buffer, settings=self._search_settings)

    def _update_find_count(self):
        """Update the match count label."""
        if not self._search_context:
            self.find_count_label.set_label("")
            return

        count = self._search_context.get_occurrences_count()
        if count < 0:
            # Still computing
            self.find_count_label.set_label("...")
        elif count == 0:
            self.find_count_label.set_label("No results")
        else:
            # Find current match position
            tab = self._get_current_tab()
            if tab and tab.buffer.get_has_selection():
                sel_start, sel_end = tab.buffer.get_selection_bounds()
                pos = self._search_context.get_occurrence_position(sel_start, sel_end)
                if pos > 0:
                    self.find_count_label.set_label(f"{pos} of {count}")
                    return
            self.find_count_label.set_label(f"{count} results")

    def _find_text(self, text: str, forward: bool = True):
        """Find text in the current editor."""
        tab = self._get_current_tab()
        if not tab:
            return

        buffer = tab.buffer

        self._ensure_search_context(text)
        if not self._search_context:
            return

        # Get current cursor position
        cursor = buffer.get_insert()
        cursor_iter = buffer.get_iter_at_mark(cursor)

        if forward:
            # Start search from selection end to avoid finding same match
            if buffer.get_has_selection():
                _, cursor_iter = buffer.get_selection_bounds()
            found, start, end, wrapped = self._search_context.forward(cursor_iter)
        else:
            # Start search from selection start
            if buffer.get_has_selection():
                cursor_iter, _ = buffer.get_selection_bounds()
            found, start, end, wrapped = self._search_context.backward(cursor_iter)

        if found:
            buffer.select_range(start, end)
            tab.view.scroll_to_iter(start, 0.2, False, 0.0, 0.5)

        # Update count after a small delay to let GtkSource compute occurrences
        GLib.timeout_add(50, lambda: self._update_find_count() or False)

    def _on_replace(self):
        """Replace current match."""
        if not self._search_context:
            return

        tab = self._get_current_tab()
        if not tab:
            return

        buffer = tab.buffer
        replace_text = self.replace_entry.get_text()

        if buffer.get_has_selection():
            start, end = buffer.get_selection_bounds()
            try:
                self._search_context.replace(start, end, replace_text, -1)
            except GLib.Error:
                pass
            # Find next
            self._on_find_next()

    def _on_replace_all(self):
        """Replace all matches."""
        if not self._search_context:
            return

        replace_text = self.replace_entry.get_text()
        try:
            count = self._search_context.replace_all(replace_text, -1)
            self.find_count_label.set_label(f"Replaced {count}")
        except GLib.Error:
            pass
