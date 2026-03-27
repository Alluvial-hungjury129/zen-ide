"""
OpenAPI scroll-sync helper widgets.

Houses _MacOSWebKitHelper (native macOS WKWebView overlay) and
_SyncPlaceholder (lightweight snapshot-sync widget).
Split from openapi_preview.py.
"""

import platform

from gi.repository import Gtk

_HAS_MACOS_WEBKIT = False
if platform.system() == "Darwin":
    try:
        from editor.preview.macos_webkit_helpers import (
            _HAS_MACOS_WEBKIT as _mac_available,
        )
        from editor.preview.macos_webkit_helpers import (
            _NSURL,
            _NSApp,
            _NSMakeRect,
            _ScrollHandler,
            _WKWebView,
            _WKWebViewConfig,
        )

        _HAS_MACOS_WEBKIT = _mac_available
    except ImportError:
        pass


class _MacOSWebKitHelper:
    """Manages a native macOS WKWebView overlaid on a GTK4 widget area."""

    def __init__(self, on_scroll_fraction=None):
        self._on_scroll_fraction = on_scroll_fraction
        config = _WKWebViewConfig.alloc().init()

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
        self._webview.setValue_forKey_(False, "drawsBackground")
        self._webview.setHidden_(True)
        self._ns_window = None
        self._attached = False

    def attach(self, gtk_widget):
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
        if not self._attached or not self._ns_window:
            return
        cv = self._ns_window.contentView()
        cv_height = cv.frame().size.height
        ns_y = y if cv.isFlipped() else cv_height - y - height
        self._webview.setFrame_(_NSMakeRect(x, ns_y, width, height))

    def load_html(self, html):
        self._webview.loadHTMLString_baseURL_(html, _NSURL.URLWithString_("about:blank"))

    def scroll_by(self, dx, dy):
        js = f"window.scrollBy({dx},{dy});"
        self._webview.evaluateJavaScript_completionHandler_(js, None)

    def set_hidden(self, hidden):
        if self._webview:
            self._webview.setHidden_(hidden)

    def destroy(self):
        if self._webview:
            self._webview.removeFromSuperview()
            self._webview = None
        self._attached = False


class _SyncPlaceholder(Gtk.Widget):
    """Lightweight widget that calls a sync function on every snapshot."""

    def __init__(self, sync_func):
        super().__init__()
        self._sync_func = sync_func

    def do_snapshot(self, snapshot):
        w = self.get_width()
        h = self.get_height()
        if self._sync_func:
            self._sync_func(self, w, h)
