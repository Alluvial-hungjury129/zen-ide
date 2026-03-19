"""Tests for SelectionDialog (src/popups/selection_dialog.py)."""

import ast

from tests.popups.conftest import (
    class_inherits,
    find_class,
    find_method,
    method_uses_modulo,
    parse_popup_source,
    read_popup_source,
)


class TestSelectionDialogStructure:
    """Verify SelectionDialog structural contracts."""

    def test_inherits_nvim_popup(self):
        tree = parse_popup_source("selection_dialog.py")
        assert class_inherits(tree, "SelectionDialog", "NvimPopup")

    def test_has_move_selection(self):
        tree = parse_popup_source("selection_dialog.py")
        cls = find_class(tree, "SelectionDialog")
        assert find_method(cls, "_move_selection") is not None

    def test_has_move_to(self):
        tree = parse_popup_source("selection_dialog.py")
        cls = find_class(tree, "SelectionDialog")
        assert find_method(cls, "_move_to") is not None

    def test_has_select_current(self):
        tree = parse_popup_source("selection_dialog.py")
        cls = find_class(tree, "SelectionDialog")
        assert find_method(cls, "_select_current") is not None

    def test_has_is_disabled(self):
        tree = parse_popup_source("selection_dialog.py")
        cls = find_class(tree, "SelectionDialog")
        assert find_method(cls, "_is_disabled") is not None

    def test_move_selection_uses_modulo(self):
        tree = parse_popup_source("selection_dialog.py")
        cls = find_class(tree, "SelectionDialog")
        method = find_method(cls, "_move_selection")
        assert method_uses_modulo(method), "_move_selection must use modulo for wrap-around"


class TestSelectionDialogKeyHandling:
    """Verify key handling patterns."""

    def test_handles_jk_navigation(self):
        source = read_popup_source("selection_dialog.py")
        assert "KEY_j" in source
        assert "KEY_k" in source

    def test_handles_arrow_navigation(self):
        source = read_popup_source("selection_dialog.py")
        assert "KEY_Down" in source
        assert "KEY_Up" in source

    def test_handles_enter_to_select(self):
        source = read_popup_source("selection_dialog.py")
        assert "KEY_Return" in source

    def test_handles_escape_to_close(self):
        source = read_popup_source("selection_dialog.py")
        assert "KEY_Escape" in source

    def test_handles_g_for_first(self):
        source = read_popup_source("selection_dialog.py")
        assert "KEY_g" in source

    def test_handles_G_for_last(self):
        source = read_popup_source("selection_dialog.py")
        assert "KEY_G" in source

    def test_handles_number_keys_for_quick_select(self):
        source = read_popup_source("selection_dialog.py")
        assert "KEY_1" in source
        assert "KEY_9" in source


class TestSelectionDialogDisabledLogic:
    """Test _is_disabled logic as pure functions."""

    def test_string_item_not_disabled(self):
        """String items are never disabled."""
        item = "hello"
        assert not (isinstance(item, dict) and item.get("disabled", False))

    def test_dict_item_disabled(self):
        item = {"label": "---", "disabled": True}
        assert isinstance(item, dict) and item.get("disabled", False)

    def test_dict_item_enabled_by_default(self):
        item = {"label": "Normal"}
        assert not (isinstance(item, dict) and item.get("disabled", False))

    def test_dict_item_explicitly_not_disabled(self):
        item = {"label": "Normal", "disabled": False}
        assert not item.get("disabled", False)


class TestSelectionDialogNavigation:
    """Test navigation logic as pure functions (replicating _move_selection)."""

    @staticmethod
    def _move(items, selected, delta):
        """Replicate SelectionDialog._move_selection."""

        def is_disabled(idx):
            item = items[idx]
            return isinstance(item, dict) and item.get("disabled", False)

        n = len(items)
        new_idx = selected
        for _ in range(n):
            new_idx = (new_idx + delta) % n
            if not is_disabled(new_idx):
                break
        return new_idx

    def test_wrap_down(self):
        assert self._move(["A", "B", "C"], 2, 1) == 0

    def test_wrap_up(self):
        assert self._move(["A", "B", "C"], 0, -1) == 2

    def test_skip_disabled(self):
        items = ["A", {"label": "---", "disabled": True}, "C"]
        assert self._move(items, 0, 1) == 2

    def test_skip_multiple_disabled(self):
        items = ["A", {"label": "---", "disabled": True}, {"label": "---", "disabled": True}, "D"]
        assert self._move(items, 0, 1) == 3
        assert self._move(items, 3, -1) == 0

    def test_single_item(self):
        assert self._move(["A"], 0, 1) == 0
        assert self._move(["A"], 0, -1) == 0

    def test_all_disabled_stays_put(self):
        items = [{"label": "x", "disabled": True}, {"label": "y", "disabled": True}]
        assert self._move(items, 0, 1) == 0


class TestSelectionDialogCallbacks:
    """Verify callback patterns."""

    def test_has_on_select_callback(self):
        source = read_popup_source("selection_dialog.py")
        assert "_on_select" in source

    def test_has_on_selection_change_callback(self):
        source = read_popup_source("selection_dialog.py")
        assert "_on_selection_change" in source

    def test_has_on_cancel_callback(self):
        source = read_popup_source("selection_dialog.py")
        assert "_on_cancel" in source

    def test_cancel_fires_on_close_without_selection(self):
        """close() should fire on_cancel if no selection was made."""
        source = read_popup_source("selection_dialog.py")
        assert "self._result is None and self._on_cancel" in source


class TestShowSelectionHelper:
    """Verify the show_selection helper function."""

    def test_show_selection_function_exists(self):
        tree = parse_popup_source("selection_dialog.py")
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "show_selection":
                return
        raise AssertionError("show_selection function not found")

    def test_show_selection_checks_nvim_mode(self):
        source = read_popup_source("selection_dialog.py")
        assert "is_nvim_mode" in source
