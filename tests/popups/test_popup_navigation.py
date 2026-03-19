"""
Tests for popup navigation behavior.

Ensures all popups wrap around (modular navigation) and skip disabled/separator items.
These tests replicate the navigation logic from each popup class to verify correctness
without requiring a GTK display server.
"""

import ast
import os

import pytest

# ---------------------------------------------------------------------------
# Helpers: replicate each popup's _move_selection logic as pure functions
# ---------------------------------------------------------------------------


def selection_dialog_move(items, selected, delta):
    """Replicate SelectionDialog._move_selection (skip disabled, modulo wrap)."""

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


def context_menu_move(items, selected, delta):
    """Replicate NvimContextMenu._move_selection (skip separators & disabled)."""
    new_idx = selected
    attempts = 0
    while attempts < len(items):
        new_idx = (new_idx + delta) % len(items)
        item = items[new_idx]
        if item.get("label") != "---" and item.get("enabled", True):
            break
        attempts += 1
    return new_idx


def simple_list_move(count, selected, delta):
    """Replicate QuickOpenDialog / CommandPaletteDialog._move_selection."""
    if count == 0:
        return selected
    return (selected + delta) % count


def global_search_move(result_indices, current_idx, delta):
    """Replicate GlobalSearchDialog._move_selection (only result rows, skip headers)."""
    if not result_indices:
        return current_idx
    return (current_idx + delta) % len(result_indices)


# Also replicate system_dialogs variants
system_context_menu_move = context_menu_move  # identical logic
system_command_palette_move = simple_list_move  # identical logic


# ---------------------------------------------------------------------------
# SelectionDialog wrap-around tests
# ---------------------------------------------------------------------------


class TestSelectionDialogNavigation:
    """Tests for SelectionDialog._move_selection."""

    def test_wrap_down_at_bottom(self):
        items = ["A", "B", "C"]
        assert selection_dialog_move(items, 2, 1) == 0

    def test_wrap_up_at_top(self):
        items = ["A", "B", "C"]
        assert selection_dialog_move(items, 0, -1) == 2

    def test_normal_down(self):
        items = ["A", "B", "C"]
        assert selection_dialog_move(items, 0, 1) == 1

    def test_normal_up(self):
        items = ["A", "B", "C"]
        assert selection_dialog_move(items, 2, -1) == 1

    def test_skip_disabled_down(self):
        items = ["A", {"label": "---", "disabled": True}, "C"]
        assert selection_dialog_move(items, 0, 1) == 2

    def test_skip_disabled_up(self):
        items = ["A", {"label": "---", "disabled": True}, "C"]
        assert selection_dialog_move(items, 2, -1) == 0

    def test_skip_disabled_wrap_down(self):
        items = ["A", "B", {"label": "---", "disabled": True}]
        assert selection_dialog_move(items, 1, 1) == 0

    def test_skip_disabled_wrap_up(self):
        items = [{"label": "---", "disabled": True}, "B", "C"]
        assert selection_dialog_move(items, 1, -1) == 2

    def test_multiple_disabled_items(self):
        items = [
            "A",
            {"label": "---", "disabled": True},
            {"label": "---", "disabled": True},
            "D",
        ]
        assert selection_dialog_move(items, 0, 1) == 3
        assert selection_dialog_move(items, 3, -1) == 0

    def test_single_item(self):
        items = ["A"]
        assert selection_dialog_move(items, 0, 1) == 0
        assert selection_dialog_move(items, 0, -1) == 0

    def test_all_disabled_stays_put(self):
        """If all items are disabled, we loop back to original index."""
        items = [{"label": "x", "disabled": True}, {"label": "y", "disabled": True}]
        # The loop runs n times and lands back on original
        assert selection_dialog_move(items, 0, 1) == 0


# ---------------------------------------------------------------------------
# NvimContextMenu wrap-around tests
# ---------------------------------------------------------------------------


