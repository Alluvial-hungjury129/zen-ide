"""Tests for tree selection — TreeItem, constants, flatten, selection logic, git status.

Covers:
- TreeItem dataclass defaults and relationships
- ICON_COLORS and GIT_STATUS_COLORS constants
- Flatten items logic
- Selection logic (single, toggle, range, effective)
- Git status propagation
- Modified directory detection
- Item at Y coordinate
"""

import os
from pathlib import Path
from unittest.mock import MagicMock

from treeview import (
    ICON_COLORS,
    TreeItem,
    get_git_status_colors,
)


# ---------------------------------------------------------------------------
# TreeItem
# ---------------------------------------------------------------------------
class TestTreeItem:
    def test_defaults(self):
        item = TreeItem(name="test.py", path=Path("/a/test.py"), is_dir=False)
        assert item.name == "test.py"
        assert item.is_dir is False
        assert item.depth == 0
        assert item.parent is None
        assert item.expanded is False
        assert item.is_last is False
        assert item.git_status == ""
        assert item.children == []

    def test_directory_item(self):
        item = TreeItem(name="src", path=Path("/a/src"), is_dir=True, depth=1, expanded=True)
        assert item.is_dir is True
        assert item.depth == 1
        assert item.expanded is True

    def test_parent_child_relationship(self):
        parent = TreeItem(name="src", path=Path("/a/src"), is_dir=True)
        child = TreeItem(name="main.py", path=Path("/a/src/main.py"), is_dir=False, parent=parent, depth=1)
        parent.children.append(child)
        assert child.parent is parent
        assert parent.children[0] is child

    def test_git_status(self):
        item = TreeItem(name="file.py", path=Path("/a/file.py"), is_dir=False, git_status="M")
        assert item.git_status == "M"

    def test_is_last(self):
        item = TreeItem(name="last.py", path=Path("/a/last.py"), is_dir=False, is_last=True)
        assert item.is_last is True


# ---------------------------------------------------------------------------
# ICON_COLORS & GIT_STATUS_COLORS constants
# ---------------------------------------------------------------------------
class TestConstants:
    def test_icon_colors_has_defaults(self):
        assert "folder" in ICON_COLORS
        assert "default" in ICON_COLORS
        assert ".py" in ICON_COLORS

    def test_git_status_colors_keys(self):
        git_colors = get_git_status_colors()
        for key in ("M", "A", "D", "R", "?"):
            assert key in git_colors


# ---------------------------------------------------------------------------
# Flatten items logic (tested via helper that mirrors _flatten_items)
# ---------------------------------------------------------------------------
def _build_tree():
    """Build a small tree for testing flatten/navigation logic."""
    root = TreeItem(name="project", path=Path("/project"), is_dir=True, expanded=True)
    src = TreeItem(name="src", path=Path("/project/src"), is_dir=True, depth=1, parent=root, expanded=True)
    main = TreeItem(name="main.py", path=Path("/project/src/main.py"), is_dir=False, depth=2, parent=src)
    utils = TreeItem(name="utils.py", path=Path("/project/src/utils.py"), is_dir=False, depth=2, parent=src)
    src.children = [main, utils]
    readme = TreeItem(name="README.md", path=Path("/project/README.md"), is_dir=False, depth=1, parent=root)
    root.children = [src, readme]
    return root, [root, src, main, utils, readme]


def _flatten(roots):
    """Pure-function replication of CustomTreePanel._flatten_items."""
    items = []

    def traverse(item):
        items.append(item)
        if item.is_dir and item.expanded:
            for child in item.children:
                traverse(child)

    for root in roots:
        traverse(root)
    return items


def _set_selection(panel, items, primary_item=None, anchor_item=None):
    """Replicate CustomTreePanel._set_selection."""
    visible_items = [item for item in items if item in panel.items]
    panel.selected_items = set(visible_items)
    if not visible_items:
        panel.selected_item = None
        panel._selection_anchor_item = None
        return
    if primary_item not in panel.selected_items:
        primary_item = visible_items[-1]
    panel.selected_item = primary_item
    if anchor_item not in panel.selected_items:
        anchor_item = primary_item
    panel._selection_anchor_item = anchor_item


def _select_single(panel, item):
    """Replicate CustomTreePanel._select_single_item."""
    if item is None:
        panel.selected_items = set()
        panel.selected_item = None
        panel._selection_anchor_item = None
        return
    _set_selection(panel, [item], primary_item=item, anchor_item=item)


def _selected_in_order(panel):
    """Replicate CustomTreePanel.get_selected_items."""
    return [item for item in panel.items if item in panel.selected_items]


