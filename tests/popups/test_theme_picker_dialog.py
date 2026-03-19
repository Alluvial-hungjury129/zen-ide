"""Tests for theme_picker_dialog (src/popups/theme_picker_dialog.py)."""

import ast

from tests.popups.conftest import parse_popup_source, read_popup_source


class TestThemePickerDialogStructure:
    """Verify theme_picker_dialog structural contracts."""

    def test_show_theme_picker_function_exists(self):
        tree = parse_popup_source("theme_picker_dialog.py")
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "show_theme_picker":
                return
        raise AssertionError("show_theme_picker function not found")

    def test_has_theme_picker_class(self):
        """theme_picker_dialog should define ThemePickerDialog class."""
        tree = parse_popup_source("theme_picker_dialog.py")
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "ThemePickerDialog":
                return
        raise AssertionError("ThemePickerDialog class not found")


class TestThemePickerDialogBehavior:
    """Verify theme picker behavior patterns."""

    def test_has_search_entry(self):
        source = read_popup_source("theme_picker_dialog.py")
        assert "search_entry" in source or "search" in source

    def test_has_live_preview(self):
        source = read_popup_source("theme_picker_dialog.py")
        assert "_on_row_selected" in source or "on_preview" in source

    def test_has_cancel_revert(self):
        source = read_popup_source("theme_picker_dialog.py")
        assert "_revert_and_close" in source or "_original_theme" in source

    def test_filters_by_dark_light_mode(self):
        source = read_popup_source("theme_picker_dialog.py")
        assert "is_dark" in source

    def test_persists_on_confirm(self):
        source = read_popup_source("theme_picker_dialog.py")
        assert "persist=True" in source

    def test_does_not_persist_on_preview(self):
        source = read_popup_source("theme_picker_dialog.py")
        assert "persist=False" in source

    def test_reverts_original_theme_on_cancel(self):
        source = read_popup_source("theme_picker_dialog.py")
        assert "original_theme" in source
