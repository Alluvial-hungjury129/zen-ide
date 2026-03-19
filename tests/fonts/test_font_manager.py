"""Tests for fonts/font_manager.py - FontManager."""

from unittest.mock import patch

from fonts.font_manager import DEFAULT_FONT, DEFAULT_FONT_WEIGHT


class TestFontManagerDefaults:
    """Test font defaults — all components use bundled Source Code Pro."""

    def _make_fm(self):
        """Create a fresh FontManager (bypassing singleton)."""
        from fonts.font_manager import FontManager

        fm = FontManager.__new__(FontManager)
        fm._initialized = False
        fm.__init__()
        return fm

    def test_default_editor_font(self):
        fm = self._make_fm()
        assert fm.get_default_editor_font() == DEFAULT_FONT

    def test_default_terminal_font(self):
        fm = self._make_fm()
        assert fm.get_default_terminal_font() == DEFAULT_FONT

    def test_default_ui_font(self):
        fm = self._make_fm()
        assert fm.get_default_ui_font() == DEFAULT_FONT

    def test_all_defaults_match(self):
        fm = self._make_fm()
        assert fm.get_default_editor_font() == fm.get_default_terminal_font() == fm.get_default_ui_font()


class TestDefaultSizeForComponent:
    """Test component-specific default font sizes."""

    def _make_fm(self):
        from fonts.font_manager import FontManager

        fm = FontManager.__new__(FontManager)
        fm._initialized = False
        fm.__init__()
        return fm

    def test_editor_default_size(self):
        fm = self._make_fm()
        assert fm.get_default_size_for_component("editor") == 16

    def test_terminal_default_size(self):
        fm = self._make_fm()
        assert fm.get_default_size_for_component("terminal") == 16

    def test_ai_chat_default_size(self):
        fm = self._make_fm()
        assert fm.get_default_size_for_component("ai_chat") == 16


class TestClampFontSize:
    """Test font size clamping."""

    def _make_fm(self):
        from fonts.font_manager import FontManager

        fm = FontManager.__new__(FontManager)
        fm._initialized = False
        fm.__init__()
        return fm

    def test_clamp_below_min(self):
        fm = self._make_fm()
        assert fm._clamp_font_size(1) == 8

    def test_clamp_above_max(self):
        fm = self._make_fm()
        assert fm._clamp_font_size(100) == 36

    def test_normal_size_unchanged(self):
        fm = self._make_fm()
        assert fm._clamp_font_size(14) == 14


class TestFontSubscriptions:
    """Test font change subscription/notification."""

    def _make_fm(self):
        from fonts.font_manager import FontManager

        fm = FontManager.__new__(FontManager)
        fm._initialized = False
        fm.__init__()
        return fm

    def test_subscribe_and_notify(self):
        fm = self._make_fm()
        calls = []
        cb = lambda comp, settings: calls.append((comp, settings))
        fm.subscribe_font_change(cb)
        fm._notify_font_change("editor", {"family": "Mono", "size": 14})
        assert len(calls) == 1
        assert calls[0][0] == "editor"

    def test_unsubscribe(self):
        fm = self._make_fm()
        calls = []
        cb = lambda comp, settings: calls.append(1)
        fm.subscribe_font_change(cb)
        fm._font_subscribers.remove(cb)
        fm._notify_font_change("editor", {})
        assert len(calls) == 0

    def test_duplicate_subscribe_ignored(self):
        fm = self._make_fm()
        calls = []
        cb = lambda comp, settings: calls.append(1)
        fm.subscribe_font_change(cb)
        fm.subscribe_font_change(cb)  # Duplicate
        fm._notify_font_change("editor", {})
        assert len(calls) == 1

    def test_notify_exception_handled(self):
        fm = self._make_fm()
        fm.subscribe_font_change(lambda c, s: 1 / 0)
        fm._notify_font_change("editor", {})  # Should not raise


class TestGetFontSettings:
    """Test font settings loading with fallback logic."""

    def _make_fm(self):
        from fonts.font_manager import FontManager

        fm = FontManager.__new__(FontManager)
        fm._initialized = False
        fm.__init__()
        return fm

    @patch("shared.settings.get_setting")
    def test_new_format(self, mock_get):
        """When fonts.editor exists, use it."""
        mock_get.return_value = {"editor": {"family": "Fira Code", "size": 15, "weight": "bold"}}
        fm = self._make_fm()
        result = fm.get_font_settings("editor")
        assert result["family"] == "Fira Code"
        assert result["size"] == 15

    @patch("shared.settings.get_setting")
    def test_old_format_ignored(self, mock_get):
        """Old format (editor.font_family) is ignored; only fonts.* is used."""

        def side_effect(key, default=None):
            if key == "fonts":
                return {}
            if key == "editor":
                return {"font_family": "Monaco", "font_size": 16}
            return default

        mock_get.side_effect = side_effect
        fm = self._make_fm()
        result = fm.get_font_settings("editor")
        # Should return defaults, not old format values
        assert result["family"] == DEFAULT_FONT
        assert result["size"] == 16
        assert result["weight"] == DEFAULT_FONT_WEIGHT

    @patch("shared.settings.get_setting")
    def test_defaults_when_no_setting(self, mock_get):
        """When no settings exist, return defaults."""
        mock_get.return_value = {}
        fm = self._make_fm()
        result = fm.get_font_settings("editor")
        assert result["family"] == DEFAULT_FONT
        assert result["size"] == 16
        assert result["weight"] == DEFAULT_FONT_WEIGHT
