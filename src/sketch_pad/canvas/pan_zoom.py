"""
Pan and zoom transform mixin for SketchCanvas.
"""

import platform

from gi.repository import Gdk, GLib, Graphene, Gtk, Pango

from shared.utils import tuple_to_gdk_rgba
from sketch_pad.sketch_model import _render_font_size_texts
from themes import get_theme

from .helpers import _hex

_MOD = Gdk.ModifierType.META_MASK if platform.system() == "Darwin" else Gdk.ModifierType.CONTROL_MASK


class PanZoomMixin:
    """Mixin providing pan, zoom, scroll, pinch-to-zoom, and image export."""

    def _on_scroll(self, controller, dx, dy):
        state = controller.get_current_event_state()
        if state & _MOD:
            self.zoom(-0.1 if dy > 0 else 0.1)
        else:
            self._target_pan_x -= dx * self._SCROLL_PAN_STEP / self._zoom
            self._target_pan_y -= dy * self._SCROLL_PAN_STEP / self._zoom
            if self._scroll_tick_id is None:
                self._scroll_tick_id = self.add_tick_callback(self._scroll_tick)
        return True

    def _on_scroll_end(self, controller):
        """Snap to final target when kinetic scrolling finishes."""
        if self._scroll_tick_id is not None:
            self._pan_x = self._target_pan_x
            self._pan_y = self._target_pan_y
            self._clamp_pan()
            self._target_pan_x = self._pan_x
            self._target_pan_y = self._pan_y
            self.remove_tick_callback(self._scroll_tick_id)
            self._scroll_tick_id = None
            self.queue_draw()

    def _scroll_tick(self, widget, frame_clock):
        lerp = self._smooth_lerp
        prev_x, prev_y = self._pan_x, self._pan_y
        self._pan_x += (self._target_pan_x - self._pan_x) * lerp
        self._pan_y += (self._target_pan_y - self._pan_y) * lerp
        self._clamp_pan()
        # If clamped, snap target to actual to avoid fighting the boundary
        if self._pan_x != prev_x + (self._target_pan_x - prev_x) * lerp:
            self._target_pan_x = self._pan_x
        if self._pan_y != prev_y + (self._target_pan_y - prev_y) * lerp:
            self._target_pan_y = self._pan_y
        self.queue_draw()
        # Stop ticking once close enough
        if abs(self._target_pan_x - self._pan_x) < 0.5 and abs(self._target_pan_y - self._pan_y) < 0.5:
            self._pan_x = self._target_pan_x
            self._pan_y = self._target_pan_y
            self._scroll_tick_id = None
            return GLib.SOURCE_REMOVE
        return GLib.SOURCE_CONTINUE

    def _on_pinch_begin(self, gesture, sequence):
        self._pinch_start_zoom = self._zoom

    def _on_pinch_scale_changed(self, gesture, scale):
        new_zoom = max(0.3, min(3.0, self._pinch_start_zoom * scale))
        if new_zoom == self._zoom:
            return
        ok, cx, cy = gesture.get_bounding_box_center()
        if ok:
            old_zoom = self._zoom
            self._pan_x += cx / new_zoom - cx / old_zoom
            self._pan_y += cy / new_zoom - cy / old_zoom
        self._zoom = new_zoom
        self._target_pan_x = self._pan_x
        self._target_pan_y = self._pan_y
        self._clamp_pan()
        self.queue_draw()

    def zoom(self, delta: float):
        self._zoom = max(0.3, min(3.0, self._zoom + delta))
        self._clamp_pan()
        self.queue_draw()

    def zoom_reset(self):
        self._zoom = 1.0
        self._pan_x = 0.0
        self._pan_y = 0.0
        self._target_pan_x = 0.0
        self._target_pan_y = 0.0
        self._clamp_pan()
        self.queue_draw()

    def export_to_image(self, path: str):
        """Export the current sketch to a PNG or JPEG image file."""
        grid = self._board.render()

        # Compute bounds on a separate copy that includes font_size text
        # so the image is large enough, but don't pollute the drawing grid
        # (font_size text is rendered separately by _draw_custom_font_texts).
        bounds_grid = dict(grid)
        _render_font_size_texts(self._board.z_sorted(), bounds_grid)
        if not bounds_grid:
            return

        padding = 20
        scale = 2  # HiDPI export for crisp text
        min_col = min(c for c, _ in bounds_grid)
        max_col = max(c for c, _ in bounds_grid)
        min_row = min(r for _, r in bounds_grid)
        max_row = max(r for _, r in bounds_grid)

        img_w = int((max_col - min_col + 1) * self._cell_w + padding * 2)
        img_h = int((max_row - min_row + 1) * self._cell_h + padding * 2)
        img_w = max(img_w, 1)
        img_h = max(img_h, 1)

        # Build render node tree using GtkSnapshot
        snap = Gtk.Snapshot()
        snap.scale(scale, scale)

        # Background
        if self._dark_mode:
            bg = _hex(get_theme().panel_bg)
            fg = _hex(get_theme().fg_color)
        else:
            bg = _hex(get_theme().fg_color)
            fg = _hex(get_theme().panel_bg)
        snap.append_color(tuple_to_gdk_rgba(bg), Graphene.Rect().init(0, 0, img_w, img_h))

        snap.save()
        snap.translate(Graphene.Point().init(padding - min_col * self._cell_w, padding - min_row * self._cell_h))

        # Draw grid chars (excludes font_size text to avoid double rendering)
        fd = Pango.FontDescription.new()
        fd.set_family(self._grid_font_family)
        fd.set_size(int(self._font_size * Pango.SCALE))
        self._draw_chars(snap, grid, fd, fg)

        # Custom font-size texts rendered via Pango (single source of truth)
        self._draw_custom_font_texts(snap, fg)

        snap.restore()

        node = snap.to_node()
        if not node:
            return

        # Render to texture using the widget's GPU renderer
        renderer = self.get_native().get_renderer()
        viewport = Graphene.Rect().init(0, 0, img_w * scale, img_h * scale)
        texture = renderer.render_texture(node, viewport)

        lower = path.lower()
        if lower.endswith((".jpg", ".jpeg")):
            # Convert texture to JPEG via PIL
            png_bytes = texture.save_to_png_bytes()
            try:
                import io

                from PIL import Image

                img = Image.open(io.BytesIO(png_bytes.get_data()))
                img = img.convert("RGB")
                img.save(path, "JPEG", quality=95)
            except ImportError:
                # Fallback: save as PNG if PIL not available
                fallback = path.rsplit(".", 1)[0] + ".png"
                texture.save_to_png(fallback)
                return fallback
        else:
            texture.save_to_png(path)

        return path
