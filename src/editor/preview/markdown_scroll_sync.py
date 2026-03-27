"""Scroll-sync helpers and macOS WebKit backend for Markdown Preview.

Contains:
  - _MacOSWebKitHelper: manages a native WKWebView overlaid on GTK4
  - _SyncPlaceholder: lightweight GTK widget for overlay positioning
  - MarkdownScrollSyncMixin: mixin with macOS WebKit UI and scroll wiring
"""

import platform
from pathlib import Path

from gi.repository import GLib, Gtk

from themes.theme_manager import get_setting

# macOS native WKWebView symbols (conditionally imported)
_NSURL = _NSApp = _NSMakeRect = _ScrollHandler = _WKWebView = _WKWebViewConfig = None
if platform.system() == "Darwin":
    try:
        from editor.preview.macos_webkit_helpers import (
            _NSURL,
            _NSApp,
            _NSMakeRect,
            _ScrollHandler,
            _WKWebView,
            _WKWebViewConfig,
        )
    except ImportError:
        pass


class _MacOSWebKitHelper:
    """Manages a native macOS WKWebView overlaid on a GTK4 widget area.

    Creates a WKWebView (via PyObjC) and adds it as a subview of the
    NSWindow's content view. Position is synced with a GTK placeholder
    widget using compute_bounds().
    """

    def __init__(self, on_scroll_fraction=None):
        self._on_scroll_fraction = on_scroll_fraction
        config = _WKWebViewConfig.alloc().init()
        # Allow loading local file:// resources (images) from HTML with file:// base URL
        prefs = config.preferences()
        prefs.setValue_forKey_(True, "allowFileAccessFromFileURLs")

        # Register JS → Python message handler for reverse scroll sync
        if on_scroll_fraction:
            self._scroll_handler = _ScrollHandler.alloc().init()
            self._scroll_handler.callback = on_scroll_fraction
            uc = config.userContentController()
            uc.addScriptMessageHandler_name_(self._scroll_handler, "zenScrollSync")

        self._webview = _WKWebView.alloc().initWithFrame_configuration_(_NSMakeRect(0, 0, 1, 1), config)
        if self._webview is None:
            self._ns_window = None
            self._attached = False
            return
        # Transparent background; CSS in the HTML handles the actual bg color
        self._webview.setValue_forKey_(False, "drawsBackground")
        self._webview.setHidden_(True)
        self._ns_window = None
        self._attached = False

    def attach(self, gtk_widget):
        """Attach WKWebView as subview of the app's NSWindow content view."""
        if self._webview is None:
            return False
        self._ns_window = _NSApp.mainWindow()
        if not self._ns_window and _NSApp.windows():
            self._ns_window = _NSApp.windows()[0]
        if not self._ns_window:
            return False

        content_view = self._ns_window.contentView()
        content_view.addSubview_(self._webview)
        self._webview.setHidden_(False)
        self._attached = True
        return True

    def update_frame(self, x, y, width, height):
        """Update WKWebView position. Coords are GTK-style (top-left origin)."""
        if not self._attached or not self._ns_window:
            return
        cv = self._ns_window.contentView()
        cv_height = cv.frame().size.height
        # NSView uses bottom-left origin unless flipped
        ns_y = y if cv.isFlipped() else cv_height - y - height
        self._webview.setFrame_(_NSMakeRect(x, ns_y, width, height))

    def load_html(self, html, base_uri=None):
        """Load HTML string into the WKWebView.

        When a file:// base_uri is given, writes HTML to a temp file and uses
        loadFileURL:allowingReadAccessToURL: so that relative <img> sources
        resolve correctly.  loadHTMLString:baseURL: does NOT grant file://
        access even with a file:// base URL – this is a known WKWebView
        security restriction.
        """
        if base_uri and base_uri.startswith("file://"):
            import tempfile

            # Clean up previous temp file
            old = getattr(self, "_tmp_html_path", None)
            if old:
                try:
                    Path(old).unlink(missing_ok=True)
                except OSError:
                    pass
            fd, tmp_path = tempfile.mkstemp(suffix=".html", prefix=".zen_preview_")
            import os

            os.write(fd, html.encode("utf-8"))
            os.close(fd)
            self._tmp_html_path = tmp_path
            file_url = _NSURL.fileURLWithPath_(tmp_path)
            # Grant read access to root so WKWebView can read both the temp
            # file and images in the project directory.
            root_url = _NSURL.fileURLWithPath_("/")
            self._webview.loadFileURL_allowingReadAccessToURL_(file_url, root_url)
        else:
            if base_uri:
                ns_url = _NSURL.URLWithString_(base_uri)
            else:
                ns_url = _NSURL.URLWithString_("about:blank")
            self._webview.loadHTMLString_baseURL_(html, ns_url)

    def scroll_by(self, dx, dy):
        """Scroll the WKWebView content by the given pixel offsets."""
        js = f"window.scrollBy({dx},{dy});"
        self._webview.evaluateJavaScript_completionHandler_(js, None)

    def set_hidden(self, hidden):
        """Show or hide the WKWebView."""
        if self._webview:
            self._webview.setHidden_(hidden)

    def destroy(self):
        """Remove the WKWebView from its superview and release."""
        # Clean up temp preview file
        tmp = getattr(self, "_tmp_html_path", None)
        if tmp:
            try:
                Path(tmp).unlink(missing_ok=True)
            except OSError:
                pass
        if self._webview:
            self._webview.removeFromSuperview()
            self._webview = None
        self._attached = False