class TestContextMenuNavigation:
    """Tests for NvimContextMenu._move_selection."""

    def test_wrap_down(self):
        items = [{"label": "A"}, {"label": "B"}, {"label": "C"}]
        assert context_menu_move(items, 2, 1) == 0

    def test_wrap_up(self):
        items = [{"label": "A"}, {"label": "B"}, {"label": "C"}]
        assert context_menu_move(items, 0, -1) == 2

    def test_skip_separator_down(self):
        items = [{"label": "A"}, {"label": "---"}, {"label": "C"}]
        assert context_menu_move(items, 0, 1) == 2

    def test_skip_separator_up(self):
        items = [{"label": "A"}, {"label": "---"}, {"label": "C"}]
        assert context_menu_move(items, 2, -1) == 0

    def test_skip_disabled_item(self):
        items = [{"label": "A"}, {"label": "B", "enabled": False}, {"label": "C"}]
        assert context_menu_move(items, 0, 1) == 2

    def test_wrap_with_separator_at_end(self):
        items = [{"label": "A"}, {"label": "B"}, {"label": "---"}]
        assert context_menu_move(items, 1, 1) == 0

    def test_wrap_with_separator_at_start(self):
        items = [{"label": "---"}, {"label": "B"}, {"label": "C"}]
        assert context_menu_move(items, 1, -1) == 2


# ---------------------------------------------------------------------------
# QuickOpen / CommandPalette simple wrap tests
# ---------------------------------------------------------------------------


class TestSimpleListNavigation:
    """Tests for QuickOpenDialog / CommandPaletteDialog._move_selection (simple modulo)."""

    def test_wrap_down(self):
        assert simple_list_move(5, 4, 1) == 0

    def test_wrap_up(self):
        assert simple_list_move(5, 0, -1) == 4

    def test_normal_down(self):
        assert simple_list_move(5, 2, 1) == 3

    def test_normal_up(self):
        assert simple_list_move(5, 2, -1) == 1

    def test_single_item(self):
        assert simple_list_move(1, 0, 1) == 0
        assert simple_list_move(1, 0, -1) == 0

    def test_empty_list(self):
        assert simple_list_move(0, 0, 1) == 0


# ---------------------------------------------------------------------------
# GlobalSearchDialog wrap tests
# ---------------------------------------------------------------------------


class TestGlobalSearchNavigation:
    """Tests for GlobalSearchDialog._move_selection (filtered result rows only)."""

    def test_wrap_down(self):
        result_indices = [0, 1, 2, 3]
        assert global_search_move(result_indices, 3, 1) == 0

    def test_wrap_up(self):
        result_indices = [0, 1, 2, 3]
        assert global_search_move(result_indices, 0, -1) == 3

    def test_empty_results(self):
        assert global_search_move([], 0, 1) == 0


# ---------------------------------------------------------------------------
# Source code audits: ensure all popups follow required patterns
# ---------------------------------------------------------------------------

POPUP_SRC = os.path.join(os.path.dirname(__file__), "..", "..", "src", "popups")


def _read_source(filename):
    """Read a source file from the popups directory."""
    path = os.path.join(POPUP_SRC, filename)
    with open(path) as f:
        return f.read()


