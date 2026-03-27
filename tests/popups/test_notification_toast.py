"""Tests for NotificationToast (src/popups/notification_toast.py)."""

import ast

from tests.popups.conftest import (
    class_inherits,
    find_class,
    find_method,
    parse_popup_source,
    read_popup_source,
)


class TestNotificationToastStructure:
    """Verify NotificationToast structural contracts."""

    def test_inherits_gtk_window(self):
        """NotificationToast inherits Gtk.Window directly, NOT NvimPopup."""
        tree = parse_popup_source("notification_toast.py")
        assert class_inherits(tree, "NotificationToast", "Window")

    def test_does_not_inherit_nvim_popup(self):
        """NotificationToast should NOT inherit from NvimPopup."""
        source = read_popup_source("notification_toast.py")
        assert "NvimPopup" not in source

    def test_has_present_method(self):
        tree = parse_popup_source("notification_toast.py")
        cls = find_class(tree, "NotificationToast")
        assert find_method(cls, "present") is not None

    def test_has_on_timeout(self):
        tree = parse_popup_source("notification_toast.py")
        cls = find_class(tree, "NotificationToast")
        assert find_method(cls, "_on_timeout") is not None

    def test_is_non_modal(self):
        source = read_popup_source("notification_toast.py")
        assert "set_modal(False)" in source


class TestNotificationToastIconMapping:
    """Test level-to-icon mapping."""

    EXPECTED_ICON_REFS = {
        "info": "IconsManager.INFO",
        "success": "IconsManager.SUCCESS",
        "warning": "IconsManager.WARNING",
        "error": "IconsManager.ERROR",
    }

    def test_all_levels_have_icons(self):
        source = read_popup_source("notification_toast.py")
        for level in self.EXPECTED_ICON_REFS:
            assert f'"{level}"' in source, f"Missing level: {level}"

    def test_icon_references_present(self):
        source = read_popup_source("notification_toast.py")
        for ref in self.EXPECTED_ICON_REFS.values():
            assert ref in source, f"Missing icon reference: {ref}"


class TestNotificationToastLevelColors:
    """Test level-to-color mapping."""

    def test_info_uses_accent_color(self):
        source = read_popup_source("notification_toast.py")
        assert "accent_color" in source

    def test_success_uses_git_added(self):
        source = read_popup_source("notification_toast.py")
        assert "git_added" in source

    def test_warning_uses_git_modified(self):
        source = read_popup_source("notification_toast.py")
        assert "git_modified" in source

    def test_error_uses_git_deleted(self):
        source = read_popup_source("notification_toast.py")
        assert "git_deleted" in source


class TestNotificationToastAutoClose:
    """Verify auto-close behavior."""

    def test_uses_timeout(self):
        source = read_popup_source("notification_toast.py")
        assert "timeout_add" in source

    def test_timeout_closes_toast(self):
        source = read_popup_source("notification_toast.py")
        assert "self.close()" in source


class TestShowToastHelper:
    """Verify the show_toast helper."""

    def test_show_toast_function_exists(self):
        tree = parse_popup_source("notification_toast.py")
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "show_toast":
                return
        raise AssertionError("show_toast function not found")
