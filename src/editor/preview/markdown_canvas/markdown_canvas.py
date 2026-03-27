"""MarkdownCanvas -- Gtk.DrawingArea that renders ContentBlocks via GtkSnapshot.

Follows the ChatCanvas pattern: DrawingArea inside ScrolledWindow with
pixel-smooth scrolling. Renders structured ContentBlocks (headings, paragraphs,
code, tables, lists, blockquotes, horizontal rules, images) using Pango layouts.

Unlike ChatCanvas (fixed line heights, ANSI buffer), MarkdownCanvas handles
variable-height blocks with word-wrapping. Each block caches its Y offset and
height for viewport culling and scroll-sync mapping.
"""

from __future__ import annotations

import os
import tempfile

from gi.repository import Gdk, GLib, Graphene, Gtk, Pango

from editor.preview.content_block import ContentBlock
from shared.utils import hex_to_gdk_rgba

from .block_layout_mixin import BlockLayoutMixin
from .media_renderer_mixin import MediaRendererMixin
from .scroll_sync_mixin import ScrollSyncMixin
from .selection_mixin import SelectionMixin
from .table_renderer_mixin import TableRendererMixin
from .text_renderer_mixin import TextRendererMixin


class MarkdownCanvas(
    ScrollSyncMixin,
    BlockLayoutMixin,
    TextRendererMixin,
    TableRendererMixin,
    MediaRendererMixin,
    SelectionMixin,
    Gtk.DrawingArea,
):
    """DrawingArea that renders a list of ContentBlocks using GtkSnapshot."""

    __gtype_name__ = "MarkdownCanvas"

    PAD_LEFT = 24
    PAD_RIGHT = 24
    PAD_TOP = 16
    BLOCK_SPACING = 10
    CODE_PAD = 12
    # Extra top margin before headings (CSS-style margin-top)
    HEADING_MARGIN_TOP = {1: 28, 2: 24, 3: 20, 4: 16, 5: 14, 6: 14}
    # Extra bottom margin after headings (space between heading and next content)
    HEADING_MARGIN_BOTTOM = {1: 10, 2: 8, 3: 6, 4: 4, 5: 4, 6: 4}
    LINE_SPACING = 4  # extra pixels between wrapped lines inside a block
    QUOTE_BAR_WIDTH = 3
    QUOTE_INDENT = 16
    COLLAPSIBLE_INDENT = 20
    CHEVRON_WIDTH = 16

    # Heading sizes relative to base font size
    HEADING_SCALES = {1: 2.0, 2: 1.5, 3: 1.25, 4: 1.1, 5: 1.0, 6: 0.9}

    def __init__(self):
        super().__init__()

        self._blocks: list[ContentBlock] = []
        self._scrolled_window = None
        self._vadjustment = None
        self._vadjustment_handler_id = None
        self._page_size_handler_id = None

        # Font
        self._base_font_size = 14
        self._font_desc = Pango.FontDescription.from_string(f"sans {self._base_font_size}")
        from fonts import get_font_settings as _get_font_settings

        _editor = _get_font_settings("editor")
        self._mono_font_desc = Pango.FontDescription.from_string(f"{_editor['family']} {self._base_font_size - 1}")
        self._line_height = 0
        self._char_width = 0
        self._measured = False

        # Colors (defaults -- overridden by set_theme)
        self._fg_hex = "#e0e0e0"
        self._bg_hex = "#1e1e1e"
        self._code_bg_hex = "#2d2d2d"
        self._accent_hex = "#61afef"
        self._dim_hex = "#808080"
        self._border_hex = "#3e3e3e"
        self._selection_bg_hex = "#264f78"

        self._fg_rgba = hex_to_gdk_rgba(self._fg_hex)
        self._bg_rgba = hex_to_gdk_rgba(self._bg_hex)
        self._code_bg_rgba = hex_to_gdk_rgba(self._code_bg_hex)
        self._accent_rgba = hex_to_gdk_rgba(self._accent_hex)
        self._dim_rgba = hex_to_gdk_rgba(self._dim_hex)
        self._border_rgba = hex_to_gdk_rgba(self._border_hex)
        self._selection_rgba = hex_to_gdk_rgba(self._selection_bg_hex)
        self._selection_rgba.alpha = 0.4

        # Selection state: (region_idx, byte_idx) tuples
        self._sel_anchor = None
        self._sel_cursor = None
        self._has_selection = False
        self._drag_start_x = 0.0
        self._drag_start_y = 0.0
        self._multi_click_mode = 0  # 0=normal, 2=word, 3=line

        # Text region cache for hit testing: [(layout, x, y), ...]
        self._text_regions: list[tuple] = []
        self._draw_x_offset = 0.0

        # Layout cache valid width
        self._layout_width = -1

        # State
        self._needs_layout = True
        self._redraw_scheduled = False

        # Zoom
        self._zoom_level = 1.0

        # Smooth scroll animation state
        self._smooth_target_y: float | None = None
        self._smooth_tick_id: int = 0
        self._LERP_FACTOR = 0.25  # fraction of remaining distance per frame
        self._animation_adjusting = False  # True while set_value runs inside tick

        # Image cache: url -> Gdk.Texture (None means load failed)
        self._image_cache: dict[str, Gdk.Texture | None] = {}
        self._base_path: str | None = None
        self._IMAGE_MAX_HEIGHT = 600

        # Remote image download cache directory
        self._remote_cache_dir = os.path.join(tempfile.gettempdir(), ".zen_image_cache")
        os.makedirs(self._remote_cache_dir, exist_ok=True)
        # URLs currently being fetched (to avoid duplicate requests)
        self._fetching_urls: set[str] = set()

        # Setup
        self.set_hexpand(True)
        self.set_vexpand(True)
        self.set_can_focus(True)
        self.set_focusable(True)
        self._setup_event_controllers()

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    @property
    def is_animation_adjusting(self) -> bool:
        """True when the canvas is programmatically adjusting scroll (animation frame)."""
        return self._animation_adjusting

    def set_blocks(self, blocks: list[ContentBlock]):
        """Set the content blocks to render."""
        self._blocks = blocks
        self._needs_layout = True
        self._schedule_redraw()

    def set_base_path(self, path: str | None):
        """Set base directory for resolving relative image paths."""
        if path != self._base_path:
            self._base_path = path
            self._image_cache.clear()

    def get_blocks(self) -> list[ContentBlock]:
        return self._blocks

    def set_theme(self, fg: str, bg: str, code_bg: str, accent: str, dim: str, border: str, selection_bg: str = ""):
        """Apply theme colors (hex strings)."""
        self._fg_hex = fg
        self._bg_hex = bg
        self._code_bg_hex = code_bg
        self._accent_hex = accent
        self._dim_hex = dim
        self._border_hex = border
        if selection_bg:
            self._selection_bg_hex = selection_bg

        self._fg_rgba = hex_to_gdk_rgba(fg)
        self._bg_rgba = hex_to_gdk_rgba(bg)
        self._code_bg_rgba = hex_to_gdk_rgba(code_bg)
        self._accent_rgba = hex_to_gdk_rgba(accent)
        self._dim_rgba = hex_to_gdk_rgba(dim)
        self._border_rgba = hex_to_gdk_rgba(border)
        if selection_bg:
            self._selection_rgba = hex_to_gdk_rgba(selection_bg)
            self._selection_rgba.alpha = 0.4

        self._schedule_redraw()

    def set_font(self, font_family: str, size: int):
        """Set the base font."""
        self._base_font_size = size
        self._font_desc = Pango.FontDescription.from_string(f"{font_family} {size}")
        from fonts import get_font_settings as _get_font_settings

        _editor = _get_font_settings("editor")
        self._mono_font_desc = Pango.FontDescription.from_string(f"{_editor['family']} {max(size - 1, 10)}")
        self._measured = False
        self._needs_layout = True
        self._schedule_redraw()

    def attach_to_scrolled_window(self, scrolled_window):
        """Bind redraws to the parent ScrolledWindow's vertical adjustment."""
        if self._scrolled_window is scrolled_window:
            return
        self._scrolled_window = scrolled_window
        scrolled_window.connect("notify::vadjustment", self._on_vadjustment_changed)
        self._connect_vadjustment(scrolled_window.get_vadjustment())

    def zoom_in(self):
        self._zoom_level = min(self._zoom_level + 0.1, 3.0)
        self._apply_zoom()

    def zoom_out(self):
        self._zoom_level = max(self._zoom_level - 0.1, 0.5)
        self._apply_zoom()

    def zoom_reset(self):
        self._zoom_level = 1.0
        self._apply_zoom()

    # ------------------------------------------------------------------ #
    #  Rendering (GtkSnapshot)                                             #
    # ------------------------------------------------------------------ #

    def do_snapshot(self, snapshot):
        """Render visible blocks using GtkSnapshot + Pango."""
        width = self.get_width()
        height = self.get_height()
        if width <= 0 or height <= 0:
            return

        if not self._measured:
            self._measure_font()

        content_width = width - self.PAD_LEFT - self.PAD_RIGHT
        if content_width <= 0:
            content_width = 100

        # Re-layout if width changed or layout needed
        if self._needs_layout or self._layout_width != content_width:
            self._layout_blocks(content_width)

        # Background
        rect = Graphene.Rect()
        rect.init(0, 0, width, height)
        snapshot.append_color(self._bg_rgba, rect)

        # Reset text region cache for hit testing
        self._text_regions = []
        self._draw_x_offset = 0.0

        if not self._blocks:
            return

        scroll_y = self._get_scroll_y()
        visible_height = self._get_visible_height()
        pango_ctx = self.get_pango_context()

        # Draw ALL blocks -- no viewport culling.
        # On macOS GTK4, do_snapshot may not be re-invoked on every scroll
        # despite queue_draw(); rendering every block ensures the full
        # snapshot is available for the viewport to translate freely.
        # Cost is negligible (just lightweight render-node creation).
        for block in self._blocks:
            self._draw_block(snapshot, pango_ctx, block, width, scroll_y, visible_height)

        # Draw selection overlay on top
        if self._has_selection:
            self._draw_selection_overlay(snapshot)

    def _draw_block(
        self, snapshot, pango_ctx, block: ContentBlock, width: float, scroll_y: float = 0.0, visible_height: float = 1e9
    ):
        """Draw a single block, dispatching by kind."""
        if block.collapsible:
            self._draw_collapsible(snapshot, pango_ctx, block, width, scroll_y, visible_height)
        elif block.kind == "heading":
            self._draw_heading(snapshot, pango_ctx, block, width)
        elif block.kind == "paragraph":
            self._draw_paragraph(snapshot, pango_ctx, block, width)
        elif block.kind == "code":
            self._draw_code_block(snapshot, pango_ctx, block, width)
        elif block.kind == "table":
            self._draw_table(snapshot, pango_ctx, block, width)
        elif block.kind == "list":
            self._draw_list(snapshot, pango_ctx, block, width)
        elif block.kind == "blockquote":
            self._draw_blockquote(snapshot, pango_ctx, block, width)
        elif block.kind == "hr":
            self._draw_hr(snapshot, block, width)
        elif block.kind == "image":
            self._draw_image(snapshot, pango_ctx, block, width)
        elif block.kind == "image_row":
            self._draw_image_row(snapshot, pango_ctx, block, width)

    # ------------------------------------------------------------------ #
    #  Font measurement                                                    #
    # ------------------------------------------------------------------ #

    def _measure_font(self):
        """Measure base font metrics for line height."""
        pango_ctx = self.get_pango_context()
        if pango_ctx is None:
            return
        layout = Pango.Layout.new(pango_ctx)
        layout.set_font_description(self._font_desc)
        layout.set_text("Mg", -1)
        _, logical = layout.get_extents()
        self._line_height = max(round(logical.height / Pango.SCALE) + 2, 1)
        self._char_width = max(logical.width / Pango.SCALE / 2, 1.0)
        self._measured = True

    # ------------------------------------------------------------------ #
    #  Sizing and scrolling                                                #
    # ------------------------------------------------------------------ #

    def _connect_vadjustment(self, vadjustment):
        if self._vadjustment is vadjustment:
            return
        if self._vadjustment is not None and self._vadjustment_handler_id is not None:
            self._vadjustment.disconnect(self._vadjustment_handler_id)
        if self._vadjustment is not None and self._page_size_handler_id is not None:
            self._vadjustment.disconnect(self._page_size_handler_id)
        self._vadjustment = vadjustment
        self._vadjustment_handler_id = None
        self._page_size_handler_id = None
        if vadjustment is not None:
            self._vadjustment_handler_id = vadjustment.connect("value-changed", self._on_scroll_value_changed)
            self._page_size_handler_id = vadjustment.connect("notify::page-size", self._on_page_size_changed)

    def _on_vadjustment_changed(self, scrolled_window, pspec):
        self._connect_vadjustment(scrolled_window.get_vadjustment())

    def _on_scroll_value_changed(self, adjustment):
        self.queue_draw()

    def _on_page_size_changed(self, adjustment, pspec):
        """Redraw when the viewport height changes (e.g. panel resize)."""
        self.queue_draw()

    def _get_vadjustment(self):
        parent = self.get_parent()
        while parent is not None:
            if isinstance(parent, Gtk.ScrolledWindow):
                return parent.get_vadjustment()
            parent = parent.get_parent()
        return None

    def _get_scroll_y(self) -> float:
        vadj = self._get_vadjustment()
        return vadj.get_value() if vadj else 0.0

    def _get_visible_height(self) -> float:
        vadj = self._get_vadjustment()
        if vadj:
            ps = vadj.get_page_size()
            if ps > 0:
                return ps
        # Fallback when page_size is 0 (e.g. during macOS surface transitions)
        return float(self.get_height()) or 100.0

    def _schedule_redraw(self):
        if not self._redraw_scheduled:
            self._redraw_scheduled = True
            GLib.idle_add(self._do_redraw)

    def _do_redraw(self):
        self._redraw_scheduled = False
        self.queue_draw()
        return False

    def _apply_zoom(self):
        self._needs_layout = True
        self._schedule_redraw()
