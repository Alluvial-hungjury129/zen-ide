"""
Neovim-style save-all confirmation popup for Zen IDE.
"""

from gi.repository import Gdk, Gtk

from popups.nvim_popup import NvimPopup


class SaveAllConfirmPopup(NvimPopup):
    """
    Nvim-style popup for confirming save of multiple files on window close.
    Options: [s]ave All, [d]iscard All, [c]ancel
    """

    def __init__(
        self,
        parent: Gtk.Window,
        filenames: list[str],
        on_save_all=None,
        on_discard_all=None,
        on_cancel=None,
    ):
        super().__init__(parent, title="Unsaved Changes", width=450, height=-1)
        self._filenames = filenames
        self._on_save_all = on_save_all
        self._on_discard_all = on_discard_all
        self._on_cancel = on_cancel
        self._result = None
        self._selected_idx = 0  # 0=Save All, 1=Discard, 2=Cancel
        self._buttons = []

        self._build_ui()

    def _build_ui(self):
        """Build the popup UI."""
        # Message
        msg_label = Gtk.Label()
        msg_label.set_markup("<b>Save changes before closing?</b>")
        msg_label.set_halign(Gtk.Align.START)
        self._content_box.append(msg_label)

        # File list (max 5, then "and N more...")
        files_text = ""
        if len(self._filenames) <= 5:
            files_text = "\n".join(f"  • {f}" for f in self._filenames)
        else:
            files_text = "\n".join(f"  • {f}" for f in self._filenames[:5])
            files_text += f"\n  ... and {len(self._filenames) - 5} more"

        files_label = Gtk.Label(label=files_text)
        files_label.set_halign(Gtk.Align.START)
        files_label.set_margin_top(8)
        files_label.add_css_class("dim-label")
        self._content_box.append(files_label)

        # Buttons: Save All | Discard All | Cancel
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_box.set_halign(Gtk.Align.CENTER)
        btn_box.set_margin_top(16)

        self._save_btn = self._create_button("[S]ave All", primary=True)
        self._save_btn.connect("clicked", self._on_save_clicked)
        btn_box.append(self._save_btn)

        self._discard_btn = self._create_button("[D]iscard All", danger=True)
        self._discard_btn.connect("clicked", self._on_discard_clicked)
        btn_box.append(self._discard_btn)

        self._cancel_btn = self._create_button("[C]ancel")
        self._cancel_btn.connect("clicked", self._on_cancel_clicked)
        btn_box.append(self._cancel_btn)

        self._buttons = [self._save_btn, self._discard_btn, self._cancel_btn]
        self._content_box.append(btn_box)

        # Keyboard hints
        hint_label = Gtk.Label()
        from themes import get_theme

        theme = get_theme()
        hint_label.set_markup(
            f"<small><span foreground='{theme.fg_dim}'>s=Save All  d=Discard All  c/Esc=Cancel  Tab=Switch</span></small>"
        )
        hint_label.set_halign(Gtk.Align.CENTER)
        hint_label.set_margin_top(12)
        self._content_box.append(hint_label)

    def _update_button_focus(self):
        """Update which button has visual focus."""
        self._buttons[self._selected_idx].grab_focus()

    def _on_key_pressed(self, controller, keyval, keycode, state) -> bool:
        """Handle key press."""
        # Escape or c = Cancel
        if keyval == Gdk.KEY_Escape or keyval == Gdk.KEY_c or keyval == Gdk.KEY_C:
            self._do_cancel()
            return True
        # s or Enter = Save All
        elif keyval in (Gdk.KEY_s, Gdk.KEY_S, Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            self._do_save_all()
            return True
        # d = Discard All
        elif keyval == Gdk.KEY_d or keyval == Gdk.KEY_D:
            self._do_discard_all()
            return True
        # Tab = cycle buttons
        elif keyval == Gdk.KEY_Tab:
            if state & Gdk.ModifierType.SHIFT_MASK:
                self._selected_idx = (self._selected_idx - 1) % 3
            else:
                self._selected_idx = (self._selected_idx + 1) % 3
            self._update_button_focus()
            return True
        # h/Left = move left
        elif keyval in (Gdk.KEY_h, Gdk.KEY_Left):
            self._selected_idx = (self._selected_idx - 1) % 3
            self._update_button_focus()
            return True
        # l/Right = move right
        elif keyval in (Gdk.KEY_l, Gdk.KEY_Right):
            self._selected_idx = (self._selected_idx + 1) % 3
            self._update_button_focus()
            return True
        return False

    def _on_save_clicked(self, button):
        self._do_save_all()

    def _on_discard_clicked(self, button):
        self._do_discard_all()

    def _on_cancel_clicked(self, button):
        self._do_cancel()

    def _do_save_all(self):
        self._result = "save_all"
        self.close()
        if self._on_save_all:
            self._on_save_all()

    def _do_discard_all(self):
        self._result = "discard_all"
        self.close()
        if self._on_discard_all:
            self._on_discard_all()

    def _do_cancel(self):
        self._result = "cancel"
        self.close()
        if self._on_cancel:
            self._on_cancel()

    def present(self):
        super().present()
        self._save_btn.grab_focus()


def show_save_all_confirm(
    parent: Gtk.Window,
    filenames: list[str],
    on_save_all=None,
    on_discard_all=None,
    on_cancel=None,
):
    """
    Show a save-all confirmation popup for multiple unsaved files.

    Args:
        parent: Parent window
        filenames: List of unsaved file names
        on_save_all: Callback when Save All is selected
        on_discard_all: Callback when Discard All is selected
        on_cancel: Callback when Cancel is selected

    Returns:
        The SaveAllConfirmPopup instance, or None for system-style dialog
    """
    from popups.system_dialogs import is_nvim_mode

    if not is_nvim_mode():
        from popups.system_dialogs import system_save_all_confirm

        system_save_all_confirm(parent, filenames, on_save_all, on_discard_all, on_cancel)
        return None
    popup = SaveAllConfirmPopup(parent, filenames, on_save_all, on_discard_all, on_cancel)
    popup.present()
    return popup
