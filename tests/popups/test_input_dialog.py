"""Tests for InputDialog (src/popups/input_dialog.py)."""

import ast

from tests.popups.conftest import (
    class_inherits,
    find_class,
    find_method,
    parse_popup_source,
    read_popup_source,
)


class TestInputDialogStructure:
    """Verify InputDialog structural contracts."""

    def test_inherits_nvim_popup(self):
        tree = parse_popup_source("input_dialog.py")
        assert class_inherits(tree, "InputDialog", "NvimPopup")

    def test_has_on_key_pressed(self):
        tree = parse_popup_source("input_dialog.py")
        cls = find_class(tree, "InputDialog")
        assert find_method(cls, "_on_key_pressed") is not None

    def test_has_create_content(self):
        tree = parse_popup_source("input_dialog.py")
        cls = find_class(tree, "InputDialog")
        assert find_method(cls, "_create_content") is not None

    def test_has_submit_method(self):
        tree = parse_popup_source("input_dialog.py")
        cls = find_class(tree, "InputDialog")
        assert find_method(cls, "_submit") is not None

    def test_has_present(self):
        tree = parse_popup_source("input_dialog.py")
        cls = find_class(tree, "InputDialog")
        assert find_method(cls, "present") is not None


class TestInputDialogKeyHandling:
    """Verify key handling patterns."""

    def test_escape_closes(self):
        source = read_popup_source("input_dialog.py")
        assert "KEY_Escape" in source

    def test_enter_submits(self):
        """Enter via activate signal should trigger submit."""
        source = read_popup_source("input_dialog.py")
        assert "activate" in source


class TestInputDialogValidation:
    """Verify validation logic patterns."""

    def test_has_validate_parameter(self):
        source = read_popup_source("input_dialog.py")
        assert "_validate" in source

    def test_has_error_label(self):
        source = read_popup_source("input_dialog.py")
        assert "_error_label" in source

    def test_on_changed_runs_validation(self):
        """The _on_changed method should call the validate callback."""
        tree = parse_popup_source("input_dialog.py")
        cls = find_class(tree, "InputDialog")
        method = find_method(cls, "_on_changed")
        assert method is not None
        # Should reference self._validate
        source = ast.dump(method)
        assert "validate" in source.lower()

    def test_submit_checks_validation(self):
        """The _submit method should check validation before closing."""
        tree = parse_popup_source("input_dialog.py")
        cls = find_class(tree, "InputDialog")
        method = find_method(cls, "_submit")
        assert method is not None
        source = ast.dump(method)
        assert "validate" in source.lower()

    def test_validation_blocks_submit_on_error(self):
        """Submit should return early if validation fails."""
        source = read_popup_source("input_dialog.py")
        # The _submit method should have a pattern that returns when error exists
        assert "if error:" in source or "if self._validate" in source


class TestInputDialogCallbacks:
    """Verify callback patterns."""

    def test_has_on_submit_callback(self):
        source = read_popup_source("input_dialog.py")
        assert "_on_submit" in source

    def test_submit_calls_callback_with_text(self):
        source = read_popup_source("input_dialog.py")
        assert "callback(text)" in source

    def test_result_set_on_escape(self):
        source = read_popup_source("input_dialog.py")
        assert "self._result = None" in source


class TestShowInputHelper:
    """Verify the show_input helper function."""

    def test_show_input_function_exists(self):
        tree = parse_popup_source("input_dialog.py")
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "show_input":
                return
        raise AssertionError("show_input function not found")

    def test_show_input_checks_nvim_mode(self):
        source = read_popup_source("input_dialog.py")
        assert "is_nvim_mode" in source
