"""
Font picker dialog for Zen IDE.
Supports target selection and search.
"""

from typing import Callable, Dict, Optional, Tuple

from gi.repository import Gdk, GLib, Gtk

from fonts import get_font_settings
from popups.font_preview import FontPreviewMixin
from popups.nvim_context_menu import show_context_menu
from popups.nvim_popup import NvimPopup

_FOCUS_CHECK_DELAY_MS = 100


class FontPickerDialog(FontPreviewMixin, NvimPopup):
    """Font picker dialog with target selection and searchable font list."""

    # Target definitions: (key, display_label)
    TARGETS = [
        ("editor", "Editor"),
        ("terminal", "Terminal"),
        ("explorer", "Explorer"),
        ("ai_chat", "AI Chat"),
        ("markdown_preview", "Markdown Preview"),
    ]

    def __init__(
        self,
        parent: Gtk.Window,
        on_apply: Optional[Callable[[str, str, int, str], None]] = None,
    ):
        """Initialize the font picker dialog.

        Args:
            parent: Parent window
            on_apply: Callback(family, weight, size, target_key) for live preview
        """
        self.on_apply = on_apply
        self._updating_ui = False
        self._preview_applied = False
        self._sub_popup = None

        # Store original settings for cancel/revert
        self.original_settings: Dict[str, Dict] = {}
        for key, _ in self.TARGETS:
            if key != "all":
                self.original_settings[key] = get_font_settings(key).copy()

        # Initialize font data from mixin
        self._init_font_data()

        super().__init__(parent, title="Font Settings", width=500, height=550)

        self._load_current_selection()

    def _create_content(self):
        """Create the dialog UI."""

        # Target selection
        self._selected_target_idx = 0

        target_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        target_label = Gtk.Label(label="Apply to:")
        target_box.append(target_label)

        self._target_button = self._create_button(self.TARGETS[0][1])
        self._target_button.set_hexpand(True)
        self._target_button.connect("clicked", self._on_target_button_clicked)
        target_box.append(self._target_button)
        self._content_box.append(target_box)

        # Font family label
        family_label = Gtk.Label(label="Font Family:")
        family_label.set_halign(Gtk.Align.START)
        family_label.set_margin_top(8)
        self._content_box.append(family_label)

        # Search entry
        self.search_entry = self._create_search_entry("Search fonts...")
        self.search_entry.connect("search-changed", self._on_search_changed)
        self._content_box.append(self.search_entry)

        # Font list (from mixin)
        scroll = self._create_font_list_widgets()
        self._content_box.append(scroll)

        # Size row
        size_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        size_box.set_margin_top(10)
        size_label = Gtk.Label(label="Size:")
        size_box.append(size_label)

        self.size_spin = Gtk.SpinButton()
        self.size_spin.set_range(6, 72)
        self.size_spin.set_increments(1, 5)
        self.size_spin.set_value(14)
        self.size_spin.connect("value-changed", self._on_size_changed)
        size_box.append(self.size_spin)

        self._content_box.append(size_box)

        # Button row
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        button_box.set_halign(Gtk.Align.CENTER)
        button_box.set_margin_top(8)

        cancel_btn = self._create_button("Cancel")
        cancel_btn.connect("clicked", self._on_cancel)
        button_box.append(cancel_btn)

        ok_btn = self._create_button("Apply", primary=True)
        ok_btn.connect("clicked", self._on_ok)
        button_box.append(ok_btn)

        self._content_box.append(button_box)

        # Focus search entry so typing works immediately
        self.search_entry.grab_focus()

    def _load_current_selection(self):
        """Load current font settings for the selected target."""
        self._updating_ui = True
        try:
            target_key = self.TARGETS[self._selected_target_idx][0]

            settings = get_font_settings(target_key)
            family = settings.get("family", "")
            size = settings.get("size", 14)

            # Select font in list
            if family:
                for i in range(self._filter_model.get_n_items()):
                    item = self._filter_model.get_item(i)
                    if item.name.lower() == family.lower():
                        self._selection_model.set_selected(i)
                        # Scroll to selection without stealing focus from search entry
                        GLib.idle_add(lambda pos=i: self.font_list.scroll_to(pos, Gtk.ListScrollFlags.NONE, None) or False)
                        break

            # Set size
            self.size_spin.set_value(size)
        finally:
            self._updating_ui = False

    def _on_target_button_clicked(self, button):
        """Show context menu for target selection."""
        # Create menu items in the correct format
        items = [{"label": label, "action": key} for key, label in self.TARGETS]

        # Get parent window
        parent_window = self.get_transient_for() or self.get_root()

        menu = show_context_menu(
            parent=parent_window,
            items=items,
            on_select=self._on_target_selected,
            source_widget=self._target_button,
            title="Apply to",
        )

        if menu:
            self._sub_popup = menu

            # Connect to the appropriate signal based on popup type
            from popups.nvim_popup import NvimPopup

            if isinstance(menu, NvimPopup):
                menu.connect("close-request", self._on_sub_popup_closing)
            else:
                # SystemContextMenu (Gtk.Popover) uses "closed" signal
                menu.connect("closed", self._on_sub_popup_closing)

    def _on_target_selected(self, action):
        """Handle target selection from context menu."""
        # Don't clear _sub_popup here - let the close signal handler do it
        for i, (key, label) in enumerate(self.TARGETS):
            if key == action:
                self._selected_target_idx = i
                self._target_button.set_label(label)
                self._load_current_selection()
                break

    def _on_sub_popup_closing(self, *args):
        """Handle sub-popup closing -- clear reference and restore focus."""
        if not self._closing:
            # Delay clearing _sub_popup until after focus is restored to prevent race condition
            GLib.idle_add(self._restore_focus_and_clear_sub_popup)
        else:
            self._sub_popup = None
        return False

    def _restore_focus_and_clear_sub_popup(self):
        """Restore focus to search entry and clear sub-popup reference."""
        if not self._closing:
            self.search_entry.grab_focus()
        self._sub_popup = None
        return False

    def _on_size_changed(self, spin):
        """Handle size spin change."""
        if not self._updating_ui:
            self._apply_preview()

    def _get_current_selection(self) -> Tuple[str, str, int]:
        """Get current font selection.

        Returns:
            Tuple of (family, weight, size)
        """
        # Family
        selected_pos = self._selection_model.get_selected()
        if selected_pos != Gtk.INVALID_LIST_POSITION:
            item = self._selection_model.get_selected_item()
            family = item.name if item else ""
        else:
            family = ""

        weight = "normal"

        # Size
        size = int(self.size_spin.get_value())

        return family, weight, size

    def _apply_preview(self):
        """Apply current selection as live preview."""
        if not self.on_apply or self._updating_ui:
            return

        family, weight, size = self._get_current_selection()
        if not family:
            return

        target_key = self.TARGETS[self._selected_target_idx][0]

        self._preview_applied = True
        self.on_apply(family, weight, size, target_key)

    def _on_ok(self, button):
        """Apply settings and close."""
        family, weight, size = self._get_current_selection()
        if family and self.on_apply:
            target_key = self.TARGETS[self._selected_target_idx][0]
            self.on_apply(family, weight, size, target_key)

        self.close()

    def _on_cancel(self, button):
        """Revert to original settings and close."""
        try:
            if self.on_apply and self._preview_applied:
                for target_key, settings in self.original_settings.items():
                    self.on_apply(
                        settings.get("family", ""),
                        settings.get("weight", "normal"),
                        settings.get("size", 14),
                        target_key,
                    )
        finally:
            self.close()

    def _on_focus_leave(self, controller):
        """Override to prevent close when dropdown/spinbutton popovers take focus."""
        # For font picker, we never auto-close on focus leave - only on ESC or button clicks
        # This prevents issues with the "Apply to" dropdown
        return

    def _on_active_changed(self, window, pspec):
        """Override to prevent auto-close when window loses active state."""
        # Don't auto-close for font picker - only manual close via buttons/ESC
        return

    def _check_active_and_close(self):
        """Override to prevent delayed close on inactive state."""
        # Don't auto-close for font picker
        return False

    def _check_focus_and_close(self):
        """Close only if focus has truly left this dialog."""
        if self._sub_popup is not None:
            return False
        if self.get_focus() is not None or self.is_active():
            return False
        self._result = None
        self.close()
        return False

    def _dismiss_click_outside(self):
        """Override to prevent close when sub-popup is open."""
        if self._sub_popup is not None:
            return False
        return super()._dismiss_click_outside()

    def _setup_keyboard(self):
        """Use CAPTURE phase so Escape is caught before child widgets consume it."""
        key_controller = Gtk.EventControllerKey()
        key_controller.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        key_controller.connect("key-pressed", self._on_key_pressed)
        self.add_controller(key_controller)

    def _on_key_pressed(self, controller, keyval, keycode, state):
        """Handle key presses - ESC to close, arrows for navigation."""
        if keyval == Gdk.KEY_Escape:
            self._on_cancel(None)
            return True
        elif keyval == Gdk.KEY_Down:
            self._move_selection(1)
            return True
        elif keyval == Gdk.KEY_Up:
            self._move_selection(-1)
            return True
        elif keyval == Gdk.KEY_Return:
            self._on_ok(None)
            return True

        # Redirect printable keys to search entry when list has focus
        if not self._has_text_entry_focus() and Gdk.keyval_to_unicode(keyval) > 0:
            self.search_entry.grab_focus()
            return False

        return False

    # Font popup fix: Override all auto-closing mechanisms to prevent
    # dialog from closing when "Apply to" combo box is clicked

    def _on_focus_leave(self):
        """Override to prevent auto-closing on focus leave."""
        return

    def _on_active_changed(self, window, active):
        """Override to prevent auto-closing on active state change."""
        return

    def _check_active_and_close(self):
        """Override to prevent delayed auto-closing."""
        return


def show_font_picker(
    parent: Gtk.Window,
    on_apply: Optional[Callable[[str, str, int, str], None]] = None,
) -> None:
    """Show the font picker dialog.

    Args:
        parent: Parent window
        on_apply: Callback(family, weight, size, target_key) for live preview and apply
    """
    dialog = FontPickerDialog(parent, on_apply)
    dialog.present()
