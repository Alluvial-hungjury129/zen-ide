"""
CLI provider mixin for AITerminalView.

Contains all CLI resolution, onboarding, shell spawn, child-exit handling,
header interaction, and session management logic.

Split from ``ai_terminal_view.py`` — no behavioural changes.
"""

import os
import time

from gi.repository import GLib, Vte

from ai.cli.cli_manager import cli_manager
from shared.settings import get_setting, set_setting


class CliProviderMixin:
    """Mixin providing CLI provider logic for AITerminalView.

    Expects the host class to supply: ``terminal``, ``cwd``, ``shell_pid``,
    ``_current_provider``, ``_current_model``, ``_session_id``,
    ``_resume_attempted``, ``_resume_spawn_time``, ``_commit_ready``,
    ``_in_escape_seq``, ``_in_osc_seq``, ``_input_buf``,
    ``_waiting_for_response``, ``_title_inferred``, ``_shutting_down``,
    ``_commit_handler_id``, ``_ai_header``, ``on_processing_changed``,
    ``on_provider_changed``, ``_get_workspace_folders``,
    ``_get_editor_context``, ``_idle_poll_id``,
    ``stop_shell()``, ``_stop_idle_poll()``,
    ``_hide_virtual_scrollbar_immediately()``, ``_on_spawn_callback()``,
    ``_enable_commit_tracking()``, ``_start_idle_poll()``.
    """

    # ------------------------------------------------------------------
    # CLI resolution
    # ------------------------------------------------------------------

    def _resolve_cli_binary(self) -> tuple[str | None, str | None]:
        """Return (binary_path, provider_key) for the configured CLI.

        Uses the per-tab provider first, then the global setting, then
        falls back through registered providers in order.
        """
        preferred = self._current_provider or get_setting("ai.provider", "")
        return cli_manager.resolve(preferred)

    def _resolve_label(self) -> str:
        """Return the CLI display name for the current setting."""
        return cli_manager.resolve_label(get_setting("ai.provider", ""))

    # ------------------------------------------------------------------
    # Onboarding (no CLI detected)
    # ------------------------------------------------------------------

    def _show_onboarding(self) -> bool:
        """Print setup instructions into the VTE when no AI CLI is found."""
        self._show_install_hint(None)
        return GLib.SOURCE_REMOVE

    def _show_install_hint(self, provider: str | None) -> None:
        """Print install instructions for a specific CLI (or both) into the VTE."""
        BOLD = "\033[1m"
        RESET = "\033[0m"
        NL = "\r\n"

        lines = [""]
        if provider:
            p = cli_manager.get(provider)
            name = p.display_name if p else provider
            lines.append(f"  {BOLD}{name} CLI is not installed.{RESET}{NL}")
            lines.extend(cli_manager.install_lines(provider))
        else:
            lines.append(f"  {BOLD}No AI CLI detected.{RESET}")
            lines.append(f"  Install one of the supported CLIs to get started:{NL}")
            lines.extend(cli_manager.install_lines())

        lines.extend(["", "  Then select the CLI from the header menu.", ""])
        self.terminal.feed(NL.join(lines).encode("utf-8"))

    # ------------------------------------------------------------------
    # Shell spawn (override TerminalShellMixin)
    # ------------------------------------------------------------------

    def spawn_shell(self, *, resume: bool = False) -> None:
        """Launch the selected AI CLI binary directly inside VTE.

        If *resume* is True and the provider is Claude CLI, pass
        ``--resume <session_id>`` when a saved session ID is available,
        otherwise fall back to ``--continue`` for the first tab only.
        """
        binary, provider = self._resolve_cli_binary()

        if not binary:
            super().spawn_shell()
            GLib.timeout_add(300, self._show_onboarding)
            return

        self._current_provider = provider
        self._update_header_label()

        from shared.utils import ensure_full_path

        env = ensure_full_path(os.environ.copy())
        env["TERM"] = "xterm-256color"
        env["COLORTERM"] = "truecolor"

        # IDE context: inject editor state as environment variables so
        # AI CLIs can reference the active file, open tabs, and workspace.
        editor_ctx = self._get_editor_context() if self._get_editor_context else {}
        if editor_ctx.get("active_file"):
            env["ZEN_ACTIVE_FILE"] = editor_ctx["active_file"]
        if editor_ctx.get("open_files"):
            env["ZEN_OPEN_FILES"] = ":".join(editor_ctx["open_files"])
        if editor_ctx.get("workspace_folders"):
            env["ZEN_WORKSPACE_FOLDERS"] = ":".join(editor_ctx["workspace_folders"])
        if editor_ctx.get("workspace_file"):
            env["ZEN_WORKSPACE_FILE"] = editor_ctx["workspace_file"]
        if editor_ctx.get("git_branch"):
            env["ZEN_GIT_BRANCH"] = editor_ctx["git_branch"]

        from shared.ide_state_writer import get_state_file_path

        env["ZEN_IDE_STATE_FILE"] = get_state_file_path()

        # Resolve resume / continue flags
        self._resume_attempted = False
        resume_session = None
        continue_last = False
        if resume and provider:
            self.validate_session_id()
            if self._session_id:
                resume_session = self._session_id
                self._resume_attempted = True
                self._resume_spawn_time = time.monotonic()
            else:
                continue_last = True

        # Model override: use per-tab model, then global setting, then CLI default.
        model = self._current_model
        if not model:
            model_setting = get_setting("ai.model", "")
            if isinstance(model_setting, dict):
                model = model_setting.get(provider, "")
            else:
                model = model_setting or ""

        # Extra workspace dirs (multi-workspace support)
        extra_dirs: list[str] = []
        if self._get_workspace_folders:
            cwd_abs = os.path.abspath(self.cwd or os.getcwd())
            for folder in self._get_workspace_folders():
                if os.path.abspath(folder) != cwd_abs:
                    extra_dirs.append(folder)

        # Build argv via the provider
        p = cli_manager.get(provider)
        argv = p.build_argv(
            binary,
            resume_session=resume_session,
            continue_last=continue_last,
            yolo=get_setting("ai.yolo_mode", True),
            model=model or "",
            extra_dirs=extra_dirs,
        )

        # IDE context: append provider-specific system prompt / instructions
        p.append_ide_context(argv, editor_ctx)

        # Reset commit readiness — CLI startup sends terminal capability
        # queries whose responses arrive via the commit signal and would
        # otherwise be captured as user input (the "Op Vte 7600 …" garbage).
        self._commit_ready = False
        self._in_escape_seq = False
        self._in_osc_seq = False
        self._input_buf.clear()

        env_list = [f"{k}={v}" for k, v in env.items()]

        self.terminal.spawn_async(
            Vte.PtyFlags.DEFAULT,
            self.cwd,
            argv,
            env_list,
            GLib.SpawnFlags.DEFAULT,
            None,
            None,
            -1,
            None,
            self._on_spawn_callback,
        )

        # Allow enough time for CLI startup queries to settle before
        # the commit handler starts tracking user input.
        GLib.timeout_add(1500, self._enable_commit_tracking)

        # Session ID detection for new (non-resumed) tabs is coordinated
        # by AITerminalStack.spawn_shell() to avoid multiple tabs claiming
        # the same session.  Only detect here when spawned standalone
        # (e.g. via _restart_cli or a manually added tab).
        if not self._session_id and not getattr(self, "_stack_detects", False) and provider:
            self._pre_spawn_sessions = self._list_sessions()
            GLib.timeout_add(3000, self._detect_session_id)

        # After enough time for a successful resume, clear the flag so
        # normal user-initiated exits aren't mistaken for resume failures.
        if self._resume_attempted:
            GLib.timeout_add(10_000, self._clear_resume_flag)

        # Pre-fetch models in background so they're cached by the time
        # the user clicks the header popup.
        if provider:
            cli_manager.prefetch_models(provider)

    def _clear_resume_flag(self) -> bool:
        """One-shot timeout: resume succeeded if the process is still alive."""
        self._resume_attempted = False
        return False

    def _on_child_exited(self, terminal, status) -> None:
        """Handle CLI exit — detect resume failure and retry fresh."""
        # Stop spinner and idle poll — the CLI is gone.
        if self._waiting_for_response:
            self._waiting_for_response = False
            self._stop_idle_poll()
            if callable(self.on_processing_changed):
                self.on_processing_changed(False)

        if self._shutting_down:
            return
        if self._resume_attempted:
            # Process exited quickly after --resume → session was stale
            self._resume_attempted = False
            self._session_id = None
            self.terminal.reset(True, True)
            GLib.timeout_add(300, lambda: self.spawn_shell(resume=False) or False)
            return
        # Normal exit — respawn fresh
        GLib.timeout_add(100, lambda: self.spawn_shell() or False)

    # ------------------------------------------------------------------
    # Header interaction
    # ------------------------------------------------------------------

    def _on_header_click(self, _button) -> None:
        """Show a popup to select the AI CLI provider."""
        availability = cli_manager.availability()
        labels = cli_manager.labels()
        current = self._current_provider or get_setting("ai.provider", "")

        items: list[dict] = []
        for pid in cli_manager.provider_ids:
            name = labels[pid]
            installed = availability[pid]
            check = "✓ " if pid == current else "  "
            suffix = "" if installed else "  ⚠ not installed"
            items.append({"label": f"{check}{name}{suffix}", "action": pid, "enabled": True})

        parent = self.get_root()
        if parent:
            from popups.nvim_context_menu import show_context_menu

            show_context_menu(parent, items, self._on_cli_selected, title="Select AI")

    def _on_cli_selected(self, provider: str) -> None:
        """Switch this tab's provider and restart the terminal.

        If the selected CLI is not installed, print install instructions instead.
        """
        if not cli_manager.find_binary(provider):
            self._show_install_hint(provider)
            return

        if provider == self._current_provider:
            return
        self._current_provider = provider
        self._current_model = None  # new provider → reset model to default
        self._session_id = None  # new provider → new session
        self._restart_cli()

    def _on_model_selected(self, model: str) -> None:
        """Switch this tab's model and restart the terminal."""
        current = self._current_model
        if not current:
            model_setting = get_setting("ai.model", "")
            if isinstance(model_setting, dict):
                current = model_setting.get(self._current_provider, "")
            else:
                current = model_setting or ""
        if model == current:
            return
        self._current_model = model
        set_setting("ai.model", model, persist=True)
        self._session_id = None  # new model → new session
        self._restart_cli()

    def _restart_cli(self) -> None:
        """Kill the running CLI and respawn with the newly selected one."""
        self.stop_shell()
        self.terminal.reset(True, True)
        self._title_inferred = False
        self._waiting_for_response = False
        self._commit_ready = False
        self._in_escape_seq = False
        self._in_osc_seq = False
        self._stop_idle_poll()
        self._hide_virtual_scrollbar_immediately()
        self._input_buf.clear()
        if callable(self.on_processing_changed):
            self.on_processing_changed(False)
        if not self._commit_handler_id:
            self._commit_handler_id = self.terminal.connect("commit", self._on_vte_commit)
        GLib.timeout_add(200, lambda: self.spawn_shell() or False)

    def _update_header_label(self) -> None:
        labels = cli_manager.labels()
        label = labels.get(self._current_provider or "", "AI")
        self._ai_header.set_label(label)
        if callable(getattr(self, "on_provider_changed", None)):
            self.on_provider_changed(label)

    # ------------------------------------------------------------------
    # Session management (delegated to CLI providers)
    # ------------------------------------------------------------------

    def validate_session_id(self) -> None:
        """Check that _session_id exists on disk; clear if stale."""
        if not self._session_id or not self._current_provider:
            return
        p = cli_manager.get(self._current_provider)
        if not p or not p.session_exists(self._session_id, cwd=self.cwd):
            self._session_id = None

    def _list_sessions(self) -> set[str]:
        """Return the set of session IDs currently on disk for the active provider."""
        p = cli_manager.get(self._current_provider) if self._current_provider else None
        return p.list_sessions(cwd=self.cwd) if p else set()

    def _sessions_dir(self):
        """Return the sessions directory path for the active provider."""
        p = cli_manager.get(self._current_provider) if self._current_provider else None
        return p.sessions_dir(cwd=self.cwd) if p else None

    def _detect_session_id(self, claimed_ids: set[str] | None = None) -> bool:
        """Detect the session ID created by the just-spawned CLI.

        *claimed_ids*, when provided, contains session IDs already owned by
        other tabs and must be excluded from detection.
        """
        pre = getattr(self, "_pre_spawn_sessions", None) or set()
        current = self._list_sessions()
        new_sessions = current - pre
        if claimed_ids:
            new_sessions -= claimed_ids

        p = cli_manager.get(self._current_provider) if self._current_provider else None
        sessions_dir = p.sessions_dir(cwd=self.cwd) if p else None

        if len(new_sessions) == 1:
            self._session_id = new_sessions.pop()
        elif len(new_sessions) > 1 and sessions_dir:
            # Multiple new sessions (unlikely) — pick the most recent
            best, best_mtime = None, 0.0
            for sid in new_sessions:
                try:
                    # Try both file patterns (file vs directory)
                    candidate = sessions_dir / sid
                    if not candidate.exists():
                        candidate = sessions_dir / f"{sid}.jsonl"
                    mt = candidate.stat().st_mtime
                    if mt > best_mtime:
                        best, best_mtime = sid, mt
                except OSError:
                    pass
            if best:
                self._session_id = best
        elif not new_sessions and not self._session_id and sessions_dir:
            # --continue was used and no new file appeared — the CLI reused
            # the most recent session.  Find it by modification time.
            excluded = claimed_ids or set()
            try:
                entries = list(sessions_dir.iterdir())
                if entries:
                    # Sort by mtime descending; pick the first unclaimed entry
                    entries.sort(key=lambda f: f.stat().st_mtime, reverse=True)
                    for entry in entries:
                        sid = entry.stem if entry.suffix else entry.name
                        if sid not in excluded:
                            self._session_id = sid
                            break
            except (ValueError, OSError):
                pass
        self._pre_spawn_sessions = None  # cleanup
        return False  # one-shot GLib timeout
