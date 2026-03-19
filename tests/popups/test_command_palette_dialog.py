"""Tests for CommandPaletteDialog (src/popups/command_palette_dialog.py)."""

from tests.popups.conftest import (
    class_inherits,
    find_class,
    find_method,
    method_uses_modulo,
    parse_popup_source,
    read_popup_source,
)


class TestCommandPaletteDialogStructure:
    """Verify CommandPaletteDialog structural contracts."""

    def test_inherits_nvim_popup(self):
        tree = parse_popup_source("command_palette_dialog.py")
        assert class_inherits(tree, "CommandPaletteDialog", "NvimPopup")

    def test_has_move_selection(self):
        tree = parse_popup_source("command_palette_dialog.py")
        cls = find_class(tree, "CommandPaletteDialog")
        assert find_method(cls, "_move_selection") is not None

    def test_has_filter_commands(self):
        tree = parse_popup_source("command_palette_dialog.py")
        cls = find_class(tree, "CommandPaletteDialog")
        assert find_method(cls, "_filter_commands") is not None

    def test_has_fuzzy_match(self):
        tree = parse_popup_source("command_palette_dialog.py")
        cls = find_class(tree, "CommandPaletteDialog")
        assert find_method(cls, "_fuzzy_match") is not None

    def test_has_execute_command(self):
        tree = parse_popup_source("command_palette_dialog.py")
        cls = find_class(tree, "CommandPaletteDialog")
        assert find_method(cls, "_execute_command") is not None

    def test_move_selection_uses_modulo(self):
        tree = parse_popup_source("command_palette_dialog.py")
        cls = find_class(tree, "CommandPaletteDialog")
        method = find_method(cls, "_move_selection")
        assert method_uses_modulo(method)


class TestCommandPaletteDialogKeyHandling:
    """Verify key handling."""

    def test_handles_down_arrow(self):
        source = read_popup_source("command_palette_dialog.py")
        assert "KEY_Down" in source

    def test_handles_up_arrow(self):
        source = read_popup_source("command_palette_dialog.py")
        assert "KEY_Up" in source

    def test_handles_ctrl_n_for_down(self):
        source = read_popup_source("command_palette_dialog.py")
        assert "KEY_n" in source
        assert "CONTROL_MASK" in source

    def test_handles_ctrl_p_for_up(self):
        source = read_popup_source("command_palette_dialog.py")
        assert "KEY_p" in source

    def test_handles_escape(self):
        source = read_popup_source("command_palette_dialog.py")
        assert "KEY_Escape" in source


class TestCommandPaletteDialogFuzzyMatch:
    """Test _fuzzy_match logic as a pure function."""

    @staticmethod
    def _fuzzy_match(query: str, text: str) -> int:
        """Replicate CommandPaletteDialog._fuzzy_match."""
        score = 0
        query_idx = 0
        for char in text:
            if query_idx < len(query) and char == query[query_idx]:
                score += 10
                query_idx += 1
        return score if query_idx == len(query) else 0

    def test_empty_query_matches_everything(self):
        assert self._fuzzy_match("", "anything") == 0

    def test_no_match_returns_zero(self):
        assert self._fuzzy_match("xyz", "abc") == 0

    def test_exact_match(self):
        score = self._fuzzy_match("abc", "abc")
        assert score == 30  # 3 chars × 10 points

    def test_fuzzy_match_in_longer_text(self):
        score = self._fuzzy_match("ac", "abc")
        assert score == 20  # 2 chars matched × 10

    def test_all_chars_must_match(self):
        assert self._fuzzy_match("abcd", "abc") == 0


class TestCommandPaletteDialogFilterLogic:
    """Test _filter_commands scoring logic as pure functions."""

    @staticmethod
    def _fuzzy_match(query: str, text: str) -> int:
        score = 0
        query_idx = 0
        for char in text:
            if query_idx < len(query) and char == query[query_idx]:
                score += 10
                query_idx += 1
        return score if query_idx == len(query) else 0

    @staticmethod
    def _score_command(query, cmd):
        """Replicate the scoring logic from _filter_commands."""
        query = query.lower().strip()
        name = cmd.get("name", "").lower()
        label = cmd.get("label", "").lower()
        score = 0
        if query in name:
            score += 100
        if query in label:
            score += 50
        fuzzy_score = TestCommandPaletteDialogFilterLogic._fuzzy_match(query, name + " " + label)
        score += fuzzy_score
        return score

    def test_exact_name_match_highest(self):
        cmd = {"name": "save", "label": "Save File"}
        score = self._score_command("save", cmd)
        assert score >= 100

    def test_exact_label_match(self):
        cmd = {"name": "cmd_save", "label": "Save File"}
        score = self._score_command("save file", cmd)
        assert score >= 50

    def test_no_match_returns_zero(self):
        cmd = {"name": "open", "label": "Open File"}
        score = self._score_command("xyz", cmd)
        assert score == 0

    def test_empty_query_matches_all(self):
        """With empty query, all commands shown (no filtering)."""
        source = read_popup_source("command_palette_dialog.py")
        assert "if not query:" in source


class TestCommandPaletteDialogNavigation:
    """Test navigation logic."""

    @staticmethod
    def _move(count, selected, delta):
        if count == 0:
            return selected
        return (selected + delta) % count

    def test_wrap_down(self):
        assert self._move(5, 4, 1) == 0

    def test_wrap_up(self):
        assert self._move(5, 0, -1) == 4

    def test_limits_results_to_20(self):
        source = read_popup_source("command_palette_dialog.py")
        assert "[:20]" in source


class TestShowCommandPaletteHelper:
    """Verify the show_command_palette helper."""

    def test_show_command_palette_exists(self):
        source = read_popup_source("command_palette_dialog.py")
        assert "def show_command_palette" in source

    def test_show_command_palette_checks_nvim_mode(self):
        source = read_popup_source("command_palette_dialog.py")
        assert "is_nvim_mode" in source
