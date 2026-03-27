"""
Inline text editing mixin for SketchCanvas.
"""

import platform

from gi.repository import Gdk

from sketch_pad.sketch_model import (
    ACTOR_HEIGHT,
    ACTOR_WIDTH,
    ActorShape,
    ArrowShape,
    CloudShape,
    DatabaseShape,
    RectangleShape,
    TopicShape,
)

_MOD = Gdk.ModifierType.META_MASK if platform.system() == "Darwin" else Gdk.ModifierType.CONTROL_MASK


class TextEditingMixin:
    """Mixin providing inline text editing on shapes."""

    def _start_text_edit_for_shape(self, shape):
        self._exit_text_edit()
        # Reset any drag state left over from the first click of a double-click
        self._dragging = False
        self._drag_start_pos.clear()
        self._text_editing = True
        self._text_shape_id = shape.id
        self._selected_ids = {shape.id}

        if isinstance(shape, (RectangleShape, DatabaseShape, CloudShape)):
            self._text_buffer = shape.text.split("\n") if shape.text else [""]
            self._text_cursor_line = len(self._text_buffer) - 1
            self._text_cursor_char = len(self._text_buffer[-1])
            interior = shape.get_interior_bounds()
            if interior:
                self._update_text_cursor_position(shape)
            else:
                self._text_cursor_col = shape.left
                self._text_cursor_row = shape.top
        elif isinstance(shape, ArrowShape):
            self._text_buffer = shape.text.split("\n") if shape.text else [""]
            self._text_cursor_line = len(self._text_buffer) - 1
            self._text_cursor_char = len(self._text_buffer[-1])
            self._update_text_cursor_position(shape)
        elif isinstance(shape, ActorShape):
            self._text_buffer = [shape.text] if shape.text else [""]
            self._text_cursor_line = 0
            self._text_cursor_char = len(self._text_buffer[0])
            self._update_text_cursor_position(shape)
        elif isinstance(shape, TopicShape):
            if shape.font_size:
                self._text_buffer = shape.text.split("\n") if shape.text else [""]
                self._text_cursor_line = len(self._text_buffer) - 1
                self._text_cursor_char = len(self._text_buffer[-1])
            else:
                self._text_buffer = [shape.text] if shape.text else [""]
                self._text_cursor_line = 0
                self._text_cursor_char = len(self._text_buffer[0])
            self._update_text_cursor_position(shape)
        self._collapse_selection()
        self.queue_draw()

    def _exit_text_edit(self):
        if not self._text_editing:
            return
        self._text_editing = False
        shape = self._board.get_shape(self._text_shape_id) if self._text_shape_id else None
        if shape:
            text = "\n".join(self._text_buffer)
            if isinstance(shape, (RectangleShape, DatabaseShape, ArrowShape, CloudShape)):
                shape.text = text
            elif isinstance(shape, ActorShape):
                shape.text = self._text_buffer[0] if self._text_buffer else ""
                shape.__post_init__()  # Update bounds for text
            elif isinstance(shape, TopicShape):
                if shape.font_size:
                    shape.text = text
                else:
                    shape.text = self._text_buffer[0] if self._text_buffer else ""
            self._snapshot_history()
        self._text_shape_id = None
        self._text_buffer = []
        self._text_cursor_line = 0
        self._text_cursor_char = 0
        self._text_sel_anchor_line = 0
        self._text_sel_anchor_char = 0
        self.queue_draw()

    def _update_text_cursor_position(self, shape=None):
        """Compute cursor position from centered text layout."""
        if shape is None:
            shape = self._board.get_shape(self._text_shape_id) if self._text_shape_id else None
        if not shape:
            return
        num_lines = len(self._text_buffer)
        cur_line = self._text_cursor_line
        cur_char = self._text_cursor_char
        line_text = self._text_buffer[cur_line] if cur_line < num_lines else ""
        if isinstance(shape, (RectangleShape, DatabaseShape, CloudShape)):
            interior = shape.get_interior_bounds()
            if not interior:
                return
            il, it, ir, ib = interior
            inner_w = ir - il + 1
            inner_h = ib - it + 1
            v_offset = max(0, (inner_h - num_lines) // 2)
            h_offset = max(0, (inner_w - len(line_text)) // 2)
            self._text_cursor_row = it + v_offset + cur_line
            self._text_cursor_col = il + h_offset + cur_char
        elif isinstance(shape, ArrowShape):
            anchor = shape.get_text_anchor()
            line_text = self._text_buffer[cur_line] if cur_line < num_lines else ""
            h_offset = -(len(line_text) // 2)  # center text horizontally
            self._text_cursor_col = anchor[0] + h_offset + cur_char
            self._text_cursor_row = anchor[1] - num_lines + cur_line + 1
        elif isinstance(shape, ActorShape):
            # Text label positioned below the actor figure
            text_row = shape.top + ACTOR_HEIGHT
            text_start = shape.left + (ACTOR_WIDTH - len(line_text)) // 2
            self._text_cursor_row = text_row
            self._text_cursor_col = text_start + cur_char
        elif isinstance(shape, TopicShape):
            interior = shape.get_interior_bounds()
            if interior:
                il, it, ir, ib = interior
                inner_w = ir - il + 1
                inner_h = ib - it + 1
                v_offset = max(0, (inner_h - num_lines) // 2)
                h_offset = max(0, (inner_w - len(line_text)) // 2)
                self._text_cursor_row = it + v_offset + cur_line
                self._text_cursor_col = il + h_offset + cur_char
            else:
                left_div = 2
                right_div = shape.width - 3
                text_col = shape.left + left_div + 1 + (right_div - left_div - 1 - len(line_text)) // 2
                text_row = shape.top + shape.height // 2
                self._text_cursor_row = text_row
                self._text_cursor_col = text_col + cur_char

    def _handle_text_key(self, keyval: int, state: int) -> bool:
        mod = bool(state & _MOD)
        shift = bool(state & Gdk.ModifierType.SHIFT_MASK)
        alt = bool(state & Gdk.ModifierType.ALT_MASK)

        if keyval == Gdk.KEY_Escape:
            self._exit_text_edit()
            return True

        # Cmd+A: select all text in shape
        if mod and keyval == Gdk.KEY_a:
            self._text_sel_anchor_line = 0
            self._text_sel_anchor_char = 0
            self._text_cursor_line = len(self._text_buffer) - 1
            self._text_cursor_char = len(self._text_buffer[-1]) if self._text_buffer else 0
            self._update_text_cursor_position()
            self.queue_draw()
            return True

        # Cmd+C: copy selected text
        if mod and keyval == Gdk.KEY_c:
            text = self._get_selected_text()
            if text:
                self.get_clipboard().set(text)
            return True

        # Cmd+X: cut selected text
        if mod and keyval == Gdk.KEY_x:
            text = self._get_selected_text()
            if text:
                self.get_clipboard().set(text)
                self._delete_text_selection()
                self._sync_text()
                self._update_text_cursor_position()
                self.queue_draw()
            return True

        # Cmd+V: paste text
        if mod and keyval == Gdk.KEY_v:
            self.get_clipboard().read_text_async(None, self._on_text_edit_paste_done)
            return True

        # Arrow keys with modifier support
        if keyval == Gdk.KEY_Left:
            if not shift and self._has_text_selection():
                sl, sc, _, _ = self._get_text_selection_ordered()
                self._text_cursor_line, self._text_cursor_char = sl, sc
            elif mod:
                self._text_cursor_char = 0
            elif alt:
                self._move_cursor_word_left()
            else:
                if self._text_cursor_char > 0:
                    self._text_cursor_char -= 1
                elif self._text_cursor_line > 0:
                    self._text_cursor_line -= 1
                    self._text_cursor_char = len(self._text_buffer[self._text_cursor_line])
            if not shift:
                self._collapse_selection()
            self._update_text_cursor_position()
            self.queue_draw()
            return True

        if keyval == Gdk.KEY_Right:
            if not shift and self._has_text_selection():
                _, _, el, ec = self._get_text_selection_ordered()
                self._text_cursor_line, self._text_cursor_char = el, ec
            elif mod:
                self._text_cursor_char = len(self._text_buffer[self._text_cursor_line]) if self._text_buffer else 0
            elif alt:
                self._move_cursor_word_right()
            else:
                line = self._text_buffer[self._text_cursor_line]
                if self._text_cursor_char < len(line):
                    self._text_cursor_char += 1
                elif self._text_cursor_line < len(self._text_buffer) - 1:
                    self._text_cursor_line += 1
                    self._text_cursor_char = 0
            if not shift:
                self._collapse_selection()
            self._update_text_cursor_position()
            self.queue_draw()
            return True

        if keyval == Gdk.KEY_Up:
            if self._text_cursor_line > 0:
                self._text_cursor_line -= 1
                self._text_cursor_char = min(self._text_cursor_char, len(self._text_buffer[self._text_cursor_line]))
            if not shift:
                self._collapse_selection()
            self._update_text_cursor_position()
            self.queue_draw()
            return True

        if keyval == Gdk.KEY_Down:
            if self._text_cursor_line < len(self._text_buffer) - 1:
                self._text_cursor_line += 1
                self._text_cursor_char = min(self._text_cursor_char, len(self._text_buffer[self._text_cursor_line]))
            if not shift:
                self._collapse_selection()
            self._update_text_cursor_position()
            self.queue_draw()
            return True

        # Home / End
        if keyval == Gdk.KEY_Home:
            self._text_cursor_char = 0
            if not shift:
                self._collapse_selection()
            self._update_text_cursor_position()
            self.queue_draw()
            return True

        if keyval == Gdk.KEY_End:
            self._text_cursor_char = len(self._text_buffer[self._text_cursor_line]) if self._text_buffer else 0
            if not shift:
                self._collapse_selection()
            self._update_text_cursor_position()
            self.queue_draw()
            return True

        # Return
        if keyval == Gdk.KEY_Return:
            if self._has_text_selection():
                self._delete_text_selection()
            shape = self._board.get_shape(self._text_shape_id)
            if shape and isinstance(shape, (RectangleShape, DatabaseShape, TopicShape, CloudShape)):
                interior = shape.get_interior_bounds()
                if interior and len(self._text_buffer) >= interior[3] - interior[1] + 1:
                    return True
            line = self._text_buffer[self._text_cursor_line]
            after = line[self._text_cursor_char :]
            self._text_buffer[self._text_cursor_line] = line[: self._text_cursor_char]
            self._text_buffer.insert(self._text_cursor_line + 1, after)
            self._text_cursor_line += 1
            self._text_cursor_char = 0
            self._collapse_selection()
            self._sync_text()
            self._update_text_cursor_position()
            self.queue_draw()
            return True

        # Backspace
        if keyval == Gdk.KEY_BackSpace:
            if self._has_text_selection():
                self._delete_text_selection()
            elif alt:
                # Option+Backspace: delete word left
                line = self._text_buffer[self._text_cursor_line]
                pos = self._text_cursor_char
                while pos > 0 and line[pos - 1] == " ":
                    pos -= 1
                while pos > 0 and line[pos - 1] != " ":
                    pos -= 1
                self._text_buffer[self._text_cursor_line] = line[:pos] + line[self._text_cursor_char :]
                self._text_cursor_char = pos
            elif self._text_cursor_char > 0:
                line = self._text_buffer[self._text_cursor_line]
                self._text_buffer[self._text_cursor_line] = (
                    line[: self._text_cursor_char - 1] + line[self._text_cursor_char :]
                )
                self._text_cursor_char -= 1
            elif self._text_cursor_line > 0:
                prev_len = len(self._text_buffer[self._text_cursor_line - 1])
                self._text_buffer[self._text_cursor_line - 1] += self._text_buffer[self._text_cursor_line]
                self._text_buffer.pop(self._text_cursor_line)
                self._text_cursor_line -= 1
                self._text_cursor_char = prev_len
            self._collapse_selection()
            self._sync_text()
            self._update_text_cursor_position()
            self.queue_draw()
            return True

        # Delete (forward)
        if keyval == Gdk.KEY_Delete:
            if self._has_text_selection():
                self._delete_text_selection()
            else:
                line = self._text_buffer[self._text_cursor_line]
                if self._text_cursor_char < len(line):
                    self._text_buffer[self._text_cursor_line] = (
                        line[: self._text_cursor_char] + line[self._text_cursor_char + 1 :]
                    )
                elif self._text_cursor_line < len(self._text_buffer) - 1:
                    self._text_buffer[self._text_cursor_line] += self._text_buffer[self._text_cursor_line + 1]
                    self._text_buffer.pop(self._text_cursor_line + 1)
            self._collapse_selection()
            self._sync_text()
            self._update_text_cursor_position()
            self.queue_draw()
            return True

        # Regular character input
        ch = chr(keyval) if 32 <= keyval <= 126 else None
        if ch and self._text_buffer:
            if self._has_text_selection():
                self._delete_text_selection()
            shape = self._board.get_shape(self._text_shape_id)
            max_w = None
            if shape and isinstance(shape, (RectangleShape, DatabaseShape, TopicShape, CloudShape)):
                if getattr(shape, "font_size", None):
                    fs = shape.font_size
                    char_w = fs * 0.6
                    if isinstance(shape, (TopicShape, CloudShape, DatabaseShape)):
                        interior = shape.get_interior_bounds()
                        iw = (interior[2] - interior[0] + 1) * self._cell_w if interior else (shape.width - 2) * self._cell_w
                    else:
                        iw = (shape.width - 2) * self._cell_w
                    max_w = int(iw / char_w) if char_w > 0 else None
                else:
                    interior = shape.get_interior_bounds()
                    if interior:
                        max_w = interior[2] - interior[0] + 1
            line = self._text_buffer[self._text_cursor_line]
            if max_w is None or len(line) < max_w:
                self._text_buffer[self._text_cursor_line] = (
                    line[: self._text_cursor_char] + ch + line[self._text_cursor_char :]
                )
                self._text_cursor_char += 1
            self._collapse_selection()
            self._sync_text()
            self._update_text_cursor_position()
            self.queue_draw()
            return True
        return False

    def _sync_text(self):
        shape = self._board.get_shape(self._text_shape_id) if self._text_shape_id else None
        if shape and isinstance(shape, (RectangleShape, DatabaseShape, ArrowShape, CloudShape)):
            shape.text = "\n".join(self._text_buffer)
        elif shape and isinstance(shape, ActorShape):
            shape.text = self._text_buffer[0] if self._text_buffer else ""
            shape.__post_init__()
        elif shape and isinstance(shape, TopicShape):
            if shape.font_size:
                shape.text = "\n".join(self._text_buffer)
            else:
                shape.text = self._text_buffer[0] if self._text_buffer else ""

    # ─────────────────────── Text Selection ───────────────────────

    def _has_text_selection(self) -> bool:
        return self._text_sel_anchor_line != self._text_cursor_line or self._text_sel_anchor_char != self._text_cursor_char

    def _collapse_selection(self):
        self._text_sel_anchor_line = self._text_cursor_line
        self._text_sel_anchor_char = self._text_cursor_char

    def _get_text_selection_ordered(self) -> tuple[int, int, int, int]:
        """Return (start_line, start_char, end_line, end_char) in order."""
        a = (self._text_sel_anchor_line, self._text_sel_anchor_char)
        c = (self._text_cursor_line, self._text_cursor_char)
        if a <= c:
            return (*a, *c)
        return (*c, *a)

    def _get_selected_text(self) -> str:
        if not self._has_text_selection():
            return ""
        sl, sc, el, ec = self._get_text_selection_ordered()
        if sl == el:
            return self._text_buffer[sl][sc:ec]
        parts = [self._text_buffer[sl][sc:]]
        for i in range(sl + 1, el):
            parts.append(self._text_buffer[i])
        parts.append(self._text_buffer[el][:ec])
        return "\n".join(parts)

    def _delete_text_selection(self):
        if not self._has_text_selection():
            return
        sl, sc, el, ec = self._get_text_selection_ordered()
        if sl == el:
            line = self._text_buffer[sl]
            self._text_buffer[sl] = line[:sc] + line[ec:]
        else:
            before = self._text_buffer[sl][:sc]
            after = self._text_buffer[el][ec:]
            self._text_buffer[sl] = before + after
            del self._text_buffer[sl + 1 : el + 1]
        self._text_cursor_line = sl
        self._text_cursor_char = sc
        self._collapse_selection()

    def _move_cursor_word_left(self):
        line = self._text_buffer[self._text_cursor_line]
        pos = self._text_cursor_char
        if pos == 0 and self._text_cursor_line > 0:
            self._text_cursor_line -= 1
            self._text_cursor_char = len(self._text_buffer[self._text_cursor_line])
            return
        while pos > 0 and line[pos - 1] == " ":
            pos -= 1
        while pos > 0 and line[pos - 1] != " ":
            pos -= 1
        self._text_cursor_char = pos

    def _move_cursor_word_right(self):
        line = self._text_buffer[self._text_cursor_line]
        pos = self._text_cursor_char
        if pos >= len(line) and self._text_cursor_line < len(self._text_buffer) - 1:
            self._text_cursor_line += 1
            self._text_cursor_char = 0
            return
        while pos < len(line) and line[pos] != " ":
            pos += 1
        while pos < len(line) and line[pos] == " ":
            pos += 1
        self._text_cursor_char = pos

    def _on_text_edit_paste_done(self, clipboard, result):
        try:
            text = clipboard.read_text_finish(result)
        except Exception:
            return
        if not text:
            return
        if self._has_text_selection():
            self._delete_text_selection()
        lines = text.split("\n")
        cur_line = self._text_buffer[self._text_cursor_line]
        before = cur_line[: self._text_cursor_char]
        after = cur_line[self._text_cursor_char :]
        if len(lines) == 1:
            self._text_buffer[self._text_cursor_line] = before + lines[0] + after
            self._text_cursor_char += len(lines[0])
        else:
            self._text_buffer[self._text_cursor_line] = before + lines[0]
            for i, ln in enumerate(lines[1:-1], 1):
                self._text_buffer.insert(self._text_cursor_line + i, ln)
            self._text_buffer.insert(self._text_cursor_line + len(lines) - 1, lines[-1] + after)
            self._text_cursor_line += len(lines) - 1
            self._text_cursor_char = len(lines[-1])
        self._collapse_selection()
        self._sync_text()
        self._update_text_cursor_position()
        self.queue_draw()
