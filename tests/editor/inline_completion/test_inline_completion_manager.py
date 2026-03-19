"""Tests for inline_completion_manager — coordination of ghost text suggestions."""

from unittest.mock import patch

from tests.editor.inline_completion.test_helpers import (
    make_manager as _make_manager,
)
from tests.editor.inline_completion.test_helpers import (
    setting_side_effect,
)

# ---------------------------------------------------------------------------
# is_enabled
# ---------------------------------------------------------------------------


class TestIsEnabled:
    @patch("editor.inline_completion.inline_completion_manager.get_setting")
    def test_enabled_by_default(self, mock_get):
        mock_get.side_effect = setting_side_effect(
            {
                "ai.is_enabled": True,
                "ai.show_inline_suggestions": True,
            }
        )

        mgr = _make_manager()
        assert mgr.is_enabled() is True

    @patch("editor.inline_completion.inline_completion_manager.get_setting")
    def test_disabled_when_ai_disabled(self, mock_get):
        mock_get.side_effect = setting_side_effect(
            {
                "ai.is_enabled": False,
                "ai.show_inline_suggestions": True,
            }
        )

        mgr = _make_manager()
        assert mgr.is_enabled() is False

    @patch("editor.inline_completion.inline_completion_manager.get_setting")
    def test_disabled_when_inline_disabled(self, mock_get):
        mock_get.side_effect = setting_side_effect(
            {
                "ai.is_enabled": True,
                "ai.show_inline_suggestions": False,
            }
        )

        mgr = _make_manager()
        assert mgr.is_enabled() is False


# ---------------------------------------------------------------------------
# handle_key
# ---------------------------------------------------------------------------


class TestHandleKey:
    def _get_gdk(self):
        """Get Gdk constants for key testing."""
        from gi.repository import Gdk

        return Gdk

    def test_no_action_when_ghost_inactive(self):
        mgr = _make_manager()
        mgr._renderer.is_active = False
        Gdk = self._get_gdk()

        result = mgr.handle_key(Gdk.KEY_Tab, 0)
        assert result is False

    def test_tab_accepts_suggestion(self):
        mgr = _make_manager()
        mgr._renderer.is_active = True
        Gdk = self._get_gdk()

        result = mgr.handle_key(Gdk.KEY_Tab, 0)
        assert result is True
        mgr._renderer.accept.assert_called_once()

    def test_escape_dismisses_suggestion(self):
        mgr = _make_manager()
        mgr._renderer.is_active = True
        Gdk = self._get_gdk()

        result = mgr.handle_key(Gdk.KEY_Escape, 0)
        assert result is True
        mgr._renderer.clear.assert_called_once()

    def test_other_key_dismisses_and_propagates(self):
        mgr = _make_manager()
        mgr._renderer.is_active = True
        Gdk = self._get_gdk()

        result = mgr.handle_key(Gdk.KEY_a, 0)
        assert result is False
        mgr._renderer.clear.assert_called_once()


# ---------------------------------------------------------------------------
# accept / accept_word / dismiss
# ---------------------------------------------------------------------------


class TestActions:
    def test_accept_delegates_to_renderer(self):
        mgr = _make_manager()
        mgr._renderer.accept.return_value = "completed code"

        mgr.accept()
        mgr._renderer.accept.assert_called_once()

    def test_accept_word_delegates(self):
        mgr = _make_manager()
        mgr._renderer.accept_word.return_value = "word"

        mgr.accept_word()
        mgr._renderer.accept_word.assert_called_once()

    def test_dismiss_clears_and_cancels(self):
        mgr = _make_manager()
        mgr._trigger_timer_id = 123

        with patch("editor.inline_completion.inline_completion_manager.GLib"):
            mgr.dismiss()

        mgr._renderer.clear.assert_called_once()
        mgr._provider.cancel.assert_called_once()


# ---------------------------------------------------------------------------
# _on_buffer_changed
# ---------------------------------------------------------------------------


