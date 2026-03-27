"""
Neovim-style input dialog for Zen IDE.
"""

from gi.repository import Gdk, Gtk

from popups.nvim_popup import NvimPopup


class InputDialog(NvimPopup):
    """Neovim-style input dialog with a single text entry."""

    def __init__(
        self,
        parent: Gtk.Window,
        title: str = "Input",
        message: str = "",
        placeholder: str = "",
        initial_value: str = "",
        on_submit=None,
        validate=None,
    ):
        self._message = message
        self._placeholder = placeholder
        self._initial_value = initial_value
        self._on_submit = on_submit
        self._validate = validate
        super().__init__(parent, title, width=450)

    def _create_content(self):
        """Create the input dialog UI."""
        # Message
        if self._message:
            msg_label = self._create_message_label(self._message)
            self._content_box.append(msg_label)

        # Input entry
        self._entry = self._create_input_entry(self._placeholder, self._initial_value)
        self._entry.connect("activate", self._on_activate)
        self._entry.connect("changed", self._on_changed)
        self._content_box.append(self._entry)

        # Error label (hidden by default)
        self._error_label = Gtk.Label()
        self._error_label.set_halign(Gtk.Align.START)
        self._error_label.add_css_class("nvim-popup-hint")
        self._error_label.set_visible(False)
        self._content_box.append(self._error_label)

        # Hint bar
        hint_bar = self._create_hint_bar([("Enter", "confirm"), ("Esc", "cancel")])
        hint_bar.set_halign(Gtk.Align.END)
        self._content_box.append(hint_bar)

    def _on_changed(self, entry):
        """Handle text change - run validation."""
        if self._validate:
            text = entry.get_text()
            error = self._validate(text)
            if error:
                self._error_label.set_text(error)
                self._error_label.set_visible(True)
            else:
                self._error_label.set_visible(False)

    def _on_activate(self, entry):
        """Handle Enter key."""
        self._submit()

    def _on_key_pressed(self, controller, keyval, keycode, state) -> bool:
        """Handle key press."""
        if keyval == Gdk.KEY_Escape:
            self._result = None
            self.close()
            return True
        return False

    def _submit(self):
        """Submit the input."""
        text = self._entry.get_text()

        # Validate
        if self._validate:
            error = self._validate(text)
            if error:
                self._error_label.set_text(error)
                self._error_label.set_visible(True)
                return

        self._result = text
        callback = self._on_submit
        self.close()
        if callback:
            callback(text)

    def present(self):
        """Show the dialog and focus the entry."""
        super().present()
        self._entry.grab_focus()
        # Select all text if there's initial value
        if self._initial_value:
            self._entry.select_region(0, -1)


def show_input(
    parent: Gtk.Window,
    title: str = "Input",
    message: str = "",
    placeholder: str = "",
    initial_value: str = "",
    on_submit=None,
    validate=None,
):
    """Show an input dialog and return it."""
    from popups.nvim_popup import show_popup
    from popups.system_command_palette_dialog import SystemInputDialog

    return show_popup(
        InputDialog,
        SystemInputDialog,
        parent,
        title,
        message,
        placeholder,
        initial_value,
        on_submit,
        validate,
    )
