"""Shared scroll-sync logic for preview panels (Markdown, OpenAPI, etc.).

Extracts the duplicated scroll synchronisation code that was previously
copy-pasted between MarkdownPreview and OpenAPIPreview.  Both classes
inherit from this mixin so behavioural fixes apply everywhere at once.
"""

from gi.repository import GLib

# JS snippet injected into webkit HTML for reverse scroll sync.
# Posts the current scroll fraction (0.0–1.0) to Python via the
# ``zenScrollSync`` message handler whenever the user scrolls.
SCROLL_SYNC_JS = (
    "<script>"
    "var _zenScrolling=false;"
    "window.addEventListener('scroll',function(){"
    "if(_zenScrolling)return;"
    "var h=Math.max(0,document.body.scrollHeight-window.innerHeight);"
    "var f=h>0?window.scrollY/h:0;"
    "if(window.webkit&&window.webkit.messageHandlers&&window.webkit.messageHandlers.zenScrollSync){"
    "window.webkit.messageHandlers.zenScrollSync.postMessage(f);"
    "}"
    "});"
    "</script>"
)


class PreviewScrollMixin:
    """Mixin providing editor ↔ preview scroll synchronisation.

    Subclasses must set ``self._backend`` before calling any scroll method
    and should call ``_init_scroll_sync()`` from their ``__init__``.
    """

    # ── Initialisation ──────────────────────────────────────────────

    def _init_scroll_sync(self):
        """Initialise scroll-sync state.  Call from subclass ``__init__``."""
        self._on_preview_scroll_callback = None
        self._syncing_scroll = False
        self._syncing_scroll_timer_id = 0
        self._scroll_sync_pending = False
        self._target_fraction = 0.0

    # ── Canvas wiring ───────────────────────────────────────────────

    def _connect_canvas_scroll_sync(self, scrolled, canvas):
        """Wire up scroll sync after creating ``scrolled`` + ``canvas``.

        Enables kinetic (momentum) scrolling and connects the
        ``value-changed`` signal for reverse sync (preview → editor).
        """
        scrolled.set_kinetic_scrolling(True)
        self._canvas_scrolled = scrolled
        self._canvas = canvas
        scrolled.get_vadjustment().connect("value-changed", self._on_canvas_scroll)

    # ── WebKitGTK wiring ────────────────────────────────────────────

    def _connect_webkit_scroll_sync(self, webview):
        """Wire up WebKitGTK scroll sync signals.

        Registers the ``zenScrollSync`` script-message handler for reverse
        sync (preview → editor) and the ``load-changed`` signal to restore
        scroll position after page loads.

        The subclass must also inject ``SCROLL_SYNC_JS`` into the rendered
        HTML so the browser-side listener posts scroll fractions.
        """
        webview.connect("load-changed", self._on_webkit_load_changed)

    # ── Textview wiring ─────────────────────────────────────────────

    def _connect_textview_scroll_sync(self, scrolled):
        """Wire up GtkTextView scroll sync.

        Connects the ``value-changed`` signal on the scrolled window's
        vertical adjustment for reverse sync (preview → editor).
        """
        self._textview_scrolled = scrolled
        scrolled.get_vadjustment().connect("value-changed", self._on_textview_scroll)

    # ── Reverse sync: preview → editor ──────────────────────────────

    def _on_canvas_scroll(self, adj):
        """Emit scroll fraction to editor when the user scrolls the preview."""
        if self._syncing_scroll:
            return
        if hasattr(self, "_canvas") and self._canvas.is_animation_adjusting:
            return
        upper = adj.get_upper()
        page = adj.get_page_size()
        if upper > page:
            fraction = adj.get_value() / (upper - page)
        else:
            fraction = 0.0
        self._target_fraction = fraction
        cb = self._on_preview_scroll_callback
        if cb:
            cb(fraction)

    def _on_preview_scrolled(self, fraction):
        """Handle scroll fraction from webkit JS (reverse sync)."""
        if self._syncing_scroll:
            return
        self._target_fraction = fraction
        cb = self._on_preview_scroll_callback
        if cb:
            cb(fraction)

    def _on_webkit_script_message(self, _ucm, js_result):
        """Handle scroll fraction posted from WebKitGTK JavaScript."""
        try:
            value = js_result.to_double()
        except Exception:
            try:
                value = js_result.get_js_value().to_double()
            except Exception:
                return
        self._on_preview_scrolled(value)

    def _on_webkit_load_changed(self, _webview, event):
        """Re-apply scroll position after WebKit finishes loading content."""
        try:
            # WebKit.LoadEvent.FINISHED == 3
            if event.value_nick == "finished" and self._target_fraction > 0.001:
                GLib.timeout_add(50, self._apply_scroll_fraction)
        except Exception:
            pass

    def _on_textview_scroll(self, adj):
        """Handle textview scroll for reverse sync (preview → editor)."""
        if self._syncing_scroll:
            return
        upper = adj.get_upper()
        page = adj.get_page_size()
        if upper > page:
            fraction = adj.get_value() / (upper - page)
            self._target_fraction = fraction
            cb = self._on_preview_scroll_callback
            if cb:
                cb(fraction)

    def set_on_preview_scroll(self, callback):
        """Register a callback invoked when the preview is scrolled by the user.

        The callback receives a single float argument: the scroll fraction
        (0.0 = top, 1.0 = bottom).
        """
        self._on_preview_scroll_callback = callback

    # ── Forward sync: editor → preview ──────────────────────────────

    def scroll_to_source_line(self, source_line: int):
        """Scroll the preview to show content for the given editor line.

        Sets the echo-guard so the canvas's own ``value-changed`` signal
        does not echo back to the editor.
        """
        if self._backend == "canvas" and hasattr(self, "_canvas"):
            self._syncing_scroll = True
            self._reset_sync_guard()
            self._canvas.scroll_to_source_line(source_line)

    def scroll_to_fraction(self, fraction):
        """Scroll the preview to the given fraction (0.0 = top, 1.0 = bottom).

        Called by the editor side — sets the guard flag so the preview's own
        scroll listener does not echo the change back.

        Uses a resettable timer: the guard stays active until 200 ms after the
        LAST call, preventing stacked-timeout races during continuous scrolling.
        """
        self._target_fraction = max(0.0, min(1.0, fraction))
        self._syncing_scroll = True
        self._reset_sync_guard()
        if not self._scroll_sync_pending:
            self._scroll_sync_pending = True
            GLib.idle_add(self._apply_scroll_fraction_throttled)

    def _apply_scroll_fraction_throttled(self):
        """Apply scroll fraction, clearing throttle flag."""
        self._scroll_sync_pending = False
        self._apply_scroll_fraction()
        return False

    def _apply_scroll_fraction(self):
        """Apply the stored scroll fraction to the active backend.

        Handles canvas, webkit (via JS), and textview backends.
        """
        f = self._target_fraction
        if self._backend == "canvas" and hasattr(self, "_canvas_scrolled"):
            vadj = self._canvas_scrolled.get_vadjustment()
            upper = vadj.get_upper()
            page = vadj.get_page_size()
            if upper > page:
                self._canvas.scroll_to_value(f * (upper - page))
        elif self._backend in ("webkit_gtk", "macos_webkit"):
            js = (
                f"_zenScrolling=true;"
                f"window.scrollTo(0, {f} * Math.max(0, document.body.scrollHeight - window.innerHeight));"
                f"setTimeout(function(){{ _zenScrolling=false; }}, 200);"
            )
            self._run_js(js)
        elif self._backend == "textview" and hasattr(self, "_textview_scrolled"):
            vadj = self._textview_scrolled.get_vadjustment()
            upper = vadj.get_upper()
            page = vadj.get_page_size()
            if upper > page:
                vadj.set_value(f * (upper - page))
        return False

    def _run_js(self, script):
        """Execute JavaScript in the preview webview."""
        if self._backend == "webkit_gtk" and hasattr(self, "webview"):
            wv = self.webview
            if hasattr(wv, "run_javascript"):
                wv.run_javascript(script, None, None)
            elif hasattr(wv, "evaluate_javascript"):
                wv.evaluate_javascript(script, -1, None, None, None, None)
        elif self._backend == "macos_webkit" and getattr(self, "_macos_attached", False):
            self._macos_helper._webview.evaluateJavaScript_completionHandler_(script, None)

    # ── Echo-guard ──────────────────────────────────────────────────

    def _reset_sync_guard(self):
        """Cancel any previous guard timer and start a new one.

        The guard remains active until 200 ms after the last sync call,
        preventing echo-back while the editor is still scrolling.
        """
        if self._syncing_scroll_timer_id:
            GLib.source_remove(self._syncing_scroll_timer_id)
        self._syncing_scroll_timer_id = GLib.timeout_add(200, self._clear_syncing_flag)

    @property
    def is_syncing_scroll(self):
        return self._syncing_scroll

    def _clear_syncing_flag(self):
        self._syncing_scroll = False
        self._syncing_scroll_timer_id = 0
        return False
