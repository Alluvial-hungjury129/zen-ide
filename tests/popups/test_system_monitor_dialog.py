"""Tests for SystemMonitorDialog (src/popups/system_monitor_dialog.py)."""

import ast

from tests.popups.conftest import (
    find_class,
    find_method,
    parse_popup_source,
    read_popup_source,
)


class TestSystemMonitorDialogStructure:
    """Verify SystemMonitorDialog structural contracts."""

    def test_inherits_gtk_window(self):
        """SystemMonitorDialog inherits Gtk.Window directly, NOT NvimPopup."""
        tree = parse_popup_source("system_monitor_dialog.py")
        cls = find_class(tree, "SystemMonitorDialog")
        assert cls is not None
        found = False
        for base in cls.bases:
            if isinstance(base, ast.Attribute) and base.attr == "Window":
                found = True
            elif isinstance(base, ast.Name) and base.id == "Window":
                found = True
        assert found, "SystemMonitorDialog must inherit from Gtk.Window"

    def test_does_not_inherit_nvim_popup(self):
        source = read_popup_source("system_monitor_dialog.py")
        assert "NvimPopup" not in source

    def test_has_on_key_pressed(self):
        tree = parse_popup_source("system_monitor_dialog.py")
        cls = find_class(tree, "SystemMonitorDialog")
        assert find_method(cls, "_on_key_pressed") is not None

    def test_has_on_close_request(self):
        tree = parse_popup_source("system_monitor_dialog.py")
        cls = find_class(tree, "SystemMonitorDialog")
        assert find_method(cls, "_on_close_request") is not None


class TestSystemMonitorDialogKeyHandling:
    """Verify key handling."""

    def test_escape_closes(self):
        source = read_popup_source("system_monitor_dialog.py")
        assert "KEY_Escape" in source


class TestSystemMonitorDialogContent:
    """Verify dialog content."""

    def test_uses_system_monitor_panel(self):
        source = read_popup_source("system_monitor_dialog.py")
        assert "SystemMonitorPanel" in source

    def test_starts_monitoring_on_show(self):
        source = read_popup_source("system_monitor_dialog.py")
        assert "show_panel" in source

    def test_stops_monitoring_on_close(self):
        source = read_popup_source("system_monitor_dialog.py")
        assert "hide_panel" in source


class TestShowSystemMonitorHelper:
    """Verify the show_system_monitor helper."""

    def test_show_system_monitor_exists(self):
        source = read_popup_source("system_monitor_dialog.py")
        assert "def show_system_monitor" in source
