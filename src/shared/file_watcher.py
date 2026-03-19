"""
File system watcher for Zen IDE (GTK4 version).

Uses watchfiles (Rust-based) for efficient file change detection.
Notifies the IDE when files change in workspace folders, triggering:
- Tree view refresh
- Git status refresh
- Editor notification for externally modified files
"""

import os
import threading
from typing import Callable, Optional, Set

try:
    import watchfiles
    from watchfiles import Change, DefaultFilter

    WATCHFILES_AVAILABLE = True
except ImportError:
    WATCHFILES_AVAILABLE = False
    Change = None  # type: ignore
    DefaultFilter = object  # type: ignore


class GitAwareFilter(DefaultFilter):
    """Custom filter that watches .git directory for commit detection.

    Extends DefaultFilter but removes .git from ignored directories so we can
    detect commits and other git operations that should trigger a status refresh.
    """

    # Override the default ignored directories - remove .git so we can detect commits
    ignore_dirs = frozenset(
        {
            "__pycache__",
            "node_modules",
            ".pytest_cache",
            ".hypothesis",
            ".mypy_cache",
            ".svn",
            ".tox",
            ".hg",
            ".idea",
            ".venv",
        }
    )

    def __init__(self):
        if WATCHFILES_AVAILABLE:
            # Call parent with our custom ignore_dirs (without .git)
            super().__init__(ignore_dirs=self.ignore_dirs)


class FileWatcher:
    """Watches workspace folders for file system changes using watchfiles.

    Features:
    - Debounced refresh (1 second window)
    - Separate tracking for tree refresh vs git refresh
    - Filters out noise (.git internals, __pycache__, etc.)
    - Thread-safe callback invocation via main-thread polling
    """

    DEBOUNCE_DELAY_MS = 1000  # 1 second debounce window

    def __init__(
        self,
        on_tree_refresh: Optional[Callable[[], None]] = None,
        on_git_refresh: Optional[Callable[[bool], None]] = None,
        on_file_modified: Optional[Callable[[str], None]] = None,
        on_file_updated: Optional[Callable[[str], None]] = None,
    ):
        """Initialize the file watcher.

        Args:
            on_tree_refresh: Callback when tree view needs full refresh (file/folder added/deleted)
            on_git_refresh: Callback when git status needs refresh (bool: force_refresh)
            on_file_modified: Callback when a specific file is modified externally (file_path)
            on_file_updated: Callback for targeted update when a file is modified (no full refresh needed)
        """
        self.on_tree_refresh = on_tree_refresh
        self.on_git_refresh = on_git_refresh
        self.on_file_modified = on_file_modified
        self.on_file_updated = on_file_updated

        self._workspace_folders: list[str] = []
        self._watcher_thread: Optional[threading.Thread] = None
        self._watcher_stop_event: Optional[threading.Event] = None

        # Debouncing state (protected by _lock for thread-safe access)
        self._lock = threading.Lock()
        self._needs_tree_refresh = False
        self._needs_git_refresh = False
        self._git_refresh_force = False
        self._pending_refresh_source: Optional[int] = None
        self._modified_files: Set[str] = set()
        self._updated_files: Set[str] = set()
        self._stopped = False

    def start(self, workspace_folders: list[str]) -> None:
        """Start watching the given workspace folders.

        Args:
            workspace_folders: List of absolute paths to watch
        """
        if not WATCHFILES_AVAILABLE:
            return

        self.stop()

        self._workspace_folders = workspace_folders
        if not workspace_folders:
            return

        # Filter to existing directories
        paths_to_watch = [p for p in workspace_folders if os.path.isdir(p)]
        if not paths_to_watch:
            return

        with self._lock:
            self._stopped = False

        self._watcher_stop_event = threading.Event()
        self._watcher_thread = threading.Thread(
            target=self._watch_thread,
            args=(paths_to_watch,),
            daemon=True,
        )
        self._watcher_thread.start()

    def stop(self) -> None:
        """Stop watching for file changes."""
        with self._lock:
            self._stopped = True
            self._needs_tree_refresh = False
            self._needs_git_refresh = False
            self._git_refresh_force = False
            self._modified_files.clear()
            self._updated_files.clear()

        if self._watcher_stop_event:
            self._watcher_stop_event.set()

        if self._watcher_thread:
            self._watcher_thread.join(timeout=1.0)
            self._watcher_thread = None

        self._watcher_stop_event = None

        # Cancel pending debounce timer
        try:
            from gi.repository import GLib

            if self._pending_refresh_source:
                GLib.source_remove(self._pending_refresh_source)
        except Exception:
            pass
        self._pending_refresh_source = None

    def _watch_thread(self, paths_to_watch: list[str]) -> None:
        """Background thread running watchfiles."""
        try:
            # Use GitAwareFilter to detect .git changes (commits, checkouts, etc.)
            git_filter = GitAwareFilter()
            for changes in watchfiles.watch(
                *paths_to_watch,
                watch_filter=git_filter,
                stop_event=self._watcher_stop_event,
            ):
                if self._watcher_stop_event.is_set():
                    break

                needs_refresh = False
                for change_type, path in changes:
                    if self._process_change(change_type, str(path)):
                        needs_refresh = True

                # Signal the main-thread poll that changes are pending.
                if needs_refresh:
                    self._trigger_debounced_refresh()

        except Exception:
            pass

    def _process_change(self, change_type, path: str) -> bool:
        """Process a single file change event.

        Returns True if a debounced refresh should be scheduled.
        """
        basename = os.path.basename(path)

        # Check for .git changes - triggers git refresh but not tree refresh
        if "/.git/" in path or path.endswith("/.git"):
            # Skip transient lock files
            if path.endswith(".lock"):
                return False
            with self._lock:
                self._needs_git_refresh = True
                self._git_refresh_force = True
            return True

        # Filter out noise files
        if basename.startswith(".") or basename.endswith((".pyc", ".pyo", ".swp", ".tmp", "~")):
            return False

        # Filter out __pycache__ and similar directories
        if "/__pycache__/" in path or "/node_modules/" in path or "/.venv/" in path:
            return False

        # Determine if this needs full tree refresh or just targeted update
        with self._lock:
            self._modified_files.add(path)

            if WATCHFILES_AVAILABLE and Change is not None:
                if change_type == Change.modified:
                    self._updated_files.add(path)
                    self._needs_git_refresh = True
                    self._git_refresh_force = True
                else:
                    self._needs_tree_refresh = True
                    self._needs_git_refresh = True
                    self._git_refresh_force = True
            else:
                self._needs_tree_refresh = True
                self._needs_git_refresh = True
                self._git_refresh_force = True

        return True

    def _trigger_debounced_refresh(self) -> None:
        """Signal that a debounced refresh is needed (thread-safe).

        Uses main_thread_call to safely schedule the debounce on the GTK
        main thread without touching GLib from the background thread.
        """
        with self._lock:
            if self._stopped:
                return
        from shared.main_thread import main_thread_call

        main_thread_call(self._schedule_debounced_refresh)

    def _schedule_debounced_refresh(self) -> None:
        """Schedule a debounced refresh on the main thread.

        Uses 'coalescing' debounce: if a refresh is already scheduled,
        just let it run. This ensures the refresh happens within debounce_delay
        of the FIRST event, not keeps getting delayed by subsequent events.
        """
        from gi.repository import GLib

        # If a refresh is already pending, don't reschedule
        if self._pending_refresh_source:
            return

        # Schedule refresh after debounce delay
        self._pending_refresh_source = GLib.timeout_add(self.DEBOUNCE_DELAY_MS, self._execute_refresh)

    def _execute_refresh(self) -> bool:
        """Execute the actual refresh callbacks (runs on main thread after debounce)."""
        self._pending_refresh_source = None

        # Snapshot and reset state under lock for thread-safety
        with self._lock:
            needs_tree = self._needs_tree_refresh
            needs_git = self._needs_git_refresh
            git_force = self._git_refresh_force
            self._needs_tree_refresh = False
            self._needs_git_refresh = False
            self._git_refresh_force = False

        # Tree refresh (only for added/deleted files - structure changed)
        if needs_tree and self.on_tree_refresh:
            # Clear updated files since full refresh will redraw everything
            with self._lock:
                self._updated_files.clear()
            try:
                self.on_tree_refresh()
            except Exception:
                pass
        else:
            # No full refresh needed - do targeted updates for modified files
            with self._lock:
                updated = list(self._updated_files)
                self._updated_files.clear()
            if updated and self.on_file_updated:
                for file_path in updated:
                    try:
                        self.on_file_updated(file_path)
                    except Exception:
                        pass

        # Git refresh
        if needs_git and self.on_git_refresh:
            try:
                self.on_git_refresh(git_force)
            except Exception:
                pass

        # Notify about modified files (for editor reload prompt)
        with self._lock:
            modified = list(self._modified_files)
            self._modified_files.clear()
        if modified and self.on_file_modified:
            for file_path in modified:
                try:
                    self.on_file_modified(file_path)
                except Exception:
                    pass

        return False  # Don't repeat