class TestOnBufferChanged:
    @patch("editor.inline_completion.inline_completion_manager.get_setting")
    @patch("editor.inline_completion.inline_completion_manager.GLib")
    def test_skips_when_inserting_ghost(self, mock_glib, mock_settings):
        mgr = _make_manager()
        mgr._renderer._inserting = True

        mgr._on_buffer_changed(mgr._tab.buffer)

        # Should not start timer when ghost text is being inserted
        mock_glib.timeout_add.assert_not_called()

    @patch("editor.inline_completion.inline_completion_manager.get_setting")
    @patch("editor.inline_completion.inline_completion_manager.GLib")
    def test_clears_active_ghost_on_change(self, mock_glib, mock_settings):
        mock_settings.side_effect = setting_side_effect(
            {
                "ai.is_enabled": True,
                "ai.show_inline_suggestions": True,
                "ai.inline_completion.trigger_delay_ms": 500,
            }
        )

        mgr = _make_manager()
        mgr._renderer._inserting = False
        mgr._renderer.is_active = True

        mgr._on_buffer_changed(mgr._tab.buffer)
        mgr._renderer.clear.assert_called_once()

    @patch("editor.inline_completion.inline_completion_manager.get_setting")
    @patch("editor.inline_completion.inline_completion_manager.GLib")
    def test_starts_debounce_timer(self, mock_glib, mock_settings):
        mock_settings.side_effect = setting_side_effect(
            {
                "ai.is_enabled": True,
                "ai.show_inline_suggestions": True,
            }
        )

        mgr = _make_manager()
        mgr._renderer._inserting = False
        mgr._renderer.is_active = False

        mgr._on_buffer_changed(mgr._tab.buffer)
        mock_glib.timeout_add.assert_called_once()
        args = mock_glib.timeout_add.call_args[0]
        assert args[0] == 500  # adaptive debounce returns 500 (mocked)


# ---------------------------------------------------------------------------
# destroy
# ---------------------------------------------------------------------------


class TestDestroy:
    def test_destroy_cleans_up(self):
        mgr = _make_manager()
        mgr._changed_handler_id = 42
        mgr._tab.buffer.handler_is_connected.return_value = True

        with patch("editor.inline_completion.inline_completion_manager.GLib"):
            mgr.destroy()

        mgr._renderer.clear.assert_called()
        mgr._provider.cancel.assert_called()
        mgr._tab.buffer.disconnect.assert_called_with(42)


# ---------------------------------------------------------------------------
# cycle_next / cycle_prev — multi-suggestion cycling
# ---------------------------------------------------------------------------


class TestCycling:
    def test_cycle_next_with_multiple_suggestions(self):
        mgr = _make_manager()
        mgr._suggestions = ["suggestion_a", "suggestion_b", "suggestion_c"]
        mgr._suggestion_index = 0

        mgr.cycle_next()
        assert mgr._suggestion_index == 1
        mgr._renderer.show.assert_called_with("suggestion_b")

    def test_cycle_prev_with_multiple_suggestions(self):
        mgr = _make_manager()
        mgr._suggestions = ["suggestion_a", "suggestion_b", "suggestion_c"]
        mgr._suggestion_index = 0

        mgr.cycle_prev()
        assert mgr._suggestion_index == 2
        mgr._renderer.show.assert_called_with("suggestion_c")

    def test_cycle_wraps_around(self):
        mgr = _make_manager()
        mgr._suggestions = ["a", "b"]
        mgr._suggestion_index = 1

        mgr.cycle_next()
        assert mgr._suggestion_index == 0
        mgr._renderer.show.assert_called_with("a")

    @patch("editor.inline_completion.inline_completion_manager.get_setting")
    @patch("editor.inline_completion.inline_completion_manager.gather_context")
    def test_cycle_next_requests_alternatives_when_single(self, mock_gather, mock_get):
        mock_get.side_effect = setting_side_effect(
            {
                "ai.is_enabled": True,
                "ai.show_inline_suggestions": True,
            }
        )

        mgr = _make_manager()
        mgr._suggestions = ["only_one"]
        mgr._suggestion_index = 0

        mgr.cycle_next()
        mgr._provider.request_alternatives.assert_called_once()

    @patch("editor.inline_completion.inline_completion_manager.get_setting")
    def test_on_alternatives_received_shows_second(self, mock_get):
        mock_get.side_effect = setting_side_effect(
            {
                "ai.is_enabled": True,
                "ai.show_inline_suggestions": True,
            }
        )

        mgr = _make_manager()
        mgr._on_alternatives_received(["alt_a", "alt_b", "alt_c"])

        assert mgr._suggestions == ["alt_a", "alt_b", "alt_c"]
        assert mgr._suggestion_index == 1
        mgr._renderer.show.assert_called_with("alt_b")

    @patch("editor.inline_completion.inline_completion_manager.get_setting")
    def test_on_alternatives_received_empty_dropped(self, mock_get):
        mock_get.side_effect = setting_side_effect(
            {
                "ai.is_enabled": True,
                "ai.show_inline_suggestions": True,
            }
        )

        mgr = _make_manager()
        mgr._on_alternatives_received([])
        assert mgr._suggestions == []
        mgr._renderer.show.assert_not_called()
