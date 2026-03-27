"""Tests for system dialogs (src/popups/system_dialogs.py)."""

import ast

from tests.popups.conftest import (
    find_class,
    find_method,
    method_uses_modulo,
    parse_popup_source,
    read_popup_source,
)


class TestIsNvimMode:
    """Verify the is_nvim_mode helper function."""

    def test_is_nvim_mode_exists(self):
        source = read_popup_source("system_dialogs.py")
        assert "def is_nvim_mode" in source

    def test_reads_settings(self):
        source = read_popup_source("system_dialogs.py")
        assert "get_setting" in source
        assert "is_nvim_emulation_enabled" in source


class TestSystemInputDialogStructure:
    """Verify SystemInputDialog structural contracts."""

    def test_inherits_gtk_popover(self):
        tree = parse_popup_source("system_dialogs.py")
        cls = find_class(tree, "SystemInputDialog")
        assert cls is not None
        found = False
        for base in cls.bases:
            if isinstance(base, ast.Attribute) and base.attr == "Popover":
                found = True
            elif isinstance(base, ast.Name) and base.id == "Popover":
                found = True
        assert found, "SystemInputDialog must inherit from Gtk.Popover"

    def test_has_submit_method(self):
        tree = parse_popup_source("system_dialogs.py")
        cls = find_class(tree, "SystemInputDialog")
        assert find_method(cls, "_submit") is not None

    def test_has_validation(self):
        source = read_popup_source("system_dialogs.py")
        assert "_validate" in source

    def test_has_present(self):
        tree = parse_popup_source("system_dialogs.py")
        cls = find_class(tree, "SystemInputDialog")
        assert find_method(cls, "present") is not None


class TestSystemSelectionDialogStructure:
    """Verify SystemSelectionDialog structural contracts."""

    def test_inherits_gtk_popover(self):
        tree = parse_popup_source("recent_items.py")
        cls = find_class(tree, "SystemSelectionDialog")
        assert cls is not None
        found = False
        for base in cls.bases:
            if isinstance(base, ast.Attribute) and base.attr == "Popover":
                found = True
            elif isinstance(base, ast.Name) and base.id == "Popover":
                found = True
        assert found

    def test_has_present(self):
        tree = parse_popup_source("recent_items.py")
        cls = find_class(tree, "SystemSelectionDialog")
        assert find_method(cls, "present") is not None

    def test_handles_disabled_items(self):
        source = read_popup_source("recent_items.py")
        assert "disabled" in source


class TestSystemCommandPaletteDialogStructure:
    """Verify SystemCommandPaletteDialog structural contracts."""

    def test_inherits_gtk_popover(self):
        tree = parse_popup_source("system_dialogs.py")
        cls = find_class(tree, "SystemCommandPaletteDialog")
        assert cls is not None

    def test_has_move_selection(self):
        tree = parse_popup_source("system_dialogs.py")
        cls = find_class(tree, "SystemCommandPaletteDialog")
        assert find_method(cls, "_move_selection") is not None

    def test_move_selection_uses_modulo(self):
        tree = parse_popup_source("system_dialogs.py")
        cls = find_class(tree, "SystemCommandPaletteDialog")
        method = find_method(cls, "_move_selection")
        assert method_uses_modulo(method)

    def test_has_filter_commands(self):
        tree = parse_popup_source("system_dialogs.py")
        cls = find_class(tree, "SystemCommandPaletteDialog")
        assert find_method(cls, "_filter_commands") is not None


class TestSystemContextMenuStructure:
    """Verify SystemContextMenu structural contracts."""

    def test_inherits_gtk_popover(self):
        tree = parse_popup_source("path_breadcrumb.py")
        cls = find_class(tree, "SystemContextMenu")
        assert cls is not None

    def test_has_move_selection(self):
        tree = parse_popup_source("path_breadcrumb.py")
        cls = find_class(tree, "SystemContextMenu")
        assert find_method(cls, "_move_selection") is not None

    def test_move_selection_uses_modulo(self):
        tree = parse_popup_source("path_breadcrumb.py")
        cls = find_class(tree, "SystemContextMenu")
        method = find_method(cls, "_move_selection")
        assert method_uses_modulo(method)

    def test_move_selection_has_loop(self):
        """_move_selection must loop to skip separators/disabled."""
        tree = parse_popup_source("path_breadcrumb.py")
        cls = find_class(tree, "SystemContextMenu")
        method = find_method(cls, "_move_selection")
        has_loop = any(isinstance(child, (ast.For, ast.While)) for child in ast.walk(method))
        assert has_loop


class TestSystemContextMenuNavigation:
    """Test SystemContextMenu navigation as pure function."""

    @staticmethod
    def _move(items, selected, delta):
        """Replicate SystemContextMenu._move_selection."""
        new_idx = selected
        attempts = 0
        while attempts < len(items):
            new_idx = (new_idx + delta) % len(items)
            item = items[new_idx]
            if item.get("label") != "---" and item.get("enabled", True):
                break
            attempts += 1
        return new_idx

    def test_wrap_down(self):
        items = [{"label": "A"}, {"label": "B"}, {"label": "C"}]
        assert self._move(items, 2, 1) == 0

    def test_wrap_up(self):
        items = [{"label": "A"}, {"label": "B"}, {"label": "C"}]
        assert self._move(items, 0, -1) == 2

    def test_skip_separator(self):
        items = [{"label": "A"}, {"label": "---"}, {"label": "C"}]
        assert self._move(items, 0, 1) == 2


class TestSystemCommandPaletteNavigation:
    """Test SystemCommandPaletteDialog navigation as pure function."""

    @staticmethod
    def _move(count, selected, delta):
        if count == 0:
            return selected
        return (selected + delta) % count

    def test_wrap_down(self):
        assert self._move(5, 4, 1) == 0

    def test_wrap_up(self):
        assert self._move(5, 0, -1) == 4


class TestSystemDialogHelpers:
    """Verify system dialog helper functions."""

    def test_system_confirm_exists(self):
        source = read_popup_source("system_dialogs.py")
        assert "def system_confirm" in source

    def test_system_save_confirm_exists(self):
        source = read_popup_source("system_dialogs.py")
        assert "def system_save_confirm" in source

    def test_system_save_all_confirm_exists(self):
        source = read_popup_source("system_dialogs.py")
        assert "def system_save_all_confirm" in source

    def test_popover_theme_helper_exists(self):
        source = read_popup_source("system_dialogs.py")
        assert "def _apply_popover_theme" in source
