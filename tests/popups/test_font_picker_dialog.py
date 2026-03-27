"""Tests for FontPickerDialog (src/popups/font_picker_dialog.py)."""

from tests.popups.conftest import (
    class_inherits,
    find_class,
    find_method,
    parse_popup_source,
    read_popup_source,
)


class TestFontPickerDialogStructure:
    """Verify FontPickerDialog structural contracts."""

    def test_inherits_nvim_popup(self):
        tree = parse_popup_source("font_picker_dialog.py")
        assert class_inherits(tree, "FontPickerDialog", "NvimPopup")

    def test_has_create_content(self):
        tree = parse_popup_source("font_picker_dialog.py")
        cls = find_class(tree, "FontPickerDialog")
        assert find_method(cls, "_create_content") is not None

    def test_has_load_current_selection(self):
        tree = parse_popup_source("font_picker_dialog.py")
        cls = find_class(tree, "FontPickerDialog")
        assert find_method(cls, "_load_current_selection") is not None

    def test_has_get_current_selection(self):
        tree = parse_popup_source("font_picker_dialog.py")
        cls = find_class(tree, "FontPickerDialog")
        assert find_method(cls, "_get_current_selection") is not None

    def test_has_apply_preview(self):
        tree = parse_popup_source("font_picker_dialog.py")
        cls = find_class(tree, "FontPickerDialog")
        assert find_method(cls, "_apply_preview") is not None

    def test_has_filter_func(self):
        tree = parse_popup_source("font_preview_mixin.py")
        cls = find_class(tree, "FontPreviewMixin")
        assert find_method(cls, "_filter_func") is not None

    def test_has_on_cancel(self):
        tree = parse_popup_source("font_picker_dialog.py")
        cls = find_class(tree, "FontPickerDialog")
        assert find_method(cls, "_on_cancel") is not None


class TestFontPickerDialogTargets:
    """Verify TARGETS constant."""

    def test_targets_constant_exists(self):
        source = read_popup_source("font_picker_dialog.py")
        assert "TARGETS" in source

    def test_has_all_target(self):
        source = read_popup_source("font_picker_dialog.py")
        assert '"all"' in source

    def test_has_editor_target(self):
        source = read_popup_source("font_picker_dialog.py")
        assert '"editor"' in source

    def test_has_terminal_target(self):
        source = read_popup_source("font_picker_dialog.py")
        assert '"terminal"' in source

    def test_has_explorer_target(self):
        source = read_popup_source("font_picker_dialog.py")
        assert '"explorer"' in source

    def test_has_ai_chat_target(self):
        source = read_popup_source("font_picker_dialog.py")
        assert '"ai_chat"' in source


class TestFontPickerDialogWeightMap:
    """Verify weight mapping."""

    def test_weight_options(self):
        source = read_popup_source("font_picker_dialog.py")
        assert '"normal"' in source


class TestFontPickerDialogKeyHandling:
    """Verify key handling."""

    def test_escape_cancels(self):
        source = read_popup_source("font_picker_dialog.py")
        assert "KEY_Escape" in source

    def test_uses_capture_phase(self):
        source = read_popup_source("font_picker_dialog.py")
        assert "PropagationPhase.CAPTURE" in source


class TestFontPickerDialogCancelRevert:
    """Verify cancel reverts to original settings."""

    def test_stores_original_settings(self):
        source = read_popup_source("font_picker_dialog.py")
        assert "original_settings" in source

    def test_cancel_reverts_settings(self):
        source = read_popup_source("font_picker_dialog.py")
        # _on_cancel should loop over original_settings
        assert "original_settings" in source
        assert "_on_cancel" in source


class TestFontPickerDialogFocusHandling:
    """Verify focus-leave override to prevent accidental close."""

    def test_overrides_focus_leave(self):
        tree = parse_popup_source("font_picker_dialog.py")
        cls = find_class(tree, "FontPickerDialog")
        assert find_method(cls, "_on_focus_leave") is not None

    def test_has_focus_check_delay(self):
        source = read_popup_source("font_picker_dialog.py")
        assert "_FOCUS_CHECK_DELAY_MS" in source


class TestFontItemClass:
    """Verify FontItem helper class."""

    def test_font_item_class_exists(self):
        tree = parse_popup_source("font_preview_mixin.py")
        assert find_class(tree, "FontItem") is not None


class TestShowFontPickerHelper:
    """Verify the show_font_picker helper."""

    def test_show_font_picker_exists(self):
        source = read_popup_source("font_picker_dialog.py")
        assert "def show_font_picker" in source
