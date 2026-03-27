"""
Keyboard handling and clipboard operations mixin for SketchCanvas.
"""

import platform

from gi.repository import Gdk

from sketch_pad.sketch_model import (
    _CLIPBOARD_XLAT,
    AbstractShape,
    ArrowShape,
    RectangleShape,
    ToolMode,
    _render_font_size_texts,
)

_MOD = Gdk.ModifierType.META_MASK if platform.system() == "Darwin" else Gdk.ModifierType.CONTROL_MASK


class KeyboardMixin:
    """Mixin providing keyboard event handling and clipboard operations."""

    def _on_key(self, controller, keyval, keycode, state):
        if self._text_editing:
            return self._handle_text_key(keyval, state)

        mod = state & _MOD

        # Undo / Redo
        if mod and keyval == Gdk.KEY_z:
            if state & Gdk.ModifierType.SHIFT_MASK:
                self.redo()
            else:
                self.undo()
            return True

        # Copy / Cut / Paste
        if mod and keyval == Gdk.KEY_c:
            self._copy_selection()
            return True
        if mod and keyval == Gdk.KEY_x:
            self._cut_selection()
            return True
        if mod and keyval == Gdk.KEY_v:
            self._paste()
            return True

        # Select all
        if mod and keyval == Gdk.KEY_a:
            self._selected_ids = set(self._board.shapes.keys())
            self.queue_draw()
            return True

        # Zoom in / out / reset
        if mod and keyval in (Gdk.KEY_equal, Gdk.KEY_plus):
            self.zoom(0.1)
            return True
        if mod and keyval == Gdk.KEY_minus:
            self.zoom(-0.1)
            return True
        if mod and keyval == Gdk.KEY_0:
            self.zoom_reset()
            return True

        # Delete
        if keyval in (Gdk.KEY_Delete, Gdk.KEY_BackSpace) and self._selected_ids:
            for sid in list(self._selected_ids):
                self._board.remove_shape(sid)
            self._selected_ids.clear()
            self._snapshot_history()
            self.queue_draw()
            return True

        # Arrow keys -- move selection
        if self._selected_ids and keyval in (Gdk.KEY_Left, Gdk.KEY_Right, Gdk.KEY_Up, Gdk.KEY_Down):
            dc = {Gdk.KEY_Left: -1, Gdk.KEY_Right: 1}.get(keyval, 0)
            dr = {Gdk.KEY_Up: -1, Gdk.KEY_Down: 1}.get(keyval, 0)
            if self._text_only_selection and len(self._selected_ids) == 1:
                for shape in self.selected_shapes:
                    if isinstance(shape, ArrowShape):
                        shape.text_offset_col += dc
                        shape.text_offset_row += dr
                    else:
                        shape.move(dc, dr)
            else:
                for shape in self.selected_shapes:
                    shape.move(dc, dr)
            self._board.update_connections()
            self._snapshot_history()
            self.queue_draw()
            return True

        # Escape
        if keyval == Gdk.KEY_Escape:
            self._selected_ids.clear()
            self.queue_draw()
            return True

        # Tool shortcuts
        tool_keys = {
            Gdk.KEY_v: ToolMode.SELECT,
            Gdk.KEY_V: ToolMode.SELECT,
            Gdk.KEY_h: ToolMode.PAN,
            Gdk.KEY_H: ToolMode.PAN,
            Gdk.KEY_r: ToolMode.RECTANGLE,
            Gdk.KEY_R: ToolMode.RECTANGLE,
            Gdk.KEY_b: ToolMode.RECTANGLE,
            Gdk.KEY_B: ToolMode.RECTANGLE,
            Gdk.KEY_a: ToolMode.ARROW,
            Gdk.KEY_A: ToolMode.ARROW,
            Gdk.KEY_l: ToolMode.ARROW,
            Gdk.KEY_L: ToolMode.ARROW,
            Gdk.KEY_p: ToolMode.ACTOR,
            Gdk.KEY_P: ToolMode.ACTOR,
            Gdk.KEY_t: ToolMode.TOPIC,
            Gdk.KEY_T: ToolMode.TOPIC,
            Gdk.KEY_d: ToolMode.DATABASE,
            Gdk.KEY_D: ToolMode.DATABASE,
            Gdk.KEY_c: ToolMode.CLOUD,
            Gdk.KEY_C: ToolMode.CLOUD,
        }
        if keyval in tool_keys and not mod:
            self.tool = tool_keys[keyval]
            return True

        # Grid toggle
        if keyval in (Gdk.KEY_g, Gdk.KEY_G) and not mod:
            self._show_grid = not self._show_grid
            self.queue_draw()
            return True

        # Dark mode toggle
        if keyval in (Gdk.KEY_m, Gdk.KEY_M) and not mod:
            self._dark_mode = not self._dark_mode
            if self._on_dark_mode_change:
                self._on_dark_mode_change(self._dark_mode)
            self.queue_draw()
            return True

        return False

    # ─────────────────────── Clipboard ───────────────────────

    # In-memory buffer keeps structured shape data for internal paste;
    # the system clipboard gets visual ASCII art for external paste.
    _internal_clipboard: list[dict] | None = None

    def _copy_selection(self):
        if not self._selected_ids:
            return
        shapes = list(self.selected_shapes)
        if not shapes:
            return
        # Store structured data in memory for internal paste
        from sketch_pad.canvas.core import SketchCanvas

        SketchCanvas._internal_clipboard = [s.to_dict() for s in shapes]
        # Put visual ASCII art on the system clipboard for external paste
        grid: dict[tuple[int, int], str] = {}
        # Render arrows first, then boxes on top (same order as Board.render)
        for s in sorted(shapes, key=lambda s: s.z_order):
            if isinstance(s, ArrowShape):
                s.render(grid)
        for s in sorted(shapes, key=lambda s: s.z_order):
            if not isinstance(s, ArrowShape):
                s.render(grid)
        _render_font_size_texts(shapes, grid)
        ascii_art = self._grid_to_text(grid)
        if ascii_art:
            self.get_clipboard().set(ascii_art)

    def _cut_selection(self):
        self._copy_selection()
        for sid in list(self._selected_ids):
            self._board.remove_shape(sid)
        self._selected_ids.clear()
        self._snapshot_history()
        self.queue_draw()

    def _paste(self):
        from sketch_pad.canvas.core import SketchCanvas

        if SketchCanvas._internal_clipboard:
            self._paste_shapes(SketchCanvas._internal_clipboard)
        else:
            self.get_clipboard().read_text_async(None, self._on_paste_done)

    def _paste_shapes(self, shape_dicts: list[dict]):
        """Paste shapes from the internal clipboard buffer."""
        import copy as _copy
        import uuid as _uuid

        shape_dicts = _copy.deepcopy(shape_dicts)
        id_map = {}
        for sd in shape_dicts:
            old_id = sd.get("id", "")
            new_id = _uuid.uuid4().hex[:8]
            id_map[old_id] = new_id
            sd["id"] = new_id
        for sd in shape_dicts:
            if sd.get("type") == "arrow":
                for conn_key in ("start_connection", "end_connection"):
                    conn = sd.get(conn_key)
                    if conn and conn.get("shape_id") in id_map:
                        conn["shape_id"] = id_map[conn["shape_id"]]
        new_ids = set()
        for sd in shape_dicts:
            shape = AbstractShape.from_dict(sd)
            self._board.add_shape(shape)
            new_ids.add(shape.id)
        self._selected_ids = new_ids
        self._snapshot_history()
        self.queue_draw()

    def _on_paste_done(self, clipboard, result):
        try:
            text = clipboard.read_text_finish(result)
        except Exception:
            return
        if not text:
            return

        # Fallback: paste plain text as a rectangle
        shape = RectangleShape(
            left=0, top=0, width=max(len(l) for l in text.split("\n")) + 2, height=len(text.split("\n")) + 2, text=text
        )
        self._board.add_shape(shape)
        self._selected_ids = {shape.id}
        self._snapshot_history()
        self.queue_draw()

    @staticmethod
    def _grid_to_text(grid: dict) -> str:
        if not grid:
            return ""
        min_c = min(c for c, _ in grid)
        max_c = max(c for c, _ in grid)
        min_r = min(r for _, r in grid)
        max_r = max(r for _, r in grid)
        lines = []
        for row in range(min_r, max_r + 1):
            lines.append("".join(grid.get((col, row), " ") for col in range(min_c, max_c + 1)).rstrip())
        while lines and not lines[-1]:
            lines.pop()
        return "\n".join(lines).translate(_CLIPBOARD_XLAT)

    def _show_shape_properties(self, shapes, sx, sy, *, text_only=False):
        """Show the shape properties popup for selected shape(s)."""
        parent = self.get_root()
        if not parent:
            return
        from sketch_pad.shape_properties_popup import ShapePropertiesPopup

        def on_apply(shape_id, **props):
            self.set_shape_property(shape_id, **props)

        popup = ShapePropertiesPopup(parent, shapes, on_apply, text_only=text_only)
        popup.present()
