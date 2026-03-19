"""Tests for editor/color_preview_renderer.py - hex color parsing."""

import pytest

from editor.color_preview_renderer import _HEX_COLOR_RE, ColorPreviewRenderer


class TestParseColor:
    """Test hex color string parsing."""

    def test_six_digit_hex(self):
        r, g, b, a = ColorPreviewRenderer._parse_color("#FF0000")
        assert r == pytest.approx(1.0)
        assert g == pytest.approx(0.0)
        assert b == pytest.approx(0.0)
        assert a == pytest.approx(1.0)

    def test_six_digit_lowercase(self):
        r, g, b, a = ColorPreviewRenderer._parse_color("#00ff00")
        assert g == pytest.approx(1.0)

    def test_eight_digit_hex_with_alpha(self):
        r, g, b, a = ColorPreviewRenderer._parse_color("#FF000080")
        assert r == pytest.approx(1.0)
        assert a == pytest.approx(128 / 255.0)

    def test_three_digit_hex(self):
        r, g, b, a = ColorPreviewRenderer._parse_color("#F00")
        assert r == pytest.approx(1.0)
        assert g == pytest.approx(0.0)
        assert b == pytest.approx(0.0)
        assert a == pytest.approx(1.0)

    def test_white(self):
        r, g, b, a = ColorPreviewRenderer._parse_color("#FFFFFF")
        assert r == pytest.approx(1.0)
        assert g == pytest.approx(1.0)
        assert b == pytest.approx(1.0)

    def test_black(self):
        r, g, b, a = ColorPreviewRenderer._parse_color("#000000")
        assert r == pytest.approx(0.0)
        assert g == pytest.approx(0.0)
        assert b == pytest.approx(0.0)

    def test_invalid_returns_none(self):
        r, g, b, a = ColorPreviewRenderer._parse_color("#GGGGGG")
        assert r is None

    def test_empty_hash(self):
        r, g, b, a = ColorPreviewRenderer._parse_color("#")
        assert r is None


class TestHexColorRegex:
    """Test the hex color regex pattern."""

    def test_matches_6_digit(self):
        assert _HEX_COLOR_RE.search("color: #FF0000;") is not None

    def test_matches_3_digit(self):
        assert _HEX_COLOR_RE.search("color: #F00;") is not None

    def test_matches_8_digit(self):
        assert _HEX_COLOR_RE.search("color: #FF000080;") is not None

    def test_no_match_invalid(self):
        assert _HEX_COLOR_RE.search("color: #GG;") is None

    def test_captures_without_hash(self):
        m = _HEX_COLOR_RE.search("#AABBCC")
        assert m.group(0) == "#AABBCC"
        assert m.group(1) == "AABBCC"

    def test_multiple_colors(self):
        text = "background: #FF0000; color: #00FF00;"
        matches = _HEX_COLOR_RE.findall(text)
        assert len(matches) == 2