def _toggle_selection(panel, item):
    """Replicate CustomTreePanel._toggle_item_selection."""
    if item in panel.selected_items:
        remaining = [selected for selected in _selected_in_order(panel) if selected != item]
        if remaining:
            new_primary = panel.selected_item if panel.selected_item != item else remaining[-1]
            new_anchor = panel._selection_anchor_item if panel._selection_anchor_item != item else new_primary
            _set_selection(panel, remaining, primary_item=new_primary, anchor_item=new_anchor)
        else:
            panel.selected_items = set()
            panel.selected_item = None
            panel._selection_anchor_item = None
        return
    items = _selected_in_order(panel)
    items.append(item)
    _set_selection(panel, items, primary_item=item, anchor_item=item)


def _select_range(panel, item):
    """Replicate CustomTreePanel._select_range_to."""
    anchor = panel._selection_anchor_item or panel.selected_item
    if anchor not in panel.items:
        _select_single(panel, item)
        return
    start = panel.items.index(anchor)
    end = panel.items.index(item)
    if start <= end:
        range_items = panel.items[start : end + 1]
    else:
        range_items = panel.items[end : start + 1]
    _set_selection(panel, range_items, primary_item=item, anchor_item=anchor)


def _effective_selection(all_items, selected_items):
    """Replicate TreeViewActionsMixin._get_effective_selection."""
    ordered_items = [item for item in all_items if item in set(selected_items)]
    selected_paths = {candidate.path for candidate in ordered_items}
    effective_items = []
    for candidate in ordered_items:
        if any(parent in selected_paths for parent in candidate.path.parents):
            continue
        effective_items.append(candidate)
    return effective_items


class TestFlattenItems:
    def test_expanded_tree(self):
        root, expected = _build_tree()
        items = _flatten([root])
        assert [i.name for i in items] == ["project", "src", "main.py", "utils.py", "README.md"]

    def test_collapsed_subtree(self):
        root, _ = _build_tree()
        # Collapse src
        root.children[0].expanded = False
        items = _flatten([root])
        assert [i.name for i in items] == ["project", "src", "README.md"]

    def test_fully_collapsed(self):
        root, _ = _build_tree()
        root.expanded = False
        items = _flatten([root])
        assert [i.name for i in items] == ["project"]

    def test_multiple_roots(self):
        root1 = TreeItem(name="a", path=Path("/a"), is_dir=True, expanded=False)
        root2 = TreeItem(name="b", path=Path("/b"), is_dir=True, expanded=False)
        items = _flatten([root1, root2])
        assert [i.name for i in items] == ["a", "b"]

    def test_empty_roots(self):
        assert _flatten([]) == []


class TestSelectionLogic:
    def _make_panel(self):
        root, items = _build_tree()
        panel = MagicMock()
        panel.items = items
        panel.selected_items = set()
        panel.selected_item = None
        panel._selection_anchor_item = None
        return panel, items

    def test_single_selection_tracks_anchor(self):
        panel, items = self._make_panel()
        _select_single(panel, items[2])
        assert panel.selected_item is items[2]
        assert panel._selection_anchor_item is items[2]
        assert _selected_in_order(panel) == [items[2]]

    def test_toggle_selection_adds_and_removes_items(self):
        panel, items = self._make_panel()
        _select_single(panel, items[2])
        _toggle_selection(panel, items[3])
        assert _selected_in_order(panel) == [items[2], items[3]]
        assert panel.selected_item is items[3]
        _toggle_selection(panel, items[3])
        assert _selected_in_order(panel) == [items[2]]
        assert panel.selected_item is items[2]

    def test_shift_selection_uses_anchor_range(self):
        panel, items = self._make_panel()
        _select_single(panel, items[1])
        _select_range(panel, items[4])
        assert _selected_in_order(panel) == items[1:5]
        assert panel.selected_item is items[4]
        assert panel._selection_anchor_item is items[1]

    def test_effective_selection_drops_descendants_of_selected_directory(self):
        root, items = _build_tree()
        effective = _effective_selection(items, [root.children[0], root.children[0].children[0], root.children[1]])
        assert effective == [root.children[0], root.children[1]]


# ---------------------------------------------------------------------------
# Git status propagation (mirrors _update_item_git_status)
# ---------------------------------------------------------------------------
def _update_git_status(roots, modified_files, status_map):
    """Pure-function replication of git status update logic."""
    # Pre-compute modified dirs
    modified_dirs = set()
    for fp in modified_files:
        parent = os.path.dirname(str(fp))
        while parent and parent not in modified_dirs:
            modified_dirs.add(parent)
            parent = os.path.dirname(parent)

    def update_item(item, inherited_status=""):
        if item.git_status == "I":
            for child in item.children:
                update_item(child, "I")
            return

        path_str = str(item.path)
        if path_str in modified_files:
            item.git_status = status_map.get(path_str, "M")
        elif inherited_status:
            item.git_status = inherited_status
        else:
            item.git_status = ""

        child_inherited = item.git_status if item.is_dir else inherited_status
        for child in item.children:
            update_item(child, child_inherited)

    for root in roots:
        update_item(root)


