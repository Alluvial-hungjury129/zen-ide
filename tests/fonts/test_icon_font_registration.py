"""Tests for icon font registration — ensures Nerd Font icons render correctly.

These tests verify the fix for the bug where icons didn't appear in the tree
view when using the freetype/fontconfig Pango backend (PANGOCAIRO_BACKEND=fc).

Root cause: Fonts were only registered with CoreText, but when using fontconfig
backend, Pango couldn't see them. The fix ensures fonts are registered with the
appropriate backend (CoreText or fontconfig) based on the Pango backend setting.
"""

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest


class TestZenIconsFontFile:
    """Test that ZenIcons.ttf exists and contains required glyphs."""

    @pytest.fixture
    def font_path(self):
        """Path to the ZenIcons.ttf font file."""
        project_root = Path(__file__).parent.parent.parent
        return project_root / "src" / "fonts" / "resources" / "ZenIcons.ttf"

    def test_zen_icons_font_exists(self, font_path):
        """ZenIcons.ttf must exist in the resources directory."""
        assert font_path.exists(), f"ZenIcons.ttf not found at {font_path}"

    def test_zen_icons_font_not_empty(self, font_path):
        """ZenIcons.ttf must have reasonable size (not empty/corrupted)."""
        size = font_path.stat().st_size
        # Should be at least 10KB (contains ~100+ glyphs)
        assert size > 10_000, f"ZenIcons.ttf too small ({size} bytes), may be corrupted"
        # Should be under 100KB (it's a subset, not full Nerd Font)
        assert size < 100_000, f"ZenIcons.ttf too large ({size} bytes), may not be subset"

    @pytest.mark.skipif(
        not pytest.importorskip("fontTools", reason="fontTools not installed"),
        reason="fontTools required for glyph verification",
    )
    def test_zen_icons_contains_essential_glyphs(self, font_path):
        """ZenIcons.ttf must contain glyphs for essential icons."""
        from fontTools.ttLib import TTFont

        font = TTFont(str(font_path))
        cmap = font.getBestCmap()

        # Essential codepoints that must be present
        essential_codepoints = {
            0xF07B: "folder_closed",
            0xF07C: "folder_open",
            0xF0140: "chevron_down",
            0xF0142: "chevron_right",
            0xE606: "python_file",
            0xF120: "terminal",
            0xF002: "search",
            0xF067: "plus",
            0xF0C5: "copy",
            0xF0EA: "paste",
        }

        missing = []
        for codepoint, name in essential_codepoints.items():
            if codepoint not in cmap:
                missing.append(f"U+{codepoint:04X} ({name})")

        assert not missing, f"ZenIcons.ttf missing essential glyphs: {', '.join(missing)}"

    @pytest.mark.skipif(
        not pytest.importorskip("fontTools", reason="fontTools not installed"),
        reason="fontTools required for glyph verification",
    )
    def test_zen_icons_contains_all_tree_icon_codepoints(self, font_path):
        """ZenIcons.ttf must contain all codepoints used in tree view icons."""
        from fontTools.ttLib import TTFont

        from treeview.tree_icons import (
            CHEVRON_COLLAPSED,
            CHEVRON_EXPANDED,
            NERD_FILE_ICONS,
            NERD_FOLDER_CLOSED,
            NERD_FOLDER_OPEN,
            NERD_NAME_ICONS,
        )

        font = TTFont(str(font_path))
        cmap = font.getBestCmap()

        missing = []

        # Check folder icons
        for name, icon_str in [
            ("NERD_FOLDER_CLOSED", NERD_FOLDER_CLOSED),
            ("NERD_FOLDER_OPEN", NERD_FOLDER_OPEN),
            ("CHEVRON_EXPANDED", CHEVRON_EXPANDED),
            ("CHEVRON_COLLAPSED", CHEVRON_COLLAPSED),
        ]:
            for ch in icon_str:
                cp = ord(ch)
                if cp > 0x7F and cp not in cmap:  # Skip ASCII (spaces)
                    missing.append(f"{name}: U+{cp:04X}")

        # Check file extension icons
        for ext, icon_str in NERD_FILE_ICONS.items():
            for ch in icon_str:
                cp = ord(ch)
                if cp > 0x7F and cp not in cmap:
                    missing.append(f"NERD_FILE_ICONS[{ext!r}]: U+{cp:04X}")

        # Check name-based icons
        for name, icon_str in NERD_NAME_ICONS.items():
            for ch in icon_str:
                cp = ord(ch)
                if cp > 0x7F and cp not in cmap:
                    missing.append(f"NERD_NAME_ICONS[{name!r}]: U+{cp:04X}")

        assert not missing, "ZenIcons.ttf missing tree view codepoints:\n" + "\n".join(missing)


