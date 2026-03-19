"""Tests for keybindings module."""

from shared.settings.keybindings import KeyBindings


class TestKeyBindingsGtk:
    """Test keybinding definitions and formatting."""

    def test_keybinding_attrs_are_strings(self):
        """All keybinding class attributes are strings."""
        for attr in ["NEW_FILE", "SAVE_FILE", "CLOSE_TAB", "FIND", "QUIT"]:
            value = getattr(KeyBindings, attr)
            assert isinstance(value, str), f"{attr} is not a string"

    def test_keybindings_contain_modifier(self):
        """All keybindings use a modifier key."""
        for attr in ["NEW_FILE", "SAVE_FILE", "CLOSE_TAB", "FIND", "QUIT"]:
            value = getattr(KeyBindings, attr)
            assert "<Meta>" in value or "<Control>" in value, f"{attr} missing modifier"
