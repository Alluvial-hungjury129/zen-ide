"""Tests for status messages — title inference, idle detection, and virtual scrollbar overlay.

Covers:
- Title inference regression tests
- PTY idle detection (_check_idle)
- Virtual scrollbar overlay
"""

import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from ai.ai_terminal_view import AITerminalView

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_view():
    """Create an AITerminalView with GTK/VTE plumbing mocked out."""
    with patch.object(AITerminalView, "__init__", lambda self, **kw: None):
        view = AITerminalView.__new__(AITerminalView)

    # Replicate the __init__ state we need
    view._current_provider = "claude_cli"
    view._input_buf = []
    view._title_inferred = True  # skip title inference in tests
    view._waiting_for_response = False
    view._commit_ready = True
    view._in_escape_seq = False
    view._in_osc_seq = False
    view._idle_poll_id = 0
    view._last_contents_serial = 0
    view._vscroll_adj = MagicMock()
    view._vscroll_adj.get_value.return_value = 100.0
    view._vscroll_inhibit = False
    view._vscroll_hide_id = 0
    view._vscroll_hovering = False
    view._jog_tick_id = 0
    view._vscrollbar = MagicMock()
    view.on_processing_changed = MagicMock()
    view.on_title_inferred = None
    view.on_user_prompt = None
    view.shell_pid = 42
    view.terminal = MagicMock()
    return view


def _send_commit(view, text):
    """Simulate the VTE commit signal with the given text."""
    view._on_vte_commit(None, text, len(text))


# ---------------------------------------------------------------------------
# Title inference regression tests
# ---------------------------------------------------------------------------


class TestTitleInference:
    """Regression tests for tab title inference from user input."""

    def test_title_inferred_on_first_message(self):
        """Title should be inferred from the very first user message."""
        view = _make_view()
        view._title_inferred = False
        view.on_title_inferred = MagicMock()

        _send_commit(view, "fix the bug in main.py\r")

        assert view._title_inferred is True
        view.on_title_inferred.assert_called_once()
        title = view.on_title_inferred.call_args[0][0]
        assert len(title) > 0
        assert "fix" in title.lower() or "bug" in title.lower()

    def test_title_not_set_if_infer_returns_none(self):
        """Regression: _title_inferred must stay False if infer_title returns None."""
        view = _make_view()
        view._title_inferred = False
        view.on_title_inferred = MagicMock()

        # Single char -- too short to infer
        _send_commit(view, "x\r")

        # Title was not inferred -- flag should remain False so next message retries
        if not view.on_title_inferred.called:
            assert view._title_inferred is False

    def test_title_retries_on_subsequent_messages(self):
        """If first message doesn't produce a title, subsequent messages should retry."""
        view = _make_view()
        view._title_inferred = False
        view.on_title_inferred = MagicMock()

        # First message might not produce a good title
        _send_commit(view, "\r")  # empty
        assert view._title_inferred is False

        # Second message should still try
        _send_commit(view, "fix the bug in main.py\r")
        assert view._title_inferred is True
        view.on_title_inferred.assert_called_once()

    def test_startup_noise_does_not_corrupt_title(self):
        """Regression: VTE startup escape sequences must not appear in title."""
        view = _make_view()
        view._title_inferred = False
        view.on_title_inferred = MagicMock()

        # Simulate startup noise followed by user input
        _send_commit(view, "\x1b[?1;2c")  # DA response
        _send_commit(view, "\x1bP>|VTE(6003)\x1b\\")  # XTVERSION
        _send_commit(view, "fix the bug\r")

        assert view._title_inferred is True
        title = view.on_title_inferred.call_args[0][0]
        assert "vte" not in title.lower()
        assert "fix" in title.lower() or "bug" in title.lower()

    def test_input_not_dropped_before_commit_ready(self):
        """Regression: user typing before _commit_ready must not be dropped."""
        view = _make_view()
        view._commit_ready = False
        view._title_inferred = False
        view.on_title_inferred = MagicMock()

        # User types before commit_ready
        _send_commit(view, "hello world\r")

        # Input should be processed -- no gating
        assert view._waiting_for_response is True
        assert view._title_inferred is True
        view.on_title_inferred.assert_called_once()

    def test_escape_fragments_stripped_from_title_input(self):
        """Regression: '[ping' must produce 'Ping', not 'Ing'."""
        view = _make_view()
        view._title_inferred = False
        view.on_title_inferred = MagicMock()

        # Simulate stray [ in buffer followed by user input
        view._input_buf = ["["]
        _send_commit(view, "ping\r")

        assert view._title_inferred is True
        title = view.on_title_inferred.call_args[0][0]
        # Must contain "ping", not be truncated to "ing"
        assert "ping" in title.lower()


