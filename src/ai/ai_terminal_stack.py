"""AI Terminal Stack — manages multiple AI terminal sessions with a tab bar."""

import re

from gi.repository import GLib, Gtk

from ai.ai_session_persistence import AISessionPersistenceMixin
from ai.ai_tab_bar import AITabBarMixin
from shared.focus_border_mixin import FocusBorderMixin
from shared.focus_manager import get_component_focus_manager
from shared.gtk_event_utils import is_click_inside_widget
from shared.settings import get_setting


class AITerminalStack(AITabBarMixin, AISessionPersistenceMixin, FocusBorderMixin, Gtk.Box):
    """Container that holds one or more AITerminalView instances in a tabbed layout.

    A single header row sits at the top:
        [<CLI name> ▾] ─────────── [🗑️] [+] [⛶]

    When more than one chat tab exists a scrollable tab bar appears below the
    header.  The active chat is shown inside a Gtk.Stack.

    Proxies the AITerminalView public API so callers can treat it as a
    drop-in replacement:  spawn_shell, cleanup, focus_input, is_processing,
    stop_ai, update_font, on_maximize.
    """

    COMPONENT_ID = "ai_chat"

    def __init__(
        self, saved_tabs: list[dict] | None = None, get_workspace_folders_callback=None, get_editor_context_callback=None
    ):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self._views: list = []
        self._tab_buttons: list = []
        self._active_idx: int = 0
        self._spinners: dict[int, dict] = {}  # view_idx -> {spinner, timeout_id}
        self.on_maximize = None
        self._saved_tabs = saved_tabs  # deferred until spawn_shell
        self._get_workspace_folders = get_workspace_folders_callback
        self._get_editor_context = get_editor_context_callback
        self._vertical_mode = get_setting("behavior.ai_chat_on_vertical_stack", False)

        self._init_focus_border()
        # In vertical mode, remove focus classes from the parent container
        # so the border goes around individual chat views instead
        if self._vertical_mode:
            self.remove_css_class(self.UNFOCUS_CSS_CLASS)

        focus_mgr = get_component_focus_manager()
        focus_mgr.register(
            self.COMPONENT_ID,
            on_focus_in=self._on_focus_in,
            on_focus_out=self._on_focus_out,
        )

        click_ctrl = Gtk.GestureClick.new()
        click_ctrl.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        click_ctrl.connect("pressed", self._on_panel_click)
        self.add_controller(click_ctrl)

        self._build_header()

        if self._vertical_mode:
            # Hide header in vertical mode (each pane has its own)
            self._header.box.set_visible(False)
            # Vertical mode: all chats visible in a scrolled vertical box
            self._content_scroll = Gtk.ScrolledWindow()
            self._content_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            self._content_scroll.set_vexpand(True)
            self._content_scroll.set_hexpand(True)
            self._content_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            self._content_scroll.set_child(self._content_container)
            self.append(self._content_scroll)
            self._content_stack = None
        else:
            self._build_tab_bar()
            self._content_stack = Gtk.Stack()
            self._content_stack.set_transition_type(Gtk.StackTransitionType.NONE)
            self._content_stack.set_vexpand(True)
            self._content_stack.set_hexpand(True)
            self.append(self._content_stack)

        # Create views: restore from saved state or create a single default tab
        if saved_tabs and len(saved_tabs) > 0:
            for tab_info in saved_tabs:
                view = self._add_view()
                title = tab_info.get("title", "")
                if title:
                    idx = len(self._views) - 1
                    if not self._vertical_mode and 0 <= idx < len(self._tab_buttons):
                        self._tab_buttons[idx].set_title(title)
                    if self._vertical_mode:
                        view._ai_header.title_label.set_label(title)
                        view._ai_header.title_label.set_visible(True)
                    # Only mark as inferred if the title is meaningful
                    # (not a generic "Chat N" placeholder), so the inferrer
                    # can still derive a real title from the first message.
                    if not re.fullmatch(r"Chat \d+", title):
                        view._title_inferred = True
                # Restore per-tab provider so each tab keeps its CLI
                provider = tab_info.get("provider")
                if provider:
                    view._current_provider = provider
                # Restore per-tab model so each tab keeps its model choice
                model = tab_info.get("model")
                if model:
                    view._current_model = model
                # Restore per-tab session ID so --resume uses the right session
                session_id = tab_info.get("session_id")
                if session_id:
                    view._session_id = session_id
            # Restore active tab
            active = saved_tabs[0].get("active_idx", 0) if saved_tabs else 0
            # active_idx is stored on the first entry by convention
            for t in saved_tabs:
                if "active_idx" in t:
                    active = t["active_idx"]
                    break
            if 0 <= active < len(self._views):
                self._switch_to_tab(active)
        else:
            self._add_view()

    # ── Header ────────────────────────────────────────────────────────

    def _build_header(self) -> None:
        from ai.ai_terminal_header import AITerminalHeader

        hdr = AITerminalHeader(label=self._resolve_label())
        hdr.header_btn.connect("clicked", self._on_header_click)
        hdr.add_btn.connect("clicked", lambda _b: self._on_add_request())
        hdr.clear_btn.connect("clicked", lambda _b: self._close_tab(self._active_idx))
        hdr.maximize_btn.connect("clicked", self._on_maximize_clicked)
        self._stack_maximize_btn = hdr.maximize_btn
        self._header = hdr
        self.append(hdr.box)

    # ── View management ───────────────────────────────────────────────

    def _add_view(self):
        from ai.ai_terminal_view import AITerminalView

        view = AITerminalView(
            get_workspace_folders_callback=self._get_workspace_folders,
            get_editor_context_callback=self._get_editor_context,
        )
        view.set_vexpand(True)

        view.on_maximize = lambda name: self._on_view_maximize(name)
        view.on_provider_changed = lambda label, v=view: self._on_view_provider_changed(v, label)
        view.on_title_inferred = lambda title, v=view: self._on_title_inferred(self._view_idx(v), title)
        view.on_user_prompt = lambda text, v=view: self._on_user_prompt(v, text)
        view.on_processing_changed = lambda p, v=view: self._on_processing_changed(self._view_idx(v), p)

        self._views.append(view)
        tab_idx = len(self._views) - 1
        self._active_idx = tab_idx

        if self._vertical_mode:
            # Vertical mode: show each view's own header, add to vertical container
            view.add_css_class(self.UNFOCUS_CSS_CLASS)
            # Wire up header buttons for pane-level add/close
            view._ai_header.add_btn.connect("clicked", lambda _b: self._on_add_request())
            view._ai_header.clear_btn.connect("clicked", lambda _b, v=view: self._close_tab_by_view(v))
            # Route pane-level maximize through view.on_maximize (like terminal_stack);
            # this avoids double-firing since _on_maximize_clicked already calls on_maximize.
            view.on_maximize = lambda _name, v=view: self._on_pane_maximize(v)
            self._content_container.prepend(view)
        else:
            view._header.set_visible(False)
            stack_name = f"ai_{id(view)}"
            self._content_stack.add_named(view, stack_name)
            self._add_tab_button(tab_idx, f"Chat {len(self._views)}")
            self._update_tab_close_buttons()
            self._update_tab_bar_visibility()
            self._content_stack.set_visible_child_name(stack_name)
            self._update_tab_selection()
            GLib.idle_add(self._scroll_tab_into_view, tab_idx)
            self._header.set_label(self._label_for_view(view))
        return view

    # ── CLI provider header logic ──────────────────────────────────────

    def _resolve_label(self) -> str:
        from ai.cli.cli_manager import cli_manager
        from shared.settings import get_setting

        return cli_manager.resolve_label(get_setting("ai.provider", ""))

    def _label_for_view(self, view) -> str:
        from ai.cli.cli_manager import cli_manager

        return cli_manager.labels().get(view._current_provider or "", "AI")

    def _on_header_click(self, _button) -> None:
        from ai.cli.cli_manager import cli_manager
        from shared.settings import get_setting

        availability = cli_manager.availability()
        labels = cli_manager.labels()
        active = self._active
        current = (active._current_provider if active else None) or get_setting("ai.provider", "")
        current_model = (active._current_model if active else None) or get_setting("ai.model", "")

        items: list[dict] = []
        for pid in cli_manager.provider_ids:
            if availability.get(pid):
                check = "✓ " if pid == current else "  "
                items.append({"label": f"{check}{labels[pid]}", "action": pid, "enabled": True})

        # Add model submenu for the active provider, fetched dynamically from the CLI
        models = cli_manager.fetch_models(current) if current else []

        if models:
            items.append({"label": "---"})
            for m in models:
                check = "✓ " if m == current_model else "  "
                items.append({"label": f"{check}{m}", "action": f"model:{m}", "enabled": True})

        if not items:
            return

        def _on_selected(action: str) -> None:
            if action.startswith("model:"):
                model = action[len("model:") :]
                if active:
                    active._on_model_selected(model)
            else:
                self._on_cli_selected(action)

        root = self.get_root()
        if root:
            from popups.nvim_context_menu import show_context_menu

            show_context_menu(root, items, _on_selected, title="Select AI")

    def _on_cli_selected(self, provider: str) -> None:
        from ai.cli.cli_manager import cli_manager

        active = self._active
        if active:
            active._on_cli_selected(provider)
        label = cli_manager.labels().get(provider, "AI")
        self._header.set_label(label)

    def _view_idx(self, view) -> int:
        """Return the current index of *view* in self._views, or -1 if not found."""
        try:
            return self._views.index(view)
        except ValueError:
            return -1

    def _on_user_prompt(self, view, user_text: str) -> None:
        """Log every user prompt to Dev Pad, keyed by session ID."""
        session_id = getattr(view, "_session_id", None)
        if not session_id:
            return
        # Derive the tab title for the Dev Pad row
        idx = self._view_idx(view)
        if self._vertical_mode and 0 <= idx < len(self._views):
            title = view._ai_header.title_label.get_label() or "AI Chat"
        elif not self._vertical_mode and 0 <= idx < len(self._tab_buttons):
            title = self._tab_buttons[idx].get_title()
        else:
            title = "AI Chat"

        from dev_pad.dev_pad import log_ai_activity

        log_ai_activity(question=user_text, chat_id=session_id, title=title)

    def _on_view_maximize(self, name: str) -> None:
        if self.on_maximize:
            self.on_maximize(name)

    def _on_view_provider_changed(self, view, label: str) -> None:
        if view is self._active:
            self._header.set_label(label)

    def _on_maximize_clicked(self, _button) -> None:
        if self.on_maximize:
            self.on_maximize("ai_chat")

    @property
    def _active(self):
        if self._views and 0 <= self._active_idx < len(self._views):
            return self._views[self._active_idx]
        return None

    # ── Click / focus ──────────────────────────────────────────────────

    def _on_panel_click(self, gesture, n_press, x, y):
        gesture.set_state(Gtk.EventSequenceState.DENIED)
        get_component_focus_manager().set_focus(self.COMPONENT_ID)

        # In vertical mode, detect which chat pane was clicked
        if self._vertical_mode:
            widget = gesture.get_widget()
            for i, view in enumerate(self._views):
                if is_click_inside_widget(widget, x, y, view):
                    if i != self._active_idx:
                        self._active_idx = i
                        self._update_vertical_focus_border()
                    break

    def _on_focus_in(self):
        if self._vertical_mode:
            self._update_vertical_focus_border()
        else:
            self._handle_panel_focus_in()
        active = self._active
        if active:
            active.terminal.grab_focus()

    def _on_focus_out(self):
        if self._vertical_mode:
            self._clear_vertical_focus_border()
        else:
            self._handle_panel_focus_out()

    def _on_pane_maximize(self, view) -> None:
        """Handle maximize button click from a pane header in vertical mode."""
        maximized = getattr(self, "_maximized_view", None)
        if maximized is view:
            # Restore: show all views
            self._maximized_view = None
            for v in self._views:
                v.set_visible(True)
                v.maximize_btn.remove_css_class("selected")
                v.maximize_btn.set_tooltip_text("Maximize")
        else:
            # Maximize: hide all except this one
            self._maximized_view = view
            for v in self._views:
                if v is view:
                    v.set_visible(True)
                else:
                    v.set_visible(False)
                    v.maximize_btn.remove_css_class("selected")
                    v.maximize_btn.set_tooltip_text("Maximize")
        # Also expand/restore the overall AI chat panel (global maximize)
        if self.on_maximize:
            self.on_maximize("ai_chat")

    @property
    def maximize_btn(self):
        """Maximize button (stack-level in tab mode, active view in vertical mode)."""
        if not self._vertical_mode and hasattr(self, "_stack_maximize_btn"):
            return self._stack_maximize_btn
        active = self._active
        return active.maximize_btn if active else None

    @property
    def _is_maximized(self):
        return getattr(self, "__is_maximized", False)

    @_is_maximized.setter
    def _is_maximized(self, value):
        self.__is_maximized = value
        # Sync CSS on per-view maximize buttons
        for v in self._views:
            if self._vertical_mode:
                maximized_view = getattr(self, "_maximized_view", None)
                if maximized_view and v is maximized_view and value:
                    v.maximize_btn.add_css_class("selected")
                    v.maximize_btn.set_tooltip_text("Restore")
                else:
                    v.maximize_btn.remove_css_class("selected")
                    v.maximize_btn.set_tooltip_text("Maximize")
            else:
                if value:
                    v.maximize_btn.add_css_class("selected")
                    v.maximize_btn.set_tooltip_text("Restore")
                else:
                    v.maximize_btn.remove_css_class("selected")
                    v.maximize_btn.set_tooltip_text("Maximize")
        if not self._vertical_mode and hasattr(self, "_stack_maximize_btn"):
            if value:
                self._stack_maximize_btn.add_css_class("selected")
                self._stack_maximize_btn.set_tooltip_text("Restore")
            else:
                self._stack_maximize_btn.remove_css_class("selected")
                self._stack_maximize_btn.set_tooltip_text("Maximize")
        if not self._vertical_mode or not self._views:
            return
        if value:
            # Pane-level maximize: hide all views except the active one
            active = self._views[self._active_idx] if 0 <= self._active_idx < len(self._views) else None
            if active and not getattr(self, "_maximized_view", None):
                self._maximized_view = active
                for v in self._views:
                    v.set_visible(v is active)
        elif getattr(self, "_maximized_view", None):
            # Restore: show all views
            self._maximized_view = None
            for v in self._views:
                v.set_visible(True)

    def _update_vertical_focus_border(self):
        """In vertical mode, apply focus border to the active view only."""
        maximized_view = getattr(self, "_maximized_view", None)
        for view in self._views:
            view.remove_css_class(self.FOCUS_CSS_CLASS)
            view.add_css_class(self.UNFOCUS_CSS_CLASS)
            if maximized_view and view is maximized_view:
                view.maximize_btn.add_css_class("selected")
            elif not maximized_view:
                view.maximize_btn.remove_css_class("selected")
        if 0 <= self._active_idx < len(self._views):
            active = self._views[self._active_idx]
            active.remove_css_class(self.UNFOCUS_CSS_CLASS)
            active.add_css_class(self.FOCUS_CSS_CLASS)

    def _clear_vertical_focus_border(self):
        """In vertical mode, remove focus border from all views."""
        for view in self._views:
            view.remove_css_class(self.FOCUS_CSS_CLASS)
            view.add_css_class(self.UNFOCUS_CSS_CLASS)

    # ── Public API (AITerminalView-compatible) ─────────────────────────

    def change_directory(self, path: str) -> None:
        """Set the working directory for all AI terminal views."""
        for view in self._views:
            view.cwd = path

    def cleanup(self) -> None:
        for idx in list(self._spinners):
            if self._vertical_mode:
                self._stop_header_spinner(idx)
            else:
                self._stop_tab_spinner(idx)
        for view in self._views:
            view.cleanup()

    def focus_input(self) -> None:
        active = self._active
        if active:
            active.focus_input()

    def is_processing(self) -> bool:
        return False

    def stop_ai(self) -> None:
        active = self._active
        if active:
            active.stop_ai()

    def update_font(self) -> None:
        for view in self._views:
            view.update_font()
        if not self._vertical_mode:
            self._header.apply_header_font()
