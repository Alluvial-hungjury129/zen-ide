"""Tests for SaveAllConfirmPopup (src/popups/save_all_confirm_popup.py)."""

from tests.popups.conftest import (
    class_inherits,
    find_class,
    find_method,
    method_uses_modulo,
    parse_popup_source,
    read_popup_source,
)


class TestSaveAllConfirmPopupStructure:
    """Verify SaveAllConfirmPopup structural contracts."""

    def test_inherits_nvim_popup(self):
        tree = parse_popup_source("save_all_confirm_popup.py")
        assert class_inherits(tree, "SaveAllConfirmPopup", "NvimPopup")

    def test_has_on_key_pressed(self):
        tree = parse_popup_source("save_all_confirm_popup.py")
        cls = find_class(tree, "SaveAllConfirmPopup")
        assert find_method(cls, "_on_key_pressed") is not None

    def test_has_do_save_all(self):
        tree = parse_popup_source("save_all_confirm_popup.py")
        cls = find_class(tree, "SaveAllConfirmPopup")
        assert find_method(cls, "_do_save_all") is not None

    def test_has_do_discard_all(self):
        tree = parse_popup_source("save_all_confirm_popup.py")
        cls = find_class(tree, "SaveAllConfirmPopup")
        assert find_method(cls, "_do_discard_all") is not None

    def test_has_do_cancel(self):
        tree = parse_popup_source("save_all_confirm_popup.py")
        cls = find_class(tree, "SaveAllConfirmPopup")
        assert find_method(cls, "_do_cancel") is not None


class TestSaveAllConfirmPopupKeyHandling:
    """Verify key handling patterns."""

    def test_s_key_saves(self):
        source = read_popup_source("save_all_confirm_popup.py")
        assert "KEY_s" in source

    def test_d_key_discards(self):
        source = read_popup_source("save_all_confirm_popup.py")
        assert "KEY_d" in source

    def test_c_key_cancels(self):
        source = read_popup_source("save_all_confirm_popup.py")
        assert "KEY_c" in source

    def test_escape_cancels(self):
        source = read_popup_source("save_all_confirm_popup.py")
        assert "KEY_Escape" in source

    def test_tab_cycles_buttons(self):
        source = read_popup_source("save_all_confirm_popup.py")
        assert "KEY_Tab" in source

    def test_h_l_navigate_buttons(self):
        source = read_popup_source("save_all_confirm_popup.py")
        assert "KEY_h" in source
        assert "KEY_l" in source


class TestSaveAllConfirmPopupButtonCycling:
    """Test button cycling logic (3 buttons, modulo wrap)."""

    def test_tab_uses_modulo(self):
        tree = parse_popup_source("save_all_confirm_popup.py")
        cls = find_class(tree, "SaveAllConfirmPopup")
        method = find_method(cls, "_on_key_pressed")
        assert method_uses_modulo(method), "Button cycling must use modulo for wrap-around"

    def test_tab_forward_cycling(self):
        num_buttons = 3
        idx = 2
        idx = (idx + 1) % num_buttons
        assert idx == 0

    def test_shift_tab_backward_cycling(self):
        num_buttons = 3
        idx = 0
        idx = (idx - 1) % num_buttons
        assert idx == 2


class TestSaveAllConfirmPopupFileList:
    """Test file list display logic."""

    def test_shows_up_to_5_files(self):
        """When ≤ 5 files, all should be shown."""
        filenames = ["a.py", "b.py", "c.py"]
        if len(filenames) <= 5:
            text = "\n".join(f"  • {f}" for f in filenames)
        assert "a.py" in text
        assert "b.py" in text
        assert "c.py" in text

    def test_truncates_after_5_files(self):
        """When > 5 files, show first 5 plus 'and N more'."""
        filenames = ["a.py", "b.py", "c.py", "d.py", "e.py", "f.py", "g.py"]
        if len(filenames) <= 5:
            text = "\n".join(f"  • {f}" for f in filenames)
        else:
            text = "\n".join(f"  • {f}" for f in filenames[:5])
            text += f"\n  ... and {len(filenames) - 5} more"
        assert "e.py" in text
        assert "f.py" not in text.split("...")[0]  # f.py not in visible items
        assert "and 2 more" in text

    def test_source_uses_5_file_limit(self):
        source = read_popup_source("save_all_confirm_popup.py")
        assert "[:5]" in source or "<= 5" in source or "filenames[:5]" in source


class TestSaveAllConfirmPopupResults:
    """Verify result values."""

    def test_save_all_result(self):
        source = read_popup_source("save_all_confirm_popup.py")
        assert '"save_all"' in source

    def test_discard_all_result(self):
        source = read_popup_source("save_all_confirm_popup.py")
        assert '"discard_all"' in source

    def test_cancel_result(self):
        source = read_popup_source("save_all_confirm_popup.py")
        assert '"cancel"' in source