class _SyncPlaceholder(Gtk.Widget):
    """Lightweight widget that calls a sync function on every snapshot.

    Replaces Gtk.DrawingArea+set_draw_func for macOS WKWebView overlay
    positioning — no Cairo dependency needed.
    """

    def __init__(self, sync_func):
        super().__init__()
        self._sync_func = sync_func

    def do_snapshot(self, snapshot):
        w = self.get_width()
        h = self.get_height()
        if self._sync_func:
            self._sync_func(self, w, h)


class MarkdownScrollSyncMixin:
    """Mixin providing macOS WebKit UI creation and scroll-line callback.

    Mixed into MarkdownPreview to keep the main class thinner.
    Methods here were originally part of the MarkdownPreview class body.
    """

    def _create_macos_webkit_ui(self):
        """Create a placeholder widget; a native WKWebView overlays it once mapped."""
        self._placeholder = _SyncPlaceholder(self._on_placeholder_sync)
        self._placeholder.set_vexpand(True)
        self._placeholder.set_hexpand(True)
        self._placeholder.set_can_target(True)
        self._placeholder.set_focusable(True)
        self.append(self._placeholder)

        # Forward trackpad scroll events to the native WKWebView via JS
        scroll_ctrl = Gtk.EventControllerScroll.new(
            Gtk.EventControllerScrollFlags.BOTH_AXES | Gtk.EventControllerScrollFlags.KINETIC
        )
        scroll_ctrl.connect("scroll", self._on_macos_scroll)
        self._placeholder.add_controller(scroll_ctrl)

        self._macos_helper = _MacOSWebKitHelper(on_scroll_fraction=self._on_preview_scrolled)
        self._macos_attached = False
        self._pending_html = None

        self._placeholder.connect("realize", self._on_macos_realize)
        self._placeholder.connect("unrealize", self._on_macos_unrealize)
        self._placeholder.connect("map", lambda _w: self._macos_set_visible(True))
        self._placeholder.connect("unmap", lambda _w: self._macos_set_visible(False))

    def _on_macos_realize(self, _widget):
        """Delay attachment until the NSWindow is ready."""
        self._macos_attach_attempts = 0
        GLib.timeout_add(200, self._try_attach_macos)

    def _try_attach_macos(self):
        _MAX_ATTEMPTS = 10
        if self._macos_attached:
            return False
        self._macos_attach_attempts += 1
        if self._macos_helper.attach(self._placeholder):
            self._macos_attached = True
            if self._pending_html:
                self._macos_helper.load_html(self._pending_html, getattr(self, "_pending_base_uri", None))
                self._pending_html = None
                self._pending_base_uri = None
            self._placeholder.queue_draw()
        elif self._macos_attach_attempts >= _MAX_ATTEMPTS:
            pass
        else:
            delay = min(200 * (2 ** (self._macos_attach_attempts - 1)), 2000)
            GLib.timeout_add(delay, self._try_attach_macos)
        return False

    def _on_placeholder_sync(self, area, width, height):
        """Sync WKWebView frame with the GTK placeholder on every snapshot."""
        if not self._macos_attached:
            return
        root = area.get_root()
        if not root:
            return
        success, bounds = area.compute_bounds(root)
        if success:
            self._macos_helper.update_frame(bounds.get_x(), bounds.get_y(), width, height)

    def _on_macos_scroll(self, _ctrl, dx, dy):
        """Forward GTK scroll events to the native WKWebView."""
        if self._macos_attached:
            speed = get_setting("scroll_speed", 0.4)
            px_per_unit = 50 * speed
            self._macos_helper.scroll_by(dx * px_per_unit, dy * px_per_unit)
        return True

    def _macos_set_visible(self, visible):
        if hasattr(self, "_macos_helper"):
            self._macos_helper.set_hidden(not visible)

    def _on_macos_unrealize(self, _widget):
        self._macos_helper.destroy()
        self._macos_attached = False

    def set_on_preview_scroll_line(self, callback):
        """Register a callback for line-level scroll sync (canvas backend only).

        The callback receives the source line number of the topmost visible block.
        """
        self._on_preview_scroll_line_callback = callback
