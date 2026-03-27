"""
OpenAPI Preview for Zen IDE GTK version.
Renders OpenAPI/Swagger specs as a styled interactive preview.
Parses YAML/JSON specs and renders endpoints, schemas, and info as HTML.

Uses the same rendering backend hierarchy as MarkdownPreview:
  1. WebKitGTK (Linux) - full HTML/CSS via GObject introspection
  2. macOS native WKWebView (via PyObjC) - full HTML/CSS overlaid on GTK4
  3. GtkTextView (fallback) - text-only summary
"""

import json
import os
import platform

import yaml
from gi.repository import GLib, Gtk, Pango

# --- Re-exports from split modules (preserve public API) ---
from editor.preview.openapi_css import (  # noqa: F401
    _HTML_TEMPLATE,
    _build_openapi_css,
)
from editor.preview.openapi_renderer import (  # noqa: F401
    _html_escape,
    _render_parameters,
    _render_request_body,
    _render_responses,
    _render_schema_table,
    _render_spec_html,
    _render_spec_text,
)
from editor.preview.openapi_schema_helpers import (  # noqa: F401
    _compose_example,
    _deep_resolve_refs,
    _merge_allof,
    _resolve_external_refs,
    _resolve_file_ref,
    _resolve_internal_refs_with_doc,
    _resolve_ref,
    _schema_summary,
    _schema_to_rows,
)
from editor.preview.openapi_scroll_sync import (  # noqa: F401
    _MacOSWebKitHelper,
    _SyncPlaceholder,
)
from editor.preview.preview_scroll_mixin import SCROLL_SYNC_JS, PreviewScrollMixin
from gi_requirements import load_webkit
from themes import ThemeAwareMixin, get_theme
from themes.theme_aware_mixin import get_setting

# --- Backend detection (same as markdown_preview) ---

WebKit = load_webkit()
_HAS_WEBKIT = WebKit is not None

_HAS_MACOS_WEBKIT = False
if not _HAS_WEBKIT and platform.system() == "Darwin":
    try:
        from editor.preview.macos_webkit_helpers import (
            _HAS_MACOS_WEBKIT as _mac_available,
        )

        _HAS_MACOS_WEBKIT = _mac_available
    except ImportError:
        pass


# HTTP method colors - derived from theme
def _method_colors():
    """Return HTTP method colors from the active theme."""
    theme = get_theme()
    return {
        "get": theme.term_blue,
        "post": theme.term_green,
        "put": theme.warning_color,
        "delete": theme.term_red,
        "patch": theme.term_cyan or theme.syntax_operator,
        "options": theme.accent_color,
        "head": theme.term_magenta,
    }


def is_openapi_content(text: str) -> bool:
    """Check if text content is an OpenAPI/Swagger spec."""
    if not text or not text.strip():
        return False
    stripped = text.strip()
    # YAML detection
    if stripped.startswith("openapi:") or stripped.startswith("swagger:"):
        return True
    # JSON detection
    if stripped.startswith("{"):
        try:
            data = json.loads(stripped)
            return isinstance(data, dict) and ("openapi" in data or "swagger" in data)
        except (json.JSONDecodeError, ValueError):
            return False
    # YAML with leading comments or document marker
    for line in stripped.split("\n")[:20]:
        line = line.strip()
        if line.startswith("#") or line == "---" or not line:
            continue
        if line.startswith("openapi:") or line.startswith("swagger:"):
            return True
        break
    return False


def _parse_spec(text: str) -> dict | None:
    """Parse OpenAPI spec from YAML or JSON text."""
    if not text or not text.strip():
        return None
    stripped = text.strip()
    try:
        if stripped.startswith("{"):
            return json.loads(stripped)
        return yaml.safe_load(stripped)
    except Exception:
        return None


