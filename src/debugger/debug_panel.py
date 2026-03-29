"""Debug Panel — bottom panel UI for debugging.

Shows debug toolbar, call stack, variables tree, breakpoints list,
and debug console. Registered via SplitPanelManager.
"""

import os

from gi.repository import Gdk, Gtk, Pango

from icons import IconsManager
from shared.ui import ZenButton
from themes import get_theme

from .breakpoint_manager import Breakpoint, get_breakpoint_manager
from .debug_console import DebugConsole
from .debug_session import DebugSession, SessionState


class DebugPanel(Gtk.Box):
    """Debug panel with toolbar, call stack, variables, breakpoints, and console."""

    COMPONENT_ID = "debug_panel"

    def __init__(self, window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self._window = window
        self._session: DebugSession | None = None
        self._breakpoint_mgr = get_breakpoint_manager()
        self.add_css_class("debug-panel")

        theme = get_theme()
        from fonts import get_font_settings

        font_settings = get_font_settings("editor")
        font_family = font_settings["family"]
        self._font_desc = Pango.FontDescription.from_string(f"{font_family} 10")
        self._font_attrs = Pango.AttrList.new()
        self._font_attrs.insert(Pango.attr_font_desc_new(self._font_desc))

        # -- Toolbar --
        self._toolbar = self._create_toolbar()
        self.append(self._toolbar)

        # -- Main content: all sections stacked vertically --
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        content_box.set_vexpand(True)
        self.append(content_box)

        # Call stack section
        content_box.append(self._create_section_label("CALL STACK"))
        stack_scroll = Gtk.ScrolledWindow()
        stack_scroll.set_vexpand(True)
        stack_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        content_box.append(stack_scroll)

        self._stack_list = Gtk.ListBox()
        self._stack_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._stack_list.connect("row-activated", self._on_stack_frame_activated)
        self._stack_list.add_css_class("debug-stack-list")
        stack_scroll.set_child(self._stack_list)

        # Variables section
        content_box.append(self._create_section_label("VARIABLES"))
        var_scroll = Gtk.ScrolledWindow()
        var_scroll.set_vexpand(True)
        var_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        content_box.append(var_scroll)

        self._var_tree = Gtk.TreeView()
        self._var_tree.set_headers_visible(True)
        self._var_tree.add_css_class("debug-var-tree")

        # Columns: Name, Value, Type
        for col_name, col_idx, min_w in [("Name", 0, 80), ("Value", 1, 100), ("Type", 2, 0)]:
            renderer = Gtk.CellRendererText()
            renderer.set_property("font-desc", self._font_desc)
            col = Gtk.TreeViewColumn(col_name, renderer, text=col_idx)
            col.set_resizable(True)
            if min_w:
                col.set_min_width(min_w)
            self._var_tree.append_column(col)

        # Force font on TreeView column headers via inline CSS
        css = Gtk.CssProvider()
        css.load_from_string(
            f"treeview header button {{ font-family: '{font_family}'; font-size: 10pt; }}"
        )
        self._var_tree.get_style_context().add_provider(css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1)

        # TreeStore: name, value, type, variables_reference (hidden)
        self._var_store = Gtk.TreeStore(str, str, str, int)
        self._var_tree.set_model(self._var_store)
        self._var_tree.connect("row-expanded", self._on_variable_expanded)
        self._var_tree.set_activate_on_single_click(True)
        self._var_tree.connect("row-activated", self._on_var_row_activated)

        # Key controller so Left/Right expand/collapse instead of scrolling
        key_ctrl = Gtk.EventControllerKey.new()
        key_ctrl.connect("key-pressed", self._on_var_key_pressed)
        self._var_tree.add_controller(key_ctrl)

        var_scroll.set_child(self._var_tree)

        # Breakpoints section
        content_box.append(self._create_section_label("BREAKPOINTS"))
        bp_scroll = Gtk.ScrolledWindow()
        bp_scroll.set_vexpand(True)
        bp_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        content_box.append(bp_scroll)

        self._bp_list = Gtk.ListBox()
        self._bp_list.set_selection_mode(Gtk.SelectionMode.NONE)
        self._bp_list.add_css_class("debug-bp-list")
        bp_scroll.set_child(self._bp_list)

        # Debug console section
        content_box.append(self._create_section_label("DEBUG CONSOLE"))
        self._console = DebugConsole(on_evaluate=self._on_evaluate)
        self._console.set_vexpand(True)
        content_box.append(self._console)

        # Subscribe to breakpoint changes
        self._breakpoint_mgr.subscribe(self._on_breakpoints_changed)
        self._refresh_breakpoints_list()

    def set_session(self, session: DebugSession | None) -> None:
        """Set the active debug session."""
        self._session = session
        self._update_toolbar_state()
        if session:
            self._console.clear()

    # -- Toolbar --

    def _create_toolbar(self) -> Gtk.Box:
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        toolbar.set_margin_top(4)
        toolbar.set_margin_bottom(4)
        toolbar.set_margin_start(8)
        toolbar.set_margin_end(8)
        toolbar.add_css_class("debug-toolbar")

        buttons = [
            ("Continue", IconsManager.CONTINUE, self._on_continue),
            ("Step Over", IconsManager.STEP_OVER, self._on_step_over),
            ("Step In", IconsManager.STEP_INTO, self._on_step_in),
            ("Step Out", IconsManager.STEP_OUT, self._on_step_out),
            ("Restart", IconsManager.RESTART, self._on_restart),
            ("Stop", IconsManager.STOP, self._on_stop),
        ]

        self._toolbar_buttons = {}
        for label, icon, callback in buttons:
            btn = ZenButton(icon=icon, tooltip=label)
            btn.connect("clicked", callback)
            btn.add_css_class("debug-toolbar-btn")
            toolbar.append(btn)
            self._toolbar_buttons[label] = btn

        # Status label
        self._status_label = Gtk.Label(label="Not debugging")
        self._status_label.set_hexpand(True)
        self._status_label.set_halign(Gtk.Align.END)
        self._status_label.add_css_class("debug-status")
        self._status_label.set_attributes(self._font_attrs)
        toolbar.append(self._status_label)

        # Close button
        close_btn = Gtk.Button()
        close_btn.set_icon_name("window-close-symbolic")
        close_btn.set_tooltip_text("Close debug panel")
        close_btn.connect("clicked", lambda _: self._window.split_panels.hide("debug"))
        close_btn.add_css_class("flat")
        toolbar.append(close_btn)

        return toolbar

    def _update_toolbar_state(self) -> None:
        """Update toolbar button sensitivity based on session state."""
        if not self._session:
            state = SessionState.IDLE
        else:
            state = self._session.state

        is_stopped = state == SessionState.STOPPED
        is_running = state == SessionState.RUNNING
        is_active = is_stopped or is_running

        self._toolbar_buttons["Continue"].set_sensitive(is_stopped)
        self._toolbar_buttons["Step Over"].set_sensitive(is_stopped)
        self._toolbar_buttons["Step In"].set_sensitive(is_stopped)
        self._toolbar_buttons["Step Out"].set_sensitive(is_stopped)
        self._toolbar_buttons["Restart"].set_sensitive(is_active)
        self._toolbar_buttons["Stop"].set_sensitive(is_active)

        state_labels = {
            SessionState.IDLE: "Not debugging",
            SessionState.INITIALIZING: "Starting...",
            SessionState.RUNNING: "Running",
            SessionState.STOPPED: "Paused",
            SessionState.TERMINATED: "",
        }
        self._status_label.set_text(state_labels.get(state, ""))

    # -- Toolbar callbacks --

    def _on_continue(self, btn):
        if self._session:
            self._session.continue_()

    def _on_step_over(self, btn):
        if self._session:
            self._session.step_over()

    def _on_step_in(self, btn):
        if self._session:
            self._session.step_into()

    def _on_step_out(self, btn):
        if self._session:
            self._session.step_out()

    def _on_restart(self, btn):
        if self._session:
            self._session.restart()

    def _on_stop(self, btn):
        if self._session:
            self._session.stop()

    # -- Call Stack --

    def update_call_stack(self, frames: list) -> None:
        """Update the call stack display."""
        # Remove all existing rows
        while True:
            row = self._stack_list.get_row_at_index(0)
            if row is None:
                break
            self._stack_list.remove(row)

        for i, frame in enumerate(frames):
            row = Gtk.ListBoxRow()
            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
            box.set_margin_start(4)
            box.set_margin_end(4)
            box.set_margin_top(2)
            box.set_margin_bottom(2)

            # Function name
            name_label = Gtk.Label(label=frame.name)
            name_label.set_halign(Gtk.Align.START)
            name_label.set_hexpand(True)
            name_label.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
            name_label.set_attributes(self._font_attrs)
            box.append(name_label)

            # File:line
            basename = os.path.basename(frame.source) if frame.source else ""
            loc_label = Gtk.Label(label=f"{basename}:{frame.line}")
            loc_label.add_css_class("dim-label")
            loc_label.set_attributes(self._font_attrs)
            box.append(loc_label)

            row.set_child(box)
            row._frame = frame
            self._stack_list.append(row)

    def _on_stack_frame_activated(self, listbox, row) -> None:
        """Handle click on a stack frame — navigate to source."""
        if not hasattr(row, "_frame"):
            return
        frame = row._frame
        if self._session:
            self._session.set_current_frame(frame)
            self._refresh_variables()
        # Navigate editor to the frame location
        if frame.source and os.path.isfile(frame.source):
            self._window.editor_view.open_file(frame.source, frame.line)

    # -- Variables --

    def _refresh_variables(self) -> None:
        """Refresh the variables tree from the current session."""
        self._var_store.clear()
        if not self._session or self._session.state != SessionState.STOPPED:
            return

        scopes = self._session.get_scopes()
        for scope in scopes:
            scope_iter = self._var_store.append(None, [scope.name, "", "", scope.variables_reference])
            # Load variables for non-expensive scopes
            if not scope.expensive and scope.variables_reference:
                variables = self._session.get_variables(scope.variables_reference)
                for var in variables:
                    var_iter = self._var_store.append(scope_iter, [var.name, var.value, var.type, var.variables_reference])
                    # Add placeholder for expandable variables
                    if var.variables_reference > 0:
                        self._var_store.append(var_iter, ["...", "", "", 0])

    def _on_variable_expanded(self, tree_view, tree_iter, tree_path) -> None:
        """Lazy-load child variables when a tree node is expanded."""
        if not self._session:
            return
        ref = self._var_store.get_value(tree_iter, 3)
        if ref <= 0:
            return

        # Check if first child is placeholder
        child = self._var_store.iter_children(tree_iter)
        if child and self._var_store.get_value(child, 0) == "...":
            # Remove placeholder
            self._var_store.remove(child)
            # Load real children
            variables = self._session.get_variables(ref)
            for var in variables:
                var_iter = self._var_store.append(tree_iter, [var.name, var.value, var.type, var.variables_reference])
                if var.variables_reference > 0:
                    self._var_store.append(var_iter, ["...", "", "", 0])

    def _on_var_row_activated(self, tree_view, path, column) -> None:
        """Toggle expand/collapse on double-click (row-activated)."""
        if tree_view.row_expanded(path):
            tree_view.collapse_row(path)
        else:
            tree_view.expand_row(path, False)

    def _on_var_key_pressed(self, controller, keyval, keycode, state) -> bool:
        """Handle Left/Right keys for expand/collapse instead of horizontal scroll."""
        sel = self._var_tree.get_selection()
        model, tree_iter = sel.get_selected()
        if tree_iter is None:
            return False

        path = model.get_path(tree_iter)

        if keyval == Gdk.KEY_Right:
            if not self._var_tree.row_expanded(path):
                self._var_tree.expand_row(path, False)
            else:
                # Move to first child
                child = model.iter_children(tree_iter)
                if child:
                    child_path = model.get_path(child)
                    self._var_tree.set_cursor(child_path, None, False)
            return True

        if keyval == Gdk.KEY_Left:
            if self._var_tree.row_expanded(path):
                self._var_tree.collapse_row(path)
            else:
                # Move to parent
                parent = model.iter_parent(tree_iter)
                if parent:
                    parent_path = model.get_path(parent)
                    self._var_tree.set_cursor(parent_path, None, False)
            return True

        return False

    # -- Breakpoints list --

    def _refresh_breakpoints_list(self) -> None:
        """Refresh the breakpoints list display."""
        while True:
            row = self._bp_list.get_row_at_index(0)
            if row is None:
                break
            self._bp_list.remove(row)

        all_bps = self._breakpoint_mgr.get_all()
        for file_path, bps in sorted(all_bps.items()):
            for bp in sorted(bps, key=lambda b: b.line):
                row = Gtk.ListBoxRow()
                box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
                box.set_margin_start(4)
                box.set_margin_end(4)
                box.set_margin_top(1)
                box.set_margin_bottom(1)

                # Enable/disable checkbox
                check = Gtk.CheckButton()
                check.set_active(bp.enabled)
                check.connect("toggled", self._on_bp_toggled, bp)
                box.append(check)

                # File:line label
                basename = os.path.basename(file_path)
                label_text = f"{basename}:{bp.line}"
                if bp.condition:
                    label_text += f" ({bp.condition})"
                elif bp.log_message:
                    label_text += f" \u2139 {bp.log_message}"

                label = Gtk.Label(label=label_text)
                label.set_halign(Gtk.Align.START)
                label.set_hexpand(True)
                label.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
                label.set_attributes(self._font_attrs)
                box.append(label)

                # Click to navigate
                gesture = Gtk.GestureClick()
                gesture.connect("pressed", self._on_bp_clicked, bp)
                row.add_controller(gesture)

                row.set_child(box)
                self._bp_list.append(row)

    def _on_bp_toggled(self, check_button, bp: Breakpoint) -> None:
        """Toggle breakpoint enabled state."""
        self._breakpoint_mgr.set_enabled(bp.file_path, bp.line, check_button.get_active())
        # Sync with adapter
        if self._session:
            self._session.sync_file_breakpoints(bp.file_path)

    def _on_bp_clicked(self, gesture, n_press, x, y, bp: Breakpoint) -> None:
        """Navigate to breakpoint location."""
        if n_press == 1 and os.path.isfile(bp.file_path):
            self._window.editor_view.open_file(bp.file_path, bp.line)

    def _on_breakpoints_changed(self, file_path: str, action: str) -> None:
        """Called when breakpoints change."""
        self._refresh_breakpoints_list()
        # Sync with adapter if session is active
        if self._session and file_path:
            self._session.sync_file_breakpoints(file_path)

    # -- Debug Console --

    def _on_evaluate(self, expression: str) -> str | None:
        """Evaluate an expression in the debug console."""
        if not self._session or self._session.state != SessionState.STOPPED:
            return "<not stopped>"
        return self._session.evaluate(expression)

    def append_output(self, text: str, category: str = "stdout") -> None:
        """Append output to the debug console."""
        self._console.append_output(text, category)

    # -- Session state callbacks --

    def on_session_state_changed(self, session: DebugSession) -> None:
        """Called when the debug session state changes."""
        self._update_toolbar_state()
        if session.state == SessionState.TERMINATED:
            self._status_label.set_text("")

    def on_session_stopped(self, session: DebugSession, thread_id: int, reason: str, file_path: str, line: int) -> None:
        """Called when execution stops (breakpoint hit, step completed)."""
        self._update_toolbar_state()

        # Update call stack
        frames = session.get_call_stack(thread_id)
        self.update_call_stack(frames)

        # Update variables
        self._refresh_variables()

        # Navigate to stopped location
        if file_path and os.path.isfile(file_path):
            self._window.editor_view.open_file(file_path, line)

        # Update status
        self._status_label.set_text("")

    # -- Helpers --

    def _create_section_label(self, text: str) -> Gtk.Label:
        label = Gtk.Label(label=text)
        label.set_halign(Gtk.Align.START)
        label.set_margin_start(8)
        label.set_margin_top(4)
        label.set_margin_bottom(2)
        label.add_css_class("dim-label")
        label.set_attributes(self._font_attrs)
        return label

    # -- Panel show/hide (required by SplitPanelManager) --

    def show_panel(self) -> None:
        """Show the debug panel."""
        self.set_visible(True)

    def hide_panel(self) -> None:
        """Hide the debug panel."""
        self.set_visible(False)

    def cleanup(self) -> None:
        """Clean up resources."""
        self._breakpoint_mgr.unsubscribe(self._on_breakpoints_changed)
        if self._session:
            self._session.stop()
