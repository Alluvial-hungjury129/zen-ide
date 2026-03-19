"""Terminal keyboard shortcuts mixin.

Handles copy/paste, word navigation, and other keyboard shortcuts
in the VTE terminal.
"""

from gi.repository import Gdk, Gtk, Vte

from icons import Icons


class TerminalShortcutsMixin:
    """Mixin providing keyboard shortcuts for the terminal."""

    def _setup_terminal_shortcuts(self):
        """Setup Cmd+C / Cmd+V keyboard shortcuts for copy/paste and Cmd+click for file navigation."""
        key_controller = Gtk.EventControllerKey()
        key_controller.connect("key-pressed", self._on_terminal_key_pressed)
        self.terminal.add_controller(key_controller)

        # Add click controller for Cmd+click file navigation
        click_ctrl = Gtk.GestureClick.new()
        click_ctrl.connect("pressed", self._on_terminal_click)
        self.terminal.add_controller(click_ctrl)

        # Add right-click context menu
        right_click = Gtk.GestureClick()
        right_click.set_button(3)
        right_click.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        right_click.connect("pressed", self._on_terminal_right_click)
        self.terminal.add_controller(right_click)

    def _on_terminal_right_click(self, gesture, n_press, x, y):
        """Handle right-click on terminal - show nvim-style context menu."""
        gesture.set_state(Gtk.EventSequenceState.CLAIMED)

        from popups.nvim_context_menu import show_context_menu

        has_selection = self.terminal.get_has_selection()

        items = [
            {"label": "Copy", "action": "copy", "icon": Icons.COPY, "enabled": has_selection},
            {"label": "Paste", "action": "paste", "icon": Icons.PASTE},
            {"label": "Select All", "action": "select_all", "icon": Icons.SELECT_ALL},
            {"label": "---"},
            {"label": "Clear", "action": "clear", "icon": Icons.TRASH},
        ]

        def on_select(action):
            if action == "copy":
                self._copy_selection()
            elif action == "paste":
                self._paste_clipboard()
            elif action == "select_all":
                self.terminal.select_all()
            elif action == "clear":
                self.clear()

        parent = self.get_root()
        if parent:
            show_context_menu(parent, items, on_select, x, y, source_widget=self.terminal)

    def _on_terminal_key_pressed(self, controller, keyval, keycode, state):
        """Handle keyboard shortcuts in terminal."""
        ctrl = state & Gdk.ModifierType.CONTROL_MASK
        shift = state & Gdk.ModifierType.SHIFT_MASK
        meta = state & Gdk.ModifierType.META_MASK

        if keyval == Gdk.KEY_c:
            if meta or (ctrl and shift):
                self._copy_selection()
                return True

        if keyval == Gdk.KEY_v:
            if meta or (ctrl and shift):
                self._paste_clipboard()
                return True

        alt = state & Gdk.ModifierType.ALT_MASK
        if keyval == Gdk.KEY_Left and alt:
            self.terminal.feed_child(b"\x1bb")  # ESC+b - shell backward-word
            return True
        if keyval == Gdk.KEY_Right and alt:
            self.terminal.feed_child(b"\x1bf")  # ESC+f - shell forward-word
            return True
        if keyval == Gdk.KEY_Up and alt:
            self.terminal.feed_child(b"\x1b[A")
            return True
        if keyval == Gdk.KEY_Down and alt:
            self.terminal.feed_child(b"\x1b[B")
            return True

        if keyval == Gdk.KEY_Left and meta:
            self.terminal.feed_child(b"\x01")  # Ctrl+A - beginning of line
            return True
        if keyval == Gdk.KEY_Right and meta:
            self.terminal.feed_child(b"\x05")  # Ctrl+E - end of line
            return True

        if keyval == Gdk.KEY_BackSpace:
            if meta:
                self.terminal.feed_child(b"\x15")  # Ctrl+U
                return True
            if alt:
                self.terminal.feed_child(b"\x1b\x7f")  # ESC+DEL - shell backward-kill-word
                return True

        return False

    def _copy_selection(self):
        """Copy terminal selection to clipboard."""
        if self.terminal.get_has_selection():
            self.terminal.copy_clipboard_format(Vte.Format.TEXT)
            # Flush GTK clipboard to system clipboard on next tick
            from gi.repository import GLib

            GLib.idle_add(self._flush_to_system_clipboard)

    def _flush_to_system_clipboard(self):
        """Read clipboard and write to OS clipboard so it survives app exit."""
        clipboard = Gdk.Display.get_default().get_clipboard()
        clipboard.read_text_async(None, self._on_clipboard_text_read)
        return False

    def _on_clipboard_text_read(self, clipboard, result):
        try:
            text = clipboard.read_text_finish(result)
            if text:
                from shared.utils import copy_to_system_clipboard

                copy_to_system_clipboard(text)
        except Exception:
            pass

    def _paste_clipboard(self):
        """Paste clipboard contents to terminal."""
        self.terminal.paste_clipboard()
