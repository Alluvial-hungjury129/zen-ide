"""AI Session Persistence mixin — session save/restore/detection for AITerminalStack."""

import os

from gi.repository import GLib


def _session_mtime(sessions_dir, sid: str) -> float:
    """Return the mtime of a session JSONL file, or 0 on error."""
    try:
        return os.path.getmtime(os.path.join(str(sessions_dir), f"{sid}.jsonl"))
    except OSError:
        return 0.0


def _session_mtime_dir(sessions_dir, sid: str) -> float:
    """Return the mtime of a session directory, or 0 on error."""
    try:
        return os.path.getmtime(os.path.join(str(sessions_dir), sid))
    except OSError:
        return 0.0


class AISessionPersistenceMixin:
    """Mixin providing session persistence, spawn orchestration, and session detection.

    Expects the host class to define:
        _views, _tab_buttons, _active_idx, _saved_tabs, _vertical_mode,
        _content_stack, _add_view, _switch_to_tab, _persist_tabs,
        _get_workspace_folders, _get_editor_context
    """

    def _persist_tabs(self) -> None:
        """Save current tab state to settings so closed tabs stay closed on restart."""
        from shared.settings import set_setting

        set_setting("workspace.ai_tabs", self.save_state(), persist=True)

    def save_state(self) -> list[dict]:
        """Return a serialisable list describing every open tab.

        The first entry carries the ``active_idx`` key so the caller only
        needs to persist a single list.  Each entry includes the Claude
        session ID (if any) so tabs can resume their individual sessions.
        """
        seen_ids: set[str] = set()
        tabs: list[dict] = []
        items = enumerate(self._tab_buttons) if not self._vertical_mode else enumerate(self._views)
        for i, item in items:
            if self._vertical_mode:
                view = item
                title = view._ai_header.title_label.get_label() or f"Chat {i + 1}"
                entry: dict = {"title": title}
            else:
                entry = {"title": item.get_title()}
            if i == 0:
                entry["active_idx"] = self._active_idx
            if True:
                view = self._views[i] if not self._vertical_mode else item
                # Persist per-tab provider
                if view._current_provider:
                    entry["provider"] = view._current_provider
                # Persist per-tab model
                if view._current_model:
                    entry["model"] = view._current_model
                # Persist per-tab session ID for individual session resume
                # Validate session exists before saving
                if hasattr(view, "validate_session_id"):
                    view.validate_session_id()
                sid = getattr(view, "_session_id", None)
                # Last-resort detection: if this view had a conversation
                # (title was inferred) but session ID is missing, try to find it
                # by picking the most recent unclaimed session.
                if not sid and getattr(view, "_title_inferred", False):
                    sid = self._detect_session_for_save(view, seen_ids)
                # Skip duplicate session IDs — each tab must have its own
                if sid and sid not in seen_ids:
                    entry["session_id"] = sid
                    seen_ids.add(sid)
            tabs.append(entry)
        return tabs

    def _detect_session_for_save(self, view, claimed_ids: set[str]) -> str | None:
        """Try to find the session ID for a view that lost it.

        Picks the most recently modified session not claimed by another tab.
        """
        all_claimed = claimed_ids | {v._session_id for v in self._views if v._session_id and v is not view}

        if view._current_provider == "copilot_cli":
            d = view._sessions_dir()
            if not d:
                return None
            try:
                candidates = sorted(
                    (p for p in d.iterdir() if p.is_dir()),
                    key=lambda p: p.stat().st_mtime,
                    reverse=True,
                )
            except OSError:
                return None
            for p in candidates:
                sid = p.name
                if sid in all_claimed:
                    continue
                # Check it has an events file (valid session)
                if (p / "events.jsonl").exists():
                    return sid
            return None

        # Claude
        d = view._sessions_dir()
        if not d:
            return None
        try:
            candidates = sorted(d.glob("*.jsonl"), key=lambda f: f.stat().st_mtime, reverse=True)
        except OSError:
            return None
        for f in candidates:
            sid = f.stem
            if sid in all_claimed:
                continue
            # Quick check: is this a conversation session (has user message)?
            try:
                with open(f) as fh:
                    for i, line in enumerate(fh):
                        if i >= 5:
                            break
                        if '"human"' in line or '"user"' in line:
                            return sid
            except OSError:
                continue
        return None

    def focus_session(self, session_id: str) -> None:
        """Focus the AI tab with the given session ID, or create one that resumes it."""
        # First, look for an existing tab with this session ID
        for i, view in enumerate(self._views):
            if getattr(view, "_session_id", None) == session_id:
                self._switch_to_tab(i)
                return

        # No existing tab — create a new one and resume the session
        prev_provider = self._views[self._active_idx]._current_provider if self._views else None
        prev_model = self._views[self._active_idx]._current_model if self._views else None
        view = self._add_view()
        if prev_provider:
            view._current_provider = prev_provider
        if prev_model:
            view._current_model = prev_model
        if self._views and len(self._views) > 1:
            view.cwd = self._views[0].cwd
        view._session_id = session_id
        view._title_inferred = True  # it's a resumed session
        view.spawn_shell(resume=True)
        self._persist_tabs()

    def _is_claude_view(self, view) -> bool:
        """Check if a view is (or will be) running Claude CLI."""
        if view._current_provider:
            return view._current_provider == "claude_cli"
        # No per-tab provider set — will resolve from global setting
        from shared.settings import get_setting

        return get_setting("ai.provider", "") != "copilot_cli"

    def _is_copilot_view(self, view) -> bool:
        """Check if a view is (or will be) running Copilot CLI."""
        if view._current_provider:
            return view._current_provider == "copilot_cli"
        from shared.settings import get_setting

        return get_setting("ai.provider", "") == "copilot_cli"

    def spawn_shell(self) -> None:
        resume = bool(self._saved_tabs)

        # Identify views that need session ID detection (no saved ID)
        claude_detect: list = []
        copilot_detect: list = []

        for view in self._views:
            if not getattr(view, "_session_id", None) or not resume:
                if self._is_claude_view(view):
                    if not resume or not getattr(view, "_session_id", None):
                        view._stack_detects = True
                        claude_detect.append(view)
                elif self._is_copilot_view(view):
                    if not resume or not getattr(view, "_session_id", None):
                        view._stack_detects = True
                        copilot_detect.append(view)

        # Snapshot existing sessions BEFORE any spawning
        pre_claude = claude_detect[0]._list_sessions() if claude_detect else set()
        pre_copilot = copilot_detect[0]._list_sessions() if copilot_detect else set()

        # Now spawn all views
        if resume:
            used_continue = False
            # Collect all saved session IDs so the --continue fallback
            # can avoid picking a session that another tab already owns.
            claimed_ids = {v._session_id for v in self._views if v._session_id}
            for view in self._views:
                has_session = bool(getattr(view, "_session_id", None))
                if has_session:
                    # Has a saved session ID — resume it directly.
                    view.spawn_shell(resume=True)
                elif not used_continue and getattr(view, "_title_inferred", False):
                    # No session ID but had a conversation — use --continue
                    # for AT MOST one tab to avoid multiple tabs resuming the
                    # same (most recent) session.
                    view.spawn_shell(resume=True)
                    used_continue = True
                else:
                    # No session to resume — start fresh.
                    view.spawn_shell(resume=False)
        else:
            for view in self._views:
                view.spawn_shell(resume=False)

        # Coordinated session detection: assign new sessions to tabs
        # by creation time after all have started.
        if claude_detect:
            self._pending_detect_claude = (claude_detect, pre_claude)
            GLib.timeout_add(4000, self._detect_sessions_claude)
        if copilot_detect:
            self._pending_detect_copilot = (copilot_detect, pre_copilot)
            GLib.timeout_add(4000, self._detect_sessions_copilot)

        self._saved_tabs = None  # consumed

    def _detect_sessions_claude(self) -> bool:
        """Assign new Claude session IDs to tabs, sorted by file mtime."""
        pending = getattr(self, "_pending_detect_claude", None)
        if not pending:
            return False
        views, pre_sessions = pending
        self._pending_detect_claude = None
        self._detect_sessions_generic(views, pre_sessions, is_copilot=False)
        self._persist_tabs()
        return False

    def _detect_sessions_copilot(self) -> bool:
        """Assign new Copilot session IDs to tabs, sorted by dir mtime."""
        pending = getattr(self, "_pending_detect_copilot", None)
        if not pending:
            return False
        views, pre_sessions = pending
        self._pending_detect_copilot = None
        self._detect_sessions_generic(views, pre_sessions, is_copilot=True)
        self._persist_tabs()
        return False

    def _detect_sessions_generic(self, views: list, pre_sessions: set, *, is_copilot: bool) -> None:
        """Assign new session IDs to tabs, one per tab, sorted by mtime."""
        if not views:
            return

        # Get current sessions and find new ones
        current = views[0]._list_sessions()
        new_ids = current - pre_sessions
        # Exclude IDs already claimed by other (resumed) tabs
        claimed = {v._session_id for v in self._views if v._session_id and v not in views}
        new_ids -= claimed

        if not new_ids:
            # Fallback: each view detects on its own (single tab --continue case)
            # Pass claimed IDs so views don't pick sessions owned by other tabs.
            for v in views:
                v._stack_detects = False
                v._pre_spawn_sessions = pre_sessions
                v._detect_session_id(claimed_ids=claimed)
                # Add newly detected ID to claimed set for next iteration
                if v._session_id:
                    claimed.add(v._session_id)
            return

        # Sort new sessions by mtime (oldest first = first tab spawned)
        if is_copilot:
            d = views[0]._sessions_dir()
            if not d:
                return
            sorted_ids = sorted(new_ids, key=lambda sid: _session_mtime_dir(d, sid))
        else:
            d = views[0]._sessions_dir()
            if not d:
                return
            sorted_ids = sorted(new_ids, key=lambda sid: _session_mtime(d, sid))

        # Assign one session per tab in spawn order
        for i, view in enumerate(views):
            if i < len(sorted_ids):
                view._session_id = sorted_ids[i]
            view._stack_detects = False
