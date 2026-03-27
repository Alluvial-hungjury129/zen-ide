"""
Mouse drag, resize, select, and marquee mixin for SketchCanvas.
"""

from gi.repository import Gdk

from sketch_pad.sketch_model import (
    ActorShape,
    ArrowShape,
    DatabaseShape,
    ToolMode,
)


class InteractionMixin:
    """Mixin providing mouse drag, move, and marquee operations."""

    def _on_click(self, gesture, n_press, x, y):
        """Handle clicks: single-click exits text edit; double-click enters it."""
        # Single click while text editing: exit if outside shape, stay if inside
        if n_press == 1 and self._text_editing:
            col, row = self._screen_to_grid(x, y)
            shape = self._board.get_shape(self._text_shape_id)
            if not shape or not shape.contains(col, row):
                self._exit_text_edit()
                self._selected_ids.clear()
            self._double_click_pending = True  # always suppress drag-begin
            self.queue_draw()
            return

        if n_press >= 2:
            self._double_click_pending = True
            self._cancel_drawing()
            col, row = self._screen_to_grid(x, y)
            shape = self._board.get_shape_at(col, row)
            if shape:
                self._start_text_edit_for_shape(shape)
            else:
                # Multi-click outside any shape: exit text edit and deselect
                self._exit_text_edit()
                self._selected_ids.clear()
            self.queue_draw()

    def _cancel_drawing(self):
        self._drawing = False
        self._draw_start = None
        self._draw_end = None
        self._draw_snap_start = None
        self._draw_snap_end = None
        self._drag_start_screen = None
        self._marquee_selecting = False
        self._marquee_start = None
        self._marquee_end = None

    def _on_drag_begin(self, gesture, sx, sy):
        self.grab_focus()

        # Skip if double-click was just handled
        if self._double_click_pending:
            self._double_click_pending = False
            return

        btn = gesture.get_current_button()
        col, row = self._screen_to_grid(sx, sy)

        # Right-click -> shape properties popup or pan
        if btn == 3:
            shape = self._board.get_shape_at(col, row)
            if shape:
                text_only = isinstance(shape, ArrowShape) and shape.text_contains(col, row)
                if shape.id in self._selected_ids and len(self._selected_ids) > 1:
                    shapes = self.selected_shapes
                else:
                    self._selected_ids = {shape.id}
                    self._text_only_selection = text_only
                    shapes = [shape]
                self.queue_draw()
                self._show_shape_properties(shapes, sx, sy, text_only=text_only)
                return
            self._panning = True
            self._pan_start_offset = (self._pan_x, self._pan_y)
            self._drag_start_screen = (sx, sy)
            return

        # Middle-click -> pan
        if btn == 2:
            self._panning = True
            self._pan_start_offset = (self._pan_x, self._pan_y)
            self._drag_start_screen = (sx, sy)
            return

        if btn != 1:
            return

        # Pan tool -- left-click drag pans the view
        if self._tool == ToolMode.PAN:
            self._panning = True
            self._pan_start_offset = (self._pan_x, self._pan_y)
            self._drag_start_screen = (sx, sy)
            return

        # Text editing is fully handled by _on_click; never start drag while editing
        if self._text_editing:
            return

        if self._tool == ToolMode.SELECT:
            # Check resize/endpoint handles BEFORE re-selecting (handles may be outside shape body)
            if len(self._selected_ids) == 1:
                # Arrow endpoint handles
                for shape in self.selected_shapes:
                    if isinstance(shape, ArrowShape):
                        ep = self._hit_arrow_endpoint(shape, sx, sy)
                        if ep:
                            self._arrow_ep_dragging = True
                            self._arrow_ep_end = ep
                            self._arrow_ep_shape_id = shape.id
                            self._drag_start_screen = (sx, sy)
                            return

                # Rectangle resize handles
                handle = self._hit_resize_handle(sx, sy)
                if handle:
                    shape = self.selected_shapes[0]
                    self._resizing = True
                    self._resize_handle = handle
                    self._resize_shape_id = shape.id
                    self._resize_orig = shape.to_dict()
                    self._drag_start_screen = (sx, sy)
                    return

            # Select shape under cursor (pass modifier for Cmd+click multi-select)
            state = gesture.get_current_event_state()
            cmd_held = bool(state & Gdk.ModifierType.META_MASK)
            self._handle_select_press(col, row, sx, sy, cmd_held=cmd_held)

            # Move drag
            if self._selected_ids:
                for shape in self.selected_shapes:
                    if shape.contains(col, row):
                        self._dragging = True
                        self._drag_start_screen = (sx, sy)
                        self._drag_start_pos = {}
                        for s in self.selected_shapes:
                            if isinstance(s, ArrowShape):
                                if self._text_only_selection and len(self._selected_ids) == 1:
                                    self._drag_start_pos[s.id] = (s.text_offset_col, s.text_offset_row)
                                else:
                                    self._drag_start_pos[s.id] = (s.start_col, s.start_row, s.end_col, s.end_row)
                            else:
                                self._drag_start_pos[s.id] = (s.left, s.top)
                        return

        elif self._tool == ToolMode.RECTANGLE:
            self._drawing = True
            self._draw_start = (col, row)
            self._draw_end = (col, row)
            self._drag_start_screen = (sx, sy)

        elif self._tool == ToolMode.ARROW:
            self._drawing = True
            snap = self._board.snap_to_edge(col, row)
            if snap:
                conn, sc, sr = snap
                self._draw_start = (sc, sr)
                self._draw_snap_start = snap
            else:
                self._draw_start = (col, row)
                self._draw_snap_start = None
            self._draw_end = self._draw_start
            self._drag_start_screen = (sx, sy)

        elif self._tool == ToolMode.ACTOR:
            # Place actor immediately on click, then revert to select
            actor = ActorShape(left=col, top=row)
            self._board.add_shape(actor)
            self._selected_ids = {actor.id}
            self._snapshot_history()
            self._tool = ToolMode.SELECT
            if self._on_tool_change:
                self._on_tool_change(ToolMode.SELECT)
            self.queue_draw()

        elif self._tool == ToolMode.DATABASE:
            # Place database immediately on click, then revert to select
            db = DatabaseShape(left=col, top=row)
            self._board.add_shape(db)
            self._selected_ids = {db.id}
            self._snapshot_history()
            self._tool = ToolMode.SELECT
            if self._on_tool_change:
                self._on_tool_change(ToolMode.SELECT)
            self.queue_draw()

        elif self._tool == ToolMode.TOPIC:
            self._drawing = True
            self._draw_start = (col, row)
            self._draw_end = (col, row)
            self._drag_start_screen = (sx, sy)

        elif self._tool == ToolMode.CLOUD:
            self._drawing = True
            self._draw_start = (col, row)
            self._draw_end = (col, row)
            self._drag_start_screen = (sx, sy)

    def _on_drag_update(self, gesture, ox, oy):
        # Drawing creation
        if self._drawing and self._draw_start and self._drag_start_screen:
            sx, sy = self._drag_start_screen
            col, row = self._screen_to_grid(sx + ox, sy + oy)
            if self._tool == ToolMode.ARROW:
                snap = self._board.snap_to_edge(col, row)
                if snap:
                    self._draw_end = (snap[1], snap[2])
                    self._draw_snap_end = snap
                else:
                    self._draw_end = (col, row)
                    self._draw_snap_end = None
            else:
                self._draw_end = (col, row)
            self.queue_draw()
            return

        # Arrow endpoint drag
        if self._arrow_ep_dragging and self._drag_start_screen:
            sx, sy = self._drag_start_screen
            col, row = self._screen_to_grid(sx + ox, sy + oy)
            shape = self._board.get_shape(self._arrow_ep_shape_id)
            if shape and isinstance(shape, ArrowShape):
                snap = self._board.snap_to_edge(col, row, exclude_id=shape.id)
                if self._arrow_ep_end == "start":
                    if snap:
                        shape.start_col, shape.start_row = snap[1], snap[2]
                        conn = snap[0]
                        conn.pinned = True
                        shape.start_connection = conn
                    else:
                        shape.start_col, shape.start_row = col, row
                        shape.start_connection = None
                else:
                    if snap:
                        shape.end_col, shape.end_row = snap[1], snap[2]
                        conn = snap[0]
                        conn.pinned = True
                        shape.end_connection = conn
                    else:
                        shape.end_col, shape.end_row = col, row
                        shape.end_connection = None
                shape._update_bounds()
            self.queue_draw()
            return

        # Rectangle resize
        if self._resizing and self._drag_start_screen and self._resize_orig:
            sx, sy = self._drag_start_screen
            col, row = self._screen_to_grid(sx + ox, sy + oy)
            self._apply_resize(col, row)
            self._board.update_connections()
            self.queue_draw()
            return

        # Move
        if self._dragging and self._drag_start_screen:
            dcol = round(ox / self._zoom / self._cell_w) if self._cell_w > 0 else 0
            drow = round(oy / self._zoom / self._cell_h) if self._cell_h > 0 else 0

            # Text-only drag: move just the text offset on the arrow
            if self._text_only_selection and len(self._selected_ids) == 1:
                for shape in self.selected_shapes:
                    if isinstance(shape, ArrowShape):
                        orig = self._drag_start_pos.get(shape.id)
                        if orig and len(orig) == 2:
                            shape.text_offset_col = orig[0] + dcol
                            shape.text_offset_row = orig[1] + drow
                self.queue_draw()
                return

            moving_ids = self._selected_ids
            for shape in self.selected_shapes:
                orig = self._drag_start_pos.get(shape.id)
                if not orig:
                    continue
                if isinstance(shape, ArrowShape):
                    osc, osr, oec, oer = orig
                    if not shape.start_connection or shape.start_connection.shape_id in moving_ids:
                        shape.start_col = osc + dcol
                        shape.start_row = osr + drow
                    if not shape.end_connection or shape.end_connection.shape_id in moving_ids:
                        shape.end_col = oec + dcol
                        shape.end_row = oer + drow
                    shape._update_bounds()
                else:
                    shape.left = orig[0] + dcol
                    shape.top = orig[1] + drow
            self._board.update_connections()
            self._compute_alignment_guides()
            self.queue_draw()
            return

        # Marquee selection
        if self._marquee_selecting and self._drag_start_screen:
            sx, sy = self._drag_start_screen
            col, row = self._screen_to_grid(sx + ox, sy + oy)
            self._marquee_end = (col, row)
            self.queue_draw()
            return

        # Pan
        if self._panning and self._pan_start_offset:
            self._pan_x = self._pan_start_offset[0] + ox / self._zoom
            self._pan_y = self._pan_start_offset[1] + oy / self._zoom
            self._target_pan_x = self._pan_x
            self._target_pan_y = self._pan_y
            self._clamp_pan()
            self.queue_draw()

    def _on_drag_end(self, gesture, ox, oy):
        if self._drawing:
            if self._drag_start_screen:
                sx, sy = self._drag_start_screen
                col, row = self._screen_to_grid(sx + ox, sy + oy)
                if self._tool == ToolMode.ARROW:
                    snap = self._board.snap_to_edge(col, row)
                    if snap:
                        self._draw_end = (snap[1], snap[2])
                        self._draw_snap_end = snap
                    else:
                        self._draw_end = (col, row)
                else:
                    self._draw_end = (col, row)
            self._finish_drawing()
            self._cancel_drawing()
            self.queue_draw()
            return
        if self._arrow_ep_dragging:
            if self._drag_start_screen and self._arrow_ep_shape_id:
                sx, sy = self._drag_start_screen
                col, row = self._screen_to_grid(sx + ox, sy + oy)
                shape = self._board.get_shape(self._arrow_ep_shape_id)
                if shape and isinstance(shape, ArrowShape):
                    snap = self._board.snap_to_edge(col, row, exclude_id=shape.id)
                    if self._arrow_ep_end == "start":
                        if snap:
                            shape.start_col, shape.start_row = snap[1], snap[2]
                            conn = snap[0]
                            conn.pinned = True
                            shape.start_connection = conn
                        else:
                            shape.start_col, shape.start_row = col, row
                            shape.start_connection = None
                    else:
                        if snap:
                            shape.end_col, shape.end_row = snap[1], snap[2]
                            conn = snap[0]
                            conn.pinned = True
                            shape.end_connection = conn
                        else:
                            shape.end_col, shape.end_row = col, row
                            shape.end_connection = None
                    shape._update_bounds()
            self._arrow_ep_dragging = False
            self._arrow_ep_end = None
            self._arrow_ep_shape_id = None
            self._snapshot_history()
        if self._resizing:
            if self._drag_start_screen and self._resize_orig:
                sx, sy = self._drag_start_screen
                col, row = self._screen_to_grid(sx + ox, sy + oy)
                self._apply_resize(col, row)
            self._resizing = False
            self._resize_handle = None
            self._resize_shape_id = None
            self._resize_orig = None
            self._board.update_connections()
            self._snapshot_history()
        if self._dragging:
            if self._drag_start_screen and self._cell_w > 0 and self._cell_h > 0:
                dcol = round(ox / self._zoom / self._cell_w)
                drow = round(oy / self._zoom / self._cell_h)
                if self._text_only_selection and len(self._selected_ids) == 1:
                    for shape in self.selected_shapes:
                        if isinstance(shape, ArrowShape):
                            orig = self._drag_start_pos.get(shape.id)
                            if orig and len(orig) == 2:
                                shape.text_offset_col = orig[0] + dcol
                                shape.text_offset_row = orig[1] + drow
                else:
                    moving_ids = self._selected_ids
                    for shape in self.selected_shapes:
                        orig = self._drag_start_pos.get(shape.id)
                        if not orig:
                            continue
                        if isinstance(shape, ArrowShape):
                            osc, osr, oec, oer = orig
                            if not shape.start_connection or shape.start_connection.shape_id in moving_ids:
                                shape.start_col = osc + dcol
                                shape.start_row = osr + drow
                            if not shape.end_connection or shape.end_connection.shape_id in moving_ids:
                                shape.end_col = oec + dcol
                                shape.end_row = oer + drow
                            shape._update_bounds()
                        else:
                            shape.left = orig[0] + dcol
                            shape.top = orig[1] + drow
                    self._board.update_connections()
            self._dragging = False
            self._drag_start_pos.clear()
            self._alignment_guides.clear()
            self._snapshot_history()
        if self._marquee_selecting:
            if self._marquee_start and self._marquee_end:
                ms, me = self._marquee_start, self._marquee_end
                left = min(ms[0], me[0])
                top = min(ms[1], me[1])
                right = max(ms[0], me[0])
                bottom = max(ms[1], me[1])
                hits = self._board.shapes_in_region(left, top, right, bottom)
                self._selected_ids = {s.id for s in hits}
            self._marquee_selecting = False
            self._marquee_start = None
            self._marquee_end = None
            self.queue_draw()
        if self._panning:
            self._panning = False
            self._pan_start_offset = None
        self._drag_start_screen = None

    def _on_motion(self, controller, x, y):
        col, row = self._screen_to_grid(x, y)
        if self._on_status_change:
            self._on_status_change(col, row, int(self._zoom * 100))
