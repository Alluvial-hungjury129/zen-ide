"""UI tests for Zen IDE window startup and main layout.

These tests verify that the IDE starts correctly and all main
panels/widgets are created and visible.

Run with: make tests
Or specifically: uv run python -m pytest tests/ui/ -v --color=yes
"""

import pytest

# All UI tests require a display
pytestmark = pytest.mark.gui


class TestWindowStartup:
    """Verify the IDE window starts and initializes correctly."""

    def test_window_is_presented(self, zen_window):
        """Window should be visible after startup."""
        assert zen_window.get_visible()

    def test_layout_ready(self, zen_window):
        """Deferred initialization should complete."""
        assert zen_window._layout_ready is True

    def test_window_has_title(self, zen_window):
        """Window title should start with 'Zen IDE'."""
        assert zen_window.get_title().startswith("Zen IDE")

    def test_window_has_default_size(self, zen_window):
        """Window should have a reasonable default size configured."""
        default_size = zen_window.get_default_size()
        width, height = default_size
        assert width > 0, "Window default width should be positive"
        assert height > 0, "Window default height should be positive"


class TestMainPanels:
    """Verify that all main IDE panels are created."""

    def test_editor_view_exists(self, zen_window):
        """EditorView should be created after deferred init."""
        assert zen_window.editor_view is not None
        assert not isinstance(zen_window.editor_view, type(None))

    def test_tree_view_exists(self, zen_window):
        """TreeView file explorer should be created."""
        assert zen_window.tree_view is not None

    def test_main_paned_exists(self, zen_window):
        """Main horizontal paned (tree | editor) should exist."""
        assert zen_window.main_paned is not None

    def test_tree_view_is_sidebar(self, zen_window):
        """TreeView should have the 'sidebar' CSS class."""
        assert zen_window.tree_view.has_css_class("sidebar")

    def test_editor_has_notebook(self, zen_window):
        """EditorView should have a notebook for tabs."""
        assert hasattr(zen_window.editor_view, "notebook")
        assert zen_window.editor_view.notebook is not None


class TestHeaderBar:
    """Verify the header bar and its contents."""

    def test_header_bar_exists(self, zen_window):
        """Window should have a header bar."""
        from gi.repository import Gtk

        header = zen_window.get_titlebar()
        assert header is not None
        assert isinstance(header, Gtk.HeaderBar)


class TestWidgetInteraction:
    """Demonstrate interactive UI testing patterns."""

    def test_editor_view_is_visible(self, zen_window):
        """Editor view should be visible in the layout."""
        assert zen_window.editor_view.get_visible()

    def test_tree_view_is_visible(self, zen_window):
        """Tree view should be visible in the layout."""
        assert zen_window.tree_view.get_visible()

    def test_bottom_panels_created(self, zen_window, process_gtk_events):
        """Bottom panels (terminal, AI chat) should be created after deferred init."""
        # Give extra time for deferred panel creation
        from ui.ui_test_helper import wait_for

        wait_for(lambda: zen_window._bottom_panels_created, timeout_s=5.0)
        assert zen_window._bottom_panels_created

    def test_find_buttons_in_header(self, zen_window):
        """Header bar should contain menu/action buttons."""
        from gi.repository import Gtk

        from ui.ui_test_helper import find_children_by_type

        header = zen_window.get_titlebar()
        buttons = find_children_by_type(header, Gtk.Button)
        # Header should have at least the menu button
        assert len(buttons) > 0, "Header bar should contain at least one button"
