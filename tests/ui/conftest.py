"""Pytest fixtures for Zen IDE UI tests.

Provides fixtures that create a real GTK4 Application + Window,
wait for deferred initialization to complete, and tear down cleanly.

Usage:
    @pytest.mark.gui
    def test_something(zen_window):
        assert zen_window.editor_view is not None
"""

import os
import sys

import pytest

# Ensure src/ is on the path (mirrors root conftest.py)
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_src = os.path.join(_project_root, "src")
for p in [_project_root, _src]:
    if p not in sys.path:
        sys.path.insert(0, p)


@pytest.fixture(scope="session")
def gtk_init():
    """Initialize GTK4 once per test session."""
    # On macOS, prevent the test app from stealing focus or appearing in the Dock
    if sys.platform == "darwin":
        try:
            from AppKit import NSApplication

            NSApplication.sharedApplication().setActivationPolicy_(1)  # NSApplicationActivationPolicyAccessory
        except Exception:
            pass

    # GTK4 doesn't have Gtk.init() the same way — the Application handles it.
    # But we ensure the display is available.
    from gi.repository import Gdk

    display = Gdk.Display.get_default()
    if display is None:
        pytest.skip("No display available (run with xvfb-run on headless systems)")


@pytest.fixture(scope="session")
def zen_app(gtk_init):
    """Create a ZenIDEApp instance for testing.

    Yields the app, then cleans up.
    """
    from zen_ide_window import ZenIDEApp

    app = ZenIDEApp()
    yield app


@pytest.fixture(scope="class")
def zen_window(zen_app, tmp_path_factory):
    """Create a fully initialized ZenIDEWindow (headless).

    The window is initialized and the main loop is pumped until
    _layout_ready is True (deferred init completed).

    The window is made invisible (opacity 0) and foreground activation
    is suppressed so tests don't steal focus or flash on screen.

    Uses a temporary directory as workspace to avoid side effects.
    Scoped per test class to reduce window create/destroy overhead.

    Yields the window, then destroys it.
    """
    from ui.ui_test_helper import process_events, wait_for

    # Use a temp workspace to avoid touching real files
    tmp_path = tmp_path_factory.mktemp("workspace")
    os.environ["ZEN_WORKSPACE"] = str(tmp_path)
    os.environ.setdefault("ZEN_SUPPRESS_GTK_WARNINGS", "1")

    from zen_ide_window import ZenIDEWindow

    win = ZenIDEWindow(zen_app)

    # Prevent the window from stealing focus and appearing on screen.
    # Monkey-patch present() so ALL self.present() calls throughout the
    # init pipeline (window_state.py) become no-ops — this is the key
    # to avoiding focus-steal on macOS where present() activates the app.
    win._activate_foreground = lambda: None
    win._activate_macos_foreground = lambda: None
    win.set_opacity(0.0)
    win.present = lambda: None

    # Map the window via set_visible (triggers the 'map' signal needed
    # for _on_window_mapped / deferred init) without activating/focusing.
    win.set_visible(True)

    # Pump the main loop until layout is ready
    ready = wait_for(lambda: win._layout_ready, timeout_s=10.0)
    if not ready:
        pytest.fail("Window layout did not become ready within 10 seconds")

    # Give a bit more time for deferred panels
    process_events(200)

    yield win

    # Cleanup: destroy the window directly (avoid _on_close_request which calls os._exit)
    try:
        win.destroy()
    except Exception:
        pass
    process_events(100)
    os.environ.pop("ZEN_WORKSPACE", None)


@pytest.fixture
def process_gtk_events():
    """Fixture that returns the process_events helper for manual use.

    Usage:
        def test_foo(zen_window, process_gtk_events):
            # do something
            process_gtk_events(200)  # wait for effects
            assert ...
    """
    from ui.ui_test_helper import process_events

    return process_events
