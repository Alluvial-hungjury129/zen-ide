"""
CustomTreePanel — core tree panel with GtkSnapshot drawing, scrolling, and data management.
Composes behavior from renderer, drag, inline-edit, and keyboard mixins.
"""

import sys
from typing import Callable, Dict, List, Optional, Set

from gi.repository import Gdk, GLib, Gtk, Pango

from fonts import get_font_settings
from icons import Icons, get_icon_font_name
from shared.settings import get_setting
from shared.utils import hex_to_rgba
from themes import (
    ThemeAwareMixin,
    get_theme,
    subscribe_settings_change,
)
from treeview.tree_canvas import TreeCanvas
from treeview.tree_icons import (
    CHEVRON_COLLAPSED,
    CHEVRON_COLOR,
    CHEVRON_EXPANDED,
    get_icon_set,
)
from treeview.tree_item import TreeItem
from treeview.tree_panel_data import TreePanelDataMixin
from treeview.tree_panel_drag import TreePanelDragMixin
from treeview.tree_panel_inline_edit import TreePanelInlineEditMixin
from treeview.tree_panel_keyboard import TreePanelKeyboardMixin
from treeview.tree_panel_renderer import TreePanelRendererMixin
from treeview.tree_panel_selection import TreePanelSelectionMixin

_PRIMARY_MOD = Gdk.ModifierType.META_MASK if sys.platform == "darwin" else Gdk.ModifierType.CONTROL_MASK


