"""
AI Terminal View for Zen IDE.

Runs the selected AI CLI (claude or copilot) directly inside a VTE terminal,
giving a native interactive experience without any custom rendering layer.

The active CLI is persisted via the ``ai.provider`` setting
(``"claude_cli"`` | ``"copilot_cli"``).  Clicking the header button opens a
popup to switch between available CLIs; the terminal restarts immediately.
"""

import os
import re

from gi.repository import GLib, Gtk, Vte

from ai.cli.cli_provider_mixin import CliProviderMixin
from terminal.jog_wheel_scrollbar_mixin import JogWheelScrollbarMixin
from terminal.terminal_view import TerminalView


def _strip_escape_fragments(text: str) -> str:
    """Remove leftover escape sequence fragments from captured VTE input.

    The commit signal can include terminal capability responses (e.g.
    ``[?1;2c``, ``[200~``) whose ESC byte (0x1b) is filtered out but
    whose remaining chars leak into the input buffer.
    """
    # CSI-style fragments: "[" then parameters then a letter/~
    text = re.sub(r"\[(?:\?[\d;]*|[\d;]+)[A-Za-z~]", "", text)
    # DA2 residue: ">digits;digits;digitsc"
    text = re.sub(r">[\d;]+[A-Za-z]", "", text)
    # Strip leading non-alphanumeric junk (stray ;?> etc from escape params)
    text = re.sub(r"^[^a-zA-Z0-9]*", "", text)
    return text.strip()