# ---------------------------------------------------------------------------
# PTY idle detection (_check_idle)
# ---------------------------------------------------------------------------


class TestIdleDetection:
    """Test the PTY-based idle poll that stops the spinner."""

    def test_content_still_changing_keeps_polling(self):
        view = _make_view()
        view._waiting_for_response = True
        view._last_contents_serial = 5
        view._idle_prev_serial = -1
        view._idle_poll_id = 1

        result = view._check_idle()

        # Serial changed -> keep polling
        assert result is True
        assert view._waiting_for_response is True
        assert view._idle_prev_serial == 5

    def test_content_stable_and_cli_is_foreground_stops_spinner(self):
        view = _make_view()
        view._waiting_for_response = True
        view._last_contents_serial = 5
        view._idle_prev_serial = 5  # stable
        view._idle_poll_id = 1

        mock_pty = MagicMock()
        mock_pty.get_fd.return_value = 3
        view.terminal.get_pty.return_value = mock_pty

        with patch("os.tcgetpgrp", return_value=42):  # matches shell_pid
            result = view._check_idle()

        assert result is False
        assert view._waiting_for_response is False
        view.on_processing_changed.assert_called_once_with(False)

    def test_content_stable_but_subprocess_running_keeps_polling(self):
        view = _make_view()
        view._waiting_for_response = True
        view._last_contents_serial = 5
        view._idle_prev_serial = 5  # stable
        view._idle_poll_id = 1

        mock_pty = MagicMock()
        mock_pty.get_fd.return_value = 3
        view.terminal.get_pty.return_value = mock_pty

        # Different PID -> a tool subprocess is the foreground process
        with patch("os.tcgetpgrp", return_value=999):
            result = view._check_idle()

        assert result is True
        assert view._waiting_for_response is True

    def test_no_pty_keeps_polling(self):
        view = _make_view()
        view._waiting_for_response = True
        view._last_contents_serial = 5
        view._idle_prev_serial = 5
        view._idle_poll_id = 1

        view.terminal.get_pty.return_value = None

        result = view._check_idle()

        assert result is True
        assert view._waiting_for_response is True

    def test_tcgetpgrp_oserror_keeps_polling(self):
        view = _make_view()
        view._waiting_for_response = True
        view._last_contents_serial = 5
        view._idle_prev_serial = 5
        view._idle_poll_id = 1

        mock_pty = MagicMock()
        mock_pty.get_fd.return_value = 3
        view.terminal.get_pty.return_value = mock_pty

        with patch("os.tcgetpgrp", side_effect=OSError("bad fd")):
            result = view._check_idle()

        assert result is True
        assert view._waiting_for_response is True

    def test_not_waiting_stops_immediately(self):
        view = _make_view()
        view._waiting_for_response = False
        view._idle_poll_id = 1

        result = view._check_idle()

        assert result is False
        assert view._idle_poll_id == 0

    def test_contents_changed_increments_serial(self):
        view = _make_view()
        assert view._last_contents_serial == 0

        view._on_contents_changed(None)
        assert view._last_contents_serial == 1

        view._on_contents_changed(None)
        view._on_contents_changed(None)
        assert view._last_contents_serial == 3


class TestVirtualScrollbarOverlay:
    def test_show_virtual_scrollbar_temporarily_reveals_and_reschedules(self):
        view = _make_view()
        view._vscrollbar = MagicMock()
        view._vscroll_hide_id = 17

        with (
            patch("terminal.terminal_jog_wheel.GLib.source_remove") as mock_remove,
            patch("terminal.terminal_jog_wheel.GLib.timeout_add", return_value=23) as mock_timeout,
        ):
            view._show_virtual_scrollbar_temporarily()

        mock_remove.assert_called_once_with(17)
        view._vscrollbar.set_visible.assert_called_once_with(True)
        mock_timeout.assert_called_once()
        assert view._vscroll_hide_id == 23

    def test_vscroll_reset_hides_scrollbar(self):
        view = _make_view()
        view._vscrollbar = MagicMock()
        view._vscroll_hide_id = 31
        view._vscroll_inhibit = False
        view._jog_tick_id = 0

        adj = MagicMock()
        adj.get_value.return_value = 50.0
        view._vscroll_adj = adj

        with patch("terminal.terminal_jog_wheel.GLib.source_remove") as mock_remove:
            view._vscroll_reset()

        mock_remove.assert_called_once_with(31)
        # Jog snaps to center from both _vscroll_reset and _hide_immediately
        assert adj.set_value.call_count == 2
        view._vscrollbar.set_visible.assert_called_once_with(False)
        assert view._vscroll_hide_id == 0
