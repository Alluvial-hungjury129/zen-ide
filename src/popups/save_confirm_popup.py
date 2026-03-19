"""
Neovim-style save confirmation popup for Zen IDE.
"""

from gi.repository import Gdk, Gtk

from popups.nvim_popup import NvimPopup


class SaveConfirmPopup(NvimPopup):
    """
    Neovim-style save confirmation popup.

    Shows a prompt asking if user wants to save, discard, or cancel
    when closing an unsaved file.
    """

    def __init__(
        self,
        parent: Gtk.Window,
        filename: str = "Untitled",
        on_save=None,
        on_discard=None,
        on_cancel=None,
    ):
        """
        Args:
            parent: Parent window
            filename: Name of the file being closed
            on_save: Callback when Save is selected
            on_discard: Callback when Don't Save is selected
            on_cancel: Callback when Cancel is selected
        """
        self._filename = filename
        self._on_save = on_save
        self._on_discard = on_discard
        self._on_cancel = on_cancel
        self._selected_idx = 2  # Default to Save (rightmost)
        super().__init__(parent, title="Unsaved Changes", width=400)

    def _create_content(self):
        """Create the save confirmation UI."""
        # Message
        msg_label = self._create_message_label(f'Save changes to "{self._filename}"?')
        self._content_box.append(msg_label)

        # Submessage
        detail_label = Gtk.Label(label="Your changes will be lost if you don't save them.")
        detail_label.set_halign(Gtk.Align.START)
        detail_label.add_css_class("nvim-popup-hint")
        detail_label.set_margin_top(4)
        self._content_box.append(detail_label)

        # Buttons row
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        button_box.set_halign(Gtk.Align.CENTER)
        button_box.set_margin_top(16)
        self._content_box.append(button_box)

        # Cancel button (c/Esc)
        self._cancel_btn = self._create_button("Cancel")
        self._cancel_btn.connect("clicked", self._on_cancel_clicked)
        button_box.append(self._cancel_btn)

        # Don't Save button (d)
        self._discard_btn = self._create_button("Don't Save")
        self._discard_btn.connect("clicked", self._on_discard_clicked)
        button_box.append(self._discard_btn)

        # Save button (s/Enter)
        self._save_btn = self._create_button("Save", primary=True)
        self._save_btn.connect("clicked", self._on_save_clicked)
        button_box.append(self._save_btn)

        self._buttons = [self._cancel_btn, self._discard_btn, self._save_btn]
        self._update_button_focus()

        # Hint
        hint_label = Gtk.Label(label="c/Esc=cancel  d=don't save  s/Enter=save  Tab=switch")
        hint_label.add_css_class("nvim-popup-hint")
        hint_label.set_halign(Gtk.Align.CENTER)
        hint_label.set_margin_top(12)
        self._content_box.append(hint_label)

    def _update_button_focus(self):
        """Update which button has visual focus."""
        self._buttons[self._selected_idx].grab_focus()

    def _on_key_pressed(self, controller, keyval, keycode, state) -> bool:
        """Handle key press."""
        num_buttons = len(self._buttons)
        # Escape or c = Cancel
        if keyval == Gdk.KEY_Escape or keyval == Gdk.KEY_c or keyval == Gdk.KEY_C:
            self._do_cancel()
            return True
        # d = Don't Save
        elif keyval in (Gdk.KEY_d, Gdk.KEY_D):
            self._do_discard()
            return True
        # s or Enter = Save
        elif keyval in (Gdk.KEY_s, Gdk.KEY_S, Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            self._do_save()
            return True
        # Tab = cycle buttons
        elif keyval == Gdk.KEY_Tab:
            if state & Gdk.ModifierType.SHIFT_MASK:
                self._selected_idx = (self._selected_idx - 1) % num_buttons
            else:
                self._selected_idx = (self._selected_idx + 1) % num_buttons
            self._update_button_focus()
            return True
        # h/Left = move left
        elif keyval in (Gdk.KEY_h, Gdk.KEY_Left):
            self._selected_idx = (self._selected_idx - 1) % num_buttons
            self._update_button_focus()
            return True
        # l/Right = move right
        elif keyval in (Gdk.KEY_l, Gdk.KEY_Right):
            self._selected_idx = (self._selected_idx + 1) % num_buttons
            self._update_button_focus()
            return True
        return False

    def _on_save_clicked(self, button):
        """Handle Save button click."""
        self._do_save()

    def _on_discard_clicked(self, button):
        """Handle Don't Save button click."""
        self._do_discard()

    def _on_cancel_clicked(self, button):
        """Handle Cancel button click."""
        self._do_cancel()

    def _do_save(self):
        """Execute save action."""
        self._result = "save"
        self.close()
        if self._on_save:
            self._on_save()

    def _do_discard(self):
        """Execute don't save action."""
        self._result = "discard"
        self.close()
        if self._on_discard:
            self._on_discard()

    def _do_cancel(self):
        """Execute cancel action."""
        self._result = "cancel"
        self.close()
        if self._on_cancel:
            self._on_cancel()

    def present(self):
        """Show the dialog and focus the Save button."""
        super().present()
        self._save_btn.grab_focus()


def show_save_confirm(
    parent: Gtk.Window,
    filename: str = "Untitled",
    on_save=None,
    on_discard=None,
    on_cancel=None,
):
    """
    Show a save confirmation popup.

    Args:
        parent: Parent window
        filename: Name of the file being closed
        on_save: Callback when Save is selected
        on_discard: Callback when Don't Save is selected
        on_cancel: Callback when Cancel is selected

    Returns:
        The SaveConfirmPopup instance, or None for system-style dialog
    """
    from popups.system_dialogs import is_nvim_mode

    if not is_nvim_mode():
        from popups.system_dialogs import system_save_confirm

        system_save_confirm(parent, filename, on_save, on_discard, on_cancel)
        return None
    popup = SaveConfirmPopup(parent, filename, on_save, on_discard, on_cancel)
    popup.present()
    return popup