class AITerminalView(CliProviderMixin, JogWheelScrollbarMixin, TerminalView):
    """VTE-based AI terminal that runs claude or copilot CLI interactively.

    Inherits all VTE machinery (theme, scroll, shortcuts, font) from
    TerminalView.  Only the header and the shell-spawn logic are overridden.

    CLI provider logic (resolution, spawn, session management, header
    interaction) lives in ``CliProviderMixin``.
    """

    COMPONENT_ID = "ai_chat"

    def __init__(self, config_dir: str | None = None, get_workspace_folders_callback=None, get_editor_context_callback=None):
        self._current_provider: str | None = None
        self._current_model: str | None = None
        self._input_buf: list[str] = []
        self._title_inferred = False
        self._waiting_for_response = False
        self._commit_ready = False  # ignore commit signals until CLI is ready
        self._in_escape_seq = False  # inside a VTE escape sequence
        self._in_osc_seq = False  # inside an OSC (Operating System Command) sequence
        self._idle_poll_id: int = 0  # GLib timer for PTY idle detection
        self._last_contents_serial: int = 0  # bumped on contents-changed
        self._session_id: str | None = None  # Claude CLI session ID for resume
        self._resume_attempted = False  # True while a --resume spawn is settling
        self._resume_spawn_time: float = 0.0
        self._jog_init_fields()
        self.on_title_inferred = None  # callback(title: str)
        self.on_user_prompt = None  # callback(user_text: str)
        self.on_processing_changed = None  # callback(processing: bool)
        self._get_workspace_folders = get_workspace_folders_callback
        self._get_editor_context = get_editor_context_callback
        super().__init__(config_dir=config_dir)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _create_ui(self) -> None:
        from ai.ai_terminal_header import AITerminalHeader

        hdr = AITerminalHeader(label=self._resolve_label())
        hdr.header_btn.connect("clicked", self._on_header_click)
        hdr.clear_btn.connect("clicked", lambda _b: self.clear())
        hdr.maximize_btn.connect("clicked", self._on_maximize_clicked)

        self.header_btn = hdr.header_btn
        self.maximize_btn = hdr.maximize_btn
        self._header = hdr.box
        self._ai_header = hdr
        self.append(hdr.box)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.NEVER)
        scrolled.set_vexpand(True)
        scrolled.set_hexpand(True)
        scrolled.set_kinetic_scrolling(True)
        scrolled.add_css_class("terminal-scrolled")
        self._scrolled_window = scrolled

        self.terminal = Vte.Terminal()
        self._configure_terminal()
        scrolled.set_child(self.terminal)

        overlay = self._jog_create_overlay(scrolled)
        self.append(overlay)

        self._commit_handler_id = self.terminal.connect("commit", self._on_vte_commit)
        self.terminal.connect("contents-changed", self._on_contents_changed)

        self._is_maximized = False
        self.on_maximize = None
        self.on_provider_changed = None

    # ------------------------------------------------------------------
    # Maximize (override TerminalView which hardcodes "terminal")
    # ------------------------------------------------------------------

    def _on_maximize_clicked(self, button):
        """Delegate maximize to parent — state and CSS managed by window_panels."""
        if hasattr(self, "on_maximize") and self.on_maximize:
            self.on_maximize("ai_chat")

    # ------------------------------------------------------------------
    # Tab title inference from first user message
    # ------------------------------------------------------------------

    def _enable_commit_tracking(self) -> bool:
        """Called after startup delay — clean up any startup noise.

        The commit handler always runs (no gating), so user input typed
        before this fires is already in the buffer.  Strip any escape
        residue that leaked through, but preserve real user chars.
        """
        self._commit_ready = True
        # Strip startup noise but keep any user input already typed
        if self._input_buf and not self._title_inferred:
            cleaned = _strip_escape_fragments("".join(self._input_buf))
            self._input_buf.clear()
            if cleaned:
                self._input_buf.extend(cleaned)
        elif not self._title_inferred:
            self._input_buf.clear()
        self._in_escape_seq = False
        self._in_osc_seq = False
        return False  # one-shot GLib timeout

    def _on_vte_commit(self, _terminal, text, _length) -> None:
        """Accumulate user input; on first Enter infer a tab title.

        Also drives the spinner: Enter → processing=True, next typing → processing=False.
        """
        for ch in text:
            # Skip escape sequences (e.g. focus-in/out \x1b[I / \x1b[O,
            # cursor reports, bracketed-paste markers) so their trailing
            # printable bytes aren't mistaken for real user input.
            if ch == "\x1b":
                self._in_escape_seq = True
                # If inside OSC/DCS payload, keep _in_osc_seq so the
                # following \\ (ST) can properly terminate it.
                if not self._in_osc_seq:
                    self._in_osc_seq = False
                continue
            if self._in_escape_seq:
                if self._in_osc_seq:
                    if ch == "\x07":
                        # BEL terminates OSC/DCS
                        self._in_escape_seq = False
                        self._in_osc_seq = False
                    elif ch == "\\":
                        # ST (\x1b\\) terminates OSC/DCS
                        self._in_escape_seq = False
                        self._in_osc_seq = False
                elif ch == "]":
                    # OSC sequence (\x1b]...BEL/ST)
                    self._in_osc_seq = True
                elif ch == "P":
                    # DCS sequence (\x1bP...ST)
                    self._in_osc_seq = True
                elif ch.isalpha() or ch == "~":
                    # CSI/short sequences end at an alpha char or ~
                    self._in_escape_seq = False
                continue

            if ch in ("\r", "\n"):
                self._vscroll_reset()
                user_text = "".join(self._input_buf).strip()
                # Strip leftover escape sequence fragments (e.g. terminal
                # capability responses like "[?1;2c" or "[200~").
                user_text = _strip_escape_fragments(user_text)
                self._input_buf.clear()
                if user_text:
                    # Start spinner — CLI is now processing
                    if not self._waiting_for_response:
                        self._waiting_for_response = True
                        self._start_idle_poll()
                        if callable(self.on_processing_changed):
                            self.on_processing_changed(True)

                    # Infer tab title from user message (keep trying until one sticks)
                    if not self._title_inferred:
                        from ai.tab_title_inferrer import infer_title

                        title = infer_title([{"role": "user", "content": user_text}])
                        if title and callable(self.on_title_inferred):
                            self._title_inferred = True
                            self.on_title_inferred(title)

                    # Notify about every user prompt (for Dev Pad tracking)
                    if callable(self.on_user_prompt):
                        self.on_user_prompt(user_text)
            elif ch == "\x7f":  # backspace
                if self._input_buf:
                    self._input_buf.pop()
                if self._waiting_for_response:
                    self._waiting_for_response = False
                    self._stop_idle_poll()
                    if callable(self.on_processing_changed):
                        self.on_processing_changed(False)
            elif ch >= " ":  # printable characters only
                self._input_buf.append(ch)
                # User is typing again — CLI returned to prompt, stop spinner
                if self._waiting_for_response:
                    self._waiting_for_response = False
                    self._stop_idle_poll()
                    if callable(self.on_processing_changed):
                        self.on_processing_changed(False)

    # ------------------------------------------------------------------
    # PTY idle detection — stop spinner when CLI waits for input
    # ------------------------------------------------------------------

    def _start_idle_poll(self) -> None:
        """Begin polling the PTY to detect when the CLI becomes idle."""
        self._stop_idle_poll()
        self._last_contents_serial = 0
        self._idle_prev_serial = -1
        self._idle_poll_id = GLib.timeout_add(500, self._check_idle)

    def _stop_idle_poll(self) -> None:
        if self._idle_poll_id:
            GLib.source_remove(self._idle_poll_id)
            self._idle_poll_id = 0

    def _check_idle(self) -> bool:
        """Periodically check whether the CLI process is waiting for input."""
        if not self._waiting_for_response:
            self._idle_poll_id = 0
            return False

        # If terminal content changed since last tick, CLI is still producing
        # output — keep waiting.
        if self._last_contents_serial != self._idle_prev_serial:
            self._idle_prev_serial = self._last_contents_serial
            return True  # keep polling

        # Content has been stable for one poll interval.  Ask the OS whether
        # the CLI process is the PTY foreground group (i.e. it is the one
        # reading from the terminal, not a tool subprocess).
        try:
            pty = self.terminal.get_pty()
            if pty is None:
                return True
            fd = pty.get_fd()
            fg_pgid = os.tcgetpgrp(fd)
            if fg_pgid == self.shell_pid:
                self._waiting_for_response = False
                self._idle_poll_id = 0
                if callable(self.on_processing_changed):
                    self.on_processing_changed(False)
                return False
        except OSError:
            pass
        return True  # keep polling

    def _setup_scroll_controller(self) -> None:
        """AI terminal: only observe wheel to show/hide the jog-wheel overlay."""
        self._jog_setup_scroll_controller()

    def _jog_scroll_lines(self, lines: int) -> None:
        """Scroll via VTE's vadjustment (scrollback buffer)."""
        vadj = self.terminal.get_vadjustment()
        if vadj is None:
            return
        char_height = self.terminal.get_char_height()
        new_val = vadj.get_value() + lines * char_height
        lower = vadj.get_lower()
        upper = vadj.get_upper() - vadj.get_page_size()
        vadj.set_value(max(lower, min(new_val, upper)))

    def _on_contents_changed(self, _terminal) -> None:
        """Track CLI output for idle detection."""
        self._last_contents_serial += 1

    # ------------------------------------------------------------------
    # Interface expected by window modules
    # ------------------------------------------------------------------

    def focus_input(self) -> None:
        """Focus the VTE widget (called by window_actions on Cmd+Shift+A)."""
        self.terminal.grab_focus()

    def is_processing(self) -> bool:
        """AI terminal delegates processing entirely to the CLI subprocess."""
        return False

    def stop_ai(self) -> None:
        """Send Ctrl+C to interrupt the running CLI command."""
        self.terminal.feed_child(b"\x03")

    def update_font(self) -> None:
        """Refresh font (called by window_fonts on font-settings change)."""
        self.apply_font_settings()
        self._ai_header.apply_header_font()
