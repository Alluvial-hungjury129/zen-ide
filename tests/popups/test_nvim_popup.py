"""Tests for NvimPopup base class (src/popups/nvim_popup.py)."""

from tests.popups.conftest import (
    class_inherits,
    find_class,
    find_method,
    parse_popup_source,
    read_popup_source,
)


class TestNvimPopupStructure:
    """Verify NvimPopup base class structural contracts."""

    def test_inherits_gtk_window(self):
        tree = parse_popup_source("nvim_popup.py")
        assert class_inherits(tree, "NvimPopup", "Window")

    def test_has_create_content_method(self):
        tree = parse_popup_source("nvim_popup.py")
        cls = find_class(tree, "NvimPopup")
        assert find_method(cls, "_create_content") is not None

    def test_has_on_key_pressed_method(self):
        tree = parse_popup_source("nvim_popup.py")
        cls = find_class(tree, "NvimPopup")
        assert find_method(cls, "_on_key_pressed") is not None

    def test_has_present_method(self):
        tree = parse_popup_source("popup_anchor_mixin.py")
        cls = find_class(tree, "PopupAnchorMixin")
        assert find_method(cls, "present") is not None

    def test_has_close_method(self):
        tree = parse_popup_source("nvim_popup.py")
        cls = find_class(tree, "NvimPopup")
        assert find_method(cls, "close") is not None

    def test_uses_capture_propagation_phase(self):
        source = read_popup_source("nvim_popup.py")
        assert "PropagationPhase.CAPTURE" in source, "NvimPopup must use CAPTURE phase for key handling"

    def test_sets_modal_and_transient(self):
        source = read_popup_source("nvim_popup.py")
        assert "set_modal(" in source
        assert "set_transient_for" in source

    def test_has_closing_guard(self):
        """close() must have a re-entrancy guard via _closing."""
        source = read_popup_source("nvim_popup.py")
        assert "_closing" in source

    def test_has_helper_factory_methods(self):
        """Base class should provide helper factories for common widgets."""
        tree = parse_popup_source("nvim_popup.py")
        cls = find_class(tree, "NvimPopup")
        helpers = [
            "_create_keybind_hint",
            "_create_hint_bar",
            "_create_message_label",
            "_create_input_entry",
            "_create_search_entry",
            "_create_scrolled_listbox",
            "_create_button",
            "_create_status_label",
        ]
        for helper in helpers:
            assert find_method(cls, helper) is not None, f"NvimPopup missing helper: {helper}"

    def test_escape_closes_popup(self):
        """Default _on_key_pressed must handle Escape."""
        source = read_popup_source("nvim_popup.py")
        assert "KEY_Escape" in source

    def test_subscribes_and_unsubscribes_theme_changes(self):
        source = read_popup_source("nvim_popup.py")
        assert "subscribe_theme_change" in source
        assert "unsubscribe_theme_change" in source

    def test_primary_button_ensures_readable_white_text(self):
        source = read_popup_source("popup_styles_mixin.py")
        assert 'ensure_text_contrast(theme.accent_color, "#ffffff")' in source
        assert "color: #ffffff;" in source