class CustomTreePanel(
    ThemeAwareMixin,
    TreePanelRendererMixin,
    TreePanelDragMixin,
    TreePanelInlineEditMixin,
    TreePanelKeyboardMixin,
    TreePanelSelectionMixin,
    TreePanelDataMixin,
    Gtk.ScrolledWindow,
):
    """Custom drawn tree control with neovim-style indent guides."""

    DEFAULT_ROW_HEIGHT = 22
    INDENT_WIDTH = 16
    LEFT_PADDING = 10

    def __init__(self, tree_view):
        super().__init__()
        self.tree_view = tree_view
        self.items: List[TreeItem] = []  # Flattened visible items
        self.roots: List[TreeItem] = []  # Root tree items
        self.selected_item: Optional[TreeItem] = None
        self.selected_items: Set[TreeItem] = set()
        self.hover_item: Optional[TreeItem] = None
        self._selection_anchor_item: Optional[TreeItem] = None

        # Git status tracking
        self._git_modified_files: Set[str] = set()
        self._git_status_map: Dict[str, str] = {}
        self._modified_dirs: Set[str] = set()

        # Theme colors (will be set in _setup_colors)
        self._setup_colors()

        # Row height (will be calculated in _setup_fonts)
        self.row_height = self.DEFAULT_ROW_HEIGHT
        self._pango_fonts_warm = False

        # Custom widget for GtkSnapshot rendering (replaces Gtk.DrawingArea)
        self.drawing_area = TreeCanvas(panel=self)

        # Font setup (needs drawing_area for widget Pango context resolution)
        self._setup_fonts()

        # Icon set
        self._setup_icons()
        self.drawing_area.set_can_focus(True)
        self.drawing_area.set_focusable(True)

        # Inline editing state
        self._inline_entry: Optional[Gtk.Entry] = None
        self._inline_item: Optional[TreeItem] = None
        self._inline_on_confirm: Optional[Callable[[str], None]] = None
        self._inline_on_cancel: Optional[Callable[[], None]] = None

        # Use Overlay to allow Entry to be placed on top of DrawingArea
        self._overlay = Gtk.Overlay()
        self._overlay.set_child(self.drawing_area)

        # Wrap in a viewport for scrolling
        self.set_child(self._overlay)
        self.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)

        # Event controllers
        self._setup_event_controllers()

        # Animation state
        self._scroll_animation_id: Optional[int] = None
        self._ensure_visible_gen: int = 0  # generation counter to invalidate stale retries

        # Scroll state for hover suppression
        self._is_scrolling = False
        self._scroll_end_timer: Optional[int] = None

        # Coalesced redraw flag
        self._redraw_pending = False

        # Custom cursor blink for selection highlight
        from shared.cursor_blink import CursorBlinker
        from shared.settings import get_setting

        self._cursor_blinker = CursorBlinker(self._request_redraw)
        self._cursor_blinker.set_enabled(get_setting("cursor_blink", True))

        # Focus tracking for cursor blink
        focus_ctrl = Gtk.EventControllerFocus()
        focus_ctrl.connect("enter", lambda c: self._cursor_blinker.on_focus_in())
        focus_ctrl.connect("leave", lambda c: self._cursor_blinker.on_focus_out())
        self.drawing_area.add_controller(focus_ctrl)

        # Drag-and-drop state
        self._drag_source_item: Optional[TreeItem] = None
        self._drop_target_item: Optional[TreeItem] = None
        self._drop_position: Optional[str] = None  # "into", "before", "after"
        self._drag_start_y: float = 0.0
        self._drag_activated: bool = False  # True once threshold exceeded
        self._drag_start_scroll_y: float = 0.0  # Scroll pos at drag begin

        # Compiled gitignore pattern cache: workspace_root -> (patterns_set, compiled_globs)
        self._pattern_cache: Dict[Optional[str], tuple] = {}

        # Connect to scroll adjustment to redraw when scrollbar is dragged
        self.connect("notify::vadjustment", self._on_vadjustment_changed)
        GLib.idle_add(self._connect_vadjustment)

        # Subscribe to theme/settings changes
        self._subscribe_theme()
        subscribe_settings_change(self._on_settings_change)

    def _connect_vadjustment(self):
        """Connect to the vertical adjustment's value-changed signal."""
        vadj = self.get_vadjustment()
        if vadj:
            vadj.connect("value-changed", self._on_scroll_value_changed)
        return False  # Don't repeat idle callback

    def _on_vadjustment_changed(self, widget, pspec):
        """Handle when the vertical adjustment property changes."""
        vadj = self.get_vadjustment()
        if vadj:
            vadj.connect("value-changed", self._on_scroll_value_changed)

    def _on_scroll_value_changed(self, adjustment):
        """Handle scrollbar/adjustment value changes - redraw the tree."""
        self._is_scrolling = True
        # Cancel any active drag — scroll invalidates drag coordinates
        if self._drag_source_item:
            self._cleanup_drag_state()
        if self.hover_item:
            self.hover_item = None

        # Cancel any existing scroll-end timer
        if self._scroll_end_timer is not None:
            GLib.source_remove(self._scroll_end_timer)

        self._scroll_end_timer = GLib.timeout_add(150, self._on_scroll_end)
        self.drawing_area.queue_draw()

    def _on_scroll_end(self):
        """Called after scrolling stops."""
        self._is_scrolling = False
        self._scroll_end_timer = None
        return False  # Don't repeat

    def _request_redraw(self):
        """Coalesce multiple redraws into a single frame."""
        if not self._redraw_pending:
            self._redraw_pending = True
            GLib.idle_add(self._do_coalesced_redraw)

    def _do_coalesced_redraw(self):
        """Execute the coalesced redraw."""
        self._redraw_pending = False
        self.drawing_area.queue_draw()
        return False

    def _setup_colors(self):
        """Setup colors from theme."""
        theme = get_theme()

        self.bg_color = hex_to_rgba(theme.tree_bg)
        self.fg_color = hex_to_rgba(theme.tree_fg)
        self.selected_bg = hex_to_rgba(theme.tree_selected_bg)
        self.hover_bg = hex_to_rgba(theme.hover_bg)
        self.guide_color = hex_to_rgba(theme.indent_guide)
        self.chevron_color = hex_to_rgba(CHEVRON_COLOR)
        self.modified_color = hex_to_rgba(theme.tree_modified_fg)
        self.ignored_color = hex_to_rgba(theme.tree_ignored_fg or theme.fg_dim)

    @staticmethod
    def _get_display_dpi():
        """Get display DPI for font size estimation."""
        import sys

        try:
            settings = Gtk.Settings.get_default()
            if settings:
                xft_dpi = settings.get_property("gtk-xft-dpi")
                if xft_dpi > 0:
                    return xft_dpi / 1024.0
        except Exception:
            pass
        return 72.0 if sys.platform == "darwin" else 96.0

    def _setup_fonts(self):
        """Setup fonts for rendering."""
        # Get display DPI for font size estimation
        self._pango_dpi = self._get_display_dpi()

        nerd_font = get_icon_font_name()

        # Get font from settings
        font_settings = get_font_settings("explorer")
        family = font_settings["family"]
        size = font_settings.get("size", 13)
        weight = font_settings.get("weight", "normal")

        # Text font
        self.text_font_desc = Pango.FontDescription.from_string(f"{family} {size}")

        from fonts import PANGO_WEIGHT_MAP

        pango_weight = PANGO_WEIGHT_MAP.get(weight, Pango.Weight.NORMAL)
        self.text_font_desc.set_weight(pango_weight)

        # Icon font - prefer user's font if it's a Nerd Font, else auto-detected
        user_is_nerd = family and "nerd font" in family.lower()
        icon_font = family if user_is_nerd else nerd_font

        # For non-Propo Nerd Fonts, icons render small due to monospace constraints.
        if icon_font and "nerd font" in icon_font.lower() and "propo" not in icon_font.lower():
            propo_name = icon_font.replace(" Mono", "").rstrip() + " Propo"
            if propo_name != icon_font:
                font_map = self.drawing_area.get_pango_context().get_font_map()
                available = {f.get_name() for f in font_map.list_families()}
                if propo_name in available:
                    icon_font = propo_name

        if icon_font:
            self.icon_font_desc = Pango.FontDescription.from_string(f"{icon_font} {size + 1}")
        else:
            self.icon_font_desc = Pango.FontDescription.from_string(f"{family} {size}")
        self.chevron_expanded = CHEVRON_EXPANDED
        self.chevron_collapsed = CHEVRON_COLLAPSED

        # Calculate row height from actual font metrics + margins
        self._calculate_row_height()

        # Icon column width (fixed for alignment)
        import sys

        platform_pad = 5 if sys.platform == "linux" else 0
        self._icon_column_width = int(size * 1.6) + platform_pad

    def _calculate_row_height(self):
        """Calculate row height from font size without Pango measurement.

        Uses a mathematical estimate to avoid the ~14ms Pango first-time font
        loading cost. The estimate matches Pango's output exactly at 72 DPI
        (macOS) and is within 1-2px at other resolutions — invisible in a tree.
        Pango warms up naturally on the first draw (after metrics are printed).
        """
        font_settings = get_font_settings("explorer")
        size = font_settings.get("size", 13)
        font_px = max(int(size * self._pango_dpi / 72), size)
        line_spacing = get_setting("treeview.line_spacing", 10)
        margin_top = line_spacing // 2
        margin_bottom = line_spacing - margin_top
        self.row_height = font_px + margin_top + margin_bottom
        # Invalidate cached text/icon heights so renderer re-measures on next draw
        self._cached_text_height = None
        self._cached_icon_height = None

    def _setup_icons(self):
        """Setup icon mappings."""
        file_icons, name_icons, folder_closed, folder_open = get_icon_set()
        self._icon_map = {
            "folder_closed": folder_closed,
            "folder_open": folder_open,
            "default": Icons.FILE + " ",
        }
        self._icon_map.update({f"ext_{k}": v for k, v in file_icons.items()})
        self._icon_map.update({f"name_{k}": v for k, v in name_icons.items()})

    def _setup_event_controllers(self):
        """Setup event controllers for mouse and keyboard."""
        # Click controller
        click_ctrl = Gtk.GestureClick.new()
        click_ctrl.connect("pressed", self._on_click)
        click_ctrl.set_button(1)  # Left button
        self.drawing_area.add_controller(click_ctrl)

        # Right-click controller
        right_click_ctrl = Gtk.GestureClick.new()
        right_click_ctrl.connect("pressed", self._on_right_click)
        right_click_ctrl.set_button(3)  # Right button
        self.drawing_area.add_controller(right_click_ctrl)

        # Motion controller for hover
        motion_ctrl = Gtk.EventControllerMotion.new()
        motion_ctrl.connect("motion", self._on_motion)
        motion_ctrl.connect("leave", self._on_leave)
        self.drawing_area.add_controller(motion_ctrl)

        # Key controller
        key_ctrl = Gtk.EventControllerKey.new()
        key_ctrl.connect("key-pressed", self._on_key)
        self.drawing_area.add_controller(key_ctrl)

        # NOTE: We don't add a custom scroll controller here.
        # The ScrolledWindow parent handles scrolling naturally, including
        # kinetic/momentum scrolling on trackpads.

        # Internal drag gesture for file reordering (avoids native DnD crash on macOS)
        drag_gesture = Gtk.GestureDrag()
        drag_gesture.connect("drag-begin", self._on_gesture_drag_begin)
        drag_gesture.connect("drag-update", self._on_gesture_drag_update)
        drag_gesture.connect("drag-end", self._on_gesture_drag_end)
        self.drawing_area.add_controller(drag_gesture)

        # External drop target for files dragged from outside the IDE
        self._setup_external_drop_target()

    def _on_theme_change(self, theme):
        """Handle theme change."""
        self._setup_colors()
        self._request_redraw()

    def _on_settings_change(self, key, value):
        """Handle settings change."""
        if key == "fonts" or key == "explorer":
            self._setup_fonts()
            self._setup_icons()
            self._update_virtual_size()
            self._request_redraw()
        elif key == "treeview":
            self._calculate_row_height()
            self._update_virtual_size()
            self._request_redraw()

    def _flatten_items(self):
        """Flatten the tree into a list of visible items."""
        self.items = []

        def traverse(item: TreeItem):
            self.items.append(item)
            if item.is_dir and item.expanded:
                for child in item.children:
                    traverse(child)

        for root in self.roots:
            traverse(root)

        self._prune_selection_to_visible_items()
        self._update_virtual_size()

    def _flatten_and_redraw(self):
        """Flatten tree and schedule a coalesced redraw."""
        self._flatten_items()
        self._request_redraw()

    def _update_virtual_size(self):
        """Update the drawing area size for scrolling."""
        height = max(len(self.items) * self.row_height, 100)
        self.drawing_area.set_size_request(-1, height)

    def _is_modified_dir(self, item: TreeItem) -> bool:
        """Check if a directory contains modified files."""
        if not item.is_dir:
            return False
        return str(item.path) in self._modified_dirs

    def _get_item_at_y(self, y):
        """Get the item at a given y coordinate."""
        index = int(y / self.row_height)
        if 0 <= index < len(self.items):
            return self.items[index]
        return None

    def _on_click(self, gesture, n_press, x, y):
        """Handle click."""
        vadj = self.get_vadjustment()
        saved_scroll = vadj.get_value() if vadj else 0
        self.drawing_area.grab_focus()
        if vadj:
            vadj.set_value(saved_scroll)
        # Cancel any running scroll animation
        if self._scroll_animation_id is not None:
            GLib.source_remove(self._scroll_animation_id)
            self._scroll_animation_id = None
        # Invalidate any pending deferred _ensure_visible calls
        self._ensure_visible_gen += 1
        state = gesture.get_current_event_state()
        is_range_select = bool(state & Gdk.ModifierType.SHIFT_MASK)
        is_toggle_select = bool(state & _PRIMARY_MOD)
        item = self._get_item_at_y(y)
        if item:
            if is_range_select:
                self._select_range_to(item)
            elif is_toggle_select:
                self._toggle_item_selection(item)
            else:
                self._select_single_item(item)
            self._cursor_blinker.reset()
            if is_range_select or is_toggle_select:
                self._request_redraw()
                return
            # For files, ignore double-clicks to avoid opening twice.
            # For directories, allow every press so rapid expand/collapse works.
            if n_press > 1 and not item.is_dir:
                self._request_redraw()
                return
            if item.is_dir:
                self._toggle_expand(item)
            else:
                # Verify file still exists before opening (handles deleted files)
                if not item.path.exists():
                    self.tree_view.refresh()
                    return
                if self.tree_view.on_file_selected:
                    self.tree_view.on_file_selected(str(item.path))
            self._request_redraw()

    def _on_right_click(self, gesture, n_press, x, y):
        """Handle right-click for context menu."""
        item = self._get_item_at_y(y)
        if item:
            if item not in self.selected_items:
                self._select_single_item(item)
            else:
                self.selected_item = item
            self._request_redraw()
            if hasattr(self.tree_view, "_show_context_menu"):
                self.tree_view._show_context_menu(item, x, y)

    def _on_motion(self, controller, x, y):
        """Handle mouse motion for hover effect."""
        if self._is_scrolling or self._inline_entry is not None:
            return

        item = self._get_item_at_y(y)
        if item != self.hover_item:
            self.hover_item = item
            self._request_redraw()

    def _on_leave(self, controller):
        """Handle mouse leave."""
        if self.hover_item:
            self.hover_item = None
            self._request_redraw()

    def _toggle_expand(self, item: TreeItem):
        """Toggle folder expansion."""
        if not item.is_dir:
            return

        vadj = self.get_vadjustment()
        saved_scroll = vadj.get_value() if vadj else 0

        item.expanded = not item.expanded

        if item.expanded and not item.children:
            self._load_children(item)

        self._flatten_and_redraw()

        if vadj:
            GLib.idle_add(lambda: vadj.set_value(saved_scroll) or False)
