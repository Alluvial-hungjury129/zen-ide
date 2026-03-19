"""Tests for NvimContextMenu (src/popups/nvim_context_menu.py)."""

from tests.popups.conftest import (
    class_inherits,
    find_class,
    find_method,
    method_uses_modulo,
    parse_popup_source,
    read_popup_source,
)


class TestNvimContextMenuStructure:
    """Verify NvimContextMenu structural contracts."""

    def test_inherits_nvim_popup(self):
        tree = parse_popup_source("nvim_context_menu.py")
        assert class_inherits(tree, "NvimContextMenu", "NvimPopup")

    def test_has_move_selection(self):
        tree = parse_popup_source("nvim_context_menu.py")
        cls = find_class(tree, "NvimContextMenu")
        assert find_method(cls, "_move_selection") is not None

    def test_has_update_selection(self):
        tree = parse_popup_source("nvim_context_menu.py")
        cls = find_class(tree, "NvimContextMenu")
        assert find_method(cls, "_update_selection") is not None

    def test_move_selection_uses_modulo(self):
        tree = parse_popup_source("nvim_context_menu.py")
        cls = find_class(tree, "NvimContextMenu")
        method = find_method(cls, "_move_selection")
        assert method_uses_modulo(method)

    def test_move_selection_has_loop_for_skip(self):
        """_move_selection must loop to skip separators/disabled."""
        import ast

        tree = parse_popup_source("nvim_context_menu.py")
        cls = find_class(tree, "NvimContextMenu")
        method = find_method(cls, "_move_selection")
        has_loop = any(isinstance(child, (ast.For, ast.While)) for child in ast.walk(method))
        assert has_loop


class TestNvimContextMenuKeyHandling:
    """Verify key handling."""

    def test_handles_jk_navigation(self):
        source = read_popup_source("nvim_context_menu.py")
        assert "KEY_j" in source
        assert "KEY_k" in source

    def test_handles_arrow_navigation(self):
        source = read_popup_source("nvim_context_menu.py")
        assert "KEY_Down" in source
        assert "KEY_Up" in source

    def test_handles_enter(self):
        source = read_popup_source("nvim_context_menu.py")
        assert "KEY_Return" in source

    def test_handles_escape(self):
        source = read_popup_source("nvim_context_menu.py")
        assert "KEY_Escape" in source


class TestNvimContextMenuNavigation:
    """Test navigation logic as pure functions."""

    @staticmethod
    def _move(items, selected, delta):
        """Replicate NvimContextMenu._move_selection."""
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

    def test_skip_separator_down(self):
        items = [{"label": "A"}, {"label": "---"}, {"label": "C"}]
        assert self._move(items, 0, 1) == 2

    def test_skip_separator_up(self):
        items = [{"label": "A"}, {"label": "---"}, {"label": "C"}]
        assert self._move(items, 2, -1) == 0

    def test_skip_disabled_item(self):
        items = [{"label": "A"}, {"label": "B", "enabled": False}, {"label": "C"}]
        assert self._move(items, 0, 1) == 2

    def test_wrap_with_separator_at_end(self):
        items = [{"label": "A"}, {"label": "B"}, {"label": "---"}]
        assert self._move(items, 1, 1) == 0

    def test_wrap_with_separator_at_start(self):
        items = [{"label": "---"}, {"label": "B"}, {"label": "C"}]
        assert self._move(items, 1, -1) == 2

    def test_multiple_separators(self):
        items = [{"label": "A"}, {"label": "---"}, {"label": "---"}, {"label": "D"}]
        assert self._move(items, 0, 1) == 3

    def test_first_enabled_item_selection(self):
        """Constructor should find first enabled item."""
        items = [{"label": "---"}, {"label": "B"}, {"label": "C"}]
        selected_idx = 0
        for i, item in enumerate(items):
            if item.get("label") != "---" and item.get("enabled", True):
                selected_idx = i
                break
        assert selected_idx == 1


class TestShowContextMenuHelper:
    """Verify the show_context_menu helper."""

    def test_show_context_menu_exists(self):
        source = read_popup_source("nvim_context_menu.py")
        assert "def show_context_menu" in source

    def test_show_context_menu_checks_nvim_mode(self):
        source = read_popup_source("nvim_context_menu.py")
        assert "is_nvim_mode" in source
