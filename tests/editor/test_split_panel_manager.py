"""Tests for editor/split_panel_manager.py - mutually exclusive panel management."""

from unittest.mock import MagicMock

from editor.split_panel_manager import SplitPanelManager


def _make_manager():
    """Create a SplitPanelManager with mock Gtk.Paned and editor."""
    paned = MagicMock()
    editor = MagicMock()
    return SplitPanelManager(paned, editor)


class TestRegister:
    """Test panel registration."""

    def test_register_panel(self):
        mgr = _make_manager()
        mgr.register("devpad", MagicMock(), MagicMock(), MagicMock())
        assert "devpad" in mgr._panels


class TestShowHide:
    """Test show/hide behavior."""

    def test_show_calls_show_fn(self):
        mgr = _make_manager()
        show_fn = MagicMock()
        mgr.register("devpad", MagicMock(), show_fn, MagicMock())
        mgr.show("devpad")
        show_fn.assert_called_once()

    def test_show_sets_active(self):
        mgr = _make_manager()
        mgr.register("devpad", MagicMock(), MagicMock(), MagicMock())
        mgr.show("devpad")
        assert mgr.is_visible("devpad") is True

    def test_show_hides_previous(self):
        mgr = _make_manager()
        hide_fn1 = MagicMock()
        mgr.register("devpad", MagicMock(), MagicMock(), hide_fn1)
        mgr.register("diff", MagicMock(), MagicMock(), MagicMock())
        mgr.show("devpad")
        mgr.show("diff")
        hide_fn1.assert_called_once()

    def test_hide_calls_hide_fn(self):
        mgr = _make_manager()
        hide_fn = MagicMock()
        mgr.register("devpad", MagicMock(), MagicMock(), hide_fn)
        mgr.show("devpad")
        mgr.hide("devpad")
        hide_fn.assert_called_once()

    def test_hide_clears_active(self):
        mgr = _make_manager()
        mgr.register("devpad", MagicMock(), MagicMock(), MagicMock())
        mgr.show("devpad")
        mgr.hide("devpad")
        assert mgr.is_visible("devpad") is False

    def test_hide_default_uses_active(self):
        mgr = _make_manager()
        hide_fn = MagicMock()
        mgr.register("devpad", MagicMock(), MagicMock(), hide_fn)
        mgr.show("devpad")
        mgr.hide()
        hide_fn.assert_called_once()

    def test_hide_unknown_noop(self):
        mgr = _make_manager()
        mgr.hide("nonexistent")  # Should not raise


class TestToggle:
    """Test toggle behavior."""

    def test_toggle_shows_inactive(self):
        mgr = _make_manager()
        show_fn = MagicMock()
        mgr.register("devpad", MagicMock(), show_fn, MagicMock())
        mgr.toggle("devpad")
        show_fn.assert_called_once()

    def test_toggle_hides_active(self):
        mgr = _make_manager()
        hide_fn = MagicMock()
        mgr.register("devpad", MagicMock(), MagicMock(), hide_fn)
        mgr.show("devpad")
        mgr.toggle("devpad")
        hide_fn.assert_called_once()


class TestIsVisible:
    """Test visibility checking."""

    def test_visible_when_active(self):
        mgr = _make_manager()
        mgr.register("devpad", MagicMock(), MagicMock(), MagicMock())
        mgr.show("devpad")
        assert mgr.is_visible("devpad") is True

    def test_not_visible_when_inactive(self):
        mgr = _make_manager()
        mgr.register("devpad", MagicMock(), MagicMock(), MagicMock())
        assert mgr.is_visible("devpad") is False

    def test_not_visible_different_panel(self):
        mgr = _make_manager()
        mgr.register("devpad", MagicMock(), MagicMock(), MagicMock())
        mgr.register("diff", MagicMock(), MagicMock(), MagicMock())
        mgr.show("diff")
        assert mgr.is_visible("devpad") is False


class TestMutualExclusion:
    """Test that only one panel is active at a time."""

    def test_only_one_active(self):
        mgr = _make_manager()
        mgr.register("devpad", MagicMock(), MagicMock(), MagicMock())
        mgr.register("diff", MagicMock(), MagicMock(), MagicMock())
        mgr.register("preview", MagicMock(), MagicMock(), MagicMock())
        mgr.show("devpad")
        mgr.show("diff")
        assert mgr.is_visible("diff") is True
        assert mgr.is_visible("devpad") is False
