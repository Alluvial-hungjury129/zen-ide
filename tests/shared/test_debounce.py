"""Tests for shared.debounce.Debouncer — centralized debounce primitive."""

from unittest.mock import MagicMock, patch


class TestDebouncerAPI:
    """Test the Debouncer public interface without a running GLib main loop."""

    def test_call_schedules_timeout(self):
        """Calling the debouncer should schedule a GLib timeout."""
        with patch("shared.debounce.GLib") as mock_glib:
            mock_glib.PRIORITY_DEFAULT = 200
            mock_glib.SOURCE_REMOVE = False
            mock_glib.timeout_add = MagicMock(return_value=42)

            from shared.debounce import Debouncer

            cb = MagicMock()
            d = Debouncer(150, cb)
            d()

            mock_glib.timeout_add.assert_called_once()
            args = mock_glib.timeout_add.call_args[0]
            assert args[0] == 150  # delay_ms

    def test_rapid_calls_cancel_previous(self):
        """Multiple rapid calls should cancel the previous timer."""
        with patch("shared.debounce.GLib") as mock_glib:
            mock_glib.PRIORITY_DEFAULT = 200
            mock_glib.SOURCE_REMOVE = False
            mock_glib.timeout_add = MagicMock(side_effect=[10, 20, 30])
            mock_glib.source_remove = MagicMock()

            from shared.debounce import Debouncer

            cb = MagicMock()
            d = Debouncer(100, cb)

            d()  # schedules timer 10
            d()  # cancels 10, schedules 20
            d()  # cancels 20, schedules 30

            assert mock_glib.source_remove.call_count == 2
            mock_glib.source_remove.assert_any_call(10)
            mock_glib.source_remove.assert_any_call(20)

    def test_cancel_removes_timer(self):
        """cancel() should remove the pending timer."""
        with patch("shared.debounce.GLib") as mock_glib:
            mock_glib.PRIORITY_DEFAULT = 200
            mock_glib.SOURCE_REMOVE = False
            mock_glib.timeout_add = MagicMock(return_value=42)
            mock_glib.source_remove = MagicMock()

            from shared.debounce import Debouncer

            cb = MagicMock()
            d = Debouncer(100, cb)

            d()
            assert d.pending
            d.cancel()
            assert not d.pending
            mock_glib.source_remove.assert_called_with(42)

    def test_cancel_noop_when_not_pending(self):
        """cancel() on a non-pending debouncer should be a no-op."""
        with patch("shared.debounce.GLib") as mock_glib:
            mock_glib.PRIORITY_DEFAULT = 200
            mock_glib.SOURCE_REMOVE = False
            mock_glib.source_remove = MagicMock()

            from shared.debounce import Debouncer

            d = Debouncer(100, MagicMock())
            d.cancel()  # should not raise or call source_remove
            mock_glib.source_remove.assert_not_called()

    def test_flush_fires_immediately(self):
        """flush() should invoke callback immediately and clear timer."""
        with patch("shared.debounce.GLib") as mock_glib:
            mock_glib.PRIORITY_DEFAULT = 200
            mock_glib.SOURCE_REMOVE = False
            mock_glib.timeout_add = MagicMock(return_value=42)
            mock_glib.source_remove = MagicMock()

            from shared.debounce import Debouncer

            cb = MagicMock()
            d = Debouncer(100, cb)

            d()
            assert d.pending
            d.flush()
            assert not d.pending
            cb.assert_called_once()
            mock_glib.source_remove.assert_called_with(42)

    def test_flush_noop_when_not_pending(self):
        """flush() without pending call should not invoke callback."""
        with patch("shared.debounce.GLib") as mock_glib:
            mock_glib.PRIORITY_DEFAULT = 200
            mock_glib.SOURCE_REMOVE = False

            from shared.debounce import Debouncer

            cb = MagicMock()
            d = Debouncer(100, cb)
            d.flush()
            cb.assert_not_called()

    def test_pending_property(self):
        """pending should reflect current state."""
        with patch("shared.debounce.GLib") as mock_glib:
            mock_glib.PRIORITY_DEFAULT = 200
            mock_glib.SOURCE_REMOVE = False
            mock_glib.timeout_add = MagicMock(return_value=42)
            mock_glib.source_remove = MagicMock()

            from shared.debounce import Debouncer

            d = Debouncer(100, MagicMock())
            assert not d.pending
            d()
            assert d.pending
            d.cancel()
            assert not d.pending

    def test_fire_invokes_callback_and_clears(self):
        """Internal _fire should invoke callback and reset source_id."""
        with patch("shared.debounce.GLib") as mock_glib:
            mock_glib.PRIORITY_DEFAULT = 200
            mock_glib.SOURCE_REMOVE = False
            mock_glib.timeout_add = MagicMock(return_value=42)

            from shared.debounce import Debouncer

            cb = MagicMock()
            d = Debouncer(100, cb)
            d()

            # Simulate GLib calling _fire
            result = d._fire()
            assert result == mock_glib.SOURCE_REMOVE
            cb.assert_called_once()
            assert not d.pending
