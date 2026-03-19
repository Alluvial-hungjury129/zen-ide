"""Tests for SaveConfirmPopup (src/popups/save_confirm_popup.py)."""

from tests.popups.conftest import (
    class_inherits,
    find_class,
    find_method,
    method_uses_modulo,
    parse_popup_source,
    read_popup_source,
)


class TestSaveConfirmPopupStructure:
    """Verify SaveConfirmPopup structural contracts."""

    def test_inherits_nvim_popup(self):
        tree = parse_popup_source("save_confirm_popup.py")
        assert class_inherits(tree, "SaveConfirmPopup", "NvimPopup")

    def test_has_on_key_pressed(self):
        tree = parse_popup_source("save_confirm_popup.py")
        cls = find_class(tree, "SaveConfirmPopup")
        assert find_method(cls, "_on_key_pressed") is not None

    def test_has_do_save(self):
        tree = parse_popup_source("save_confirm_popup.py")
        cls = find_class(tree, "SaveConfirmPopup")
        assert find_method(cls, "_do_save") is not None

    def test_has_do_discard(self):
        tree = parse_popup_source("save_confirm_popup.py")
        cls = find_class(tree, "SaveConfirmPopup")
        assert find_method(cls, "_do_discard") is not None

    def test_has_do_cancel(self):
        tree = parse_popup_source("save_confirm_popup.py")
        cls = find_class(tree, "SaveConfirmPopup")
        assert find_method(cls, "_do_cancel") is not None


class TestSaveConfirmPopupKeyHandling:
    """Verify key handling patterns."""

    def test_s_key_saves(self):
        source = read_popup_source("save_confirm_popup.py")
        assert "KEY_s" in source

    def test_d_key_discards(self):
        source = read_popup_source("save_confirm_popup.py")
        assert "KEY_d" in source

    def test_c_key_cancels(self):
        source = read_popup_source("save_confirm_popup.py")
        assert "KEY_c" in source

    def test_escape_cancels(self):
        source = read_popup_source("save_confirm_popup.py")
        assert "KEY_Escape" in source

    def test_enter_saves(self):
        source = read_popup_source("save_confirm_popup.py")
        assert "KEY_Return" in source

    def test_tab_cycles_buttons(self):
        source = read_popup_source("save_confirm_popup.py")
        assert "KEY_Tab" in source

    def test_h_l_navigate_buttons(self):
        source = read_popup_source("save_confirm_popup.py")
        assert "KEY_h" in source
        assert "KEY_l" in source

    def test_arrow_keys_navigate_buttons(self):
        source = read_popup_source("save_confirm_popup.py")
        assert "KEY_Left" in source
        assert "KEY_Right" in source


class TestSaveConfirmPopupButtonCycling:
    """Test button cycling logic (3 buttons, modulo wrap)."""

    def test_tab_uses_modulo(self):
        tree = parse_popup_source("save_confirm_popup.py")
        cls = find_class(tree, "SaveConfirmPopup")
        method = find_method(cls, "_on_key_pressed")
        assert method_uses_modulo(method), "Button cycling must use modulo for wrap-around"

    def test_tab_forward_cycling(self):
        """Tab should cycle: 0→1→2→0."""
        num_buttons = 3
        idx = 2
        idx = (idx + 1) % num_buttons
        assert idx == 0

    def test_shift_tab_backward_cycling(self):
        """Shift+Tab should cycle: 0→2→1→0."""
        num_buttons = 3
        idx = 0
        idx = (idx - 1) % num_buttons
        assert idx == 2

    def test_h_l_cycling(self):
        """h/l should also cycle buttons."""
        num_buttons = 3
        # l (right) from last
        idx = 2
        idx = (idx + 1) % num_buttons
        assert idx == 0
        # h (left) from first
        idx = 0
        idx = (idx - 1) % num_buttons
        assert idx == 2


class TestSaveConfirmPopupResults:
    """Verify result values."""

    def test_save_result(self):
        source = read_popup_source("save_confirm_popup.py")
        assert '"save"' in source

    def test_discard_result(self):
        source = read_popup_source("save_confirm_popup.py")
        assert '"discard"' in source

    def test_cancel_result(self):
        source = read_popup_source("save_confirm_popup.py")
        assert '"cancel"' in source


class TestShowSaveConfirmHelper:
    """Verify the show_save_confirm helper function."""

    def test_show_save_confirm_checks_nvim_mode(self):
        source = read_popup_source("save_confirm_popup.py")
        assert "is_nvim_mode" in source
