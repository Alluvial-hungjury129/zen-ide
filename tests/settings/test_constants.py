"""Tests for constants module."""

from constants import (
    CURSOR_ALPHA,
    DEFAULT_BOTTOM_PANEL_MIN_HEIGHT,
    DEFAULT_EDITOR_SPLIT,
    DEFAULT_FONT_SIZE,
    DEFAULT_TREE_MIN_WIDTH,
    DEFAULT_TREE_WIDTH,
    DEFAULT_WINDOW_HEIGHT,
    DEFAULT_WINDOW_WIDTH,
    DIFF_MINIMAP_WIDTH,
    FOCUS_ANIM_DURATION_MS,
    FOCUS_ANIM_STEPS,
    FOCUS_BORDER_WIDTH,
    INDENT_GUIDE_ALPHA,
    MAX_FONT_SIZE,
    MIN_FONT_SIZE,
    MINIMAP_WIDTH,
    PANEL_BUTTON_SIZE,
    STATUS_BAR_FONT_FAMILY,
    TREE_ROW_MARGIN_BOTTOM,
    TREE_ROW_MARGIN_TOP,
    TREE_SCROLL_SPEED,
)


class TestConstantsRanges:
    """Verify constants are within sensible ranges."""

    def test_window_dimensions_positive(self):
        assert DEFAULT_WINDOW_WIDTH > 0
        assert DEFAULT_WINDOW_HEIGHT > 0

    def test_font_size_range(self):
        assert MIN_FONT_SIZE > 0
        assert MAX_FONT_SIZE > MIN_FONT_SIZE
        assert MIN_FONT_SIZE <= DEFAULT_FONT_SIZE <= MAX_FONT_SIZE

    def test_tree_width_non_negative(self):
        assert DEFAULT_TREE_WIDTH >= 0
        assert DEFAULT_TREE_MIN_WIDTH >= 0

    def test_cursor_alpha_in_range(self):
        assert 0.0 <= CURSOR_ALPHA <= 1.0

    def test_indent_guide_alpha_in_range(self):
        assert 0.0 <= INDENT_GUIDE_ALPHA <= 1.0

    def test_minimap_width_positive(self):
        assert MINIMAP_WIDTH > 0
        assert DIFF_MINIMAP_WIDTH > 0

    def test_scroll_speeds_positive(self):
        assert TREE_SCROLL_SPEED > 0

    def test_panel_button_size_positive(self):
        assert PANEL_BUTTON_SIZE > 0

    def test_editor_split_positive(self):
        assert DEFAULT_EDITOR_SPLIT > 0
        assert DEFAULT_BOTTOM_PANEL_MIN_HEIGHT > 0

    def test_focus_animation_values(self):
        assert FOCUS_ANIM_DURATION_MS > 0
        assert FOCUS_ANIM_STEPS > 0
        assert FOCUS_BORDER_WIDTH > 0

    def test_tree_row_margins_non_negative(self):
        assert TREE_ROW_MARGIN_TOP >= 0
        assert TREE_ROW_MARGIN_BOTTOM >= 0

    def test_status_bar_font_family(self):
        assert STATUS_BAR_FONT_FAMILY == ""  # empty = derive from editor settings
