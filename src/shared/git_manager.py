"""
GitManager - Centralized facade for all git operations.
All git subprocess calls should go through this module.
"""

import os
import subprocess
import threading
import time
from typing import Dict, List, Optional, Set, Tuple


class GitManager:
    """
    Centralized git operations facade.

    Repo roots are cached (rarely change).
    Branch names are cached with short TTL.
    All other operations query git directly.

    Uses GIT_OPTIONAL_LOCKS=0 for read-only operations to prevent
    index.lock contention when multiple IDE instances share a repo.
    """

    REPO_ROOT_CACHE_TTL = 300  # 5 minutes - repo roots rarely change
    MODIFIED_FILES_CACHE_TTL = 2  # 2 seconds - modified files change often but cache briefly to avoid spam
    BRANCH_CACHE_TTL = 5  # 5 seconds - branch changes rarely, cache to avoid subprocess spam

    # Env for read-only git commands: prevents index.lock acquisition
    _NO_LOCK_ENV = {**os.environ, "GIT_OPTIONAL_LOCKS": "0"}

    def __init__(self):
        self._lock = threading.RLock()
        # Cache: {folder_path: (repo_root, timestamp)}
        self._repo_root_cache: Dict[str, Tuple[Optional[str], float]] = {}
        # Cache: {repo_root: (modified_files, timestamp)}
        self._modified_files_cache: Dict[str, Tuple[Set[str], float]] = {}
        # Cache: {repo_root: (branch_name, timestamp)}
        self._branch_cache: Dict[str, Tuple[str, float]] = {}

    # -------------------------------------------------------------------------
    # Repository root operations
    # -------------------------------------------------------------------------

    def get_repo_root(self, path: str) -> Optional[str]:
        """
        Get git repository root for a file or folder, using cache.
        Returns None if path is not in a git repo.
        """
        # Normalize to folder
        if os.path.isfile(path):
            folder_path = os.path.dirname(path)
        else:
            folder_path = path

        now = time.time()

        with self._lock:
            # Check direct cache hit first
            if folder_path in self._repo_root_cache:
                root, timestamp = self._repo_root_cache[folder_path]
                if now - timestamp < self.REPO_ROOT_CACHE_TTL:
                    return root

            # Optimization: check if this folder is under a known cached repo root
            # This avoids spawning git for every subdirectory
            for cached_folder, (cached_root, timestamp) in self._repo_root_cache.items():
                if now - timestamp >= self.REPO_ROOT_CACHE_TTL:
                    continue  # Skip expired entries
                if cached_root and folder_path.startswith(cached_root + os.sep):
                    # This folder is under a known repo root - cache it
                    self._repo_root_cache[folder_path] = (cached_root, now)
                    return cached_root

        # Cache miss - query git
        root = self._query_repo_root(folder_path)

        with self._lock:
            self._repo_root_cache[folder_path] = (root, now)

        return root

    def get_repo_root_cached(self, path: str) -> Optional[str]:
        """Return a cached repo root for *path*, or ``None`` if not cached.

        Unlike ``get_repo_root`` this never spawns a subprocess — it only
        checks the in-memory cache.  Used on the main thread where blocking
        is unacceptable (e.g. AI terminal spawn).
        """
        if os.path.isfile(path):
            folder_path = os.path.dirname(path)
        else:
            folder_path = path

        now = time.time()
        with self._lock:
            if folder_path in self._repo_root_cache:
                root, timestamp = self._repo_root_cache[folder_path]
                if now - timestamp < self.REPO_ROOT_CACHE_TTL:
                    return root
            for _cached_folder, (cached_root, timestamp) in self._repo_root_cache.items():
                if now - timestamp >= self.REPO_ROOT_CACHE_TTL:
                    continue
                if cached_root and folder_path.startswith(cached_root + os.sep):
                    return cached_root
        return None

    def _query_repo_root(self, folder_path: str) -> Optional[str]:
        """Query git for repo root"""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                cwd=folder_path,
                capture_output=True,
                text=True,
                timeout=2,
                start_new_session=True,
                env=self._NO_LOCK_ENV,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            pass
        return None

    def invalidate_modified_files(self, repo_root: str = None):
        """Invalidate modified files cache.

        Args:
            repo_root: If provided, invalidate only that repo. Otherwise invalidate all.
        """
        with self._lock:
            if repo_root:
                self._modified_files_cache.pop(repo_root, None)
            else:
                self._modified_files_cache.clear()

    # -------------------------------------------------------------------------
    # Branch operations
    # -------------------------------------------------------------------------

    def get_current_branch(self, repo_root: str) -> str:
        """Get the current branch name. Returns 'current' on error. Uses cache."""
        now = time.time()

        # Check cache first
        with self._lock:
            if repo_root in self._branch_cache:
                branch, timestamp = self._branch_cache[repo_root]
                if now - timestamp < self.BRANCH_CACHE_TTL:
                    return branch

        # Cache miss - query git
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=repo_root,
                capture_output=True,
                text=True,
                timeout=2,
                start_new_session=True,
                env=self._NO_LOCK_ENV,
            )
            if result.returncode == 0:
                branch = result.stdout.strip()
                with self._lock:
                    self._branch_cache[repo_root] = (branch, now)
                return branch
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            pass
        return "current"

    def get_current_branch_cached(self, repo_root: str) -> str:
        """Return cached branch name, or empty string if not cached.

        Unlike ``get_current_branch`` this never spawns a subprocess.
        """
        now = time.time()
        with self._lock:
            if repo_root in self._branch_cache:
                branch, timestamp = self._branch_cache[repo_root]
                if now - timestamp < self.BRANCH_CACHE_TTL:
                    return branch
        return ""

    # -------------------------------------------------------------------------
    # File content at ref operations
    # -------------------------------------------------------------------------

    def get_file_at_ref(self, repo_root: str, rel_path: str, ref: str) -> Optional[str]:
        """
        Get file content at a specific git ref (branch, tag, or commit SHA).

        Args:
            repo_root: Git repository root path
            rel_path: Path relative to repo root
            ref: Git ref (branch name, tag, or commit SHA)

        Returns:
            File content as string, or None if not found
        """
        try:
            result = subprocess.run(
                ["git", "show", f"{ref}:{rel_path}"],
                cwd=repo_root,
                capture_output=True,
                text=True,
                timeout=10,
                start_new_session=True,
                env=self._NO_LOCK_ENV,
            )
            if result.returncode == 0:
                return result.stdout
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError, UnicodeDecodeError):
            pass
        return None

    def is_file_tracked(self, repo_root: str, rel_path: str) -> bool:
        """Check if a file is tracked or staged in the git repo."""
        try:
            result = subprocess.run(
                ["git", "ls-files", rel_path],
                cwd=repo_root,
                capture_output=True,
                text=True,
                timeout=2,
                start_new_session=True,
                env=self._NO_LOCK_ENV,
            )
            return result.returncode == 0 and result.stdout.strip() != ""
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return False

    def get_file_at_main_branch(self, repo_root: str, rel_path: str) -> Optional[str]:
        """
        Get file content from main/master/develop branch.
        Tries branches in order until one works.

        Args:
            repo_root: Git repository root path
            rel_path: Path relative to repo root

        Returns:
            File content as string, or None if not found
        """
        for branch in ["main", "master", "develop"]:
            content = self.get_file_at_ref(repo_root, rel_path, branch)
            if content is not None:
                return content
        return None

    # -------------------------------------------------------------------------
    # Status operations
    # -------------------------------------------------------------------------

    def get_detailed_status(self, repo_root: str) -> Dict[str, str]:
        """
        Get detailed git status with status codes for each file.
        Similar to neovim/neo-tree git hints.

        Status codes:
        - 'M' = Modified (tracked file with changes)
        - 'A' = Added (new file staged)
        - 'D' = Deleted
        - 'R' = Renamed
        - 'C' = Copied
        - 'U' = Updated but unmerged (conflict)
        - '?' = Untracked (new file not staged)
        - '!' = Ignored

        Args:
            repo_root: The git repository root path

        Returns:
            Dict mapping absolute file paths to their status code
        """
        now = time.time()

        # Check cache first
        with self._lock:
            if repo_root in self._modified_files_cache:
                cached_status, timestamp = self._modified_files_cache[repo_root]
                if now - timestamp < self.MODIFIED_FILES_CACHE_TTL:
                    # Handle old cache format (Set) gracefully
                    if isinstance(cached_status, dict):
                        return cached_status
                    # Old format was Set - invalidate and recompute
                    pass

        # Cache miss - query git
        status_map: Dict[str, str] = {}

        try:
            result = subprocess.run(
                ["git", "status", "--porcelain", "-z"],
                cwd=repo_root,
                capture_output=True,
                text=True,
                timeout=2,
                start_new_session=True,
                env=self._NO_LOCK_ENV,
            )

            if result.returncode == 0 and result.stdout:
                entries = result.stdout.split("\0")
                for entry in entries:
                    if entry and len(entry) >= 3:
                        # Porcelain format: XY filename
                        # X = index status, Y = worktree status
                        index_status = entry[0]
                        worktree_status = entry[1]
                        file_path = entry[3:]

                        if " -> " in file_path:
                            file_path = file_path.split(" -> ")[-1]

                        # Strip trailing slash (git reports untracked dirs as "new_folder/")
                        file_path = file_path.rstrip("/")

                        full_path = os.path.join(repo_root, file_path)

                        # Determine the display status code
                        # Priority: untracked > conflict > staged changes > worktree changes
                        if index_status == "?" and worktree_status == "?":
                            status_code = "?"  # Untracked
                        elif index_status == "!" and worktree_status == "!":
                            status_code = "!"  # Ignored
                        elif "U" in (index_status, worktree_status) or (
                            index_status in ("D", "A") and worktree_status in ("D", "A")
                        ):
                            status_code = "U"  # Conflict
                        elif index_status == "A":
                            status_code = "A"  # Added (staged)
                        elif index_status == "D" or worktree_status == "D":
                            status_code = "D"  # Deleted
                        elif index_status == "R":
                            status_code = "R"  # Renamed
                        elif index_status == "C":
                            status_code = "C"  # Copied
                        elif index_status == "M" or worktree_status == "M":
                            status_code = "M"  # Modified
                        else:
                            status_code = "M"  # Default to modified for any other change

                        status_map[full_path] = status_code

        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            pass

        # Cache the result
        with self._lock:
            self._modified_files_cache[repo_root] = (status_map, now)

        return status_map

    def get_all_detailed_status(self, workspace_folders: list) -> Dict[str, str]:
        """
        Get detailed git status across multiple workspace folders.
        Batches requests by repo root to minimize git calls.

        Args:
            workspace_folders: List of folder paths to check

        Returns:
            Dict mapping absolute file paths to their status code
        """
        repos_to_query: Dict[str, bool] = {}

        for folder in workspace_folders:
            if not folder or not os.path.isdir(folder):
                continue
            repo_root = self.get_repo_root(folder)
            if repo_root:
                repos_to_query[repo_root] = True

        all_status: Dict[str, str] = {}
        for repo_root in repos_to_query:
            status = self.get_detailed_status(repo_root)
            all_status.update(status)

        return all_status

    # -------------------------------------------------------------------------
    # Log/history operations
    # -------------------------------------------------------------------------

    def get_file_commits(self, file_path: str, limit: int = 50) -> List[Dict[str, str]]:
        """
        Get list of commits that modified a specific file.

        Args:
            file_path: Absolute path to the file
            limit: Maximum number of commits to return

        Returns:
            List of dicts with keys: sha, message, author, date
        """
        try:
            repo_root = self.get_repo_root(file_path)
            if not repo_root:
                return []

            rel_path = os.path.relpath(file_path, repo_root)
            result = subprocess.run(
                [
                    "git",
                    "log",
                    f"-{limit}",
                    "--pretty=format:%H|%s|%an|%ad",
                    "--date=short",
                    "--",
                    rel_path,
                ],
                cwd=repo_root,
                capture_output=True,
                text=True,
                timeout=10,
                start_new_session=True,
                env=self._NO_LOCK_ENV,
            )
            if result.returncode != 0:
                return []

            commits = []
            for line in result.stdout.strip().split("\n"):
                if line:
                    parts = line.split("|", 3)
                    if len(parts) >= 4:
                        commits.append(
                            {
                                "sha": parts[0],
                                "message": parts[1][:50],
                                "author": parts[2],
                                "date": parts[3],
                            }
                        )
            return commits
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return []

    # -------------------------------------------------------------------------
    # Discard/restore operations
    # -------------------------------------------------------------------------

    def discard_changes(self, file_path: str) -> Tuple[bool, str]:
        """
        Discard all changes to a file, restoring it to the last committed state.

        Args:
            file_path: Absolute path to the file

        Returns:
            Tuple of (success, message)
        """
        try:
            repo_root = self.get_repo_root(file_path)
            if not repo_root:
                return False, "File is not in a git repository"

            rel_path = os.path.relpath(file_path, repo_root)

            # Check if file is untracked (new file)
            status = self.get_detailed_status(repo_root)
            if file_path in status and status[file_path] == "?":
                return False, "Cannot discard untracked file. Use delete instead."

            # Use git restore (Git 2.23+) or fallback to git checkout
            result = subprocess.run(
                ["git", "restore", "--", rel_path],
                cwd=repo_root,
                capture_output=True,
                text=True,
                timeout=5,
                start_new_session=True,
            )

            if result.returncode != 0:
                # Fallback to git checkout for older git versions
                result = subprocess.run(
                    ["git", "checkout", "--", rel_path],
                    cwd=repo_root,
                    capture_output=True,
                    text=True,
                    timeout=5,
                    start_new_session=True,
                )

            if result.returncode == 0:
                # Invalidate cache since file status changed
                self.invalidate_modified_files(repo_root)
                return True, f"Changes discarded for {os.path.basename(file_path)}"
            else:
                return False, result.stderr.strip() or "Failed to discard changes"

        except subprocess.TimeoutExpired:
            return False, "Git command timed out"
        except (FileNotFoundError, OSError) as e:
            return False, str(e)

    # -------------------------------------------------------------------------
    # Cache management
    # -------------------------------------------------------------------------

    def clear_all(self):
        """Clear all caches"""
        with self._lock:
            self._repo_root_cache.clear()
            self._modified_files_cache.clear()
            self._branch_cache.clear()


# Global singleton instance
_git_manager: Optional[GitManager] = None


def get_git_manager() -> GitManager:
    """Get or create the global GitManager instance"""
    global _git_manager
    if _git_manager is None:
        _git_manager = GitManager()
    return _git_manager
