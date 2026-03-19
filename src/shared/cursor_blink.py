"""Shared cursor blink timer for custom-drawn cursors.

Provides a reusable blink controller that alternates a ``cursor_visible``
flag and calls back to trigger repaints.  Used by the editor, tree panel,
and any other component that draws its own cursor/selection highlight.
"""

from gi.repository import GLib

from constants import CURSOR_BLINK_OFF_MS, CURSOR_BLINK_ON_MS


class CursorBlinker:
    """Toggles cursor visibility on a timer and triggers repaints.

    Parameters
    ----------
    queue_draw : callable
        Called whenever visibility toggles so the owner can repaint.
    on_ms / off_ms : int
        Duration of visible / hidden phases in milliseconds.
    """

    def __init__(
        self,
        queue_draw,
        on_ms: int = CURSOR_BLINK_ON_MS,
        off_ms: int = CURSOR_BLINK_OFF_MS,
    ):
        self._queue_draw = queue_draw
        self._on_ms = on_ms
        self._off_ms = off_ms
        self._timer_id: int | None = None
        self._visible = True
        self._enabled = True

    @property
    def cursor_visible(self) -> bool:
        """Whether the cursor should be drawn right now."""
        return self._visible or not self._enabled

    def set_enabled(self, enabled: bool):
        """Enable or disable blinking.  When disabled, cursor stays visible."""
        self._enabled = enabled
        if not enabled:
            self._stop_timer()
            if not self._visible:
                self._visible = True
                self._queue_draw()

    def reset(self):
        """Restart the blink cycle with cursor visible (call on cursor move)."""
        if not self._enabled:
            return
        self._visible = True
        self._restart_timer()
        self._queue_draw()

    def on_focus_in(self):
        """Start blinking when the widget gains focus."""
        self._visible = True
        if self._enabled:
            self._restart_timer()
        self._queue_draw()

    def on_focus_out(self):
        """Stop blinking and hide cursor when focus is lost."""
        self._stop_timer()
        self._visible = True
        self._queue_draw()

    def destroy(self):
        """Clean up the timer."""
        self._stop_timer()

    # -- internal ---------------------------------------------------------

    def _restart_timer(self):
        self._stop_timer()
        self._timer_id = GLib.timeout_add(self._on_ms, self._on_tick)

    def _stop_timer(self):
        if self._timer_id is not None:
            GLib.source_remove(self._timer_id)
            self._timer_id = None

    def _on_tick(self):
        self._visible = not self._visible
        self._queue_draw()
        delay = self._off_ms if not self._visible else self._on_ms
        self._timer_id = GLib.timeout_add(delay, self._on_tick)
        return False  # don't repeat; we schedule the next tick manually
