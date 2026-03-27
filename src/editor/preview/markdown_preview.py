"""
Markdown Preview for Zen IDE.
Renders markdown content using cmarkgfm (GitHub Flavored Markdown).
Uses WebKit for rich HTML rendering when available, with GtkTextView fallback.

Rendering backends (in priority order):
  1. WebKitGTK (Linux) - full HTML/CSS via GObject introspection
  2. macOS native WKWebView (via PyObjC) - full HTML/CSS overlaid on GTK4
  3. GtkTextView (fallback) - text-only with formatting tags
"""

import hashlib
import platform

import cmarkgfm
from gi.repository import GLib, Gtk, Pango

from editor.preview.markdown_css import _build_github_css, _HtmlToTextView
from editor.preview.markdown_scroll_sync import MarkdownScrollSyncMixin
from editor.preview.preview_scroll_mixin import SCROLL_SYNC_JS, PreviewScrollMixin
from gi_requirements import load_webkit
from themes import ThemeAwareMixin, get_theme
from themes.theme_aware_mixin import get_setting

# --- Backend detection ---

# 1. WebKitGTK (Linux)
WebKit = load_webkit()
_HAS_WEBKIT = WebKit is not None

# 2. macOS native WKWebView (via PyObjC)
_HAS_MACOS_WEBKIT = False
if not _HAS_WEBKIT and platform.system() == "Darwin":
    try:
        from editor.preview.macos_webkit_helpers import (
            _HAS_MACOS_WEBKIT as _mac_available,
        )

        _HAS_MACOS_WEBKIT = _mac_available
    except ImportError:
        pass


