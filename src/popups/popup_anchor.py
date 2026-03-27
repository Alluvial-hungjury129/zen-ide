"""
Anchor positioning and platform integration mixin for NvimPopup.

Provides anchored positioning relative to any widget via anchor_widget + anchor_rect,
macOS AppKit coordinate conversion, Linux Gtk.Popover-based positioning,
focus-restore logic for non-focus-stealing popups, and platform-specific
click-outside detection and macOS NSWindow setup.

Mixed into NvimPopup via PopupAnchorMixin.
"""

import sys

from gi.repository import Gdk, Graphene, Gtk

from themes import get_theme

# macOS-specific flag (mirrors nvim_popup._IS_MACOS)
_IS_MACOS = sys.platform == "darwin"


class PopupAnchorMixin:
    """Mixin providing anchor positioning, present/popup/popdown, focus restore,
    and platform-specific window management (macOS NSWindow, click-outside).

    Expects the host class to have the following attributes (set in __init__):
        _anchor_widget, _anchor_rect, _steal_focus, _width, _height,
        _closing, _linux_popover, _parent, _parent_ns_window, _ns_window,
        _modal, _theme_change_cb, _result, _on_key_pressed,
        _macos_click_monitor
    """

    def _center_on_parent(self):
        """Center the popup on the parent window."""
        # GTK4 handles this automatically with set_transient_for
        pass

    def present(self):
        """Show the popup."""
        if self._width > 0:
            self.set_default_size(self._width, self._height if self._height > 0 else -1)

        # Re-show existing Linux popover
        if self._linux_popover:
            if self._anchor_rect:
                self._linux_popover.set_pointing_to(self._anchor_rect)
            self._linux_popover.popup()
            if not self._steal_focus:
                from gi.repository import GLib

                GLib.idle_add(self._restore_parent_focus)
            return

        # Capture parent's NSWindow before presenting — needed for both
        # anchor positioning (coordinate conversion) and focus restore.
        if _IS_MACOS and (not self._steal_focus or self._anchor_widget):
            try:
                from AppKit import NSApp

                self._parent_ns_window = NSApp.keyWindow()
            except Exception:
                self._parent_ns_window = None

        # On Linux, use Gtk.Popover for anchor-positioned popups.
        # Gtk.Window cannot be positioned on Wayland (no API), and X11
        # XMoveWindow has timing issues.  Gtk.Popover uses xdg_popup on
        # Wayland and works reliably on both X11 and Wayland.
        if not _IS_MACOS and self._anchor_widget and self._anchor_rect:
            self._present_via_popover()
            return

        super().present()
        self._center_on_parent()

        if self._anchor_widget and self._anchor_rect:
            self._position_at_anchor()

        if not self._steal_focus:
            # On macOS, immediately restore parent as key window to prevent
            # visible focus bounce (cursor/line-highlight flicker in editor).
            # The idle_add fallback below handles edge cases where the
            # synchronous restore isn't sufficient.
            if _IS_MACOS and self._parent_ns_window:
                try:
                    self._parent_ns_window.makeKeyWindow()
                except Exception:
                    pass
            from gi.repository import GLib

            GLib.idle_add(self._restore_parent_focus)

        # On macOS, GTK4 focus-leave is unreliable for detecting clicks
        # outside the popup.  Install an NSEvent local monitor that fires
        # for every mouse-down in the app — if the click targets a window
        # other than this popup, dismiss it.
        if _IS_MACOS and self._steal_focus:
            from gi.repository import GLib

            GLib.idle_add(self._install_macos_click_monitor)

    def popup(self):
        """Show the popup (alias for present, popover-compatible API)."""
        self.present()

    def get_visible(self):
        """Return True if the popup is currently visible (accounts for Linux Popover path)."""
        if self._linux_popover:
            return self._linux_popover.get_visible()
        return super().get_visible()

    def popdown(self):
        """Hide the popup without destroying it."""
        if self._linux_popover:
            self._linux_popover.popdown()
            return
        self.set_visible(False)

    def set_anchor_rect(self, rect: Gdk.Rectangle):
        """Update the anchor rectangle for positioned popups.

        Args:
            rect: Rectangle relative to anchor_widget (x, y, width, height)
        """
        self._anchor_rect = rect
        if self._linux_popover:
            self._linux_popover.set_pointing_to(rect)

    def _present_via_popover(self):
        """Present popup content via Gtk.Popover on Linux.

        Gtk.Window cannot be reliably positioned on Wayland (no API) and X11
        XMoveWindow has timing issues.  Gtk.Popover creates an xdg_popup
        surface on Wayland which supports precise positioning, and works
        correctly on X11 as well.
        """
        content = self.get_child()
        if not content:
            return

        # Detach content from the Window and move it into the Popover
        self.set_child(None)
        if self._width > 0:
            content.set_size_request(self._width, self._height if self._height > 0 else -1)

        popover = Gtk.Popover()
        popover.set_parent(self._anchor_widget)
        popover.set_pointing_to(self._anchor_rect)
        popover.set_has_arrow(False)
        popover.set_autohide(self._steal_focus)
        popover.set_child(content)
        popover.add_css_class("nvim-popup-popover")

        # Keyboard handling — mirror the controller attached to the Window
        if self._steal_focus:
            key_controller = Gtk.EventControllerKey()
            key_controller.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
            key_controller.connect("key-pressed", self._on_key_pressed)
            popover.add_controller(key_controller)

        popover.connect("closed", self._on_popover_closed)

        self._linux_popover = popover
        popover.popup()

        if not self._steal_focus:
            from gi.repository import GLib

            GLib.idle_add(self._restore_parent_focus)

    def _on_popover_closed(self, popover):
        """Handle Gtk.Popover closed signal (autohide click-outside)."""
        if self._closing:
            return
        self._result = None
        self.close()

    def _position_at_anchor(self):
        """Reposition the popup relative to anchor_widget + anchor_rect."""
        if not self._anchor_widget or not self._anchor_rect:
            return False
        # Linux anchor positioning is handled via Gtk.Popover
        if _IS_MACOS:
            self._macos_position_at_anchor()
        return False

    def _macos_position_at_anchor(self):
        """Position popup at anchor using macOS AppKit APIs."""
        try:
            from AppKit import NSApp, NSPoint, NSScreen

            ns_window = getattr(self, "_ns_window", None)
            if not ns_window:
                # Try to find our window (should be key after present)
                ns_window = NSApp.keyWindow()
                if ns_window:
                    self._ns_window = ns_window

            parent_ns = self._parent_ns_window
            if not ns_window or not parent_ns:
                return

            # Compute anchor position in parent window coordinates
            root = self._anchor_widget.get_root()
            if not root:
                return

            point = Graphene.Point()
            point.x = float(self._anchor_rect.x)
            point.y = float(self._anchor_rect.y)
            success, result = self._anchor_widget.compute_point(root, point)
            if not success:
                return

            # Convert GTK coords (top-left origin) to macOS screen coords (bottom-left origin)
            parent_frame = parent_ns.frame()
            content_rect = parent_ns.contentRectForFrameRect_(parent_frame)
            title_bar_height = parent_frame.size.height - content_rect.size.height

            screen_x = content_rect.origin.x + result.x
            # GTK y grows downward; macOS y grows upward from bottom of screen
            anchor_screen_y = content_rect.origin.y + content_rect.size.height - result.y - title_bar_height

            popup_frame = ns_window.frame()
            popup_h = popup_frame.size.height
            popup_w = popup_frame.size.width

            # Default: position below the anchor point
            screen_y = anchor_screen_y - popup_h

            # Clamp to visible screen bounds (excludes menu bar and dock)
            screen = parent_ns.screen() or NSScreen.mainScreen()
            if screen:
                vf = screen.visibleFrame()
                s_bottom = vf.origin.y
                s_top = vf.origin.y + vf.size.height
                s_left = vf.origin.x
                s_right = vf.origin.x + vf.size.width

                # If popup goes below visible area, flip above the anchor
                if screen_y < s_bottom:
                    screen_y = anchor_screen_y
                # If popup goes above visible area, clamp to top
                if screen_y + popup_h > s_top:
                    screen_y = s_top - popup_h
                # Final clamp to bottom
                if screen_y < s_bottom:
                    screen_y = s_bottom
                # Horizontal: keep within visible area
                if screen_x + popup_w > s_right:
                    screen_x = s_right - popup_w
                if screen_x < s_left:
                    screen_x = s_left

            ns_window.setFrameOrigin_(NSPoint(screen_x, screen_y))
        except Exception:
            pass

    def _restore_parent_focus(self):
        """Return keyboard focus to parent window/editor after presenting."""
        if _IS_MACOS and self._parent_ns_window:
            try:
                self._parent_ns_window.makeKeyWindow()
            except Exception:
                pass
        elif self._anchor_widget:
            self._anchor_widget.grab_focus()
        elif self._parent:
            self._parent.present()
        return False

    # --- Platform: macOS NSWindow setup ---

    def _on_realize_disable_decorations(self, widget):
        """Disable decorations on the surface after realization (macOS fix for rounded corners)."""
        surface = self.get_surface()
        if surface and hasattr(surface, "set_decorated"):
            surface.set_decorated(False)

    def _setup_macos_window(self, widget):
        """Set up the macOS NSWindow to match editor background."""
        if not _IS_MACOS:
            return

        # Delay to next idle tick so the NSWindow is fully created and mapped
        from gi.repository import GLib

        GLib.idle_add(self._apply_macos_square_corners)

    def _apply_macos_square_corners(self):
        """Apply borderless style to NSWindow for square corners on macOS."""
        try:
            from AppKit import NSApp, NSColor, NSWindowStyleMaskBorderless

            ns_window = NSApp.keyWindow()
            if ns_window is not None:
                self._ns_window = ns_window  # Store for repositioning
                ns_window.setStyleMask_(NSWindowStyleMaskBorderless)
                ns_window.setHasShadow_(False)
                # Use main_bg (editor background) so any residual decoration
                # pixels blend in rather than showing as a grey line.
                theme = get_theme()
                from shared.utils import hex_to_rgb_float

                r, g, b = hex_to_rgb_float(theme.main_bg)
                ns_window.setOpaque_(True)
                ns_window.setBackgroundColor_(NSColor.colorWithRed_green_blue_alpha_(r, g, b, 1.0))
        except Exception:
            pass
        return False  # Don't repeat idle_add

    # --- Platform: click-outside detection ---

    def _setup_click_outside(self):
        """Setup click-outside-to-close behavior."""
        if self._parent and self._steal_focus:
            # Only add focus-leave auto-close for focus-stealing (modal) popups.
            # Non-focus-stealing popups manage their own dismiss logic.
            focus_controller = Gtk.EventControllerFocus()
            focus_controller.connect("leave", self._on_focus_leave)
            self.add_controller(focus_controller)
            if not _IS_MACOS:
                # On Linux, GTK4 focus-leave can be unreliable for detecting
                # clicks outside the popup (especially on Wayland).  Monitor
                # the window's is-active property as a fallback — it reliably
                # fires when the user clicks on another window or the desktop.
                self.connect("notify::is-active", self._on_active_changed)

    def _on_focus_leave(self, controller):
        """Handle focus leaving the popup window - close it."""
        if self._closing:
            return
        self._result = None
        self.close()

    def _on_active_changed(self, window, pspec):
        """Handle window losing active state (Linux fallback for click-outside).

        Use a short delay before closing — dropdown popovers and child dialogs
        temporarily steal the active state and return it immediately.
        """
        if self._closing or self.get_property("is-active"):
            return
        from gi.repository import GLib

        GLib.timeout_add(150, self._check_active_and_close)

    def _check_active_and_close(self):
        """Close if the popup is still inactive after the delay.

        Only close when the *parent* window is active — that means the user
        clicked on the parent (i.e. "clicked outside" the popup).  If both
        the popup and the parent are inactive the user switched to a
        different application and the popup should stay open.
        """
        if self._closing:
            return False
        if self.get_property("is-active"):
            return False
        # If the parent window is also inactive, the user switched apps —
        # don't dismiss the popup.
        if self._parent and not self._parent.is_active():
            return False
        self._result = None
        self.close()
        return False

    def _install_macos_click_monitor(self):
        """Install an NSEvent local monitor to detect clicks outside the popup on macOS."""
        if self._macos_click_monitor or self._closing:
            return False  # already installed or closing
        try:
            from AppKit import NSEvent, NSLeftMouseDownMask, NSRightMouseDownMask

            mask = NSLeftMouseDownMask | NSRightMouseDownMask

            def _on_mouse_down(event):
                ns_win = self._ns_window
                if ns_win and not self._closing:
                    if event.window() != ns_win:
                        from gi.repository import GLib

                        GLib.idle_add(self._dismiss_click_outside)
                return event

            self._macos_click_monitor = NSEvent.addLocalMonitorForEventsMatchingMask_handler_(mask, _on_mouse_down)
        except Exception:
            pass
        return False  # don't repeat idle_add

    def _dismiss_click_outside(self):
        """Dismiss the popup triggered by a click outside (macOS)."""
        if self._closing:
            return False
        self._result = None
        self.close()
        return False  # don't repeat idle_add

    def _remove_macos_click_monitor(self):
        """Remove the NSEvent click monitor if installed."""
        if self._macos_click_monitor:
            try:
                from AppKit import NSEvent

                NSEvent.removeMonitor_(self._macos_click_monitor)
            except Exception:
                pass
            self._macos_click_monitor = None