class TestGitStatusPropagation:
    def test_file_gets_status(self):
        root, _ = _build_tree()
        modified = {"/project/src/main.py"}
        _update_git_status([root], modified, {"/project/src/main.py": "M"})
        main = root.children[0].children[0]
        assert main.git_status == "M"

    def test_unmodified_file_cleared(self):
        root, _ = _build_tree()
        _update_git_status([root], set(), {})
        utils = root.children[0].children[1]
        assert utils.git_status == ""

    def test_directory_inherits_status(self):
        """When a dir has status, children inherit it."""
        root, _ = _build_tree()
        modified = {"/project/src"}
        _update_git_status([root], modified, {"/project/src": "A"})
        src = root.children[0]
        assert src.git_status == "A"
        # Children inherit dir status
        assert src.children[0].git_status == "A"
        assert src.children[1].git_status == "A"

    def test_gitignored_item_preserved(self):
        """Items with 'I' status keep it and pass 'I' inherited to children."""
        root, _ = _build_tree()
        src = root.children[0]
        src.git_status = "I"
        # Children also marked as ignored
        src.children[0].git_status = "I"
        src.children[1].git_status = "I"
        _update_git_status([root], {"/project/src/main.py"}, {"/project/src/main.py": "M"})
        # I status is preserved on parent
        assert src.git_status == "I"
        # Children with I status keep it (not overridden by modified)
        assert src.children[0].git_status == "I"
        assert src.children[1].git_status == "I"

    def test_default_status_is_M(self):
        """When status_map has no entry, default to 'M'."""
        root, _ = _build_tree()
        modified = {"/project/README.md"}
        _update_git_status([root], modified, {})
        readme = root.children[1]
        assert readme.git_status == "M"

    def test_multiple_statuses(self):
        root, _ = _build_tree()
        modified = {"/project/src/main.py", "/project/README.md"}
        status_map = {"/project/src/main.py": "A", "/project/README.md": "?"}
        _update_git_status([root], modified, status_map)
        assert root.children[0].children[0].git_status == "A"
        assert root.children[1].git_status == "?"


# ---------------------------------------------------------------------------
# Modified directory detection (mirrors _is_modified_dir)
# ---------------------------------------------------------------------------
class TestIsModifiedDir:
    def _is_modified_dir(self, item, modified_dirs):
        if not item.is_dir:
            return False
        return str(item.path) in modified_dirs

    def test_directory_in_set(self):
        d = TreeItem(name="src", path=Path("/project/src"), is_dir=True)
        assert self._is_modified_dir(d, {"/project/src"}) is True

    def test_directory_not_in_set(self):
        d = TreeItem(name="src", path=Path("/project/src"), is_dir=True)
        assert self._is_modified_dir(d, set()) is False

    def test_file_returns_false(self):
        f = TreeItem(name="a.py", path=Path("/project/a.py"), is_dir=False)
        assert self._is_modified_dir(f, {"/project/a.py"}) is False


# ---------------------------------------------------------------------------
# Item at Y coordinate (mirrors _get_item_at_y)
# ---------------------------------------------------------------------------
class TestGetItemAtY:
    def _get_item_at_y(self, items, row_height, y):
        index = int(y / row_height)
        if 0 <= index < len(items):
            return items[index]
        return None

    def test_first_item(self):
        items = [TreeItem(name="a", path=Path("/a"), is_dir=False)]
        assert self._get_item_at_y(items, 30, 10) is items[0]

    def test_second_item(self):
        items = [
            TreeItem(name="a", path=Path("/a"), is_dir=False),
            TreeItem(name="b", path=Path("/b"), is_dir=False),
        ]
        assert self._get_item_at_y(items, 30, 40) is items[1]

    def test_out_of_bounds_returns_none(self):
        items = [TreeItem(name="a", path=Path("/a"), is_dir=False)]
        assert self._get_item_at_y(items, 30, 100) is None

    def test_negative_y_maps_to_first_item(self):
        """int(-5/30) == 0, which is in bounds — matches actual code behavior."""
        items = [TreeItem(name="a", path=Path("/a"), is_dir=False)]
        assert self._get_item_at_y(items, 30, -5) is items[0]

    def test_empty_items_returns_none(self):
        assert self._get_item_at_y([], 30, 10) is None