class TestPopupSourceCodeContracts:
    """Scan popup source code to enforce architectural invariants."""

    def test_nvim_popup_uses_capture_phase(self):
        """NvimPopup key controller must use CAPTURE propagation phase."""
        source = _read_source("nvim_popup.py")
        assert "PropagationPhase.CAPTURE" in source, (
            "NvimPopup._setup_keyboard must set propagation phase to CAPTURE "
            "so arrow key wrap-around works before GTK ListBox handles them"
        )

    @pytest.mark.parametrize(
        "filename",
        [
            "selection_dialog.py",
            "nvim_context_menu.py",
            "quick_open_dialog.py",
            "command_palette_dialog.py",
            "global_search_dialog.py",
        ],
    )
    def test_move_selection_uses_modulo_wrap(self, filename):
        """All popup _move_selection methods must use modulo (%) for wrap-around."""
        source = _read_source(filename)
        tree = ast.parse(source)

        found_move_selection = False
        uses_modulo = False

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name == "_move_selection":
                    found_move_selection = True
                    # Check for Mod (%) operator in the function body
                    for child in ast.walk(node):
                        if isinstance(child, ast.BinOp) and isinstance(child.op, ast.Mod):
                            uses_modulo = True
                            break

        assert found_move_selection, f"{filename} must define _move_selection"
        assert uses_modulo, f"{filename}._move_selection must use modulo (%) for wrap-around navigation"

    @pytest.mark.parametrize(
        "filename",
        [
            "selection_dialog.py",
            "nvim_context_menu.py",
            "quick_open_dialog.py",
            "command_palette_dialog.py",
            "global_search_dialog.py",
        ],
    )
    def test_popup_inherits_nvim_popup(self, filename):
        """All nvim-mode popups must inherit from NvimPopup."""
        source = _read_source(filename)
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Check if any base class references NvimPopup
                for base in node.bases:
                    if isinstance(base, ast.Name) and base.id == "NvimPopup":
                        return  # Found it
                    if isinstance(base, ast.Attribute) and base.attr == "NvimPopup":
                        return

        pytest.fail(f"{filename} must contain a class inheriting from NvimPopup")

    @pytest.mark.parametrize(
        "filename",
        [
            "selection_dialog.py",
            "nvim_context_menu.py",
        ],
    )
    def test_move_selection_skips_disabled_items(self, filename):
        """Popups with disabled/separator items must skip them during navigation."""
        source = _read_source(filename)
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name == "_move_selection":
                    # Should have a loop (for or while) to skip disabled items
                    has_loop = any(isinstance(child, (ast.For, ast.While)) for child in ast.walk(node))
                    assert has_loop, f"{filename}._move_selection must loop to skip disabled/separator items"
                    return

        pytest.fail(f"{filename} must define _move_selection")

    def test_system_context_menu_uses_modulo(self):
        """SystemContextMenu._move_selection must also use modulo wrapping."""
        source = _read_source("system_dialogs.py")
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "SystemContextMenu":
                for method in ast.walk(node):
                    if isinstance(method, ast.FunctionDef) and method.name == "_move_selection":
                        for child in ast.walk(method):
                            if isinstance(child, ast.BinOp) and isinstance(child.op, ast.Mod):
                                return
                        pytest.fail("SystemContextMenu._move_selection must use modulo for wrap-around")
                return

    def test_system_command_palette_uses_modulo(self):
        """SystemCommandPaletteDialog._move_selection must use modulo wrapping."""
        source = _read_source("system_dialogs.py")
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "SystemCommandPaletteDialog":
                for method in ast.walk(node):
                    if isinstance(method, ast.FunctionDef) and method.name == "_move_selection":
                        for child in ast.walk(method):
                            if isinstance(child, ast.BinOp) and isinstance(child.op, ast.Mod):
                                return
                        pytest.fail("SystemCommandPaletteDialog._move_selection must use modulo for wrap-around")
                return


# ---------------------------------------------------------------------------
# Consistency: all popups handle both j/k AND arrow keys
# ---------------------------------------------------------------------------


class TestKeyBindingConsistency:
    """Ensure all list-based popups handle both j/k and Up/Down arrow keys."""

    @pytest.mark.parametrize(
        "filename",
        [
            "selection_dialog.py",
            "nvim_context_menu.py",
            "quick_open_dialog.py",
            "global_search_dialog.py",
        ],
    )
    def test_handles_jk_and_arrows(self, filename):
        """Popups must handle j/k AND Up/Down for navigation."""
        source = _read_source(filename)
        assert "KEY_j" in source or "KEY_Down" in source, f"{filename} must handle Down/j"
        assert "KEY_k" in source or "KEY_Up" in source, f"{filename} must handle Up/k"
        assert "KEY_Down" in source, f"{filename} must handle Down arrow"
        assert "KEY_Up" in source, f"{filename} must handle Up arrow"