class OpenAPIPreview(ThemeAwareMixin, PreviewScrollMixin, Gtk.Box):
    """OpenAPI spec preview widget. Rendering backends:
    1. WebKitGTK (Linux) - full HTML/CSS
    2. macOS native WKWebView (PyObjC) - full HTML/CSS overlaid on GTK4
    3. GtkTextView (fallback) - text-only summary
    """

    _ZOOM_STEP = 0.1
    _ZOOM_MIN = 0.3
    _ZOOM_MAX = 3.0

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self._init_scroll_sync()
        self._zoom_level = 1.0
        self._last_content = None
        self._last_file_path = None
        self._css_provider = None

        # Canvas backend is the default — native GTK scroll physics
        # (DrawingArea in ScrolledWindow, same architecture as MarkdownPreview).
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
        ucm = WebKit.UserContentManager()
        ucm.connect("script-message-received::zenScrollSync", self._on_webkit_script_message)
        ucm.register_script_message_handler("zenScrollSync")
        self.webview = WebKit.WebView.new_with_user_content_manager(ucm)
        self.webview.set_vexpand(True)
        self.webview.set_hexpand(True)

        settings = self.webview.get_settings()
        if hasattr(settings, "set_enable_developer_extras"):
            settings.set_enable_developer_extras(False)

        theme = get_theme()
        self._css_provider = Gtk.CssProvider()
        self._css_provider.load_from_data(f"webview {{ background-color: {theme.main_bg}; }}".encode())
        self.webview.get_style_context().add_provider(self._css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        self.append(self.webview)
        self._connect_webkit_scroll_sync(self.webview)

    # -- macOS native WKWebView (PyObjC) --

    def _create_macos_webkit_ui(self):
        self._placeholder = _SyncPlaceholder(self._on_placeholder_sync)
        self._placeholder.set_vexpand(True)
        self._placeholder.set_hexpand(True)
        self._placeholder.set_can_target(True)
        self._placeholder.set_focusable(True)
        self.append(self._placeholder)

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
        GLib.timeout_add(200, self._try_attach_macos)

    def _try_attach_macos(self):
        if self._macos_attached:
            return False
        if self._macos_helper.attach(self._placeholder):
            self._macos_attached = True
            if self._pending_html:
                self._macos_helper.load_html(self._pending_html)
                self._pending_html = None
            self._placeholder.queue_draw()
        else:
            GLib.timeout_add(200, self._try_attach_macos)
        return False

    def _on_placeholder_sync(self, area, width, height):
        if not self._macos_attached:
            return
        root = area.get_root()
        if not root:
            return
        success, bounds = area.compute_bounds(root)
        if success:
            self._macos_helper.update_frame(bounds.get_x(), bounds.get_y(), width, height)

    def _on_macos_scroll(self, _ctrl, dx, dy):
        if self._macos_attached:
            from themes.theme_aware_mixin import get_setting

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

    # -- GtkTextView fallback --

    def _create_textview_ui(self):
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_vexpand(True)
        scrolled.set_hexpand(True)
        self.append(scrolled)

        self.text_view = Gtk.TextView()
        self.text_view.set_editable(False)
        self.text_view.set_focusable(False)
        self.text_view.set_wrap_mode(Gtk.WrapMode.WORD)
        self.text_view.set_monospace(True)
        self.text_view.set_margin_start(8)
        self.text_view.set_margin_end(8)
        self.text_view.set_margin_top(8)
        self.text_view.set_margin_bottom(8)

        self.buffer = self.text_view.get_buffer()
        scrolled.set_child(self.text_view)

        # Reverse scroll sync for textview fallback
        self._connect_textview_scroll_sync(scrolled)

        self._apply_styles()

    def _apply_styles(self):
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
        self._zoom_level = min(self._zoom_level + self._ZOOM_STEP, self._ZOOM_MAX)
        self._apply_zoom()

    def zoom_out(self):
        self._zoom_level = max(self._zoom_level - self._ZOOM_STEP, self._ZOOM_MIN)
        self._apply_zoom()

    def zoom_reset(self):
        self._zoom_level = 1.0
        self._apply_zoom()

    def _apply_zoom(self):
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
            base_size = 14
            scaled = int(base_size * self._zoom_level * Pango.SCALE)
            font_desc = Pango.FontDescription()
            font_desc.set_size(scaled)
            self.text_view.override_font(font_desc)

    def render(self, content: str, file_path: str = None):
        """Parse and render OpenAPI spec content."""
        self._last_content = content
        self._last_file_path = file_path
        spec = _parse_spec(content)
        base_dir = os.path.dirname(file_path) if file_path else None
        spec = _resolve_external_refs(spec, base_dir)

        if self._backend == "canvas":
            from editor.preview.openapi_block_renderer import OpenAPIBlockRenderer

            renderer = OpenAPIBlockRenderer()
            blocks = renderer.render(spec)
            self._canvas.set_blocks(blocks)
            return

        if self._backend in ("webkit_gtk", "macos_webkit"):
            theme = get_theme()
            css = _build_openapi_css(theme)
            body = _render_spec_html(spec)
            full_html = _HTML_TEMPLATE.format(css=css, body=body)
            # Inject scroll sync JS before closing </body>
            full_html = full_html.replace("</body>", f"{SCROLL_SYNC_JS}</body>")

            if self._backend == "webkit_gtk":
                self.webview.load_html(full_html, None)
            elif self._macos_attached:
                self._macos_helper.load_html(full_html)
                if self._target_fraction > 0.001:
                    GLib.timeout_add(300, self._apply_scroll_fraction)
            else:
                self._pending_html = full_html
        else:
            text = _render_spec_text(spec)
            self.buffer.set_text(text)
            if self._target_fraction > 0.001:
                GLib.idle_add(self._apply_scroll_fraction)

    def _on_theme_change(self, theme):
        """Update preview styles when theme changes."""
        if self._backend == "canvas" and hasattr(self, "_canvas"):
            self._apply_canvas_theme(theme)
            if self._last_content is not None:
                GLib.idle_add(lambda: self.render(self._last_content, self._last_file_path) or False)
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
        if self._last_content is not None:
            GLib.idle_add(lambda: self.render(self._last_content, self._last_file_path) or False)

    def _on_font_change(self, component, settings):
        """Re-render preview when markdown_preview or editor font changes."""
        if component in ("markdown_preview", "editor"):
            if self._backend == "canvas" and hasattr(self, "_canvas") and component == "markdown_preview":
                font_family = settings["family"]
                font_size = settings.get("size", 14)
                self._canvas.set_font(font_family, font_size)
            if self._last_content is not None:
                GLib.idle_add(lambda: self.render(self._last_content, self._last_file_path) or False)

    def update_from_editor(self, content: str, file_path: str = None):
        """Update preview from editor content (for live preview)."""
        self.render(content, file_path)
