"""Gtk.TextView subclass with optional wide (block) cursor.

When the top-level ``wide_cursor`` setting is True, hides the native GTK
caret and draws a block cursor.  Cursor blink is controlled by
``cursor_blink``.  When ``wide_cursor`` is False the native thin GTK caret
is used (default).
"""

from gi.repository import GLib, Gtk

from constants import CURSOR_BLINK_OFF_MS, CURSOR_BLINK_ON_MS
from shared.settings import get_setting


class BlockCursorTextView(Gtk.TextView):
    """TextView with optional wide (block) cursor.

    Reads ``wide_cursor`` and ``cursor_blink`` settings at construction time.
    """

    __gtype_name__ = "BlockCursorTextView"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._wide = get_setting("wide_cursor", False)
        if not self._wide:
            return

        # -- block-cursor state ------------------------------------------------
        self._cursor_visible = True
        self._blink_timer_id = None
        self._has_focus = False
        self._blink_enabled = get_setting("cursor_blink", False)

        # Hide native caret visually via CSS (not set_cursor_visible which
        # also disables cursor movement via arrow keys in GTK4).
        css = Gtk.CssProvider()
        css.load_from_data(b"textview text { caret-color: transparent; }")
        self.get_style_context().add_provider(css, Gtk.STYLE_PROVIDER_PRIORITY_USER + 10)

        # Focus tracking
        fc = Gtk.EventControllerFocus()
        fc.connect("enter", self._on_focus_enter)
        fc.connect("leave", self._on_focus_leave)
        self.add_controller(fc)

        # Repaint on cursor movement
        self.get_buffer().connect("notify::cursor-position", lambda *_: self.queue_draw())

    # -- focus / blink --------------------------------------------------------

    def _on_focus_enter(self, *_):
        self._has_focus = True
        self._cursor_visible = True
        if self._blink_enabled:
            self._start_blink()
        self.queue_draw()

    def _on_focus_leave(self, *_):
        self._has_focus = False
        self._stop_blink()
        self._cursor_visible = True
        self.queue_draw()

    def _start_blink(self):
        self._stop_blink()
        self._blink_timer_id = GLib.timeout_add(CURSOR_BLINK_ON_MS, self._tick)

    def _stop_blink(self):
        if self._blink_timer_id is not None:
            GLib.source_remove(self._blink_timer_id)
            self._blink_timer_id = None

    def _tick(self):
        self._cursor_visible = not self._cursor_visible
        self.queue_draw()
        ms = CURSOR_BLINK_OFF_MS if not self._cursor_visible else CURSOR_BLINK_ON_MS
        self._blink_timer_id = GLib.timeout_add(ms, self._tick)
        return False

    # -- drawing --------------------------------------------------------------

    def do_snapshot(self, snapshot):
        Gtk.TextView.do_snapshot(self, snapshot)
        if not self._wide or not self._has_focus or not self._cursor_visible:
            return
        from shared.block_cursor_draw import draw_block_cursor

        draw_block_cursor(self, snapshot)