class MarkdownPreview(ThemeAwareMixin, MarkdownScrollSyncMixin, PreviewScrollMixin, Gtk.Box):
    """Markdown preview using cmarkgfm. Rendering backends:
    1. WebKitGTK (Linux) - full HTML/CSS
    2. macOS native WKWebView (PyObjC) - full HTML/CSS overlaid on GTK4
    3. GtkTextView (fallback) - text-only with formatting tags
    """

    _ZOOM_STEP = 0.1
    _ZOOM_MIN = 0.3
    _ZOOM_MAX = 3.0

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self._init_scroll_sync()
        self._zoom_level = 1.0
        self._last_markdown = None
        self._css_provider = None
        self._on_preview_scroll_line_callback = None

        # Canvas backend is the default — native GTK scroll physics
        # (DrawingArea in ScrolledWindow, same architecture as ChatCanvas).
        # Override via preview.backend setting to use "webkit_gtk" or "macos_webkit".
        backend_override = get_setting("preview.backend", "")
        if backend_override == "webkit_gtk" and _HAS_WEBKIT:
            self._backend = "webkit_gtk"
        elif backend_override == "macos_webkit" and _HAS_MACOS_WEBKIT:
            self._backend = "macos_webkit"
        else:
            self._backend = "canvas"
        self._create_ui()
        self._subscribe_theme()
        from fonts import subscribe_font_change

        subscribe_font_change(self._on_font_change)

    def _create_ui(self):
        """Create the markdown preview UI."""
        if self._backend == "canvas":
            self._create_canvas_ui()
        elif self._backend == "webkit_gtk":
            self._create_webkit_gtk_ui()
        elif self._backend == "macos_webkit":
            self._create_macos_webkit_ui()
        else:
            self._create_textview_ui()

    # -- Native Canvas --

    def _create_canvas_ui(self):
        """Create native MarkdownCanvas preview — pixel-perfect scroll sync."""
        from editor.preview.markdown_canvas import MarkdownCanvas

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_vexpand(True)
        scrolled.set_hexpand(True)
        self.append(scrolled)

        canvas = MarkdownCanvas()
        scrolled.set_child(canvas)
        canvas.attach_to_scrolled_window(scrolled)

        # Shared scroll sync wiring (kinetic scrolling + value-changed signal)
        self._connect_canvas_scroll_sync(scrolled, canvas)

        # Apply theme
        theme = get_theme()
        self._apply_canvas_theme(theme)

        # Apply font
        from fonts import get_font_settings

        md_settings = get_font_settings("markdown_preview")
        font_family = md_settings["family"]
        font_size = md_settings.get("size", 14)
        self._canvas.set_font(font_family, font_size)

    def _apply_canvas_theme(self, theme):
        """Apply theme to MarkdownCanvas."""
        self._canvas.set_theme(
            fg=theme.fg_color,
            bg=theme.main_bg,
            code_bg=theme.panel_bg,
            accent=theme.accent_color,
            dim=theme.fg_dim,
            border=theme.border_color,
            selection_bg=theme.selection_bg,
        )

    # -- WebKitGTK (Linux) --

    def _create_webkit_gtk_ui(self):
        """Create WebKit-based preview for rich HTML rendering."""
        # Use a UserContentManager to receive JS scroll messages
        ucm = WebKit.UserContentManager()
        ucm.connect("script-message-received::zenScrollSync", self._on_webkit_script_message)
        ucm.register_script_message_handler("zenScrollSync")
        self.webview = WebKit.WebView.new_with_user_content_manager(ucm)
        self.webview.set_vexpand(True)
        self.webview.set_hexpand(True)

        settings = self.webview.get_settings()
        if hasattr(settings, "set_enable_developer_extras"):
            settings.set_enable_developer_extras(False)
        if hasattr(settings, "set_enable_javascript"):
            settings.set_enable_javascript(True)
        if hasattr(settings, "set_allow_file_access_from_file_urls"):
            settings.set_allow_file_access_from_file_urls(True)

        theme = get_theme()
        self._css_provider = Gtk.CssProvider()
        self._css_provider.load_from_data(f"webview {{ background-color: {theme.main_bg}; }}".encode())
        self.webview.get_style_context().add_provider(self._css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        self.append(self.webview)
        self._connect_webkit_scroll_sync(self.webview)

    # -- macOS native WKWebView (PyObjC) --
    # Methods provided by MarkdownScrollSyncMixin

    # -- GtkTextView fallback --

    def _create_textview_ui(self):
        """Create GtkTextView-based preview as fallback."""
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_vexpand(True)
        scrolled.set_hexpand(True)
        self.append(scrolled)
        self._textview_scrolled = scrolled

        self.text_view = Gtk.TextView()
        self.text_view.set_editable(False)
        self.text_view.set_focusable(False)
        self.text_view.set_wrap_mode(Gtk.WrapMode.WORD)
        self.text_view.set_margin_start(24)
        self.text_view.set_margin_end(0)
        self.text_view.set_margin_top(0)
        self.text_view.set_margin_bottom(0)
        self.text_view.set_pixels_above_lines(2)
        self.text_view.set_pixels_below_lines(2)

        self.buffer = self.text_view.get_buffer()
        scrolled.set_child(self.text_view)

        # Reverse scroll sync for textview fallback
        self._connect_textview_scroll_sync(scrolled)

        self._setup_tags()
        self._apply_styles()

    def _setup_tags(self):
        """Setup text tags for markdown formatting."""
        theme = get_theme()
        from fonts import get_font_settings

        editor_settings = get_font_settings("editor")
        editor_font = editor_settings["family"]
        md_settings = get_font_settings("markdown_preview")
        md_font = md_settings["family"]
        self.buffer.create_tag("h1", weight=Pango.Weight.BOLD, scale=2.2, pixels_above_lines=16, pixels_below_lines=4)
        self.buffer.create_tag("h2", weight=Pango.Weight.BOLD, scale=1.6, pixels_above_lines=16, pixels_below_lines=4)
        self.buffer.create_tag("h3", weight=Pango.Weight.BOLD, scale=1.3, pixels_above_lines=12, pixels_below_lines=4)
        self.buffer.create_tag("h4", weight=Pango.Weight.BOLD, scale=1.1, pixels_above_lines=8, pixels_below_lines=2)
        self.buffer.create_tag("h5", weight=Pango.Weight.BOLD, scale=1.0, pixels_above_lines=8, pixels_below_lines=2)
        self.buffer.create_tag("h6", weight=Pango.Weight.BOLD, scale=0.9, pixels_above_lines=8, pixels_below_lines=2)
        self.buffer.create_tag("bold", weight=Pango.Weight.BOLD)
        self.buffer.create_tag("italic", style=Pango.Style.ITALIC)
        self.buffer.create_tag("strikethrough", strikethrough=True)
        self.buffer.create_tag("code", family=editor_font, background=theme.panel_bg)
        self.buffer.create_tag("link", foreground=theme.accent_color, underline=Pango.Underline.SINGLE)
        self.buffer.create_tag(
            "quote",
            left_margin=32,
            foreground=theme.fg_dim,
            style=Pango.Style.ITALIC,
            pixels_above_lines=4,
            pixels_below_lines=4,
        )
        self.buffer.create_tag("quote_bar", foreground=theme.accent_color)
        self.buffer.create_tag("list_item", left_margin=24, pixels_above_lines=1, pixels_below_lines=1)
        self.buffer.create_tag(
            "code_block",
            family=editor_font,
            background=theme.panel_bg,
            paragraph_background=theme.panel_bg,
            pixels_above_lines=6,
            pixels_below_lines=6,
            left_margin=16,
            right_margin=16,
            pixels_inside_wrap=2,
        )
        self.buffer.create_tag("hr", foreground=theme.fg_dim)
        self.buffer.create_tag("heading_rule", foreground=theme.fg_dim, pixels_below_lines=8)
        self.buffer.create_tag(
            "table_header",
            family=md_font,
            weight=Pango.Weight.BOLD,
            pixels_above_lines=0,
            pixels_below_lines=0,
        )
        self.buffer.create_tag(
            "table_cell",
            family=md_font,
            pixels_above_lines=0,
            pixels_below_lines=0,
        )

    def _apply_styles(self):
        """Apply custom styles."""
        theme = get_theme()
        self._css_provider = Gtk.CssProvider()
        css = f"""
            textview text {{
                background-color: {theme.main_bg};
                color: {theme.fg_color};
            }}
        """
        self._css_provider.load_from_data(css.encode())
        self.text_view.get_style_context().add_provider(self._css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    # -- Public API --

    def zoom_in(self):
        """Increase zoom level."""
        self._zoom_level = min(self._zoom_level + self._ZOOM_STEP, self._ZOOM_MAX)
        self._apply_zoom()

    def zoom_out(self):
        """Decrease zoom level."""
        self._zoom_level = max(self._zoom_level - self._ZOOM_STEP, self._ZOOM_MIN)
        self._apply_zoom()

    def zoom_reset(self):
        """Reset zoom to 100%."""
        self._zoom_level = 1.0
        self._apply_zoom()

    def _apply_zoom(self):
        """Apply current zoom level to the preview backend."""
        if self._backend == "canvas" and hasattr(self, "_canvas"):
            self._canvas._zoom_level = self._zoom_level
            self._canvas._needs_layout = True
            self._canvas._schedule_redraw()
        elif self._backend == "webkit_gtk" and hasattr(self, "webview"):
            self.webview.set_zoom_level(self._zoom_level)
        elif self._backend == "macos_webkit" and hasattr(self, "_macos_helper"):
            js = f"document.body.style.zoom = '{self._zoom_level}';"
            self._macos_helper._webview.evaluateJavaScript_completionHandler_(js, None)
        elif self._backend == "textview" and hasattr(self, "text_view"):
            # Scale font size for textview fallback
            base_size = 14
            scaled = int(base_size * self._zoom_level * Pango.SCALE)
            font_desc = Pango.FontDescription()
            font_desc.set_size(scaled)
            self.text_view.override_font(font_desc)

    # -- Scroll sync --
    # set_on_preview_scroll_line() provided by MarkdownScrollSyncMixin

    def render(self, markdown_text: str, file_path: str = None):
        """Render markdown text to the preview."""
        self._last_markdown = markdown_text
        self._last_file_path = file_path

        # Skip re-render if content is identical
        content_hash = hashlib.md5(markdown_text.encode("utf-8")).hexdigest()
        if getattr(self, "_last_content_hash", None) == content_hash:
            return
        self._last_content_hash = content_hash

        if self._backend == "canvas":
            from editor.preview.markdown_block_renderer import MarkdownBlockRenderer

            if file_path:
                from pathlib import Path

                self._canvas.set_base_path(str(Path(file_path).parent))
            renderer = MarkdownBlockRenderer()
            blocks = renderer.render(markdown_text)
            self._canvas.set_blocks(blocks)
            if self._target_fraction > 0.001:
                GLib.idle_add(self._apply_scroll_fraction)
            return

        try:
            html = cmarkgfm.github_flavored_markdown_to_html(markdown_text)
        except Exception:
            html = "<pre style='color:red;'>Error rendering markdown</pre>"

        # Build base URI from file path so relative images resolve
        base_uri = None
        if file_path:
            base_uri = Path(file_path).parent.as_uri() + "/"

        if self._backend in ("webkit_gtk", "macos_webkit"):
            theme = get_theme()
            css = _build_github_css(theme)
            # Inject <base> tag so relative image/link paths resolve from
            # the markdown file's directory (needed when HTML is loaded
            # from a temp file on macOS).
            base_tag = ""
            if base_uri:
                base_tag = f'<base href="{base_uri}">'
            full_html = f'<!DOCTYPE html>\n<html>\n<head><meta charset="utf-8">{base_tag}<style>{css}</style></head>\n<body>{html}{SCROLL_SYNC_JS}</body>\n</html>'

            if self._backend == "webkit_gtk":
                self.webview.load_html(full_html, base_uri)
            elif self._macos_attached:
                self._macos_helper.load_html(full_html, base_uri)
                if self._target_fraction > 0.001:
                    GLib.timeout_add(300, self._apply_scroll_fraction)
            else:
                self._pending_html = full_html
                self._pending_base_uri = base_uri
        else:
            self.buffer.set_text("")
            parser = _HtmlToTextView(self.buffer)
            parser.feed(html)
            if self._target_fraction > 0.001:
                GLib.idle_add(self._apply_scroll_fraction)

    def _on_theme_change(self, theme):
        """Update preview styles when theme changes."""
        if self._backend == "canvas" and hasattr(self, "_canvas"):
            self._apply_canvas_theme(theme)
            if self._last_markdown is not None:
                self._schedule_debounced_render()
            return
        if self._css_provider:
            if self._backend == "webkit_gtk":
                self._css_provider.load_from_data(f"webview {{ background-color: {theme.main_bg}; }}".encode())
            elif self._backend == "textview" and hasattr(self, "text_view"):
                css = f"""
                    textview text {{
                        background-color: {theme.main_bg};
                        color: {theme.fg_color};
                    }}
                """
                self._css_provider.load_from_data(css.encode())
        if self._last_markdown is not None:
            self._schedule_debounced_render()

    def _on_font_change(self, component, settings):
        """Re-render preview when markdown_preview or editor font changes."""
        if component in ("markdown_preview", "editor"):
            if self._backend == "canvas" and hasattr(self, "_canvas") and component == "markdown_preview":
                font_family = settings["family"]
                font_size = settings.get("size", 14)
                self._canvas.set_font(font_family, font_size)
            if self._last_markdown is not None:
                self._schedule_debounced_render()

    def _schedule_debounced_render(self):
        """Schedule a re-render after a short delay, cancelling any pending one."""
        pending = getattr(self, "_debounce_render_id", None)
        if pending:
            GLib.source_remove(pending)
        self._debounce_render_id = GLib.timeout_add(100, self._do_debounced_render)

    def _do_debounced_render(self):
        self._debounce_render_id = None
        # Clear hash so render() actually re-renders
        self._last_content_hash = None
        file_path = getattr(self, "_last_file_path", None)
        self.render(self._last_markdown, file_path)
        return False

    def update_from_editor(self, content: str, file_path: str = None):
        """Update preview from editor content (for live preview)."""
        self.render(content, file_path)
