"""
Neovim-style Popup Base Class for Zen IDE.

All floating popups MUST inherit from NvimPopup for consistent styling,
keyboard handling, and behavior.  Border drawing lives in border_overlay,
anchor positioning in popup_anchor, CSS styles in popup_styles.
"""

import sys

from gi.repository import Gdk, Gtk

from fonts import get_font_settings
from popups.border_overlay import _BorderOverlay
from popups.popup_anchor import PopupAnchorMixin
from popups.popup_styles import PopupStylesMixin
from shared.ui import ZenButton
from themes import subscribe_theme_change, unsubscribe_theme_change

# macOS-specific flag for removing rounded corners (AppKit imported lazily)
_IS_MACOS = sys.platform == "darwin"


class NvimPopup(PopupStylesMixin, PopupAnchorMixin, Gtk.Window):
    """
    Base class for Neovim-style floating popups.

    ALL popups in Zen IDE MUST inherit from this class to ensure consistent:
    - Styling (dark floating window with accent border)
    - Keyboard handling (Escape to close, vim-style navigation)
    - Centering on parent window (default) or anchored positioning
    - Modal behavior (default) or non-modal inline mode

    Subclasses should:
    - Override _create_content() to add their specific UI
    - Override _on_key_pressed() for custom key handling (call super first)
    - Use self._content_box to add widgets

    Anchor mode (anchor_widget is set):
        The popup positions itself relative to anchor_widget + anchor_rect
        instead of centering on the parent. Use set_anchor_rect() to update
        the position dynamically (e.g. follow cursor movement).

    Non-focus-stealing mode (steal_focus=False):
        The popup does not steal keyboard focus from the parent/editor.
        Useful for inline popups like autocomplete where typing must continue.
        close() hides instead of destroying (popup is reusable).
    """

    def __init__(
        self,
        parent: Gtk.Window,
        title: str = "",
        width: int = 400,
        height: int = -1,
        anchor_widget: Gtk.Widget = None,
        anchor_rect: Gdk.Rectangle = None,
        modal: bool = True,
        steal_focus: bool = True,
    ):
        """
        Initialize the popup.

        Args:
            parent: Parent window to attach to
            title: Optional title shown in header
            width: Popup width in pixels (-1 for natural size)
            height: Popup height in pixels (-1 for natural size)
            anchor_widget: Widget to anchor to (None = center on parent)
            anchor_rect: Rectangle relative to anchor_widget for positioning
            modal: Whether the popup is modal (blocks parent interaction)
            steal_focus: Whether presenting the popup steals keyboard focus
        """
        super().__init__()
        self.add_css_class("nvim-popup-window")
        self.set_transient_for(parent)
        # On Linux, avoid GTK's modal system — it blocks parent input events
        # entirely, preventing click-outside-to-close detection.  We handle
        # dismiss-on-click-outside ourselves via a parent gesture instead.
        self.set_modal(modal and _IS_MACOS)
        self.set_decorated(False)
        self.set_resizable(False)

        # Also set decorated=False on the surface after realization (macOS fix)
        self.connect("realize", self._on_realize_disable_decorations)

        # Make window background match editor bg so macOS decorations blend in
        self.connect("realize", self._setup_macos_window)

        self._parent = parent
        self._title = title
        self._width = width
        self._height = height
        self._result = None
        self._css_provider = None
        self._closing = False
        self._anchor_widget = anchor_widget
        self._anchor_rect = anchor_rect
        self._modal = modal
        self._steal_focus = steal_focus
        self._ns_window = None  # macOS NSWindow reference (set on first present)
        self._parent_ns_window = None  # parent's NSWindow (for focus restore)
        self._macos_click_monitor = None  # NSEvent monitor for click-outside
        self._linux_popover = None  # Gtk.Popover used for anchor positioning on Linux

        # Half the title label height — used to push the frame down
        # so the title straddles the border (half inside, half outside)
        _, font_size = self._get_popup_font()
        self._title_half_height = int((font_size + 1) * 0.75) if self._title else 0

        self._create_base_ui()
        self._apply_styles()
        self._setup_keyboard()
        self._setup_click_outside()
        self._create_content()

        # Re-apply styles when theme changes (e.g. live preview)
        self._theme_change_cb = lambda _theme: (self._apply_styles(), self._border_area.queue_draw())
        subscribe_theme_change(self._theme_change_cb)

    def _create_base_ui(self):
        """Create Neovim-style popup with GtkSnapshot-drawn border and overlay title.

        The frame fills the entire window (no margin-top) so the popup
        background is uniform.  The GtkSnapshot border is drawn at y=title_half_height
        and the title label (valign=START) straddles that line — half above,
        half below — exactly like Neovim.  Because the frame bg is the same
        everywhere, the title's transparent CSS background blends seamlessly.
        """
        overlay = Gtk.Overlay()
        self.set_child(overlay)

        # Frame fills the full window — uniform dark background
        self._outer_frame = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._outer_frame.add_css_class("nvim-popup-frame")
        overlay.set_child(self._outer_frame)

        self._main_box = self._outer_frame

        # Content area — extra top margin when title present to clear the
        # border line + title that straddles it
        top_margin = (self._title_half_height * 2 + 19) if self._title else 8
        self._content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self._content_box.set_margin_start(12)
        self._content_box.set_margin_end(12)
        self._content_box.set_margin_top(top_margin)
        self._content_box.set_margin_bottom(12)
        self._outer_frame.append(self._content_box)

        # Border overlay — draws the border with a gap for the title
        self._title_label = None
        self._border_area = _BorderOverlay(self)
        self._border_area.set_can_target(False)
        overlay.add_overlay(self._border_area)

        # Title overlaid so it straddles the top border (half in, half out)
        if self._title:
            self._title_label = Gtk.Label(label=f" {self._title} ")
            self._title_label.add_css_class("nvim-popup-title")
            self._title_label.set_halign(Gtk.Align.CENTER)
            self._title_label.set_valign(Gtk.Align.START)
            overlay.add_overlay(self._title_label)
            self._title_label.set_can_target(False)
            # Redraw border when title size is known
            self._title_label.connect("notify::allocation", lambda *_: self._border_area.queue_draw())

    def _get_popup_font(self) -> tuple[str, int]:
        """Get the editor font family and size for popup styling."""
        settings = get_font_settings("editor")
        return settings["family"], settings["size"]

    def _get_icon_font(self) -> str:
        """Get the icon font name for icon labels."""
        from icons import get_icon_font_name

        return get_icon_font_name()

    def _setup_keyboard(self):
        """Setup keyboard event handling."""
        key_controller = Gtk.EventControllerKey()
        key_controller.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        key_controller.connect("key-pressed", self._on_key_pressed)
        self.add_controller(key_controller)

    def _create_content(self):
        """
        Create the popup content. Override in subclasses.

        Use self._content_box to add widgets.
        """
        pass

    def _has_text_entry_focus(self) -> bool:
        """Check if a text entry widget currently has keyboard focus."""
        focus = self.get_focus()
        return isinstance(focus, (Gtk.Text, Gtk.Entry, Gtk.SearchEntry))

    def _on_key_pressed(self, controller, keyval, keycode, state) -> bool:
        """
        Handle key press events. Override in subclasses for custom handling.

        Args:
            controller: The key controller
            keyval: The key value
            keycode: The key code
            state: Modifier state

        Returns:
            True if the key was handled, False otherwise
        """
        if keyval == Gdk.KEY_Escape:
            self._result = None
            self.close()
            return True
        return False

    def close(self):
        """Close the popup.

        For non-focus-stealing popups (steal_focus=False), hides instead of
        destroying so the popup can be reused via popup()/popdown().
        """
        if self._closing:
            return
        if self._linux_popover:
            if not self._steal_focus:
                self._linux_popover.popdown()
                return
            self._closing = True
            if self._theme_change_cb:
                unsubscribe_theme_change(self._theme_change_cb)
                self._theme_change_cb = None
            self._linux_popover.popdown()
            self._linux_popover.unparent()
            self._linux_popover = None
            return
        if not self._steal_focus:
            self.set_visible(False)
            return
        self._closing = True
        self._remove_macos_click_monitor()
        if self._theme_change_cb:
            unsubscribe_theme_change(self._theme_change_cb)
            self._theme_change_cb = None
        super().close()

    # Helper methods for subclasses

    def _create_keybind_hint(self, key: str, action: str) -> Gtk.Box:
        """
        Create a keybind hint widget showing key -> action.

        Args:
            key: The key combination (e.g., "Enter", "Esc", "j/k")
            action: The action description (e.g., "confirm", "close")

        Returns:
            A Gtk.Box with the hint
        """
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)

        key_label = Gtk.Label(label=key)
        key_label.add_css_class("nvim-popup-keybind")
        box.append(key_label)

        action_label = Gtk.Label(label=action)
        action_label.add_css_class("nvim-popup-hint")
        box.append(action_label)

        return box

    def _create_hint_bar(self, hints: list[tuple[str, str]]) -> Gtk.Box:
        """
        Create a hint bar with multiple keybind hints.

        Args:
            hints: List of (key, action) tuples

        Returns:
            A Gtk.Box with all hints
        """
        hint_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        hint_box.set_halign(Gtk.Align.CENTER)
        hint_box.set_margin_top(8)

        for key, action in hints:
            hint_box.append(self._create_keybind_hint(key, action))

        return hint_box

    def _create_message_label(self, text: str, wrap: bool = True) -> Gtk.Label:
        """
        Create a styled message label.

        Args:
            text: The message text
            wrap: Whether to wrap text

        Returns:
            A styled Gtk.Label
        """
        label = Gtk.Label(label=text)
        label.set_halign(Gtk.Align.START)
        label.add_css_class("nvim-popup-message")
        if wrap:
            label.set_wrap(True)
            label.set_max_width_chars(70)
        return label

    def _create_input_entry(self, placeholder: str = "", initial_value: str = "") -> Gtk.Entry:
        """
        Create a styled input entry.

        Args:
            placeholder: Placeholder text
            initial_value: Initial value

        Returns:
            A styled ZenEntry (Gtk.Entry subclass)
        """
        from shared.ui.zen_entry import ZenEntry

        entry = ZenEntry(placeholder=placeholder, initial_value=initial_value)
        entry.add_css_class("nvim-popup-input")
        return entry

    def _create_search_entry(self, placeholder: str = "Search...") -> Gtk.SearchEntry:
        """
        Create a styled search entry.

        Args:
            placeholder: Placeholder text

        Returns:
            A styled ZenSearchEntry (Gtk.SearchEntry subclass)
        """
        from shared.ui.zen_entry import ZenSearchEntry

        entry = ZenSearchEntry(placeholder=placeholder)
        entry.add_css_class("nvim-popup-search")
        return entry

    def _create_scrolled_listbox(
        self,
        min_height: int = 200,
        max_height: int = 400,
    ) -> tuple[Gtk.ScrolledWindow, Gtk.ListBox]:
        """
        Create a scrolled listbox for selection lists.

        Args:
            min_height: Minimum content height
            max_height: Maximum content height

        Returns:
            Tuple of (ScrolledWindow, ListBox)
        """
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_min_content_height(min_height)
        scrolled.set_max_content_height(max_height)

        listbox = Gtk.ListBox()
        listbox.add_css_class("nvim-popup-list")
        listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        scrolled.set_child(listbox)

        return scrolled, listbox

    def _create_button(
        self,
        label: str,
        primary: bool = False,
        danger: bool = False,
    ) -> Gtk.Button:
        """
        Create a styled button.

        Args:
            label: Button label
            primary: Use primary (accent) style
            danger: Use danger (red) style

        Returns:
            A styled ZenButton
        """
        variant = "danger" if danger else ("primary" if primary else "flat")
        button = ZenButton(label=label, variant=variant)
        button.add_css_class("nvim-popup-button")

        if danger:
            button.add_css_class("nvim-popup-button-danger")
        elif primary:
            button.add_css_class("nvim-popup-button-primary")

        return button

    def _create_status_label(self, text: str = "") -> Gtk.Label:
        """
        Create a status label (e.g., for result counts).

        Args:
            text: Initial text

        Returns:
            A styled Gtk.Label
        """
        label = Gtk.Label(label=text)
        label.set_halign(Gtk.Align.START)
        label.add_css_class("nvim-popup-status")
        return label

    def _create_button_row(self, *buttons, default_focus: int = -1) -> tuple[Gtk.Box, list]:
        """Create a centered button row with optional cycling support.

        Args:
            *buttons: Tuples of (label, callback) or (label, callback, kwargs).
                      kwargs can include primary=True, danger=True.
            default_focus: Index of button to focus initially (-1 = last).

        Returns:
            (Gtk.Box, list of button widgets)
        """
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        box.set_halign(Gtk.Align.CENTER)
        box.set_margin_top(16)

        btn_widgets = []
        for item in buttons:
            label, callback = item[0], item[1]
            kwargs = item[2] if len(item) > 2 else {}
            btn = self._create_button(label, **kwargs)
            if callback:
                btn.connect("clicked", lambda b, cb=callback: cb())
            btn_widgets.append(btn)
            box.append(btn)

        self._buttons = btn_widgets
        self._selected_idx = default_focus if default_focus >= 0 else len(btn_widgets) - 1
        return box, btn_widgets

    def _close_with_result(self, result, callback=None):
        """Close the popup, set result, and call optional callback."""
        self._result = result
        self.close()
        if callback:
            callback()

    def _handle_button_navigation(self, keyval, state) -> bool:
        """Handle Tab/Shift-Tab/h/l/Left/Right cycling for button rows.

        Call from _on_key_pressed to add vim-style button navigation.
        Returns True if the key was handled.
        """
        if not getattr(self, "_buttons", None):
            return False
        num = len(self._buttons)
        delta = None
        if keyval == Gdk.KEY_Tab:
            delta = -1 if state & Gdk.ModifierType.SHIFT_MASK else 1
        elif keyval in (Gdk.KEY_h, Gdk.KEY_Left):
            delta = -1
        elif keyval in (Gdk.KEY_l, Gdk.KEY_Right):
            delta = 1
        if delta is not None:
            self._selected_idx = (self._selected_idx + delta) % num
            self._buttons[self._selected_idx].grab_focus()
            return True
        return False


def show_popup(nvim_cls, system_fallback, parent, *args, **kwargs):
    """Generic factory for showing a popup with nvim/system mode switching.

    Args:
        nvim_cls: The NvimPopup subclass to use in nvim mode.
        system_fallback: System dialog class/function to use otherwise.
            If callable with a ``present`` attr on the result, it's treated
            as a class (instantiated then presented). Otherwise it's called
            directly as a function and None is returned.
        parent: Parent Gtk.Window.
        *args, **kwargs: Forwarded to both nvim_cls and system_fallback.

    Returns:
        The dialog instance, or None for system-function fallbacks.
    """
    from popups.system_dialogs import is_nvim_mode

    if not is_nvim_mode():
        result = system_fallback(parent, *args, **kwargs)
        if hasattr(result, "present"):
            result.present()
            return result
        return None
    dialog = nvim_cls(parent, *args, **kwargs)
    dialog.present()
    return dialog
