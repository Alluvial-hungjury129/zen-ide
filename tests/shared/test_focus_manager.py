"""Tests for focus_manager.py - ComponentFocusManager."""

from shared.focus_manager import ComponentFocusManager


class TestRegisterUnregister:
    """Registration and unregistration of components."""

    def test_register_component(self):
        mgr = ComponentFocusManager()
        mgr.register("editor")
        assert "editor" in mgr._components

    def test_register_with_callbacks(self):
        mgr = ComponentFocusManager()
        mgr.register("editor", on_focus_in=lambda: None, on_focus_out=lambda: None)
        assert mgr._components["editor"]["on_focus_in"] is not None


class TestSetFocus:
    """Setting focus on components."""

    def test_set_focus_calls_focus_in(self):
        calls = []
        mgr = ComponentFocusManager()
        mgr.register("editor", on_focus_in=lambda: calls.append("in"))
        mgr.set_focus("editor")
        assert calls == ["in"]

    def test_set_focus_unfocuses_previous(self):
        calls = []
        mgr = ComponentFocusManager()
        mgr.register("editor", on_focus_out=lambda: calls.append("editor_out"))
        mgr.register("terminal", on_focus_in=lambda: calls.append("terminal_in"))
        mgr.set_focus("editor")
        mgr.set_focus("terminal")
        assert "editor_out" in calls
        assert "terminal_in" in calls

    def test_set_focus_same_component_noop(self):
        calls = []
        mgr = ComponentFocusManager()
        mgr.register("editor", on_focus_in=lambda: calls.append("in"))
        mgr.set_focus("editor")
        mgr.set_focus("editor")
        assert calls == ["in"]  # Only called once

    def test_set_focus_unknown_noop(self):
        mgr = ComponentFocusManager()
        mgr.set_focus("unknown")  # Should not raise

    def test_focus_in_exception_handled(self):
        """on_focus_in raising should not propagate."""
        mgr = ComponentFocusManager()
        mgr.register("editor", on_focus_in=lambda: 1 / 0)
        mgr.set_focus("editor")  # Should not raise

    def test_focus_out_exception_handled(self):
        """on_focus_out raising should not propagate."""
        mgr = ComponentFocusManager()
        mgr.register("editor", on_focus_out=lambda: 1 / 0)
        mgr.register("terminal")
        mgr.set_focus("editor")
        mgr.set_focus("terminal")  # Should not raise


class TestClearFocus:
    """Clearing focus from components."""

    def test_clear_focus_calls_focus_out(self):
        calls = []
        mgr = ComponentFocusManager()
        mgr.register("editor", on_focus_out=lambda: calls.append("out"))
        mgr.set_focus("editor")
        mgr.clear_focus("editor")
        assert calls == ["out"]

    def test_clear_focus_sets_current_none(self):
        mgr = ComponentFocusManager()
        mgr.register("editor")
        mgr.set_focus("editor")
        mgr.clear_focus("editor")
        assert mgr.get_current_focus() is None

    def test_clear_focus_unfocused_noop(self):
        calls = []
        mgr = ComponentFocusManager()
        mgr.register("editor", on_focus_out=lambda: calls.append("out"))
        mgr.clear_focus("editor")
        assert calls == []

    def test_clear_focus_unknown_noop(self):
        mgr = ComponentFocusManager()
        mgr.clear_focus("unknown")  # Should not raise


class TestHasFocus:
    """Checking focus state."""

    def test_has_focus_true(self):
        mgr = ComponentFocusManager()
        mgr.register("editor")
        mgr.set_focus("editor")
        assert mgr.has_focus("editor") is True

    def test_has_focus_false(self):
        mgr = ComponentFocusManager()
        mgr.register("editor")
        assert mgr.has_focus("editor") is False

    def test_has_focus_unknown_false(self):
        mgr = ComponentFocusManager()
        assert mgr.has_focus("unknown") is False


class TestGetCurrentFocus:
    """Getting the currently focused component."""

    def test_initial_focus_is_none(self):
        mgr = ComponentFocusManager()
        assert mgr.get_current_focus() is None

    def test_returns_focused_component(self):
        mgr = ComponentFocusManager()
        mgr.register("editor")
        mgr.set_focus("editor")
        assert mgr.get_current_focus() == "editor"


class TestClearAll:
    """Clearing all focus."""

    def test_clear_all(self):
        calls = []
        mgr = ComponentFocusManager()
        mgr.register("editor", on_focus_out=lambda: calls.append("out"))
        mgr.set_focus("editor")
        mgr.clear_all()
        assert mgr.get_current_focus() is None
        assert "out" in calls

    def test_clear_all_no_focus(self):
        mgr = ComponentFocusManager()
        mgr.clear_all()  # Should not raise
