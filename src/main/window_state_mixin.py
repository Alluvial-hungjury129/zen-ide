"""Window state mixin — deferred initialization, state save/restore, close handling."""

import os
import sys
import time

from gi.repository import GLib

from main.startup_optimizer_mixin import StartupOptimizerMixin
from main.window_persistence_mixin import WindowPersistenceMixin


class WindowStateMixin(StartupOptimizerMixin, WindowPersistenceMixin):
    """Mixin: deferred init, state persistence, window close handling."""

    def _on_window_mapped(self, widget):
        """Called when window is mapped — build visible UI synchronously.

        Only VISIBLE work runs here: EditorView, startup-critical CSS,
        TreeView, and workspace load.  INVISIBLE work (actions, shortcuts,
        focus controllers) is deferred to _deferred_init_panels — the user
        cannot interact within the first ~130ms anyway.
        Eliminates GLib transition overhead (~44ms) by keeping all visible
        work in one synchronous batch.
        """
        if self._layout_ready:
            return
        elapsed = time.monotonic() - self._startup_time
        print(f"\033[36m⚡ [ZEN] First paint: {elapsed:.3f}s\033[0m")
        self._layout_ready = True

        # Swap stub titlebar for real HeaderBar (~2ms on already-realized window).
        # Must happen before any code references self._header.
        self._ensure_header_bar()

        # Create EditorView (minimal for user interaction)
        self._deferred_init_editor()

        # Register bundled fonts and apply startup-critical CSS only.
        # Full CSS is applied in _deferred_init_panels.
        from fonts import register_resource_fonts, subscribe_font_change

        register_resource_fonts()
        self._apply_startup_theme()
        subscribe_font_change(lambda comp, _s: self._apply_theme() if comp in ("editor", "terminal") else None)

        # Create real TreeView (replaces placeholder — import preloaded in do_activate)
        from constants import DEFAULT_TREE_MIN_WIDTH
        from treeview import TreeView

        self.tree_view = TreeView()
        self.tree_view.set_size_request(DEFAULT_TREE_MIN_WIDTH, -1)
        self.tree_view.add_css_class("sidebar")
        self.tree_view.on_file_selected = self._on_tree_file_selected
        self.main_paned.set_start_child(self.tree_view)
        self._reapply_saved_positions()

        elapsed = time.monotonic() - self._startup_time
        print(f"\033[33m⚡ [ZEN] Fully loaded: {elapsed:.3f}s\033[0m")

        # --- Workspace load (visible: populates tree + sets title) ---
        self._init_workspace_and_files()

        elapsed = time.monotonic() - self._startup_time
        print(f"\033[34m⚡ [ZEN] Full UI visible: {elapsed:.3f}s\033[0m")

        # Auto-quit for startup benchmark mode
        if os.environ.get("ZEN_STARTUP_BENCH"):
            GLib.timeout_add(500, lambda: self.get_application().quit() or False)

        # Bring app to foreground
        self._activate_foreground()

        # Schedule deferred work: actions, shortcuts, focus, bottom panels
        GLib.timeout_add(0, self._deferred_init_panels)

    def _activate_foreground(self):
        """Bring app to foreground at first paint — cross-platform.

        macOS: uses PyObjC AppKit (preloaded in background thread at module
        import time, so it's already cached by first paint).
        Also closes the native Cocoa splash window shown by the runtime hook.
        Linux: re-present via GTK4.
        """
        self.present()
        if sys.platform == "darwin":
            self._close_cocoa_splash()
            self._activate_macos_foreground()

    def _activate_macos_foreground(self):
        """Activate macOS foreground using preloaded AppKit.

        Uses NSApp.activate() (modern API, macOS 14+) with fallback to
        activateIgnoringOtherApps_ for older versions. Defers activation
        to an idle callback so GTK has finished processing the window map.
        """
        import zen_ide_window

        ready = zen_ide_window._macos_appkit_loaded
        if not ready:
            return

        if ready.is_set():
            self._do_macos_activate()
        else:
            # AppKit still loading (unlikely) — poll until ready
            def _check():
                if ready.is_set():
                    self._do_macos_activate()
                    self.present()
                    return False
                return True

            GLib.timeout_add(5, _check)

    @staticmethod
    def _close_cocoa_splash():
        """Close the native Cocoa splash window shown by the runtime hook."""
        try:
            import builtins

            splash = getattr(builtins, "_zen_splash_window", None)
            if splash:
                splash.orderOut_(None)
                splash.close()
                builtins._zen_splash_window = None
        except Exception:
            pass

    @staticmethod
    def _do_macos_activate():
        """Activate macOS foreground via AppKit (must be on main thread).

        Tries modern NSApp.activate() first (macOS 14+), falls back to
        deprecated activateIgnoringOtherApps_ for older versions.
        """
        try:
            from AppKit import NSApplication

            ns_app = NSApplication.sharedApplication()
            try:
                ns_app.activate()
            except (AttributeError, TypeError):
                ns_app.activateIgnoringOtherApps_(True)
        except ImportError:
            pass
        except Exception:
            pass
        return False  # For GLib.idle_add

    # ------------------------------------------------------------------
    # IDE editor context for AI terminals
    # ------------------------------------------------------------------

    def _get_editor_context(self) -> dict:
        """Return a dict describing the current editor state.

        Called by ``AITerminalView`` at spawn time (for env vars / system
        prompt) and by the dynamic state-file writer on tab switch events.

        Uses the fast path (no git subprocess calls) to avoid blocking the
        main thread.  Git branch info is populated from the cache maintained
        by ``_update_ide_state_file`` and is available after the first
        background refresh completes.
        """
        ctx = self._get_editor_context_fast()

        # Populate git branch info from the git manager's cache without
        # spawning new subprocesses.  get_repo_root / get_current_branch
        # return cached values when available; skip if the cache is cold
        # to avoid blocking the UI with ~1s of subprocess calls on large
        # multi-repo workspaces.
        git_branch = ""
        git_branches: dict[str, str] = {}
        try:
            from shared.git_manager import get_git_manager

            git = get_git_manager()
            workspace_folders = ctx.get("workspace_folders", [])
            active_file = ctx.get("active_file", "")

            seen_roots: set[str] = set()
            targets = list(workspace_folders)
            if active_file:
                targets.insert(0, active_file)
            for target in targets:
                repo_root = git.get_repo_root_cached(target)
                if repo_root and repo_root not in seen_roots:
                    seen_roots.add(repo_root)
                    branch = git.get_current_branch_cached(repo_root) or ""
                    if branch:
                        git_branches[os.path.basename(repo_root)] = branch

            target = active_file or (workspace_folders[0] if workspace_folders else "")
            if target:
                git_branch = git.get_current_branch_cached(target) or ""
        except Exception:
            pass

        ctx["git_branch"] = git_branch
        ctx["git_branches"] = git_branches
        return ctx

    def _update_ide_state_file(self) -> None:
        """Debounced update of ``~/.zen_ide/ide_state.json``.

        Git queries run in a background thread to avoid blocking the UI.
        Multiple calls within 200 ms are coalesced into a single write.
        """
        debouncer = getattr(self, "_ide_state_debouncer", None)
        if debouncer is None:
            from shared.debouncer import Debouncer

            debouncer = Debouncer(200, self._do_update_ide_state)
            self._ide_state_debouncer = debouncer
        debouncer()

    def _do_update_ide_state(self) -> None:
        """Actually collect context and write ide_state.json in a thread."""

        import threading

        from shared.ide_state_writer import write_ide_state

        ctx = self._get_editor_context_fast()

        def _bg():
            # Expensive git queries happen off the main thread.
            git_branch, git_branches = self._collect_git_branches()
            ctx["git_branch"] = git_branch
            ctx["git_branches"] = git_branches
            write_ide_state(**ctx)

        threading.Thread(target=_bg, daemon=True).start()

    def _get_editor_context_fast(self) -> dict:
        """Collect editor context *without* git queries (main-thread safe)."""
        active_file = ""
        open_files: list[str] = []
        workspace_folders: list[str] = []
        workspace_file = ""

        try:
            active_file = self.editor_view.get_current_file_path() or ""
        except Exception:
            pass
        try:
            for tab in self.editor_view.tabs.values():
                if tab.file_path:
                    open_files.append(tab.file_path)
        except Exception:
            pass
        try:
            workspace_folders = list(self.tree_view.get_workspace_folders() or [])
        except Exception:
            pass
        try:
            from shared.settings import get_setting

            workspace_file = get_setting("workspace.workspace_file", "") or ""
        except Exception:
            pass

        return {
            "active_file": active_file,
            "open_files": open_files,
            "workspace_folders": workspace_folders,
            "workspace_file": workspace_file,
            "git_branch": "",
            "git_branches": {},
        }

    def _collect_git_branches(self) -> tuple[str, dict[str, str]]:
        """Collect git branch info for all workspace repos (thread-safe)."""
        git_branch = ""
        git_branches: dict[str, str] = {}
        try:
            from shared.git_manager import get_git_manager

            git = get_git_manager()
            workspace_folders = list(self.tree_view.get_workspace_folders() or [])
            active_file = ""
            try:
                active_file = self.editor_view.get_current_file_path() or ""
            except Exception:
                pass

            seen_roots: set[str] = set()
            targets = list(workspace_folders)
            if active_file:
                targets.insert(0, active_file)
            for target in targets:
                repo_root = git.get_repo_root(target)
                if repo_root and repo_root not in seen_roots:
                    seen_roots.add(repo_root)
                    branch = git.get_current_branch(repo_root) or ""
                    if branch:
                        git_branches[os.path.basename(repo_root)] = branch

            target = active_file or (workspace_folders[0] if workspace_folders else "")
            if target:
                git_branch = git.get_current_branch(target) or ""
        except Exception:
            pass
        return git_branch, git_branches
