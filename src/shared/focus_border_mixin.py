"""
Focus Border Mixin for GTK4 - provides visual focus indication via CSS.

This mixin adds CSS class-based focus indication when a component gains or loses
focus. Uses GTK4's CSS system for clean, theme-consistent styling.

Usage:
    class MyPanel(FocusBorderMixin, Gtk.Box):
        COMPONENT_ID = "terminal"

        def __init__(self):
            Gtk.Box.__init__(self)
            self._init_focus_border()

            # Register with focus manager
            from shared.focus_manager import get_component_focus_manager
            focus_mgr = get_component_focus_manager()
            focus_mgr.register(
                self.COMPONENT_ID,
                on_focus_in=self._on_focus_in,
                on_focus_out=self._on_focus_out,
            )

        def _on_focus_in(self):
            self._set_focused(True)

        def _on_focus_out(self):
            self._set_focused(False)
"""


class FocusBorderMixin:
    """
    Mixin that provides CSS-based focus border indication for panels.

    Adds/removes the 'panel-focused' CSS class to indicate focus state.
    The actual styling is handled by CSS in the theme.
    """

    # CSS class names
    FOCUS_CSS_CLASS = "panel-focused"
    UNFOCUS_CSS_CLASS = "panel-unfocused"

    def _init_focus_border(self):
        """Initialize focus border state."""
        self._is_panel_focused = False
        # Add the unfocused class initially
        self.add_css_class(self.UNFOCUS_CSS_CLASS)

    def _set_focused(self, focused: bool):
        """
        Set the focus state and update CSS classes.

        Args:
            focused: Whether the panel should appear focused
        """
        if self._is_panel_focused == focused:
            return

        self._is_panel_focused = focused

        if focused:
            self.remove_css_class(self.UNFOCUS_CSS_CLASS)
            self.add_css_class(self.FOCUS_CSS_CLASS)
        else:
            self.remove_css_class(self.FOCUS_CSS_CLASS)
            self.add_css_class(self.UNFOCUS_CSS_CLASS)

    def _handle_panel_click_focus(self):
        """Shared panel click handler to route focus through the focus manager."""
        from shared.focus_manager import get_component_focus_manager

        get_component_focus_manager().set_focus(self.COMPONENT_ID)

    def _handle_panel_focus_in(self):
        """Shared focus-in handler used by panel components."""
        self._set_focused(True)

    def _handle_panel_focus_out(self):
        """Shared focus-out handler used by panel components."""
        self._set_focused(False)
