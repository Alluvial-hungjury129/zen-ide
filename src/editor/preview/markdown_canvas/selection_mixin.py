"""Text selection and clipboard mixin for MarkdownCanvas."""

from __future__ import annotations

from gi.repository import Gdk, Graphene, Gtk, Pango

from editor.preview.content_block import ContentBlock


class SelectionMixin:
    """Mixin for text selection, hit testing, and clipboard support."""

    def _block_to_text(self, block: ContentBlock) -> str:
        if block.kind in ("heading", "paragraph"):
            return "".join(s.text for s in block.spans)
        elif block.kind == "code":
            return block.code
        elif block.kind == "table":
            lines = []
            if block.headers:
                lines.append(" | ".join(block.headers))
            for row in block.rows:
                lines.append(" | ".join(row))
            return "\n".join(lines)
        elif block.kind == "list":
            parts = []
            for i, item in enumerate(block.items):
                prefix = f"{i + 1}." if block.ordered else "\u25aa"
                text = "".join(s.text for s in item)
                parts.append(f"{prefix} {text}")
            return "\n".join(parts)
        elif block.kind == "blockquote":
            return "\n".join("> " + "".join(s.text for s in c.spans) for c in block.children)
        elif block.kind == "hr":
            return "---"
        elif block.kind == "image":
            return f"![{block.image_alt}]({block.image_url})"
        elif block.kind == "image_row":
            return " ".join(f"![{img.get('alt', '')}]({img['url']})" for img in block.images)
        return ""

    def copy_clipboard(self):
        """Copy selected text (or all text if no selection) to clipboard."""
        if self._has_selection:
            text = self._get_selected_text()
        else:
            parts = []
            for block in self._blocks:
                parts.append(self._block_to_text(block))
            text = "\n\n".join(parts)
        if text:
            clipboard = Gdk.Display.get_default().get_clipboard()
            clipboard.set(text)
            from shared.utils import copy_to_system_clipboard

            copy_to_system_clipboard(text)

    # ------------------------------------------------------------------ #
    #  Event controllers                                                   #
    # ------------------------------------------------------------------ #

    def _setup_event_controllers(self):
        """Setup mouse and keyboard events for text selection."""
        click = Gtk.GestureClick()
        click.set_button(1)
        click.connect("pressed", self._on_click_pressed)
        self.add_controller(click)

        drag = Gtk.GestureDrag()
        drag.set_button(1)
        drag.connect("drag-begin", self._on_drag_begin)
        drag.connect("drag-update", self._on_drag_update)
        drag.connect("drag-end", self._on_drag_end)
        self.add_controller(drag)

        key = Gtk.EventControllerKey()
        key.connect("key-pressed", self._on_key_pressed)
        self.add_controller(key)

    def _on_click_pressed(self, gesture, n_press, x, y):
        """Handle double/triple click for word/line selection."""
        if n_press == 2:
            self._multi_click_mode = 2
            self._select_word_at(x, y)
        elif n_press >= 3:
            self._multi_click_mode = 3
            self._select_line_at(x, y)
        else:
            self._multi_click_mode = 0

    def _on_drag_begin(self, gesture, start_x, start_y):
        """Set selection anchor on mouse press."""
        self.grab_focus()
        self._drag_start_x = start_x
        self._drag_start_y = start_y
        if self._multi_click_mode:
            return
        self._clear_selection()
        pos = self._hit_test(start_x, start_y)
        if pos:
            self._sel_anchor = pos

    def _on_drag_update(self, gesture, offset_x, offset_y):
        """Extend selection during mouse drag."""
        if self._multi_click_mode:
            return
        if not self._sel_anchor:
            return
        x = self._drag_start_x + offset_x
        y = self._drag_start_y + offset_y
        pos = self._hit_test(x, y)
        if pos:
            self._sel_cursor = pos
            self._has_selection = self._sel_cursor != self._sel_anchor
            self._schedule_redraw()

    def _on_drag_end(self, gesture, offset_x, offset_y):
        """Finalize selection or handle click on drag end."""
        if self._multi_click_mode:
            self._multi_click_mode = 0
            return
        if abs(offset_x) < 3 and abs(offset_y) < 3:
            # Short click -- handle collapsible toggle or link
            self._clear_selection()
            self._schedule_redraw()

            abs_y = self._drag_start_y
            toggled = self._find_and_toggle_collapsible(self._blocks, abs_y)
            if toggled:
                self._needs_layout = True
                self._schedule_redraw()
                return

            for block in self._blocks:
                if block._y_offset <= abs_y < block._y_offset + block._height:
                    if block.kind in ("heading", "paragraph"):
                        for span in block.spans:
                            if span.link_url:
                                try:
                                    Gtk.show_uri(None, span.link_url, Gdk.CURRENT_TIME)
                                except Exception:
                                    pass
                                return
                    break

    def _on_key_pressed(self, controller, keyval, keycode, state):
        """Handle Cmd+C (copy) and Cmd+A (select all)."""
        mod = state & (Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.META_MASK)
        if mod and keyval == Gdk.KEY_c:
            self.copy_clipboard()
            return True
        if mod and keyval == Gdk.KEY_a:
            self._select_all()
            return True
        if keyval == Gdk.KEY_Escape:
            self._clear_selection()
            self._schedule_redraw()
            return True
        return False

    def _find_and_toggle_collapsible(self, blocks: list[ContentBlock], abs_y: float) -> bool:
        """Recursively find and toggle a collapsible block header at abs_y."""
        for block in blocks:
            if block._y_offset > abs_y:
                break
            if block._y_offset + block._height < abs_y:
                continue
            if block.collapsible:
                header_bottom = block._y_offset + block._header_height
                if block._y_offset <= abs_y < header_bottom:
                    block.collapsed = not block.collapsed
                    return True
                # If expanded, check children
                if not block.collapsed and block.children:
                    if self._find_and_toggle_collapsible(block.children, abs_y):
                        return True
        return False

    # ------------------------------------------------------------------ #
    #  Hit testing                                                         #
    # ------------------------------------------------------------------ #

    def _hit_test(self, x, y):
        """Find the text region and byte position at canvas coordinates (x, y)."""
        for i, (layout, lx, ly) in enumerate(self._text_regions):
            _, logical = layout.get_pixel_extents()
            if ly <= y <= ly + logical.height:
                rel_x = int((x - lx) * Pango.SCALE)
                rel_y = int((y - ly) * Pango.SCALE)
                inside, index, trailing = layout.xy_to_index(rel_x, rel_y)
                if inside or (lx <= x <= lx + logical.width):
                    byte_idx = index
                    if trailing:
                        text_bytes = layout.get_text().encode("utf-8")
                        byte_idx = index + 1
                        while byte_idx < len(text_bytes) and (text_bytes[byte_idx] & 0xC0) == 0x80:
                            byte_idx += 1
                    return (i, byte_idx)
        # No exact hit -- find closest region by y
        if self._text_regions:
            best_i = 0
            best_dist = float("inf")
            for i, (layout, lx, ly) in enumerate(self._text_regions):
                _, logical = layout.get_pixel_extents()
                mid_y = ly + logical.height / 2
                dist = abs(y - mid_y)
                if dist < best_dist:
                    best_dist = dist
                    best_i = i
            _, lx, ly = self._text_regions[best_i]
            text = self._text_regions[best_i][0].get_text()
            n_bytes = len(text.encode("utf-8"))
            return (best_i, 0 if y < ly else n_bytes)
        return None

    # ------------------------------------------------------------------ #
    #  Selection drawing                                                   #
    # ------------------------------------------------------------------ #

    def _draw_selection_overlay(self, snapshot):
        """Draw semi-transparent highlight rectangles over selected text."""
        if not self._sel_anchor or not self._sel_cursor:
            return

        start, end = self._sel_anchor, self._sel_cursor
        if start > end:
            start, end = end, start

        start_region, start_byte = start
        end_region, end_byte = end

        for i in range(start_region, min(end_region + 1, len(self._text_regions))):
            layout, lx, ly = self._text_regions[i]
            n_bytes = len(layout.get_text().encode("utf-8"))

            if i == start_region and i == end_region:
                sel_s, sel_e = start_byte, end_byte
            elif i == start_region:
                sel_s, sel_e = start_byte, n_bytes
            elif i == end_region:
                sel_s, sel_e = 0, end_byte
            else:
                sel_s, sel_e = 0, n_bytes

            self._draw_region_selection(snapshot, layout, lx, ly, sel_s, sel_e)

    def _draw_region_selection(self, snapshot, layout, lx, ly, sel_start, sel_end):
        """Draw selection highlight for a byte range within a single layout."""
        if sel_start >= sel_end:
            return

        layout_iter = layout.get_iter()
        while True:
            line = layout_iter.get_line_readonly()
            line_start = line.start_index
            line_end = line_start + line.length

            overlap_start = max(sel_start, line_start)
            overlap_end = min(sel_end, line_end)

            if overlap_start < overlap_end:
                start_pos = layout.index_to_pos(overlap_start)
                end_pos = layout.index_to_pos(overlap_end)

                x1 = start_pos.x / Pango.SCALE
                x2 = end_pos.x / Pango.SCALE
                if x1 > x2:
                    x1, x2 = x2, x1

                _, line_logical = layout_iter.get_line_extents()
                line_y = line_logical.y / Pango.SCALE
                line_h = line_logical.height / Pango.SCALE

                # Extend to layout width for full-line selections
                if overlap_end == line_end and sel_end > line_end:
                    _, layout_logical = layout.get_pixel_extents()
                    x2 = max(x2, float(layout_logical.width))

                rect = Graphene.Rect()
                rect.init(lx + x1, ly + line_y, max(x2 - x1, 2), line_h)
                snapshot.append_color(self._selection_rgba, rect)

            if not layout_iter.next_line():
                break

    # ------------------------------------------------------------------ #
    #  Selection text extraction                                           #
    # ------------------------------------------------------------------ #

    def _get_selected_text(self) -> str:
        """Extract plain text from the current selection."""
        if not self._has_selection or not self._sel_anchor or not self._sel_cursor:
            return ""

        start, end = self._sel_anchor, self._sel_cursor
        if start > end:
            start, end = end, start

        start_region, start_byte = start
        end_region, end_byte = end

        parts = []
        for i in range(start_region, min(end_region + 1, len(self._text_regions))):
            layout = self._text_regions[i][0]
            text_bytes = layout.get_text().encode("utf-8")

            if i == start_region and i == end_region:
                selected = text_bytes[start_byte:end_byte]
            elif i == start_region:
                selected = text_bytes[start_byte:]
            elif i == end_region:
                selected = text_bytes[:end_byte]
            else:
                selected = text_bytes

            parts.append(selected.decode("utf-8", errors="replace"))

        return "\n".join(parts)

    def _select_word_at(self, x, y):
        """Select the word at the given canvas coordinates."""
        pos = self._hit_test(x, y)
        if not pos:
            return
        region_idx, byte_idx = pos
        layout = self._text_regions[region_idx][0]
        text = layout.get_text()
        text_bytes = text.encode("utf-8")

        char_idx = len(text_bytes[:byte_idx].decode("utf-8", errors="replace"))

        start = char_idx
        while start > 0 and (text[start - 1].isalnum() or text[start - 1] == "_"):
            start -= 1
        end = char_idx
        while end < len(text) and (text[end].isalnum() or text[end] == "_"):
            end += 1

        if start == end:
            return

        start_byte = len(text[:start].encode("utf-8"))
        end_byte = len(text[:end].encode("utf-8"))

        self._sel_anchor = (region_idx, start_byte)
        self._sel_cursor = (region_idx, end_byte)
        self._has_selection = True
        self._schedule_redraw()

    def _select_line_at(self, x, y):
        """Select the entire Pango line at the given canvas coordinates."""
        pos = self._hit_test(x, y)
        if not pos:
            return
        region_idx, byte_idx = pos
        layout = self._text_regions[region_idx][0]

        layout_iter = layout.get_iter()
        while True:
            line = layout_iter.get_line_readonly()
            line_start = line.start_index
            line_end = line_start + line.length

            if line_start <= byte_idx <= line_end or not layout_iter.next_line():
                self._sel_anchor = (region_idx, line_start)
                self._sel_cursor = (region_idx, line_end)
                self._has_selection = True
                self._schedule_redraw()
                return

    def _clear_selection(self):
        """Clear the current text selection."""
        self._sel_anchor = None
        self._sel_cursor = None
        self._has_selection = False

    def _select_all(self):
        """Select all text in the canvas."""
        if self._text_regions:
            last_layout = self._text_regions[-1][0]
            last_n_bytes = len(last_layout.get_text().encode("utf-8"))
            self._sel_anchor = (0, 0)
            self._sel_cursor = (len(self._text_regions) - 1, last_n_bytes)
            self._has_selection = True
            self._schedule_redraw()
