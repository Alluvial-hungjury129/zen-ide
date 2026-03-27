"""
Search engine module for global search — ripgrep, git grep, and grep integration.

Extracted from global_search_dialog.py — contains SearchResult, search backends,
and SearchEngineMixin for use by GlobalSearchDialog.
"""

import fnmatch
import os
import subprocess

from shared.git_ignore_utils import collect_global_patterns, get_global_patterns

# Binary file extensions to skip
BINARY_EXTENSIONS = frozenset(
    {
        ".pyc",
        ".pyo",
        ".so",
        ".dll",
        ".dylib",
        ".exe",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".bmp",
        ".ico",
        ".svg",
        ".webp",
        ".pdf",
        ".doc",
        ".docx",
        ".xls",
        ".xlsx",
        ".ppt",
        ".pptx",
        ".zip",
        ".tar",
        ".gz",
        ".bz2",
        ".xz",
        ".7z",
        ".rar",
        ".mp3",
        ".mp4",
        ".wav",
        ".avi",
        ".mov",
        ".mkv",
        ".ttf",
        ".otf",
        ".woff",
        ".woff2",
        ".eot",
        ".db",
        ".sqlite",
        ".sqlite3",
        ".class",
        ".jar",
        ".war",
        ".o",
        ".a",
        ".lib",
    }
)


class SearchResult:
    """Represents a single search result."""

    def __init__(self, file_path: str, line_number: int, line_text: str, match_start: int, match_end: int):
        self.file_path = file_path
        self.line_number = line_number
        self.line_text = line_text.strip()
        self.match_start = match_start
        self.match_end = match_end


class SearchEngineMixin:
    """Mixin providing search backend methods for GlobalSearchDialog.

    Expects the host class to have:
        - self.workspace_folders: list[str]
        - self.case_sensitive: Gtk.CheckButton (with .get_active())
        - self._get_search_folders() -> list[str]
    """

    def _should_skip_path(self, rel_path: str) -> bool:
        """Check if a path should be excluded from search results."""
        global_patterns = get_global_patterns()
        parts = rel_path.replace("\\", "/").split("/")
        for part in parts:
            if part in global_patterns:
                return True
            # Check glob patterns (e.g., *.pyc, *.egg-info)
            for pattern in global_patterns:
                if "*" in pattern and fnmatch.fnmatch(part, pattern):
                    return True
        # Check file extension for binary files
        ext = os.path.splitext(rel_path)[1].lower()
        if ext in BINARY_EXTENSIONS:
            return True
        return False

    def _search_worker(self, query: str):
        """Search worker running in background thread."""
        from shared.main_thread import main_thread_call

        results = []
        case_flag = [] if self.case_sensitive.get_active() else ["-i"]

        search_folders = self._get_search_folders()

        # Ensure global patterns are collected
        collect_global_patterns(self.workspace_folders)

        for folder in search_folders:
            if not os.path.isdir(folder):
                continue

            is_git_repo = os.path.isdir(os.path.join(folder, ".git"))
            search_results = None

            if is_git_repo:
                search_results = self._git_grep_search(folder, query, case_flag)

            if search_results is None:
                # Fallback to ripgrep or grep
                search_results = self._ripgrep_search(folder, query, case_flag)

            if search_results is None:
                search_results = self._grep_search(folder, query, case_flag)

            if search_results:
                for file_path, line_num, line_text, match_start, match_end in search_results:
                    results.append(SearchResult(file_path, line_num, line_text, match_start, match_end))
                    if len(results) >= 500:
                        break

            if len(results) >= 500:
                break

        # Update UI on main thread
        main_thread_call(self._update_results, results)

    def _git_grep_search(self, folder: str, query: str, case_flag: list) -> list | None:
        """Search using git grep (respects .gitignore, only tracked files)."""
        try:
            result = subprocess.run(
                ["git", "grep", "-n", "--no-color", "-I", "-F"] + case_flag + ["--", query],
                cwd=folder,
                capture_output=True,
                text=True,
                timeout=30,
                start_new_session=True,
            )

            # returncode 1 means no matches, which is valid
            if result.returncode not in (0, 1):
                return None

            results = []
            for line in result.stdout.split("\n"):
                if not line:
                    continue

                parts = line.split(":", 2)
                if len(parts) >= 3:
                    rel_path = parts[0]

                    # Skip excluded directories
                    if self._should_skip_path(rel_path):
                        continue

                    file_path = os.path.join(folder, rel_path)
                    try:
                        line_num = int(parts[1])
                    except ValueError:
                        continue
                    line_text = parts[2]

                    match_start = line_text.lower().find(query.lower()) if case_flag else line_text.find(query)
                    match_end = match_start + len(query) if match_start >= 0 else 0

                    results.append((file_path, line_num, line_text, match_start, match_end))

                    if len(results) >= 500:
                        break

            return results
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return None

    def _ripgrep_search(self, folder: str, query: str, case_flag: list) -> list | None:
        """Search using ripgrep with exclusions."""
        try:
            # Build exclusion flags for ripgrep using global patterns
            exclude_args = []
            for pattern in get_global_patterns():
                exclude_args.extend(["-g", f"!{pattern}"])

            result = subprocess.run(
                ["rg", "-n", "--no-heading", "--color=never", "--hidden", "-F"] + case_flag + exclude_args + ["--", query],
                cwd=folder,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode not in (0, 1):
                return None

            results = []
            for line in result.stdout.split("\n"):
                if not line:
                    continue

                parts = line.split(":", 2)
                if len(parts) >= 3:
                    rel_path = parts[0]

                    if self._should_skip_path(rel_path):
                        continue

                    file_path = os.path.join(folder, rel_path)
                    try:
                        line_num = int(parts[1])
                    except ValueError:
                        continue
                    line_text = parts[2]

                    match_start = line_text.lower().find(query.lower()) if case_flag else line_text.find(query)
                    match_end = match_start + len(query) if match_start >= 0 else 0

                    results.append((file_path, line_num, line_text, match_start, match_end))

                    if len(results) >= 500:
                        break

            return results
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return None

    def _grep_search(self, folder: str, query: str, case_flag: list) -> list | None:
        """Fallback search using grep with exclusions."""
        try:
            # Build exclusion flags for grep using global patterns
            exclude_args = []
            for pattern in get_global_patterns():
                exclude_args.extend(["--exclude-dir", pattern])

            result = subprocess.run(
                ["grep", "-r", "-n", "-I", "-F"] + case_flag + exclude_args + ["--", query, "."],
                cwd=folder,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode not in (0, 1):
                return None

            results = []
            for line in result.stdout.split("\n"):
                if not line:
                    continue

                parts = line.split(":", 2)
                if len(parts) >= 3:
                    rel_path = parts[0]
                    if rel_path.startswith("./"):
                        rel_path = rel_path[2:]

                    if self._should_skip_path(rel_path):
                        continue

                    file_path = os.path.join(folder, rel_path)
                    try:
                        line_num = int(parts[1])
                    except ValueError:
                        continue
                    line_text = parts[2]

                    match_start = line_text.lower().find(query.lower()) if case_flag else line_text.find(query)
                    match_end = match_start + len(query) if match_start >= 0 else 0

                    results.append((file_path, line_num, line_text, match_start, match_end))

                    if len(results) >= 500:
                        break

            return results
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return None
