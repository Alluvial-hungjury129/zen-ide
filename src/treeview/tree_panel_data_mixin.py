"""
CustomTreePanel data mixin — directory loading, gitignore, and git status logic.
"""

import os
from pathlib import Path
from typing import Dict, Optional, Set

from shared.git_ignore_utils import get_global_patterns, get_matcher, get_workspace_patterns
from treeview.tree_item import TreeItem


class TreePanelDataMixin:
    """Mixin providing data loading and git status methods for CustomTreePanel."""

    def _load_children(self, item: TreeItem):
        """Load children for a directory."""
        try:
            entries = sorted(item.path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
        except PermissionError:
            return

        item.children = []

        parent_inherited = item.git_status if item.is_dir else ""

        for i, entry in enumerate(entries):
            is_last = i == len(entries) - 1
            path_str = str(entry)

            is_ignored = self._should_skip(entry)

            if is_ignored:
                git_status = "I"
            elif path_str in self._git_modified_files:
                git_status = self._git_status_map.get(path_str, "M")
            elif parent_inherited:
                git_status = parent_inherited
            else:
                git_status = ""
            child = TreeItem(
                name=entry.name,
                path=entry,
                is_dir=entry.is_dir(),
                depth=item.depth + 1,
                parent=item,
                is_last=is_last,
                git_status=git_status,
            )
            item.children.append(child)

    def _should_skip(self, path: Path) -> bool:
        """Check if a path should be skipped (uses cached compiled patterns)."""
        name = path.name

        workspace_root = None
        path_str = str(path)
        for root in self.roots:
            root_str = str(root.path)
            if path_str.startswith(root_str + os.sep) or path_str == root_str:
                workspace_root = root_str
                break

        if workspace_root not in self._pattern_cache:
            self._compile_patterns(workspace_root)

        exact_names, compiled_globs = self._pattern_cache[workspace_root]

        if name in exact_names:
            return True
        for regex in compiled_globs:
            if regex.match(name):
                return True

        # Fall back to full GitIgnoreUtils matcher for path-based patterns
        if workspace_root:
            matcher = get_matcher(workspace_root)
            return matcher.is_ignored(path_str, path.is_dir())

        return False

    def _compile_patterns(self, workspace_root):
        """Compile and cache gitignore patterns for a workspace root."""
        import fnmatch as fnmatch_mod
        import re as re_mod

        patterns = get_workspace_patterns(workspace_root) if workspace_root else get_global_patterns()
        exact_names = set()
        compiled_globs = []
        for pattern in patterns:
            if "*" in pattern:
                compiled_globs.append(re_mod.compile(fnmatch_mod.translate(pattern)))
            else:
                exact_names.add(pattern)
        self._pattern_cache[workspace_root] = (exact_names, compiled_globs)

    def load_directory(self, path: Path, expanded: bool = False):
        """Load a directory as a root."""
        root = TreeItem(
            name=path.name,
            path=path,
            is_dir=True,
            depth=0,
            expanded=expanded,
            is_last=True,
        )
        self.roots.append(root)
        if expanded:
            self._load_children(root)
        self._flatten_and_redraw()

    def clear(self):
        """Clear all items."""
        self.roots = []
        self.items = []
        self._clear_selection()
        self.hover_item = None
        self._pattern_cache.clear()
        self._request_redraw()

    def set_git_modified_files(self, modified_files: Set[str], status_map: Optional[Dict[str, str]] = None):
        """Set git modified files and update tree display."""
        new_status_map = status_map or {}

        if self._git_modified_files == modified_files and self._git_status_map == new_status_map:
            return

        self._git_modified_files = modified_files
        self._git_status_map = new_status_map

        # Pre-compute directories containing modified files
        self._modified_dirs = set()
        for file_path in modified_files:
            parent = os.path.dirname(str(file_path))
            while parent and parent not in self._modified_dirs:
                self._modified_dirs.add(parent)
                parent = os.path.dirname(parent)

        self._update_item_git_status()
        self._request_redraw()

    def _update_item_git_status(self):
        """Update git_status field on all tree items."""

        def update_item(item: TreeItem, inherited_status: str = ""):
            if item.git_status == "I":
                for child in item.children:
                    update_item(child, "I")
                return

            path_str = str(item.path)
            if path_str in self._git_modified_files:
                item.git_status = self._git_status_map.get(path_str, "M")
            elif inherited_status:
                item.git_status = inherited_status
            else:
                item.git_status = ""

            child_inherited = item.git_status if item.is_dir else inherited_status
            for child in item.children:
                update_item(child, child_inherited)

        for root in self.roots:
            update_item(root)
