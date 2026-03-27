"""Centralized debounce and scheduling helpers for GLib main-loop callbacks.

Replaces the manual ``timeout_add`` / ``source_remove`` pattern that is
duplicated across 30+ files with a reusable, testable primitive.

Usage::

    from shared.debouncer import Debouncer

    # Create a debouncer that fires after 150 ms of inactivity
    _highlight = Debouncer(150, self._do_highlight)

    # Each call resets the timer — only the last one fires
    _highlight()          # starts 150 ms timer
    _highlight()          # cancels previous, restarts
    # ... 150 ms later → _do_highlight() runs once

    # Cancel without firing
    _highlight.cancel()

    # Fire immediately (cancels pending timer)
    _highlight.flush()
"""

from gi.repository import GLib


class Debouncer:
    """Coalesce rapid calls into a single deferred callback.

    Parameters
    ----------
    delay_ms : int
        Minimum quiet period (in milliseconds) before the callback fires.
    callback : callable
        Zero-argument function to invoke after the delay.
    priority : int, optional
        GLib source priority.  Defaults to ``GLib.PRIORITY_DEFAULT``.
        Use ``GLib.PRIORITY_LOW`` for non-visual work that should yield
        to rendering.
    """

    __slots__ = ("_delay_ms", "_callback", "_priority", "_source_id")

    def __init__(
        self,
        delay_ms: int,
        callback,
        *,
        priority: int = GLib.PRIORITY_DEFAULT,
    ):
        self._delay_ms = delay_ms
        self._callback = callback
        self._priority = priority
        self._source_id: int = 0

    # -- public API ----------------------------------------------------------

    def __call__(self) -> None:
        """Schedule (or reschedule) the callback."""
        if self._source_id:
            GLib.source_remove(self._source_id)
        if self._priority == GLib.PRIORITY_DEFAULT:
            self._source_id = GLib.timeout_add(self._delay_ms, self._fire)
        else:
            self._source_id = GLib.timeout_add(self._delay_ms, self._fire, priority=self._priority)

    def cancel(self) -> None:
        """Cancel any pending invocation without firing."""
        if self._source_id:
            GLib.source_remove(self._source_id)
            self._source_id = 0

    def flush(self) -> None:
        """Fire immediately if a call is pending, then cancel the timer."""
        if self._source_id:
            GLib.source_remove(self._source_id)
            self._source_id = 0
            self._callback()

    @property
    def pending(self) -> bool:
        """Return True if a call is scheduled but hasn't fired yet."""
        return self._source_id != 0

    # -- internal ------------------------------------------------------------

    def _fire(self) -> bool:
        self._source_id = 0
        self._callback()
        return GLib.SOURCE_REMOVE