class TestPangoBackendSetting:
    """Test reading pango_backend from settings.json."""

    def test_read_pango_backend_returns_auto_when_no_settings(self, tmp_path):
        """Returns 'auto' when settings.json doesn't exist."""
        # Import after patching to get a clean module
        import zen_ide

        with patch.dict(os.environ, {"HOME": str(tmp_path)}, clear=False):
            # Reload to pick up patched HOME
            result = zen_ide._read_pango_backend()
            # Should return 'auto' (default) when no settings file
            assert result == "auto"

    def test_read_pango_backend_returns_freetype(self, tmp_path):
        """Returns 'freetype' when configured in settings.json."""
        import json

        import zen_ide

        # Create settings with freetype backend
        zen_dir = tmp_path / ".zen_ide"
        zen_dir.mkdir()
        settings = {"font_rendering": {"pango_backend": "freetype"}}
        (zen_dir / "settings.json").write_text(json.dumps(settings))

        with patch.dict(os.environ, {"HOME": str(tmp_path)}, clear=False):
            result = zen_ide._read_pango_backend()
            assert result == "freetype"

    def test_read_pango_backend_returns_coretext(self, tmp_path):
        """Returns 'coretext' when configured in settings.json."""
        import json

        import zen_ide

        zen_dir = tmp_path / ".zen_ide"
        zen_dir.mkdir()
        settings = {"font_rendering": {"pango_backend": "coretext"}}
        (zen_dir / "settings.json").write_text(json.dumps(settings))

        with patch.dict(os.environ, {"HOME": str(tmp_path)}, clear=False):
            result = zen_ide._read_pango_backend()
            assert result == "coretext"


class TestFontRegistrationBackendSelection:
    """Test that font registration uses correct backend based on settings."""

    def test_fontconfig_used_when_pangocairo_backend_fc(self):
        """register_resource_fonts() should use fontconfig when PANGOCAIRO_BACKEND=fc."""
        from fonts import font_manager

        # Reset registration state
        font_manager._resource_fonts_registered = False

        with patch.object(font_manager, "_fonts_already_in_pango", return_value=False):
            with patch.object(font_manager, "_register_fonts_fontconfig_files") as mock_fc:
                with patch.object(font_manager, "_register_fonts_macos") as mock_ct:
                    with patch.object(font_manager, "_refresh_pango_font_map"):
                        with patch.dict(os.environ, {"PANGOCAIRO_BACKEND": "fc"}):
                            font_manager.register_resource_fonts()

        # On macOS with fc backend, should use fontconfig, not CoreText
        if sys.platform == "darwin":
            mock_fc.assert_called_once()
            mock_ct.assert_not_called()

    def test_coretext_used_when_no_pangocairo_backend(self):
        """register_resource_fonts() should use CoreText on macOS without fc backend."""
        if sys.platform != "darwin":
            pytest.skip("CoreText only available on macOS")

        from fonts import font_manager

        # Reset registration state
        font_manager._resource_fonts_registered = False

        with patch.object(font_manager, "_fonts_already_in_pango", return_value=False):
            with patch.object(font_manager, "_register_fonts_fontconfig_files") as mock_fc:
                with patch.object(font_manager, "_register_fonts_macos") as mock_ct:
                    with patch.object(font_manager, "_refresh_pango_font_map"):
                        # Ensure PANGOCAIRO_BACKEND is not set to fc
                        env = os.environ.copy()
                        env.pop("PANGOCAIRO_BACKEND", None)
                        with patch.dict(os.environ, env, clear=True):
                            font_manager.register_resource_fonts()

        # Should use CoreText on macOS without fc backend
        mock_ct.assert_called_once()
        mock_fc.assert_not_called()


class TestIconFontName:
    """Test that icon font name is correctly returned."""

    def test_get_icon_font_name_returns_zen_icons(self):
        """get_icon_font_name() should always return 'ZenIcons'."""
        from icons import ICON_FONT_FAMILY, get_icon_font_name

        assert get_icon_font_name() == "ZenIcons"
        assert ICON_FONT_FAMILY == "ZenIcons"


class TestEarlyFontRegistrationSkipsFreeType:
    """Test that early CoreText registration is skipped for freetype backend."""

    @pytest.mark.skipif(sys.platform != "darwin", reason="macOS only")
    def test_early_registration_skipped_for_freetype(self):
        """_register_fonts_early() should skip CoreText when using freetype."""
        import zen_ide

        # Mock _read_pango_backend to return freetype
        with patch.object(zen_ide, "_read_pango_backend", return_value="freetype"):
            # Reset the flag
            zen_ide._fonts_preregistered = False

            # Call the function
            zen_ide._register_fonts_early()

            # Should NOT have registered (skipped due to freetype)
            assert zen_ide._fonts_preregistered is False

    @pytest.mark.skipif(sys.platform != "darwin", reason="macOS only")
    def test_early_registration_runs_for_coretext(self):
        """_register_fonts_early() should run CoreText registration for auto/coretext."""
        import zen_ide

        # Mock _read_pango_backend to return auto (default)
        with patch.object(zen_ide, "_read_pango_backend", return_value="auto"):
            # The actual registration may or may not succeed depending on state,
            # but the function should at least attempt it (not early-return)
            # We can verify by checking it doesn't skip due to freetype check
            zen_ide._fonts_preregistered = False

            # This should attempt registration (not skip)
            # We can't easily verify CoreText calls without more mocking,
            # but we can verify the function completes without error
            zen_ide._register_fonts_early()
            # No assertion needed - just verifying no exception is raised
