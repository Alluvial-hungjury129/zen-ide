"""Tests for AboutPopup (src/popups/about_popup.py)."""

from tests.popups.conftest import (
    class_inherits,
    find_class,
    find_method,
    parse_popup_source,
    read_popup_source,
)


class TestAboutPopupStructure:
    """Verify AboutPopup structural contracts."""

    def test_inherits_nvim_popup(self):
        tree = parse_popup_source("about_popup.py")
        assert class_inherits(tree, "AboutPopup", "NvimPopup")

    def test_has_create_content(self):
        tree = parse_popup_source("about_popup.py")
        cls = find_class(tree, "AboutPopup")
        assert find_method(cls, "_create_content") is not None

    def test_has_on_key_pressed(self):
        tree = parse_popup_source("about_popup.py")
        cls = find_class(tree, "AboutPopup")
        assert find_method(cls, "_on_key_pressed") is not None


class TestAboutPopupKeyHandling:
    """Verify key handling."""

    def test_q_closes(self):
        source = read_popup_source("about_popup.py")
        assert "KEY_q" in source

    def test_escape_closes(self):
        """Escape handled via super()._on_key_pressed."""
        source = read_popup_source("about_popup.py")
        assert "super()._on_key_pressed" in source


class TestAboutPopupContent:
    """Verify popup content."""

    def test_shows_app_name(self):
        source = read_popup_source("about_popup.py")
        assert "Zen IDE" in source

    def test_shows_version(self):
        source = read_popup_source("about_popup.py")
        assert "Version" in source

    def test_shows_framework_info(self):
        source = read_popup_source("about_popup.py")
        assert "GTK4" in source

    def test_shows_license(self):
        source = read_popup_source("about_popup.py")
        assert "MIT" in source

    def test_does_not_load_icon(self):
        source = read_popup_source("about_popup.py")
        assert "zen_icon.png" not in source
        assert "Gtk.Image" not in source

    def test_has_hint_bar(self):
        source = read_popup_source("about_popup.py")
        assert "_create_hint_bar" in source


class TestShowAboutHelper:
    """Verify the show_about helper."""

    def test_show_about_exists(self):
        source = read_popup_source("about_popup.py")
        assert "def show_about" in source
