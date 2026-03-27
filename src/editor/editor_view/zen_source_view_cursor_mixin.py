"""Block cursor rendering and blink logic for ZenSourceView."""

from gi.repository import GLib, Gtk

from shared.settings import get_setting


class ZenSourceViewCursorMixin:
    """Mixin providing block cursor drawing and blink for ZenSourceView."""

    def _init_cursor(self):
        """Initialize optional block cursor state. Call from __init__."""
        self._wide_cursor = get_setting("wide_cursor", False)
        if self._wide_cursor:
            from constants import CURSOR_BLINK_OFF_MS, CURSOR_BLINK_ON_MS

            self._bc_visible = True
            self._bc_focused = False
            self._bc_blink_id = None
            self._bc_blink_on = CURSOR_BLINK_ON_MS
            self._bc_blink_off = CURSOR_BLINK_OFF_MS
            self._bc_blink_enabled = get_setting("cursor_blink", False)

            # Hide native caret visually via CSS (not set_cursor_visible which
            # also disables cursor movement via arrow keys in GTK4).
            css = Gtk.CssProvider()
            css.load_from_data(b"textview text { caret-color: transparent; }")
            self.get_style_context().add_provider(css, Gtk.STYLE_PROVIDER_PRIORITY_USER + 10)

            fc = Gtk.EventControllerFocus()
            fc.connect("enter", self._bc_focus_in)
            fc.connect("leave", self._bc_focus_out)
            self.add_controller(fc)

            # Repaint on cursor movement (initial buffer + future swaps)
            # Note: _connect_buffer also connects this signal for buffer swaps;
            # the initial buffer is handled there to avoid duplicate handlers.

    # -- block cursor helpers -------------------------------------------------

    def _bc_focus_in(self, *_):
        # No suppression check here: block cursor must always restore when
        # GTK focus returns.  On window resume, EventControllerFocus.enter
        # fires while the FocusManager is still suppressed; blocking
        # this would leave _bc_focused=False permanently (cursor disappears).
        self._bc_focused = True
        self._bc_visible = True
        if self._bc_blink_enabled:
            self._bc_start_blink()
        if not self._suppress_focus_effects:
            self.queue_draw()

    def _bc_focus_out(self, *_):
        if self._suppress_focus_effects:
            return
        self._bc_focused = False
        self._bc_stop_blink()
        self._bc_visible = True
        self.queue_draw()

    def _bc_start_blink(self):
        self._bc_stop_blink()
        self._bc_blink_id = GLib.timeout_add(self._bc_blink_on, self._bc_tick)

    def _bc_stop_blink(self):
        if self._bc_blink_id is not None:
            GLib.source_remove(self._bc_blink_id)
            self._bc_blink_id = None

    def _bc_tick(self):
        self._bc_visible = not self._bc_visible
        self.queue_draw()
        ms = self._bc_blink_off if not self._bc_visible else self._bc_blink_on
        self._bc_blink_id = GLib.timeout_add(ms, self._bc_tick)
        return False
