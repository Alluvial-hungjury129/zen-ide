"""
CustomTreePanel keyboard navigation and scroll animation mixin.
"""

import sys

from gi.repository import Gdk, GLib

# Animation constants
SCROLL_ANIMATION_DURATION_MS = 300  # Total animation duration
SCROLL_ANIMATION_FRAME_MS = 16  # ~60fps

_MOD = Gdk.ModifierType.META_MASK if sys.platform == "darwin" else Gdk.ModifierType.CONTROL_MASK


class TreePanelKeyboardMixin:
    """Mixin providing keyboard navigation and scroll animation for CustomTreePanel."""

    def _on_key(self, controller, keyval, keycode, state):
        """Handle keyboard navigation (arrow keys + vim j/k/h/l)."""
        # Ignore key events while inline editing is active
        if self._inline_entry is not None:
            return False

        if not self.items:
            return False

        # Cmd+C / Ctrl+C — copy selected item
        if keyval == Gdk.KEY_c and (state & _MOD):
            if self.selected_item:
                self.tree_view._action_copy_item(self.selected_item)
            return True

        # Cmd+V / Ctrl+V — paste copied item
        if keyval == Gdk.KEY_v and (state & _MOD):
            if self.selected_item:
                self.tree_view._action_paste_item(self.selected_item)
            return True

        # Cmd+Delete / Cmd+Backspace — delete selected item(s)
        if keyval in (Gdk.KEY_Delete, Gdk.KEY_BackSpace) and (state & _MOD):
            if self.selected_item:
                self.tree_view._action_delete(self.selected_item)
            return True

        # Up / k (vim)
        if keyval == Gdk.KEY_Up or keyval == Gdk.KEY_k:
            self._navigate(-1)
            return True
        # Down / j (vim)
        elif keyval == Gdk.KEY_Down or keyval == Gdk.KEY_j:
            self._navigate(1)
            return True
        elif keyval == Gdk.KEY_Return:
            if self.selected_item:
                if self.selected_item.is_dir:
                    self._toggle_expand(self.selected_item)
                else:
                    if not self.selected_item.path.exists():
                        self.tree_view.refresh()
                        return True
                    if self.tree_view.on_file_selected:
                        self.tree_view.on_file_selected(str(self.selected_item.path))
            return True
        # Left / h (vim) - collapse or go to parent
        elif keyval == Gdk.KEY_Left or keyval == Gdk.KEY_h:
            if self.selected_item and self.selected_item.is_dir and self.selected_item.expanded:
                self._toggle_expand(self.selected_item)
            elif self.selected_item and not self.selected_item.is_dir:
                if self.selected_item.path.exists() and self.tree_view.on_file_selected:
                    self.tree_view.on_file_selected(str(self.selected_item.path))
            elif self.selected_item and self.selected_item.parent:
                self._select_single_item(self.selected_item.parent)
                self._ensure_visible(self.selected_item)
                self._request_redraw()
            return True
        # Right / l (vim) - expand or enter
        elif keyval == Gdk.KEY_Right or keyval == Gdk.KEY_l:
            if self.selected_item and self.selected_item.is_dir:
                if not self.selected_item.expanded:
                    self._toggle_expand(self.selected_item)
                elif self.selected_item.children:
                    self._select_single_item(self.selected_item.children[0])
                    self._ensure_visible(self.selected_item)
                    self._request_redraw()
            elif self.selected_item and not self.selected_item.is_dir:
                if self.selected_item.path.exists() and self.tree_view.on_file_selected:
                    self.tree_view.on_file_selected(str(self.selected_item.path))
            return True

        return False

    def _navigate(self, direction):
        """Navigate up/down in the list."""
        if not self.items:
            return

        if self.selected_item is None:
            self._select_single_item(self.items[0])
        else:
            try:
                idx = self.items.index(self.selected_item)
                new_idx = max(0, min(len(self.items) - 1, idx + direction))
                self._select_single_item(self.items[new_idx])
            except ValueError:
                self._select_single_item(self.items[0])

        self._cursor_blinker.reset()
        self._ensure_visible(self.selected_item)
        self._request_redraw()

    def _ensure_visible(self, item, animate=False, _retries=0, _gen=-1):
        """Scroll to make an item visible (only if currently out of view)."""
        # On fresh calls (not retries), bump generation to invalidate stale retries
        if _gen == -1:
            self._ensure_visible_gen += 1
            _gen = self._ensure_visible_gen
        elif _gen != self._ensure_visible_gen:
            return False  # stale retry from a previous call - ignore

        try:
            idx = self.items.index(item)
            vadj = self.get_vadjustment()
            if not vadj:
                return False

            item_y = idx * self.row_height
            view_height = vadj.get_page_size()
            scroll_y = vadj.get_value()

            # Defer scroll if view_height is not yet properly set (widget not realized)
            if view_height <= 0:
                if _retries < 5:
                    GLib.idle_add(self._ensure_visible, item, animate, _retries + 1, _gen)
                return False

            item_top = item_y
            item_bottom = item_y + self.row_height

            if animate:
                # For reveal animations (file opened/tab switched):
                # only scroll if item is completely off-screen.
                item_visible = item_bottom > scroll_y and item_top < scroll_y + view_height
            else:
                # For keyboard navigation: scroll if not fully visible
                tolerance = 1.0
                item_visible = item_top >= scroll_y - tolerance and item_bottom <= scroll_y + view_height + tolerance

            if item_visible:
                if self._scroll_animation_id is not None:
                    GLib.source_remove(self._scroll_animation_id)
                    self._scroll_animation_id = None
                return False

            # Calculate target scroll position (center the item if possible)
            target_y = None
            if item_top < scroll_y:
                target_y = max(0, item_y - view_height / 2 + self.row_height / 2)
            elif item_bottom > scroll_y + view_height:
                target_y = min(vadj.get_upper() - view_height, item_y - view_height / 2 + self.row_height / 2)

            if target_y is not None:
                if animate:
                    self._animate_scroll_to(target_y)
                else:
                    vadj.set_value(target_y)
        except ValueError:
            pass
        return False

    def _animate_scroll_to(self, target_y):
        """Animate scroll to a target position using easing."""
        # Cancel any existing animation
        if self._scroll_animation_id is not None:
            GLib.source_remove(self._scroll_animation_id)
            self._scroll_animation_id = None

        vadj = self.get_vadjustment()
        if not vadj:
            return

        start_y = vadj.get_value()
        distance = target_y - start_y

        # Skip animation for very small distances
        if abs(distance) < 5:
            vadj.set_value(target_y)
            return

        start_time = GLib.get_monotonic_time() / 1000.0  # Convert to ms
        duration = SCROLL_ANIMATION_DURATION_MS

        def ease_out_cubic(t):
            """Cubic ease-out for smooth deceleration."""
            return 1 - pow(1 - t, 3)

        def animation_step():
            current_time = GLib.get_monotonic_time() / 1000.0
            elapsed = current_time - start_time
            progress = min(1.0, elapsed / duration)

            # Apply easing
            eased = ease_out_cubic(progress)
            new_y = start_y + distance * eased

            vadj.set_value(new_y)

            if progress >= 1.0:
                self._scroll_animation_id = None
                return False  # Stop animation
            return True  # Continue animation

        self._scroll_animation_id = GLib.timeout_add(SCROLL_ANIMATION_FRAME_MS, animation_step)
