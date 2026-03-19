"""
AI Chat Tabs - Multi-session chat management for Zen IDE
Allows running multiple AI conversations in parallel.
"""

import json
from pathlib import Path
from typing import Callable, Optional

from gi.repository import Gdk, GLib, Gtk

from constants import PANEL_HEADER_FONT_SIZE, TAB_BUTTON_FONT_SIZE
from icons import Icons
from popups.nvim_context_menu import show_context_menu
from shared.focus_border_mixin import FocusBorderMixin
from shared.focus_manager import get_component_focus_manager
from shared.gtk_event_utils import is_button_click, is_click_inside_widget
from shared.settings import get_setting as get_behavior_setting
from shared.ui import ZenButton
from shared.ui.tab_button import TabButton
from themes import get_theme, subscribe_theme_change


# Import spinner and title utils from shared
def _load_shared_ai():
    """Load shared AI utilities from project root /shared/ directory."""
    import importlib.util
    import os

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # Load Spinner directly from spinner.py
    spinner_path = os.path.join(project_root, "shared", "ai", "spinner.py")
    Spinner = None
    if os.path.exists(spinner_path):
        try:
            spec = importlib.util.spec_from_file_location("spinner", spinner_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            Spinner = module.Spinner
        except Exception:
            pass

    # Load infer_title from tab_title_inferrer.py
    title_path = os.path.join(project_root, "shared", "ai", "tab_title_inferrer.py")
    infer_title = None
    MAX_TITLE_LENGTH = 30
    if os.path.exists(title_path):
        try:
            spec = importlib.util.spec_from_file_location("tab_title_inferrer", title_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            infer_title = module.infer_title
            MAX_TITLE_LENGTH = module.MAX_TITLE_LENGTH
        except Exception:
            pass

    # Fall back to local implementations if needed
    if not Spinner:

        class Spinner:
            def __init__(self):
                self._chars = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
                self._pos = 0

            def spin(self) -> str:
                char = self._chars[self._pos]
                self._pos = (self._pos + 1) % len(self._chars)
                return char

            def reset(self):
                self._pos = 0

    if not infer_title:

        def infer_title(messages):
            if not messages:
                return None
            for msg in messages:
                if msg.get("role") == "user":
                    text = msg.get("content", "").strip()[:30]
                    words = text.split()
                    filtered = [
                        w
                        for w in words
                        if w.lower()
                        not in {"i", "the", "a", "an", "is", "are", "can", "you", "please", "help", "me", "with"}
                    ]
                    if filtered:
                        title = " ".join(filtered[:4])[:30]
                        if title:
                            return title.title()
            return None

    return Spinner, infer_title, MAX_TITLE_LENGTH


Spinner, infer_title, MAX_TITLE_LENGTH = _load_shared_ai()


class AITabButton(TabButton):
    """Tab button for AI chat sessions with spinner and right-click support."""

    def __init__(
        self,
        session_id: int,
        title: str,
        on_select: Callable[[int], None],
        on_close: Callable[[int], None],
        show_close: bool = True,
        on_right_click: Optional[Callable[[int, float, float, "AITabButton"], None]] = None,
    ):
        self.on_right_click = on_right_click
        self.processing = False
        self.spinner = Spinner() if Spinner else None
        self._spinner_timeout_id = None
        self._font_family = self._load_font_family()
        super().__init__(session_id, title, on_select, on_close, show_close)

    @property
    def session_id(self):
        return self.tab_id

    def _setup_events(self):
        """Add right-click handling on top of base events."""
        super()._setup_events()
        right_click = Gtk.GestureClick.new()
        right_click.set_button(3)
        right_click.connect("pressed", self._on_right_click_pressed)
        self.add_controller(right_click)

    def _load_font_family(self):
        """Load AI chat font family from settings."""
        from fonts import get_font_settings

        font_settings = get_font_settings("ai_chat")
        return font_settings["family"]

    def _get_font_css(self):
        return f"font-family: '{self._font_family}'; font-size: {TAB_BUTTON_FONT_SIZE}pt;"

    def apply_font_settings(self):
        """Re-read AI chat font settings and re-apply styling."""
        self._font_family = self._load_font_family()
        self._apply_theme()

    def _on_right_click_pressed(self, gesture, n_press, x, y):
        """Handle right-click for context menu."""
        if self.on_right_click:
            self.on_right_click(self.session_id, x, y, self)

    def set_show_close(self, show: bool):
        """Show or hide close button."""
        self._show_close = show
        self.close_btn.set_visible(show or self.processing)

    def set_title(self, title: str):
        """Update tab title."""
        self.title = title
        self.label.set_label(title)

    def set_processing(self, processing: bool):
        """Set processing state - show spinner when processing."""
        if self.processing == processing:
            return

        self.processing = processing
        if processing:
            self._start_spinner()
        else:
            self._stop_spinner()
            self.close_btn.set_label("\u00d7")

        self.close_btn.set_visible(self._show_close or processing)
        self._apply_theme()

    def _start_spinner(self):
        """Start spinner animation."""
        if self._spinner_timeout_id:
            GLib.source_remove(self._spinner_timeout_id)

        if self.spinner:
            self.spinner.reset()
        self._update_spinner()
        self._spinner_timeout_id = GLib.timeout_add(80, self._on_spinner_tick)

    def _stop_spinner(self):
        """Stop spinner animation."""
        if self._spinner_timeout_id:
            GLib.source_remove(self._spinner_timeout_id)
            self._spinner_timeout_id = None

    def _on_spinner_tick(self):
        """Update spinner display."""
        if self.processing:
            self._update_spinner()
            return True  # Continue
        return False  # Stop

    def _update_spinner(self):
        """Update the spinner character."""
        if self.spinner:
            self.close_btn.set_label(self.spinner.spin())

    def apply_theme(self, theme):
        """Apply new theme."""
        self.theme = theme
        self._apply_theme()


# CopilotPopup moved to popups/copilot_popup.py
from popups.copilot_popup import CopilotPopup  # noqa: E402, F401


class AIChatTabs(FocusBorderMixin, Gtk.Box):
    """Wrapper that manages multiple AI chat sessions in tabs.

    Supports two layout modes controlled by ``behavior.ai_chat_on_vertical_stack``:

    * **Horizontal tab bar** (default, ``False``): a horizontal scrollable tab bar sits at the top and
      a ``Gtk.Stack`` shows only the active chat.
    * **Vertical stack** (``True``): all chats are stacked vertically
      and visible simultaneously – each pane has its own header with +/× buttons.
    """

    COMPONENT_ID = "ai_chat"

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)

        # Initialize focus border
        self._init_focus_border()

        # Register with focus manager
        focus_mgr = get_component_focus_manager()
        focus_mgr.register(
            self.COMPONENT_ID,
            on_focus_in=self._on_focus_in,
            on_focus_out=self._on_focus_out,
        )

        # Read layout mode from settings
        self._vertical_mode = get_behavior_setting("behavior.ai_chat_on_vertical_stack", False)

        # In vertical mode, remove focus classes from the parent container
        # so the border goes around individual chat views instead
        if self._vertical_mode:
            self.remove_css_class(self.UNFOCUS_CSS_CLASS)

        # Callbacks (set by parent window)
        self.get_workspace_folders = None
        self.get_current_file = None
        self.on_maximize = None

        # Chat sessions
        self.sessions = []
        self.active_session_idx = -1
        self.next_session_id = 1
        self._last_saved_state_hash = None

        # Config directory
        self.config_dir = Path.home() / ".python_ide" / "chat_sessions"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.sessions_state_file = self.config_dir / "sessions_state.json"

        self._is_maximized = False

        self.theme = get_theme()
        self._create_ui()

        # Restore sessions after UI is ready
        GLib.idle_add(self._restore_sessions)

        # Subscribe to theme changes
        subscribe_theme_change(self._on_theme_change)

        # Add click controller to gain focus (BUBBLE phase so child buttons
        # receive the full press→release sequence first, matching terminal_view)
        click_ctrl = Gtk.GestureClick.new()
        click_ctrl.connect("pressed", self._on_panel_click)
        self.add_controller(click_ctrl)

    def _create_ui(self):

        # Apply base styling
        self._apply_base_css()

        # Header row (provider button, model label, + button, maximize button)
        self.header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.header_box.set_margin_start(8)
        self.header_box.set_margin_end(8)
        self.header_box.set_margin_top(8)
        self.header_box.set_margin_bottom(4)

        # Combined AI settings button (provider + model)
        self.ai_settings_btn = ZenButton(label="Ai Chat", tooltip="AI settings")
        self.ai_settings_btn.add_css_class("header-button")
        self.ai_settings_btn.connect("clicked", self._on_ai_settings_clicked)
        self.header_box.append(self.ai_settings_btn)

        # Spacer
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        self.header_box.append(spacer)

        # New tab button
        self.new_tab_btn = ZenButton(icon=Icons.PLUS, tooltip="New chat")
        self.new_tab_btn.connect("clicked", lambda b: self.new_session())
        self.header_box.append(self.new_tab_btn)

        # Maximize button (using Unicode icons)
        self.maximize_btn = ZenButton(icon=Icons.MAXIMIZE, tooltip="Maximize")
        self.maximize_btn.connect("clicked", self._on_maximize_clicked)
        self.header_box.append(self.maximize_btn)

        self.append(self.header_box)

        # Hide header in vertical mode (unnecessary duplication)
        if self._vertical_mode:
            self.header_box.set_visible(False)

        # Build tab bar UI (hidden in vertical mode)
        if not self._vertical_mode:
            self._build_tab_bar()

        # Container that holds chat sessions
        if self._vertical_mode:
            # Vertical mode: chats are direct children of self (in a scrolled container)
            self._content_scroll = Gtk.ScrolledWindow()
            self._content_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            self._content_scroll.set_vexpand(True)
            self._content_scroll.set_hexpand(True)
            self._content_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            self._content_container.set_margin_start(8)
            self._content_container.set_margin_end(8)
            self._content_scroll.set_child(self._content_container)
            self.append(self._content_scroll)
            # No tab bar or content_stack in vertical mode
            self.tab_bar = None
            self.content_stack = None
        else:
            # Tab mode: chats live in a Gtk.Stack
            self.content_stack = Gtk.Stack()
            self.content_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
            self.content_stack.set_transition_duration(75)
            self.content_stack.set_vexpand(True)
            self.content_stack.set_hexpand(True)
            self.content_stack.set_margin_start(8)
            self.content_stack.set_margin_end(8)
            self.append(self.content_stack)

    def _build_tab_bar(self):
        """Create tab bar for horizontal tab mode."""
        # Tab bar in a scrolled window to prevent minimum width growth
        self.tab_bar_scroll = Gtk.ScrolledWindow()
        self.tab_bar_scroll.set_policy(Gtk.PolicyType.EXTERNAL, Gtk.PolicyType.NEVER)
        self.tab_bar_scroll.set_propagate_natural_width(False)
        self.tab_bar_scroll.set_margin_start(8)
        self.tab_bar_scroll.set_margin_end(8)
        self.tab_bar_scroll.set_margin_bottom(6)

        self.tab_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.tab_bar_scroll.set_child(self.tab_bar)
        self.append(self.tab_bar_scroll)

    def _apply_base_css(self):
        """Apply base CSS styling."""
        from fonts import get_font_settings

        theme = self.theme

        # Match the chat content's font: ai_chat setting, falling back to terminal font
        font_settings = get_font_settings("ai_chat")
        font_family = font_settings["family"]
        font_size = font_settings.get("size", 13)

        css = f"""
            .header-button,
            .header-button label {{
                font-family: "{font_family}";
                font-size: {PANEL_HEADER_FONT_SIZE}pt;
                font-weight: 500;
                text-decoration: none;
                color: {theme.fg_color};
                padding: 4px 8px;
                min-height: 0;
            }}
            .header-button:hover {{
                color: {theme.accent_color};
            }}
            .model-label,
            .model-label label {{
                font-family: "{font_family}";
                font-size: {int(font_size * 0.9)}pt;
                color: {theme.fg_dim};
                padding: 4px 8px;
                min-height: 0;
            }}
            .session-title,
            .session-title label {{
                font-family: "{font_family}";
                font-size: {int(font_size * 0.9)}pt;
                color: {theme.accent_color};
                padding: 4px 8px;
                min-height: 0;
                opacity: 0.8;
            }}
        """

        provider = Gtk.CssProvider()
        provider.load_from_data(css.encode())
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_USER + 1,
        )

    def _on_theme_change(self, theme):
        """Handle theme change."""
        self.theme = theme
        self._apply_base_css()

        # Update all tabs
        for session in self.sessions:
            if session.get("tab_btn"):
                session["tab_btn"].apply_theme(theme)
            if session.get("chat"):
                session["chat"].apply_theme()

    def _on_maximize_clicked(self, button):
        """Toggle maximize state."""
        self._is_maximized = not self._is_maximized

        if self._is_maximized:
            button.add_css_class("selected")
            button.set_tooltip_text("Restore")
        else:
            button.remove_css_class("selected")
            button.set_tooltip_text("Maximize")

        if self.on_maximize:
            self.on_maximize("ai_chat")

    def new_session(self):
        """Create a new chat session."""
        from ai.ai_chat_terminal import AIChatTerminalView

        chat = AIChatTerminalView(show_header=False, show_pane_header=self._vertical_mode)

        session_id = self.next_session_id
        self.next_session_id += 1

        # Set callbacks
        chat.get_workspace_folders = self.get_workspace_folders
        chat.get_current_file = self.get_current_file

        # Set chat messages file for persistence
        chat.chat_messages_file = self.config_dir / f"chat_{session_id}.json"

        # Create tab button (only for horizontal tab mode)
        display_num = len(self.sessions) + 1
        tab_text = self._get_tab_text(display_num, None, [])
        show_close = len(self.sessions) > 0
        tab_btn = None

        if not self._vertical_mode:
            tab_btn = AITabButton(
                session_id=session_id,
                title=tab_text,
                on_select=lambda sid: self.switch_to_session(self._find_session_idx_by_id(sid)),
                on_close=lambda sid: self.close_session(self._find_session_idx_by_id(sid)),
                show_close=show_close,
                on_right_click=lambda sid, x, y, w: self._show_tab_context_menu(sid, x, y, w),
            )
            # Insert tab at beginning (newest first)
            self.tab_bar.prepend(tab_btn)
            # Add chat to stack
            stack_name = f"chat_{session_id}"
            self.content_stack.add_named(chat, stack_name)
        else:
            # Vertical mode: add chat directly to the content container
            stack_name = f"chat_{session_id}"
            chat.set_vexpand(True)
            # Apply border class immediately to avoid layout shift on first focus
            chat.add_css_class(self.UNFOCUS_CSS_CLASS)
            # Wire up vertical mode callbacks for pane header
            chat.on_add_chat = self._on_add_request
            chat.on_close_chat = lambda _chat=chat: self._close_chat_pane(_chat)
            chat.on_maximize_chat = self._on_pane_maximize
            chat.on_tab_actions = self._on_pane_tab_actions
            # Set session display info for pane header title
            chat.set_session_info(display_num, None)
            self._content_container.prepend(chat)
            # In vertical mode, update header from new session's provider
            self._update_header_from_chat(chat)

        session = {
            "chat": chat,
            "tab_btn": tab_btn,
            "session_id": session_id,
            "stack_name": stack_name,
            "display_name": None,
            "is_processing": False,
        }

        self.sessions.insert(0, session)

        # Wire up callbacks for processing state and message sent
        def on_processing_change(is_processing):
            self._on_session_processing_change(session_id, is_processing)

        def on_message_sent():
            self._on_message_sent(session_id)

        chat.on_processing_state_change = on_processing_change
        chat.on_message_sent = on_message_sent

        # Adjust active index
        if self.active_session_idx >= 0:
            self.active_session_idx += 1

        # Update close button visibility (both modes)
        self._update_close_buttons()

        # Switch to new session
        self.switch_to_session(0)

        self._save_sessions_state()
        return chat

    def _find_session_idx_by_id(self, session_id: int) -> int:
        """Find session index by session_id."""
        for i, s in enumerate(self.sessions):
            if s["session_id"] == session_id:
                return i
        return -1

    def _update_close_buttons(self):
        """Show/hide close buttons based on number of sessions."""
        show_close = len(self.sessions) > 1
        if self._vertical_mode:
            # Vertical mode: update close button visibility on each chat pane
            for session in self.sessions:
                chat = session.get("chat")
                if chat and hasattr(chat, "_close_btn") and chat._close_btn:
                    chat._close_btn.set_visible(show_close)
        else:
            # Tab mode: update tab button close visibility
            for session in self.sessions:
                tab_btn = session.get("tab_btn")
                if tab_btn:
                    tab_btn.set_show_close(show_close or session.get("is_processing", False))

    def _on_add_request(self):
        """Handle + button press in vertical mode: add a new chat pane."""
        self.new_session()

    def _close_chat_pane(self, chat):
        """Close a specific chat pane in vertical mode."""
        # Find the session index for this chat
        idx = -1
        for i, session in enumerate(self.sessions):
            if session.get("chat") is chat:
                idx = i
                break
        if idx >= 0:
            self.close_session(idx)

    def _on_pane_tab_actions(self, chat, source_widget):
        """Handle session title click in vertical mode: show tab context menu."""
        for session in self.sessions:
            if session.get("chat") is chat:
                self._show_tab_context_menu(session["session_id"], 0, 0, source_widget)
                break

    def _on_pane_maximize(self, panel_name, chat=None):
        """Handle maximize button click from a pane header.

        In vertical mode, this maximizes a single chat pane within the stack.
        In tab mode or when called from the main header, delegates to parent maximize.
        """
        if self._vertical_mode and chat is not None:
            # Vertical mode: maximize/restore a single pane within the stack
            maximized_chat = getattr(self, "_maximized_chat", None)

            if maximized_chat == chat:
                # Restore: show all chats
                self._maximized_chat = None
                for session in self.sessions:
                    session_chat = session.get("chat")
                    if session_chat:
                        session_chat.set_visible(True)
                        # Reset maximize state on other chats
                        if session_chat != chat:
                            session_chat._is_maximized = False
                            if hasattr(session_chat, "_maximize_btn") and session_chat._maximize_btn:
                                session_chat._maximize_btn.remove_css_class("selected")
                                session_chat._maximize_btn.set_tooltip_text("Maximize")
            else:
                # Maximize: hide other chats, show only the clicked one
                self._maximized_chat = chat
                for session in self.sessions:
                    session_chat = session.get("chat")
                    if session_chat:
                        if session_chat == chat:
                            session_chat.set_visible(True)
                        else:
                            session_chat.set_visible(False)
                            # Reset maximize state on hidden chats
                            session_chat._is_maximized = False
                            if hasattr(session_chat, "_maximize_btn") and session_chat._maximize_btn:
                                session_chat._maximize_btn.remove_css_class("selected")
                                session_chat._maximize_btn.set_tooltip_text("Maximize")

            # Also trigger parent maximize to expand the overall AI panel
            if self.on_maximize:
                self.on_maximize(panel_name)
        else:
            # Tab mode or main header: just delegate to parent
            if self.on_maximize:
                self.on_maximize(panel_name)

    def switch_to_session(self, idx: int):
        """Switch to a session."""
        if idx < 0 or idx >= len(self.sessions):
            return

        old_idx = self.active_session_idx
        session_changed = idx != old_idx
        session = self.sessions[idx]
        chat = session["chat"]

        if not self._vertical_mode:
            # Update tab styling (tab mode only)
            if old_idx >= 0 and old_idx < len(self.sessions):
                old_tab_btn = self.sessions[old_idx].get("tab_btn")
                if old_tab_btn:
                    old_tab_btn.set_selected(False)

            tab_btn = session.get("tab_btn")
            if tab_btn:
                tab_btn.set_selected(True)

            # Show chat
            self.content_stack.set_visible_child_name(session["stack_name"])

        # Update header with active chat's provider info
        self._update_header_from_chat(chat)

        self.active_session_idx = idx

        # In vertical mode, move focus border to active chat if panel is focused
        if self._vertical_mode:
            fm = get_component_focus_manager()
            if fm.get_current_focus() == self.COMPONENT_ID:
                self._update_vertical_focus_border()

        # Ensure chat content is restored when switching to it
        # Use idle_add to give GTK time to realize/map the widget first
        restore_scroll_mode = "bottom" if session_changed else "none"
        if hasattr(chat, "ensure_restored"):
            GLib.idle_add(chat.ensure_restored, restore_scroll_mode)

        # Only auto-scroll when a different tab becomes visible.
        # Visible chats should keep the user's current viewport during resize/focus churn.
        if session_changed and not getattr(chat, "_pending_restore", False):
            if hasattr(chat, "schedule_activation_scroll_to_bottom"):
                GLib.idle_add(chat.schedule_activation_scroll_to_bottom)
            elif hasattr(chat, "scroll_to_bottom"):
                GLib.idle_add(chat.scroll_to_bottom)
            elif hasattr(chat, "_scroll_to_bottom"):
                GLib.idle_add(chat._scroll_to_bottom)

        if session_changed:
            chat.focus_input()

        self._save_sessions_state()

    def _update_header_from_chat(self, chat):
        """Update header labels from the active chat."""
        # Build combined label: "PROVIDER • model"
        provider_name = "Ai Chat"
        if hasattr(chat, "_get_provider_display_name"):
            provider_name = chat._get_provider_display_name()

        model_name = ""
        if hasattr(chat, "_current_model") and chat._current_model:
            model_name = chat._current_model

        if model_name:
            combined_label = f"{provider_name} • {model_name}"
        else:
            combined_label = provider_name

        self.ai_settings_btn.set_label(combined_label)

        # Cache provider availability for popup
        self._update_provider_availability(chat)

    def _update_provider_availability(self, chat):
        """Cache provider availability from the active chat."""
        self._current_provider = chat._current_provider if hasattr(chat, "_current_provider") else ""

    def _on_ai_settings_clicked(self, button):
        """Show AI settings popup with two combo boxes (provider + model)."""
        if self.active_session_idx < 0 or self.active_session_idx >= len(self.sessions):
            return

        chat = self.sessions[self.active_session_idx].get("chat")
        if not chat:
            return

        from popups.ai_settings_popup import show_ai_settings

        parent = self.get_root()
        if not parent:
            return

        # Get provider availability from chat state
        availability = {
            "copilot_api": getattr(chat, "_copilot_api_available", False),
            "anthropic_api": getattr(chat, "_anthropic_api_available", False),
        }

        current_provider = getattr(chat, "_current_provider", "copilot_api")
        current_model = getattr(chat, "_current_model", "") or ""

        def on_provider_changed(provider):
            self._select_provider_for_active_chat(provider)
            self._update_header_from_chat(chat)

        def on_model_changed(model):
            self._select_model_for_active_chat(model)
            self._update_header_from_chat(chat)

        def on_setup_api_key(provider):
            # Close settings popup and show API key setup
            if hasattr(self, "_ai_settings_popup") and self._ai_settings_popup:
                self._ai_settings_popup.close()
                self._ai_settings_popup = None

            from popups.api_key_setup_popup import show_api_key_setup

            def on_complete(configured_provider):
                if self.active_session_idx >= 0 and self.active_session_idx < len(self.sessions):
                    active_chat = self.sessions[self.active_session_idx].get("chat")
                    if active_chat and hasattr(active_chat, "_on_api_key_configured"):
                        active_chat._on_api_key_configured(configured_provider)
                        self._update_header_from_chat(active_chat)

            show_api_key_setup(parent=parent, provider=provider, on_complete=on_complete)

        self._ai_settings_popup = show_ai_settings(
            parent=parent,
            current_provider=current_provider,
            current_model=current_model,
            provider_availability=availability,
            on_provider_changed=on_provider_changed,
            on_model_changed=on_model_changed,
            on_setup_api_key=on_setup_api_key,
        )

    def _select_provider_for_active_chat(self, provider: str):
        """Select provider for the active chat session."""
        if self.active_session_idx >= 0 and self.active_session_idx < len(self.sessions):
            chat = self.sessions[self.active_session_idx].get("chat")
            if chat and hasattr(chat, "_select_provider"):
                chat._select_provider(provider)
                # Also update model from settings and save provider preference
                if hasattr(chat, "_get_model_from_settings"):
                    from shared.settings import get_settings

                    chat._current_model = chat._get_model_from_settings(get_settings())
                if hasattr(chat, "_save_provider_preference"):
                    chat._save_provider_preference()
                # Update header after selection
                self._update_header_from_chat(chat)

    def _select_model_for_active_chat(self, model: str):
        """Select model for the active chat session."""
        if self.active_session_idx >= 0 and self.active_session_idx < len(self.sessions):
            chat = self.sessions[self.active_session_idx].get("chat")
            if chat and hasattr(chat, "_select_model"):
                chat._select_model(model)
                # Update header after selection
                self._update_header_from_chat(chat)

    def close_session(self, idx: int):
        """Close a session."""
        if len(self.sessions) <= 1:
            # Clear the only session instead of closing
            self.sessions[0]["chat"].new_session()
            return

        if idx < 0 or idx >= len(self.sessions):
            return

        session = self.sessions[idx]

        # Stop any running AI process before closing
        chat = session.get("chat")
        if chat and hasattr(chat, "stop_ai"):
            chat.stop_ai(silent=True)

        # Nullify chat_messages_file FIRST to prevent any async callback
        # (e.g., pending AI response) from recreating the file after deletion
        if chat and hasattr(chat, "chat_messages_file"):
            chat.chat_messages_file = None

        # Delete the chat file to prevent restoration on restart
        session_id = session["session_id"]
        chat_file = self.config_dir / f"chat_{session_id}.json"
        try:
            if chat_file.exists():
                chat_file.unlink()
        except Exception:
            pass

        # Stop spinner timer on tab button before removal
        tab_btn = session.get("tab_btn")
        if tab_btn and hasattr(tab_btn, "_stop_spinner"):
            tab_btn._stop_spinner()

        # Remove UI - guard against widgets already removed from containers
        if self._vertical_mode:
            # Vertical mode: remove chat from content container
            if session["chat"].get_parent() == self._content_container:
                self._content_container.remove(session["chat"])
            # Reset maximize state if the closed chat was maximized
            if getattr(self, "_maximized_chat", None) == session["chat"]:
                self._maximized_chat = None
        else:
            # Tab mode: remove from tab bar and stack
            if tab_btn and tab_btn.get_parent() == self.tab_bar:
                self.tab_bar.remove(tab_btn)
            if session["chat"].get_parent() == self.content_stack:
                self.content_stack.remove(session["chat"])

        self.sessions.pop(idx)

        if self._vertical_mode:
            # Ensure all remaining chats are visible (restore from maximize)
            for s in self.sessions:
                s_chat = s.get("chat")
                if s_chat:
                    s_chat.set_visible(True)
                    if hasattr(s_chat, "_is_maximized"):
                        s_chat._is_maximized = False
                    if hasattr(s_chat, "_maximize_btn") and s_chat._maximize_btn:
                        s_chat._maximize_btn.remove_css_class("selected")
                        s_chat._maximize_btn.set_tooltip_text("Maximize")

        # Update close button visibility (both modes)
        self._update_close_buttons()

        # Renumber tabs and pane headers
        self._renumber_tabs()

        # Switch to appropriate session (prefer next tab on the right)
        if self.active_session_idx == idx:
            if idx < len(self.sessions):
                self.active_session_idx = idx
            else:
                self.active_session_idx = len(self.sessions) - 1
        elif self.active_session_idx > idx:
            self.active_session_idx -= 1

        self.switch_to_session(self.active_session_idx)
        self._save_sessions_state()

    def _show_tab_context_menu(self, session_id: int, x: float, y: float, source_widget):
        """Show context menu for tab using NvimContextMenu."""
        idx = self._find_session_idx_by_id(session_id)
        if idx < 0:
            return

        session = self.sessions[idx]
        is_processing = session.get("is_processing", False)

        # Build menu items
        items = [
            {"label": "Stop AI", "action": "stop", "enabled": is_processing, "icon": Icons.STOP},
            {"label": "---"},
            {"label": "New Tab", "action": "new", "icon": Icons.PLUS},
            {"label": "Close Tab", "action": "close", "icon": Icons.CLOSE},
        ]

        # Only show "Close All" if there are multiple tabs
        if len(self.sessions) > 1:
            items.append({"label": "---"})
            items.append({"label": "Close All AI Tabs", "action": "close_all", "icon": Icons.ERROR_X})

        def on_select(action):
            if action == "stop":
                self._stop_session(session_id)
            elif action == "new":
                self.new_session()
            elif action == "close":
                self.close_session(idx)
            elif action == "close_all":
                self._close_all_sessions()

        # Get the parent window
        parent = self.get_root()
        if parent:
            show_context_menu(parent, items, on_select, x=x, y=y, source_widget=source_widget)

    def _stop_session(self, session_id: int):
        """Stop AI generation for a specific session."""
        idx = self._find_session_idx_by_id(session_id)
        if idx >= 0 and idx < len(self.sessions):
            session = self.sessions[idx]
            chat = session.get("chat")
            if chat:
                if hasattr(chat, "stop_ai"):
                    chat.stop_ai()

    def _close_all_sessions(self):
        """Close all AI chat sessions and delete their persisted files."""
        # Delete all chat files to prevent restoration on restart
        try:
            chat_files = list(self.config_dir.glob("chat_*.json"))
            for chat_file in chat_files:
                try:
                    chat_file.unlink()
                except Exception:
                    pass
        except Exception:
            pass

        # Close from end to beginning to avoid index issues
        while len(self.sessions) > 1:
            self.close_session(len(self.sessions) - 1)

        # Clear the remaining session instead of closing it
        if len(self.sessions) == 1:
            self._clear_session(self.sessions[0]["session_id"])

    def _renumber_tabs(self):
        """Renumber tabs after close (updates both tab mode buttons and vertical mode pane headers)."""
        for i, session in enumerate(self.sessions):
            display_num = i + 1
            messages = session["chat"].messages if session.get("chat") else []
            tab_text = self._get_tab_text(display_num, session.get("display_name"), messages)

            if not self._vertical_mode:
                # Tab mode: update tab button
                tab_btn = session.get("tab_btn")
                if tab_btn and not session.get("is_processing"):
                    tab_btn.set_title(tab_text)
            else:
                # Vertical mode: update pane header title
                chat = session.get("chat")
                if chat and hasattr(chat, "set_session_info"):
                    chat.set_session_info(display_num, session.get("display_name"))

    def _on_session_processing_change(self, session_id: int, is_processing: bool):
        """Handle processing state change for a session."""
        idx = self._find_session_idx_by_id(session_id)
        if idx < 0 or idx >= len(self.sessions):
            return

        session = self.sessions[idx]
        session["is_processing"] = is_processing

        # Update tab button's processing state (shows/hides spinner)
        tab_btn = session.get("tab_btn")
        if tab_btn:
            tab_btn.set_processing(is_processing)

        # Update close button visibility
        self._update_close_buttons()

        # Update macOS dock badge
        from ai.dock_badge import clear_ai_badge, set_ai_badge

        if is_processing:
            set_ai_badge()
        else:
            clear_ai_badge()

    def _on_message_sent(self, session_id: int):
        """Handle message sent - update tab title."""
        idx = self._find_session_idx_by_id(session_id)
        if idx < 0 or idx >= len(self.sessions):
            return

        session = self.sessions[idx]
        display_num = idx + 1
        messages = session["chat"].messages if session.get("chat") else []
        tab_text = self._get_tab_text(display_num, session.get("display_name"), messages)

        if not session.get("is_processing"):
            tab_btn = session.get("tab_btn")
            if tab_btn:
                tab_btn.set_title(tab_text)

        # In vertical mode, also update the chat's pane header title
        if self._vertical_mode and session.get("chat"):
            chat = session["chat"]
            if hasattr(chat, "set_session_info"):
                # Infer display_name from messages if not already set
                inferred_name = None
                if messages and infer_title:
                    inferred_name = infer_title(messages)
                if inferred_name and not session.get("display_name"):
                    session["display_name"] = inferred_name
                chat.set_session_info(display_num, session.get("display_name") or inferred_name)

        self._save_sessions_state()

    def _get_tab_text(self, display_num: int, display_name: str = None, messages: list = None) -> str:
        """Get tab text."""
        if display_name:
            clean_name = " ".join(display_name.split())
            if len(clean_name) > MAX_TITLE_LENGTH:
                clean_name = clean_name[: MAX_TITLE_LENGTH - 1] + "…"
            return clean_name.title()

        if messages and infer_title:
            inferred = infer_title(messages)
            if inferred:
                return inferred

        return f"Chat {display_num}"

    def _save_sessions_state(self):
        """Save sessions state."""
        try:
            state = {
                "session_ids": [s["session_id"] for s in self.sessions],
                "display_names": {s["session_id"]: s.get("display_name") for s in self.sessions},
                "active_session_idx": self.active_session_idx,
                "next_session_id": self.next_session_id,
            }

            state_hash = hash(json.dumps(state, sort_keys=True))
            if state_hash == self._last_saved_state_hash:
                return

            with open(self.sessions_state_file, "w") as f:
                json.dump(state, f, indent=2)
            self._last_saved_state_hash = state_hash

        except Exception:
            pass

    def _restore_sessions(self):
        """Restore sessions from saved state.

        Only restores sessions listed in sessions_state.json that have
        non-empty chat files. Orphaned chat files are cleaned up.
        """
        MAX_SESSIONS_TO_RESTORE = 20  # Limit to avoid overwhelming the UI

        try:
            # Load saved state for active index and display names
            saved_active_session_id = None
            display_names = {}
            session_ids = []

            if self.sessions_state_file.exists():
                with open(self.sessions_state_file, "r") as f:
                    state = json.load(f)

                session_ids = state.get("session_ids", [])
                display_names = state.get("display_names", {})
                saved_active_idx = state.get("active_session_idx", 0)
                self.next_session_id = state.get("next_session_id", 1)

                # Remember which session was active
                if session_ids and saved_active_idx < len(session_ids):
                    saved_active_session_id = session_ids[saved_active_idx]

            if not session_ids:
                # No saved state - create default session
                self.new_session()
                return False

            # Only restore sessions listed in sessions_state.json
            session_ids_set = set(session_ids)
            session_info = []
            for session_id in session_ids:
                chat_file = self.config_dir / f"chat_{session_id}.json"
                if not chat_file.exists():
                    continue
                try:
                    # Check if file has any messages (skip empty chats)
                    with open(chat_file, "r") as f:
                        data = json.load(f)
                        messages = data if isinstance(data, list) else data.get("messages", [])
                        if messages:  # Only restore non-empty chats
                            session_info.append((session_id, chat_file))

                    # Update next_session_id to be higher than any existing
                    if session_id >= self.next_session_id:
                        self.next_session_id = session_id + 1

                except (ValueError, json.JSONDecodeError, KeyError):
                    continue

            # Clean up orphaned chat files not in sessions_state.json
            try:
                all_chat_files = list(self.config_dir.glob("chat_*.json"))
                for chat_file in all_chat_files:
                    try:
                        file_session_id = int(chat_file.stem.split("_")[1])
                        if file_session_id not in session_ids_set:
                            chat_file.unlink()
                    except (ValueError, IndexError):
                        continue
            except Exception:
                pass

            # Limit to MAX_SESSIONS_TO_RESTORE
            session_info = session_info[:MAX_SESSIONS_TO_RESTORE]

            if session_info:
                # Find the index of the previously active session
                active_idx = 0
                for i, (session_id, _) in enumerate(session_info):
                    if session_id == saved_active_session_id:
                        active_idx = i
                        break

                for session_id, _ in session_info:
                    try:
                        display_name = display_names.get(str(session_id))
                        self._restore_session(session_id, display_name)
                    except Exception:
                        pass

                if self.sessions:
                    self._update_close_buttons()
                    self.switch_to_session(active_idx)

                    # In vertical mode, all sessions are visible so restore all of them
                    if self._vertical_mode:
                        for session in self.sessions:
                            chat = session.get("chat")
                            if chat and hasattr(chat, "ensure_restored"):
                                GLib.idle_add(chat.ensure_restored)

                    # Save state after restore to persist what was actually restored
                    # (some sessions may have been filtered out or failed)
                    self._last_saved_state_hash = None
                    self._save_sessions_state()
                    return False

        except Exception:
            pass

        # Create default session if none restored
        self.new_session()
        return False

    def _restore_session(self, session_id: int, display_name: str = None):
        """Restore a single session."""
        from ai.ai_chat_terminal import AIChatTerminalView

        chat = AIChatTerminalView(show_header=False, show_pane_header=self._vertical_mode)

        # Set callbacks
        chat.get_workspace_folders = self.get_workspace_folders
        chat.get_current_file = self.get_current_file

        # Set chat messages file for persistence and restore messages
        chat.chat_messages_file = self.config_dir / f"chat_{session_id}.json"
        if hasattr(chat, "restore_from_file"):
            chat.restore_from_file()

        # Create tab button (only for horizontal tab mode)
        display_num = len(self.sessions) + 1
        tab_text = self._get_tab_text(display_num, display_name, chat.messages if hasattr(chat, "messages") else [])
        show_close = len(self.sessions) > 0
        tab_btn = None
        stack_name = f"chat_{session_id}"

        if not self._vertical_mode:
            tab_btn = AITabButton(
                session_id=session_id,
                title=tab_text,
                on_select=lambda sid: self.switch_to_session(self._find_session_idx_by_id(sid)),
                on_close=lambda sid: self.close_session(self._find_session_idx_by_id(sid)),
                show_close=show_close,
                on_right_click=lambda sid, x, y, w: self._show_tab_context_menu(sid, x, y, w),
            )
            self.tab_bar.append(tab_btn)
            self.content_stack.add_named(chat, stack_name)
        else:
            # Vertical mode: add chat directly to the content container
            chat.set_vexpand(True)
            # Apply border class immediately to avoid layout shift on first focus
            chat.add_css_class(self.UNFOCUS_CSS_CLASS)
            # Wire up vertical mode callbacks for pane header
            chat.on_add_chat = self._on_add_request
            chat.on_close_chat = lambda _chat=chat: self._close_chat_pane(_chat)
            chat.on_maximize_chat = self._on_pane_maximize
            chat.on_tab_actions = self._on_pane_tab_actions
            # Infer display_name from messages if not already set
            if not display_name and hasattr(chat, "messages") and chat.messages and infer_title:
                inferred = infer_title(chat.messages)
                if inferred:
                    display_name = inferred
            # Set session display info for pane header title
            chat.set_session_info(display_num, display_name)
            self._content_container.append(chat)

        session = {
            "chat": chat,
            "tab_btn": tab_btn,
            "session_id": session_id,
            "stack_name": stack_name,
            "display_name": display_name,
            "is_processing": False,
        }

        # Wire up callbacks for processing state and message sent
        def on_processing_change(is_processing):
            self._on_session_processing_change(session_id, is_processing)

        def on_message_sent():
            self._on_message_sent(session_id)

        chat.on_processing_state_change = on_processing_change
        chat.on_message_sent = on_message_sent

        self.sessions.append(session)

    def focus_input(self):
        """Focus the input of the active chat."""
        if self.active_session_idx >= 0 and self.active_session_idx < len(self.sessions):
            chat = self.sessions[self.active_session_idx].get("chat")
            if chat:
                chat.focus_input()

    def stop_ai(self):
        """Stop AI generation in the active session."""
        if self.active_session_idx >= 0 and self.active_session_idx < len(self.sessions):
            session = self.sessions[self.active_session_idx]
            chat = session.get("chat")
            if chat:
                if hasattr(chat, "stop_ai"):
                    chat.stop_ai()

    def cleanup(self):
        """Stop all AI processes across all sessions. Called on IDE shutdown."""
        for session in self.sessions:
            chat = session.get("chat")
            if chat:
                if hasattr(chat, "stop_ai"):
                    chat.stop_ai(silent=True)

    def is_processing(self) -> bool:
        """Check if the active session is processing."""
        if self.active_session_idx >= 0 and self.active_session_idx < len(self.sessions):
            session = self.sessions[self.active_session_idx]
            return session.get("is_processing", False)
        return False

    def apply_theme(self):
        """Apply current theme."""
        self.theme = get_theme()
        self._on_theme_change(self.theme)

    def update_font(self):
        """Update fonts for all sessions."""
        self._apply_base_css()
        for session in self.sessions:
            tab_btn = session.get("tab_btn")
            if tab_btn and hasattr(tab_btn, "apply_font_settings"):
                tab_btn.apply_font_settings()
            if session.get("chat") and hasattr(session["chat"], "update_font"):
                session["chat"].update_font()

    def _on_panel_click(self, gesture, n_press, x, y):
        """Handle click on panel to gain focus (BUBBLE phase)."""
        # Deny so this gesture does not claim the sequence away from buttons
        # that have already handled the press in the TARGET phase.
        gesture.set_state(Gtk.EventSequenceState.DENIED)

        picked_widget = self.pick(x, y, Gtk.PickFlags.DEFAULT)
        if is_button_click(picked_widget):
            return
        fm = get_component_focus_manager()
        already_focused = fm.get_current_focus() == self.COMPONENT_ID
        fm.set_focus(self.COMPONENT_ID)

        # In vertical mode, detect which chat pane was clicked
        if self._vertical_mode:
            widget = gesture.get_widget()
            for i, session in enumerate(self.sessions):
                chat = session.get("chat")
                if chat and is_click_inside_widget(widget, x, y, chat):
                    if i != self.active_session_idx:
                        self.active_session_idx = i
                        self._update_vertical_focus_border()
                    break

        # Only auto-focus input when panel first gains focus, not on every click
        # (allows text selection in chat content)
        if not already_focused and n_press == 1:
            GLib.timeout_add(150, self.focus_input)

    def _on_focus_in(self):
        """Called when this panel gains focus."""
        if self._vertical_mode:
            self._update_vertical_focus_border()
        else:
            self._set_focused(True)
        GLib.timeout_add(150, self.focus_input)

    def _on_focus_out(self):
        """Called when this panel loses focus."""
        if self._vertical_mode:
            self._clear_vertical_focus_border()
        else:
            self._set_focused(False)

    def _update_vertical_focus_border(self):
        """In vertical mode, apply focus border to the active chat view only."""
        for session in self.sessions:
            chat = session.get("chat")
            if chat:
                chat.remove_css_class(self.FOCUS_CSS_CLASS)
                chat.add_css_class(self.UNFOCUS_CSS_CLASS)
        if 0 <= self.active_session_idx < len(self.sessions):
            chat = self.sessions[self.active_session_idx].get("chat")
            if chat:
                chat.remove_css_class(self.UNFOCUS_CSS_CLASS)
                chat.add_css_class(self.FOCUS_CSS_CLASS)

    def _clear_vertical_focus_border(self):
        """In vertical mode, remove focus border from all chat views."""
        for session in self.sessions:
            chat = session.get("chat")
            if chat:
                chat.remove_css_class(self.FOCUS_CSS_CLASS)
                chat.add_css_class(self.UNFOCUS_CSS_CLASS)
