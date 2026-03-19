"""Tests for KeyboardShortcutsPopup (src/popups/keyboard_shortcuts_popup.py)."""

from tests.popups.conftest import (
    class_inherits,
    find_class,
    find_method,
    parse_popup_source,
    read_popup_source,
)


class TestKeyboardShortcutsPopupStructure:
    """Verify KeyboardShortcutsPopup structural contracts."""

    def test_inherits_nvim_popup(self):
        tree = parse_popup_source("keyboard_shortcuts_popup.py")
        assert class_inherits(tree, "KeyboardShortcutsPopup", "NvimPopup")

    def test_has_create_content(self):
        tree = parse_popup_source("keyboard_shortcuts_popup.py")
        cls = find_class(tree, "KeyboardShortcutsPopup")
        assert find_method(cls, "_create_content") is not None

    def test_has_on_key_pressed(self):
        tree = parse_popup_source("keyboard_shortcuts_popup.py")
        cls = find_class(tree, "KeyboardShortcutsPopup")
        assert find_method(cls, "_on_key_pressed") is not None


class TestKeyboardShortcutsPopupKeyHandling:
    """Verify key handling."""

    def test_q_closes(self):
        source = read_popup_source("keyboard_shortcuts_popup.py")
        assert "KEY_q" in source

    def test_escape_closes_via_super(self):
        source = read_popup_source("keyboard_shortcuts_popup.py")
        assert "super()._on_key_pressed" in source


class TestKeyboardShortcutsPopupContent:
    """Verify content structure."""

    def test_uses_keybindings_data(self):
        source = read_popup_source("keyboard_shortcuts_popup.py")
        assert "get_shortcut_categories" in source

    def test_has_scrolled_content(self):
        source = read_popup_source("keyboard_shortcuts_popup.py")
        assert "ScrolledWindow" in source

    def test_has_hint_bar(self):
        source = read_popup_source("keyboard_shortcuts_popup.py")
        assert "_create_hint_bar" in source


class TestShowKeyboardShortcutsHelper:
    """Verify the show_keyboard_shortcuts helper."""

    def test_show_keyboard_shortcuts_exists(self):
        source = read_popup_source("keyboard_shortcuts_popup.py")
        assert "def show_keyboard_shortcuts" in source
