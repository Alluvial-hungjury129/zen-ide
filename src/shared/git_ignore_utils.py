"""
GitIgnoreUtils - Parses and matches paths against .gitignore patterns.

Collects patterns from all workspace .gitignore files to build a unified
set of patterns that should be ignored across the entire workspace.
"""

import fnmatch
import os
from typing import Dict, List, Optional, Set

# Cache of matchers per workspace root
_matcher_cache: Dict[str, "GitIgnoreUtils"] = {}

# Global patterns collected from all workspace repos
_global_patterns: Set[str] = set()
_global_patterns_initialized: bool = False

# Per-workspace patterns (not merged across workspaces)
_per_workspace_patterns: Dict[str, Set[str]] = {}


def get_matcher(root_path: str) -> "GitIgnoreUtils":
    """Get or create a GitIgnoreUtils for a workspace root (cached)"""
    if root_path not in _matcher_cache:
        _matcher_cache[root_path] = GitIgnoreUtils(root_path)
    return _matcher_cache[root_path]


def collect_global_patterns(workspace_roots: List[str]) -> Set[str]:
    """
    Collect simple directory/file patterns from all workspace .gitignore files.
    These patterns are used globally across all workspaces.
    Only collects simple patterns (no slashes, no wildcards except simple globs).
    Also populates per-workspace patterns for scoped filtering.
    """
    global _global_patterns, _global_patterns_initialized

    # Check if all requested roots already have cached patterns
    if _global_patterns_initialized:
        new_roots = [r for r in workspace_roots if r not in _per_workspace_patterns]
        if not new_roots:
            return _global_patterns
        # New roots found - load their patterns and merge
        for root in new_roots:
            root_patterns = {".git"}
            gitignore_path = os.path.join(root, ".gitignore")
            if os.path.isfile(gitignore_path):
                try:
                    with open(gitignore_path, "r", encoding="utf-8", errors="ignore") as f:
                        for line in f:
                            line = line.strip()
                            if not line or line.startswith("#") or line.startswith("!"):
                                continue
                            if line.endswith("/"):
                                line = line[:-1]
                            if "/" not in line and line:
                                _global_patterns.add(line)
                                root_patterns.add(line)
                except Exception:
                    pass
            _per_workspace_patterns[root] = root_patterns
        return _global_patterns

    patterns = set()
    # Always skip .git
    patterns.add(".git")

    for root in workspace_roots:
        root_patterns = {".git"}
        gitignore_path = os.path.join(root, ".gitignore")
        if not os.path.isfile(gitignore_path):
            _per_workspace_patterns[root] = root_patterns
            continue

        try:
            with open(gitignore_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    # Skip empty lines, comments, and negations
                    if not line or line.startswith("#") or line.startswith("!"):
                        continue

                    # Remove trailing slash (directory marker)
                    if line.endswith("/"):
                        line = line[:-1]

                    # Only collect simple patterns (no path separators)
                    # These are patterns like ".ruff_cache", "__pycache__", "*.pyc"
                    if "/" not in line and line:
                        patterns.add(line)
                        root_patterns.add(line)
        except Exception:
            pass

        _per_workspace_patterns[root] = root_patterns

    _global_patterns = patterns
    _global_patterns_initialized = True
    return _global_patterns


def get_global_patterns() -> Set[str]:
    """Get the current global patterns (must call collect_global_patterns first)."""
    return _global_patterns


def get_workspace_patterns(workspace_root: str) -> Set[str]:
    """Get patterns for a specific workspace root (scoped, not merged)."""
    return _per_workspace_patterns.get(workspace_root, {".git"})


def find_workspace_root(path: str, workspace_roots: List[str]) -> Optional[str]:
    """Find the workspace root that contains a given path"""
    for root in workspace_roots:
        if path.startswith(root + os.sep) or path == root:
            return root
    return None


def should_skip(path: str, workspace_roots: List[str]) -> bool:
    """Check if a path should be completely skipped (hidden) - uses .gitignore"""
    root = find_workspace_root(path, workspace_roots)
    if root:
        matcher = get_matcher(root)
        is_dir = os.path.isdir(path)
        return matcher.is_ignored(path, is_dir)
    return False


def is_ignored(path: str, workspace_roots: List[str]) -> bool:
    """Check if a path should be marked as ignored (greyed out) - uses .gitignore"""
    return should_skip(path, workspace_roots)


class GitIgnoreUtils:
    """Parses and matches paths against .gitignore patterns"""

    def __init__(self, root_path: str):
        self.root_path = root_path
        self.patterns: List[tuple] = []  # List of (pattern, is_negation, is_dir_only)
        self._nested_cache: Dict[str, List[tuple]] = {}
        self._load_gitignore()

    @staticmethod
    def _parse_gitignore_file(gitignore_path: str) -> List[tuple]:
        """Parse a .gitignore file into (pattern, is_negation, is_dir_only) tuples."""
        patterns = []
        if not os.path.isfile(gitignore_path):
            return patterns
        try:
            with open(gitignore_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.rstrip("\n\r")
                    if not line or line.startswith("#"):
                        continue
                    is_negation = False
                    is_dir_only = False
                    if line.startswith("!"):
                        is_negation = True
                        line = line[1:]
                    if line.endswith("/"):
                        is_dir_only = True
                        line = line[:-1]
                    if not line:
                        continue
                    if line.startswith("/"):
                        line = line[1:]
                    patterns.append((line, is_negation, is_dir_only))
        except Exception:
            pass
        return patterns

    def _load_gitignore(self):
        """Load patterns from root .gitignore file"""
        self.patterns = self._parse_gitignore_file(os.path.join(self.root_path, ".gitignore"))

    def _get_nested_patterns(self, dir_path: str) -> List[tuple]:
        """Get parsed patterns from a nested .gitignore, cached."""
        if dir_path not in self._nested_cache:
            self._nested_cache[dir_path] = self._parse_gitignore_file(os.path.join(dir_path, ".gitignore"))
        return self._nested_cache[dir_path]

    def is_ignored(self, path: str, is_dir: bool = False) -> bool:
        """Check if a path should be ignored based on all .gitignore patterns (root + nested)"""
        # Get path relative to root
        try:
            rel_path = os.path.relpath(path, self.root_path)
        except ValueError:
            return False

        # Normalize separators
        rel_path = rel_path.replace(os.sep, "/")

        # Get basename for simple pattern matching
        basename = os.path.basename(rel_path)

        # Check against global patterns (collected from all workspace .gitignore files)
        # Always skip .git directory
        if basename == ".git":
            return True

        # Check per-workspace patterns (scoped to this workspace root only)
        workspace_patterns = _per_workspace_patterns.get(self.root_path, _global_patterns)
        for part in rel_path.split("/"):
            if part in workspace_patterns:
                return True
            # Check glob patterns (e.g., *.pyc)
            for pattern in workspace_patterns:
                if "*" in pattern and fnmatch.fnmatch(part, pattern):
                    return True

        ignored = False

        # Check root .gitignore patterns
        if self.patterns:
            for pattern, is_negation, is_dir_only in self.patterns:
                # Skip dir-only patterns for files
                if is_dir_only and not is_dir:
                    continue

                matched = False

                # Pattern with slash matches full path, otherwise just basename
                if "/" in pattern:
                    # Full path matching
                    matched = fnmatch.fnmatch(rel_path, pattern) or fnmatch.fnmatch(rel_path, pattern + "/**")
                    # Also check if any parent matches (e.g., "build/" should match "build/foo")
                    if not matched:
                        parts = rel_path.split("/")
                        for i in range(len(parts)):
                            sub_path = "/".join(parts[: i + 1])
                            if fnmatch.fnmatch(sub_path, pattern):
                                matched = True
                                break
                else:
                    # Basename matching - pattern applies to any level
                    matched = fnmatch.fnmatch(basename, pattern)
                    # Also check each path component
                    if not matched:
                        for part in rel_path.split("/"):
                            if fnmatch.fnmatch(part, pattern):
                                matched = True
                                break

                if matched:
                    ignored = not is_negation

        if ignored:
            return True

        # Check nested .gitignore files in each ancestor directory
        rel_parts = rel_path.split("/")
        if len(rel_parts) > 1:
            for i in range(len(rel_parts) - 1):
                subdir = os.path.join(self.root_path, *rel_parts[: i + 1])
                nested_patterns = self._get_nested_patterns(subdir)
                if not nested_patterns:
                    continue

                # Path relative to the nested .gitignore's directory
                nested_rel = "/".join(rel_parts[i + 1 :])
                nested_basename = rel_parts[-1]

                for pattern, is_negation, is_dir_only in nested_patterns:
                    if is_dir_only and not is_dir:
                        continue

                    matched = False
                    if "/" in pattern:
                        matched = fnmatch.fnmatch(nested_rel, pattern)
                    else:
                        matched = fnmatch.fnmatch(nested_basename, pattern)
                        if not matched:
                            for part in nested_rel.split("/"):
                                if fnmatch.fnmatch(part, pattern):
                                    matched = True
                                    break

                    if matched:
                        ignored = not is_negation

                if ignored:
                    return True

        return ignored