# Singleton instance
_watcher: Optional[FileWatcher] = None


def get_file_watcher() -> FileWatcher:
    """Get the singleton file watcher instance."""
    global _watcher
    if _watcher is None:
        _watcher = FileWatcher()
    return _watcher


def start_file_watcher(
    workspace_folders: list[str],
    on_tree_refresh: Optional[Callable[[], None]] = None,
    on_git_refresh: Optional[Callable[[bool], None]] = None,
    on_file_modified: Optional[Callable[[str], None]] = None,
    on_file_updated: Optional[Callable[[str], None]] = None,
) -> FileWatcher:
    """Start watching workspace folders for file changes.

    Args:
        workspace_folders: List of absolute paths to watch
        on_tree_refresh: Callback when tree view needs full refresh (file/folder added/deleted)
        on_git_refresh: Callback when git status needs refresh (bool: force_refresh)
        on_file_modified: Callback when a specific file is modified externally (for editor reload)
        on_file_updated: Callback for targeted tree row update when file modified (no full refresh)

    Returns:
        The FileWatcher instance
    """
    watcher = get_file_watcher()
    watcher.on_tree_refresh = on_tree_refresh
    watcher.on_git_refresh = on_git_refresh
    watcher.on_file_modified = on_file_modified
    watcher.on_file_updated = on_file_updated
    watcher.start(workspace_folders)
    return watcher


def stop_file_watcher() -> None:
    """Stop the file watcher."""
    watcher = get_file_watcher()
    watcher.stop()
