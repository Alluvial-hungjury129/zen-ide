"""Tests for shared.utils."""

from shared.utils import (
    blend_hex_colors,
    contrast_color,
    contrast_ratio,
    display_width,
    ensure_full_path,
    ensure_text_contrast,
    find_word_boundary_left,
    find_word_boundary_right,
    hex_to_rgb,
    hex_to_rgb_float,
    hex_to_rgba,
    hex_to_rgba_css,
    relative_luminance,
    sanitize_font_for_vte,
)


class TestHexToRgba:
    def test_black(self):
        assert hex_to_rgba("#000000") == (0.0, 0.0, 0.0, 1.0)

    def test_white(self):
        assert hex_to_rgba("#ffffff") == (1.0, 1.0, 1.0, 1.0)

    def test_red(self):
        r, g, b, a = hex_to_rgba("#ff0000")
        assert r == 1.0
        assert g == 0.0
        assert b == 0.0
        assert a == 1.0

    def test_custom_alpha(self):
        _, _, _, a = hex_to_rgba("#abcdef", alpha=0.5)
        assert a == 0.5

    def test_without_hash(self):
        assert hex_to_rgba("ff8800") == hex_to_rgba("#ff8800")


class TestHexToRgb:
    def test_black(self):
        assert hex_to_rgb("#000000") == (0, 0, 0)

    def test_white(self):
        assert hex_to_rgb("#ffffff") == (255, 255, 255)

    def test_red(self):
        assert hex_to_rgb("#ff0000") == (255, 0, 0)

    def test_without_hash(self):
        assert hex_to_rgb("00ff00") == (0, 255, 0)

    def test_mixed(self):
        assert hex_to_rgb("#1a2b3c") == (26, 43, 60)


class TestHexToRgbFloat:
    def test_black(self):
        assert hex_to_rgb_float("#000000") == (0.0, 0.0, 0.0)

    def test_white(self):
        assert hex_to_rgb_float("#ffffff") == (1.0, 1.0, 1.0)

    def test_without_hash(self):
        r, g, b = hex_to_rgb_float("ff0000")
        assert r == 1.0
        assert g == 0.0
        assert b == 0.0

    def test_malformed_returns_default(self):
        assert hex_to_rgb_float("#abc") == (0.15, 0.15, 0.15)

    def test_empty_returns_default(self):
        assert hex_to_rgb_float("") == (0.15, 0.15, 0.15)


class TestHexToRgbaCss:
    def test_basic(self):
        assert hex_to_rgba_css("#ff0000") == "rgba(255, 0, 0, 1.0)"

    def test_with_alpha(self):
        assert hex_to_rgba_css("#00ff00", alpha=0.5) == "rgba(0, 255, 0, 0.5)"

    def test_without_hash(self):
        assert hex_to_rgba_css("0000ff", alpha=0.8) == "rgba(0, 0, 255, 0.8)"


class TestContrastColor:
    def test_white_bg_returns_black(self):
        assert contrast_color("#ffffff") == "#000000"

    def test_black_bg_returns_white(self):
        assert contrast_color("#000000") == "#ffffff"

    def test_light_bg_returns_black(self):
        assert contrast_color("#cccccc") == "#000000"

    def test_dark_bg_returns_white(self):
        assert contrast_color("#333333") == "#ffffff"


class TestColorContrastHelpers:
    def test_blend_hex_colors_midpoint(self):
        assert blend_hex_colors("#000000", "#ffffff", 0.5) == "#808080"

    def test_relative_luminance_orders_light_over_dark(self):
        assert relative_luminance("#ffffff") > relative_luminance("#111111")

    def test_contrast_ratio_is_high_for_black_on_white(self):
        assert contrast_ratio("#000000", "#ffffff") > 20

    def test_ensure_text_contrast_darkens_light_accent_for_white_text(self):
        adjusted = ensure_text_contrast("#89b4fa", "#ffffff")
        assert adjusted != "#89b4fa"
        assert contrast_ratio(adjusted, "#ffffff") >= 4.5

    def test_ensure_text_contrast_preserves_already_accessible_color(self):
        assert ensure_text_contrast("#1d4ed8", "#ffffff") == "#1d4ed8"


