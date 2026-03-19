"""Theme picker dialog - standalone popup for selecting IDE themes with live preview."""

from gi.repository import Gdk, GLib, Gtk, Pango

from popups.nvim_popup import NvimPopup
from themes import get_theme, set_theme
from themes.theme_definitions import get_theme_metadata

_PREVIEW_DEBOUNCE_MS = 60


class ThemePickerDialog(NvimPopup):
    """Theme picker with search bar and live preview."""

    def __init__(self, parent, apply_theme_callback):
        self._apply_theme = apply_theme_callback
        current_theme = get_theme()
        self._original_theme = current_theme.name
        self._select_original_on_next_populate = True
        is_dark = current_theme.is_dark

        self._all_items = [
            {"label": display_name, "value": name}
            for name, display_name, theme_is_dark in get_theme_metadata()
            if theme_is_dark == is_dark
        ]

        self._filtered_items = list(self._all_items)
        self._in_preview = False
        self._preview_timeout_id = 0
        super().__init__(parent, title="Theme", width=500)

    def _create_content(self):
        self._search_entry = self._create_search_entry("Search themes...")
        self._search_entry.connect("search-changed", self._on_search_changed)
        self._content_box.append(self._search_entry)

        row_height = 42
        max_visible = 10
        self._scrolled, self._listbox = self._create_scrolled_listbox(
            min_height=min(len(self._filtered_items), max_visible) * row_height,
            max_height=max_visible * row_height,
        )
        self._listbox.connect("row-activated", self._on_row_activated)
        self._listbox.connect("row-selected", self._on_row_selected)
        self._content_box.append(self._scrolled)

        self._populate_list()

        hint_label = Gtk.Label(label="Type to filter • j/k or ↑↓ to navigate • Enter to select • Esc to cancel")
        hint_label.add_css_class("nvim-popup-hint")
        hint_label.set_halign(Gtk.Align.CENTER)
        hint_label.set_margin_top(2)
        self._content_box.append(hint_label)

    def _populate_list(self):
        while True:
            row = self._listbox.get_row_at_index(0)
            if row is None:
                break
            self._listbox.remove(row)

        for item in self._filtered_items:
            row = Gtk.ListBoxRow()
            row._item = item
            row.add_css_class("nvim-popup-list-item")

            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
            box.set_margin_start(2)
            box.set_margin_end(2)
            box.set_margin_top(4)
            box.set_margin_bottom(4)

            label = Gtk.Label(label=item["label"])
            label.set_halign(Gtk.Align.START)
            label.add_css_class("nvim-popup-list-item-text")
            label.set_ellipsize(Pango.EllipsizeMode.END)
            label.set_hexpand(True)
            box.append(label)

            row.set_child(box)
            self._listbox.append(row)

        if self._filtered_items:
            selected_idx = 0
            if self._select_original_on_next_populate:
                for idx, item in enumerate(self._filtered_items):
                    if item["value"] == self._original_theme:
                        selected_idx = idx
                        break
                self._select_original_on_next_populate = False
            row = self._listbox.get_row_at_index(selected_idx)
            if row:
                self._listbox.select_row(row)
                GLib.idle_add(self._scroll_row_into_view, row)

    def _scroll_row_into_view(self, row):
        adjustment = self._scrolled.get_vadjustment()
        allocation = row.get_allocation()
        row_top = allocation.y
        row_bottom = allocation.y + allocation.height
        view_top = adjustment.get_value()
        page_size = adjustment.get_page_size()
        view_bottom = view_top + page_size

        if row_top < view_top:
            adjustment.set_value(row_top)
        elif row_bottom > view_bottom:
            max_value = max(adjustment.get_lower(), adjustment.get_upper() - page_size)
            adjustment.set_value(min(row_bottom - page_size, max_value))
        return GLib.SOURCE_REMOVE

    def _on_search_changed(self, entry):
        query = entry.get_text().strip().lower()
        if query:
            self._filtered_items = [item for item in self._all_items if query in item["label"].lower()]
        else:
            self._filtered_items = list(self._all_items)
        self._populate_list()

    def _on_key_pressed(self, controller, keyval, keycode, state):
        meta = state & Gdk.ModifierType.META_MASK

        if keyval == Gdk.KEY_Escape:
            self._revert_and_close()
            return True
        elif keyval == Gdk.KEY_Return:
            self._confirm_current()
            return True
        elif keyval == Gdk.KEY_Down:
            self._move_selection(1)
            return True
        elif keyval == Gdk.KEY_Up:
            self._move_selection(-1)
            return True
        elif keyval == Gdk.KEY_BackSpace and meta:
            self._search_entry.set_text("")
            return True

        # j/k navigation only when not typing in search entry
        if not self._has_text_entry_focus():
            if keyval == Gdk.KEY_j:
                self._move_selection(1)
                return True
            elif keyval == Gdk.KEY_k:
                self._move_selection(-1)
                return True
        return False

    def _move_selection(self, delta):
        row = self._listbox.get_selected_row()
        if not row:
            if self._filtered_items:
                self._listbox.select_row(self._listbox.get_row_at_index(0))
            return
        idx = row.get_index() + delta
        idx = max(0, min(idx, len(self._filtered_items) - 1))
        target = self._listbox.get_row_at_index(idx)
        if target:
            self._listbox.select_row(target)
            target.grab_focus()

    def _on_row_selected(self, listbox, row):
        if row and hasattr(row, "_item"):
            if self._preview_timeout_id:
                GLib.source_remove(self._preview_timeout_id)
            item = row._item
            self._preview_timeout_id = GLib.timeout_add(_PREVIEW_DEBOUNCE_MS, self._apply_preview, item["value"])

    def _apply_preview(self, theme_name):
        self._preview_timeout_id = 0
        self._in_preview = True
        set_theme(theme_name, persist=False)
        self._apply_theme()
        GLib.idle_add(self._end_preview)
        return GLib.SOURCE_REMOVE

    def _end_preview(self):
        self._in_preview = False
        self._search_entry.grab_focus()
        return GLib.SOURCE_REMOVE

    def _on_focus_leave(self, controller):
        if self._in_preview:
            return
        super()._on_focus_leave(controller)

    def _on_row_activated(self, listbox, row):
        if hasattr(row, "_item"):
            self._confirm_item(row._item)

    def _confirm_current(self):
        row = self._listbox.get_selected_row()
        if row and hasattr(row, "_item"):
            self._confirm_item(row._item)

    def _confirm_item(self, item):
        set_theme(item["value"], persist=True)
        self._apply_theme()
        self._result = item
        self.close()

    def _revert_and_close(self):
        set_theme(self._original_theme, persist=False)
        self._apply_theme()
        self.close()

    def close(self):
        if self._preview_timeout_id:
            GLib.source_remove(self._preview_timeout_id)
            self._preview_timeout_id = 0
        if not self._closing and self._result is None:
            set_theme(self._original_theme, persist=False)
            self._apply_theme()
        super().close()

    def present(self):
        super().present()
        self._search_entry.grab_focus()


def show_theme_picker(parent, apply_theme_callback):
    """Open theme picker with search and live preview."""
    dialog = ThemePickerDialog(parent, apply_theme_callback)
    dialog.present()
