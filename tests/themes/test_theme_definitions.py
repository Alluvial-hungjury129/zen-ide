"""Tests for theme definitions registry."""

from themes.theme import Theme
from themes.theme_definitions import THEMES


class TestThemeDefinitions:
    """Verify all theme definitions are valid."""

    def test_themes_dict_not_empty(self):
        """THEMES dict contains entries."""
        assert len(THEMES) > 0

    def test_all_values_are_theme_instances(self):
        """Every value in THEMES is a Theme dataclass."""
        for name, theme in THEMES.items():
            assert isinstance(theme, Theme), f"{name} is not a Theme instance"

    def test_all_keys_match_theme_name(self):
        """Dict key matches theme.name field."""
        for key, theme in THEMES.items():
            assert key == theme.name, f"Key '{key}' != theme.name '{theme.name}'"

    def test_all_themes_have_display_name(self):
        """Every theme has a non-empty display_name."""
        for name, theme in THEMES.items():
            assert theme.display_name, f"{name} has empty display_name"

    def test_known_themes_present(self):
        """Expected built-in themes exist."""
        expected = ["zen_dark", "dracula", "one_dark", "tokyonight"]
        for name in expected:
            assert name in THEMES, f"Missing expected theme: {name}"

    def test_all_themes_have_required_colors(self):
        """Every theme has non-empty required color fields."""
        required = [
            "main_bg",
            "panel_bg",
            "fg_color",
            "accent_color",
            "syntax_keyword",
            "syntax_string",
            "syntax_comment",
        ]
        for name, theme in THEMES.items():
            for field in required:
                val = getattr(theme, field, "")
                assert val, f"{name}.{field} is empty"

    def test_hex_color_format(self):
        """Color fields use valid hex format (#RRGGBB)."""
        import re

        hex_re = re.compile(r"^#[0-9a-fA-F]{6}$")
        color_fields = ["main_bg", "fg_color", "accent_color", "syntax_keyword"]
        for name, theme in THEMES.items():
            for field in color_fields:
                val = getattr(theme, field, "")
                assert hex_re.match(val), f"{name}.{field} = '{val}' is not valid hex"
