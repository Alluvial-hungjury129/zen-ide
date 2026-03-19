"""Tests for DockBadge — macOS dock badge counter logic."""

from unittest.mock import patch

from ai import dock_badge


class TestBadgeCounter:
    """Tests for the active AI count logic (platform-independent)."""

    def setup_method(self):
        dock_badge._active_ai_count = 0

    def test_set_increments_count(self):
        dock_badge.set_ai_badge()
        assert dock_badge._active_ai_count == 1

    def test_multiple_sets_increment(self):
        dock_badge.set_ai_badge()
        dock_badge.set_ai_badge()
        dock_badge.set_ai_badge()
        assert dock_badge._active_ai_count == 3

    def test_clear_decrements_count(self):
        dock_badge._active_ai_count = 2
        dock_badge.clear_ai_badge()
        assert dock_badge._active_ai_count == 1

    def test_clear_does_not_go_negative(self):
        dock_badge._active_ai_count = 0
        dock_badge.clear_ai_badge()
        assert dock_badge._active_ai_count == 0

    def test_set_then_clear_returns_to_zero(self):
        dock_badge.set_ai_badge()
        dock_badge.clear_ai_badge()
        assert dock_badge._active_ai_count == 0

    def test_clear_only_triggers_dock_at_zero(self):
        """When count > 0 after clear, dock should NOT be updated (other AI still running)."""
        dock_badge._active_ai_count = 3
        dock_badge.clear_ai_badge()
        # Count is now 2, so badge should stay
        assert dock_badge._active_ai_count == 2

    @patch.object(dock_badge, "_is_macos", return_value=False)
    def test_set_badge_noop_on_non_macos(self, mock_macos):
        """set_ai_badge should still increment counter on non-macOS."""
        dock_badge.set_ai_badge()
        assert dock_badge._active_ai_count == 1

    @patch.object(dock_badge, "_is_macos", return_value=False)
    def test_clear_badge_noop_on_non_macos(self, mock_macos):
        """clear_ai_badge should still decrement counter on non-macOS."""
        dock_badge._active_ai_count = 1
        dock_badge.clear_ai_badge()
        assert dock_badge._active_ai_count == 0
