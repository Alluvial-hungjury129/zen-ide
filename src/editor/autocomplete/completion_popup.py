"""Completion popup UI mixin for Autocomplete.

Handles NvimPopup creation, CSS styling, listbox rendering,
signature preview, click/focus dismiss, and row selection.
"""

from __future__ import annotations

from gi.repository import Gtk, GtkSource, Pango

from constants import AUTOCOMPLETE_MAX_ITEMS
from fonts import get_font_settings
from shared.settings import get_setting
from themes import get_theme


class CompletionPopupMixin:
    """Mixin providing popup UI logic for the Autocomplete class.

    Expects the host class to define:
    - self._view, self._buffer, self._tab
    - self._popup, self._listbox, self._hbox
    - self._sig_box, self._sig_sep, self._sig_buffer, self._sig_view
    - self._css_provider
    - self._completions, self._filtered, self._selected_idx
    - self._word_start_offset, self._inserting
    - self._dismiss_guard, self._dismiss_guard_timer, self._focus_suppress_idle
    - self._changed_handler, self._auto_trigger_timer
    """

    def _ensure_popup(self):
        """Lazily build the completion popup on first use.

        The NvimPopup requires a parent Gtk.Window which may not be available
        when the Autocomplete is first constructed (the editor view might not
        yet be in the widget hierarchy).
        """
        if self._popup is not None:
            return True

        parent = self._view.get_root()
        if parent is None:
            return False

        self._build_popup(parent)
        return True

    def _build_popup(self, parent):
        """Build the completion popup using NvimPopup with anchor support."""
        from popups.nvim_popup import NvimPopup

        self._popup = NvimPopup(
            parent=parent,
            width=-1,
            height=-1,
            modal=False,
            steal_focus=False,
            anchor_widget=self._view,
        )
        self._popup.add_css_class("autocomplete-popup")

        # Compact margins for autocomplete (override NvimPopup defaults)
        self._popup._content_box.set_margin_start(2)
        self._popup._content_box.set_margin_end(2)
        self._popup._content_box.set_margin_top(4)
        self._popup._content_box.set_margin_bottom(2)
        self._popup._content_box.set_spacing(0)

        theme = get_theme()
        font_family = get_font_settings("editor")["family"]
        border_radius = get_setting("popup.border_radius", 0)

        if self._css_provider is None:
            self._css_provider = Gtk.CssProvider()
            css = f"""
                .zen-autocomplete .autocomplete-row {{
                    padding: 3px 10px;
                    color: {theme.fg_color};
                    font-family: '{font_family}';
                    font-size: 12px;
                    border-radius: 0;
                    min-height: 22px;
                }}
                .zen-autocomplete row:selected .autocomplete-row,
                .zen-autocomplete .autocomplete-row.selected {{
                    background: {theme.selection_bg};
                    color: {theme.fg_color};
                }}
                .zen-autocomplete row:selected {{
                    background: {theme.selection_bg};
                    outline: 1px solid {theme.accent_color};
                    outline-offset: -1px;
                    border-radius: {border_radius}px;
                }}
                .zen-autocomplete row:focus,
                .zen-autocomplete row:focus-visible,
                .zen-autocomplete row:focus-within {{
                    outline: none;
                    border: none;
                    box-shadow: none;
                }}
                .zen-autocomplete listbox:focus,
                .zen-autocomplete listbox:focus-visible {{
                    outline: none;
                    border: none;
                    box-shadow: none;
                }}
                .zen-autocomplete .autocomplete-sig-box {{
                    padding: 4px 6px;
                }}
                .zen-autocomplete .autocomplete-sig-box textview text {{
                    background-color: {theme.panel_bg};
                    color: {theme.fg_color};
                }}
                .zen-autocomplete .autocomplete-sig-box textview.view {{
                    background-color: {theme.panel_bg};
                }}
            """
            self._css_provider.load_from_data(css.encode())
            Gtk.StyleContext.add_provider_for_display(
                self._view.get_display(), self._css_provider, Gtk.STYLE_PROVIDER_PRIORITY_USER
            )

        self._hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self._hbox.add_css_class("zen-autocomplete")
        self._hbox.set_size_request(700, 350)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_max_content_height(400)
        scrolled.set_propagate_natural_height(True)
        scrolled.set_size_request(250, -1)
        scrolled.set_vexpand(True)

        self._listbox = Gtk.ListBox()
        self._listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._listbox.set_can_focus(False)
        self._listbox.connect("row-selected", self._on_row_selected)
        self._listbox.connect("row-activated", self._on_row_activated)
        scrolled.set_child(self._listbox)

        self._sig_buffer = GtkSource.Buffer()
        lang_manager = GtkSource.LanguageManager.get_default()
        py_lang = lang_manager.get_language("python3") or lang_manager.get_language("python")
        if py_lang:
            self._sig_buffer.set_language(py_lang)
        scheme_manager = GtkSource.StyleSchemeManager.get_default()
        from editor.editor_view import _generate_style_scheme

        scheme_id = _generate_style_scheme(theme)
        scheme = scheme_manager.get_scheme(scheme_id)
        if scheme:
            self._sig_buffer.set_style_scheme(scheme)

        self._sig_view = GtkSource.View(buffer=self._sig_buffer)
        self._sig_view.set_editable(False)
        self._sig_view.set_cursor_visible(False)
        self._sig_view.set_can_focus(False)
        self._sig_view.set_monospace(True)
        self._sig_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self._sig_view.set_top_margin(2)
        self._sig_view.set_bottom_margin(2)
        self._sig_view.set_left_margin(4)
        self._sig_view.set_right_margin(4)

        sig_css = Gtk.CssProvider()
        sig_css.load_from_data(
            f"""
            textview {{ font-family: '{font_family}'; font-size: 11px; }}
        """.encode()
        )
        self._sig_view.get_style_context().add_provider(sig_css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1)

        sig_scrolled = Gtk.ScrolledWindow()
        sig_scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sig_scrolled.set_max_content_height(400)
        sig_scrolled.set_propagate_natural_height(True)
        sig_scrolled.set_min_content_width(350)
        sig_scrolled.set_hexpand(True)
        sig_scrolled.set_child(self._sig_view)

        self._sig_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self._sig_box.add_css_class("autocomplete-sig-box")
        self._sig_box.set_vexpand(True)
        self._sig_box.append(sig_scrolled)
        self._sig_box.set_visible(False)

        sep = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        self._sig_sep = sep
        sep.set_visible(False)

        scrolled.set_hexpand(False)
        self._hbox.append(scrolled)
        self._hbox.append(sep)
        self._hbox.append(self._sig_box)
        self._popup._content_box.append(self._hbox)

    def _setup_click_dismiss(self):
        """Hide popup when clicking on the editor view."""
        click = Gtk.GestureClick()
        click.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        click.connect("pressed", self._on_view_clicked)
        self._view.add_controller(click)

    def _setup_focus_dismiss(self):
        """Hide popup when the editor view loses focus (e.g. clicking terminal)."""
        focus_ctrl = Gtk.EventControllerFocus()
        focus_ctrl.connect("leave", self._on_view_focus_leave)
        self._view.add_controller(focus_ctrl)

    def _on_view_focus_leave(self, controller):
        """Dismiss autocomplete when focus leaves the editor view."""
        if self.is_visible() and not self._dismiss_guard:
            self.hide()

    def _on_view_clicked(self, gesture, n_press, x, y):
        """Dismiss autocomplete on any click in the editor."""
        if self.is_visible() and not self._dismiss_guard:
            self.hide()

    def _on_row_selected(self, listbox, row):
        """Sync _selected_idx when a row is selected (e.g., by mouse click)."""
        if row is not None:
            self._selected_idx = row.get_index()
        self._update_signature_preview()

    def _on_row_activated(self, listbox, row):
        """Insert completion when a row is activated (double-click or Enter in listbox)."""
        if row is not None:
            self._selected_idx = row.get_index()
            self._insert_selected()

    def _update_signature_preview(self):
        """Show or hide the function signature and docstring for the selected completion."""
        if not self._popup or not self._popup.get_visible():
            if self._sig_box:
                self._sig_box.set_visible(False)
            if self._sig_sep:
                self._sig_sep.set_visible(False)
            return
        if self._filtered and 0 <= self._selected_idx < len(self._filtered):
            item = self._filtered[self._selected_idx]
            sig = item.signature
            doc = item.docstring
            if sig or doc:
                text = sig or ""
                if doc:
                    doc_lines = "\n".join(f"# {line}" for line in doc.splitlines())
                    text = f"{text}\n{doc_lines}" if text else doc_lines
                self._sig_buffer.set_text(text)
                was_hidden = not self._sig_box.get_visible()
                self._sig_sep.set_visible(True)
                self._sig_box.set_visible(True)
                if was_hidden:
                    self._force_popup_resize()
                return
        was_visible = self._sig_box.get_visible()
        self._sig_box.set_visible(False)
        self._sig_sep.set_visible(False)
        if was_visible:
            self._force_popup_resize()

    def _force_popup_resize(self):
        """Force popup to recalculate size by re-attaching its content."""
        if self._popup and self._hbox:
            self._popup._content_box.remove(self._hbox)
            self._popup._content_box.append(self._hbox)

    def _highlight_selected(self):
        """Highlight the currently selected row."""
        row = self._listbox.get_row_at_index(self._selected_idx)
        if row:
            self._listbox.select_row(row)

    def _update_filter(self, partial):
        """Filter completions and rebuild the listbox."""
        from editor.autocomplete.autocomplete import COMPLETION_ICONS, CompletionKind

        if partial:
            self._filtered = [c for c in self._completions if c.name.lower().startswith(partial)]
        else:
            self._filtered = self._completions[:]

        # Limit results
        self._filtered = self._filtered[:AUTOCOMPLETE_MAX_ITEMS]
        self._selected_idx = 0

        # Rebuild listbox - use remove_all() for O(1) clear
        self._listbox.remove_all()

        for item in self._filtered:
            icon = COMPLETION_ICONS.get(item.kind, " ")
            display_name = item.insert_text if item.kind == CompletionKind.PARAMETER and item.insert_text else item.name
            label = Gtk.Label(label=f"{icon} {display_name}")
            label.set_xalign(0)
            label.set_ellipsize(Pango.EllipsizeMode.END)
            label.set_max_width_chars(50)
            label.add_css_class("autocomplete-row")
            row = Gtk.ListBoxRow()
            row.set_child(label)
            row.set_can_focus(False)
            self._listbox.append(row)

        # Select first row
        if self._filtered:
            first_row = self._listbox.get_row_at_index(0)
            if first_row:
                self._listbox.select_row(first_row)
        else:
            self._sig_box.set_visible(False)
            self._sig_sep.set_visible(False)
