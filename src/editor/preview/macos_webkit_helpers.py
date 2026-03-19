"""Shared macOS WKWebView helpers for preview panels.

Defines the _ScrollHandler ObjC class once so it can be imported by
both MarkdownPreview and OpenAPIPreview without duplicate registration.
"""

import platform

from gi.repository import GLib

_HAS_MACOS_WEBKIT = False
_ScrollHandler = None
_NSApp = None
_NSURL = None
_NSMakeRect = None
_WKWebView = None
_WKWebViewConfig = None

if platform.system() == "Darwin":
    try:
        from AppKit import NSApp
        from Foundation import NSURL, NSMakeRect
        from Foundation import NSObject as _NSObject
        from WebKit import WKWebView, WKWebViewConfiguration

        _HAS_MACOS_WEBKIT = True
        _NSApp = NSApp
        _NSURL = NSURL
        _NSMakeRect = NSMakeRect
        _WKWebView = WKWebView
        _WKWebViewConfig = WKWebViewConfiguration

        class _ZenScrollHandler(_NSObject):
            """PyObjC message handler for WKWebView scroll sync.

            Defined once here so the ObjC class is registered only once.
            Set ``callback`` on each instance before use.
            """

            callback = None

            def userContentController_didReceiveScriptMessage_(self, controller, message):
                body = message.body()
                if isinstance(body, (int, float)) and self.callback:
                    cb = self.callback
                    GLib.idle_add(lambda: cb(float(body)) or False)

        _ScrollHandler = _ZenScrollHandler

    except ImportError:
        pass