class TestSanitizeFontForVte:
    def test_empty_string(self):
        assert sanitize_font_for_vte("") == ""

    def test_regular_font_unchanged(self):
        assert sanitize_font_for_vte("Monospace") == "Monospace"

    def test_propo_converted_to_mono(self):
        assert sanitize_font_for_vte("FiraCode Nerd Font Propo") == "FiraCode Nerd Font Mono"

    def test_nerd_font_gets_mono_suffix(self):
        assert sanitize_font_for_vte("Hack Nerd Font") == "Hack Nerd Font Mono"

    def test_nerd_font_mono_unchanged(self):
        assert sanitize_font_for_vte("Hack Nerd Font Mono") == "Hack Nerd Font Mono"

    def test_saucecodepro_exception(self):
        assert sanitize_font_for_vte("SauceCodePro Nerd Font") == "SauceCodePro Nerd Font"


class TestEnsureFullPath:
    def test_adds_missing_dirs(self):
        env = {"PATH": "/usr/bin"}
        result = ensure_full_path(env)
        assert "/opt/homebrew/bin" in result["PATH"]
        assert "/usr/local/bin" in result["PATH"]

    def test_does_not_duplicate_existing(self):
        env = {"PATH": "/opt/homebrew/bin:/usr/bin"}
        result = ensure_full_path(env)
        assert result["PATH"].count("/opt/homebrew/bin") == 1

    def test_empty_path(self):
        env = {"PATH": ""}
        result = ensure_full_path(env)
        assert "/opt/homebrew/bin" in result["PATH"]

    def test_missing_path_key(self):
        env = {}
        result = ensure_full_path(env)
        assert "PATH" in result


class TestFindWordBoundaryLeft:
    def test_underscore_treated_as_word_char(self):
        assert find_word_boundary_left("$ message_id", 12) == 2

    def test_stops_at_whitespace(self):
        assert find_word_boundary_left("hello world", 11) == 6

    def test_at_start(self):
        assert find_word_boundary_left("hello", 0) == 0

    def test_skips_trailing_whitespace(self):
        assert find_word_boundary_left("hello  ", 7) == 0

    def test_multiple_underscores(self):
        assert find_word_boundary_left("a_b_c_d", 7) == 0

    def test_mixed_punctuation(self):
        # dot is not a word char, so stops at boundary
        assert find_word_boundary_left("file.txt", 8) == 5

    def test_from_middle(self):
        assert find_word_boundary_left("$ message_id", 9) == 2


class TestFindWordBoundaryRight:
    def test_underscore_treated_as_word_char(self):
        assert find_word_boundary_right("$ message_id", 2) == 12

    def test_stops_at_whitespace(self):
        assert find_word_boundary_right("hello world", 0) == 5

    def test_at_end(self):
        assert find_word_boundary_right("hello", 5) == 5

    def test_skips_leading_whitespace(self):
        assert find_word_boundary_right("  hello", 0) == 7

    def test_multiple_underscores(self):
        assert find_word_boundary_right("a_b_c_d end", 0) == 7

    def test_mixed_punctuation(self):
        assert find_word_boundary_right("file.txt", 0) == 4


class TestDisplayWidth:
    """Tests for terminal display width calculation."""

    def test_ascii(self):
        assert display_width("hello") == 5

    def test_empty(self):
        assert display_width("") == 0

    def test_wide_emoji(self):
        assert display_width("✅") == 2
        assert display_width("❌") == 2

    def test_narrow_symbols(self):
        assert display_width("→") == 1
        assert display_width("—") == 1
        assert display_width("✓") == 1

    def test_box_drawing(self):
        assert display_width("│") == 1
        assert display_width("─") == 1
        assert display_width("┌┐") == 2

    def test_mixed_content(self):
        # "text ✅ more" = 4 + 1 + 2 + 1 + 4 = 12
        assert display_width("text ✅ more") == 12

    def test_combining_marks_skipped(self):
        # e + combining acute accent = 1 visible character
        assert display_width("e\u0301") == 1
