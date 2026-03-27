"""Tests for drag and drop — drop position computation and drop validation.

Covers:
- Drop position computation (mirrors _compute_drop_position)
- Drop validation (mirrors _is_valid_drop)
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from treeview import (
    TreeItem,
)


# ---------------------------------------------------------------------------
# Drop position computation (mirrors _compute_drop_position)
# ---------------------------------------------------------------------------
class TestComputeDropPosition:
    """Test the drop position logic extracted from CustomTreePanel."""

    def _compute(self, items, row_height, y):
        """Replicate _compute_drop_position logic."""
        index = int(y / row_height)
        if index < 0 or index >= len(items):
            return None, None
        item = items[index]
        row_y = y - index * row_height
        fraction = row_y / row_height
        if item.is_dir:
            if fraction < 0.25:
                return item, "before"
            elif fraction > 0.75:
                return item, "after"
            else:
                return item, "into"
        else:
            if fraction < 0.5:
                return item, "before"
            else:
                return item, "after"

    def test_file_top_half_before(self):
        f = TreeItem(name="a.py", path=Path("/a.py"), is_dir=False)
        item, pos = self._compute([f], 30, 5)
        assert item is f
        assert pos == "before"

    def test_file_bottom_half_after(self):
        f = TreeItem(name="a.py", path=Path("/a.py"), is_dir=False)
        item, pos = self._compute([f], 30, 25)
        assert item is f
        assert pos == "after"

    def test_dir_top_quarter_before(self):
        d = TreeItem(name="src", path=Path("/src"), is_dir=True)
        item, pos = self._compute([d], 40, 5)
        assert pos == "before"

    def test_dir_middle_into(self):
        d = TreeItem(name="src", path=Path("/src"), is_dir=True)
        item, pos = self._compute([d], 40, 20)
        assert pos == "into"

    def test_dir_bottom_quarter_after(self):
        d = TreeItem(name="src", path=Path("/src"), is_dir=True)
        item, pos = self._compute([d], 40, 35)
        assert pos == "after"

    def test_out_of_bounds(self):
        f = TreeItem(name="a.py", path=Path("/a.py"), is_dir=False)
        item, pos = self._compute([f], 30, 100)
        assert item is None
        assert pos is None

    def test_second_item(self):
        f1 = TreeItem(name="a.py", path=Path("/a.py"), is_dir=False)
        f2 = TreeItem(name="b.py", path=Path("/b.py"), is_dir=False)
        item, pos = self._compute([f1, f2], 30, 35)
        assert item is f2
        assert pos == "before"


# ---------------------------------------------------------------------------
# Drop validation (mirrors _is_valid_drop)
# ---------------------------------------------------------------------------
class TestIsValidDrop:
    """Test drag-and-drop validation logic."""

    def _make_panel_mock(self, roots, drag_source):
        """Create a mock with the fields _is_valid_drop reads."""
        mock = MagicMock()
        mock.roots = roots
        mock._drag_source_item = drag_source
        return mock

    def _is_valid_drop(self, roots, drag_source, target_item, position):
        """Replicate _is_valid_drop logic from CustomTreePanel."""
        if not drag_source or not target_item:
            return False
        src = drag_source
        if src.path == target_item.path:
            return False
        if position == "into":
            dest_dir = target_item.path
        else:
            dest_dir = target_item.path.parent
        if src.path.parent == dest_dir:
            return False
        src_root = None
        dest_root = None
        for root in roots:
            root_resolved = root.path.resolve()
            try:
                src.path.resolve().relative_to(root_resolved)
                src_root = root_resolved
            except ValueError:
                pass
            try:
                dest_dir.resolve().relative_to(root_resolved)
                dest_root = root_resolved
            except ValueError:
                pass
        if not src_root or not dest_root or src_root != dest_root:
            return False
        if src.is_dir:
            try:
                dest_dir.resolve().relative_to(src.path.resolve())
                return False
            except ValueError:
                pass
        return True

    def test_drop_onto_self(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = TreeItem(name="root", path=Path(tmp), is_dir=True)
            f = TreeItem(name="a.py", path=Path(tmp) / "a.py", is_dir=False, parent=root)
            assert self._is_valid_drop([root], f, f, "before") is False

    def test_drop_into_same_parent(self):
        """Moving a file within the same directory is a no-op."""
        with tempfile.TemporaryDirectory() as tmp:
            root = TreeItem(name="root", path=Path(tmp), is_dir=True)
            f1 = TreeItem(name="a.py", path=Path(tmp) / "a.py", is_dir=False, parent=root)
            f2 = TreeItem(name="b.py", path=Path(tmp) / "b.py", is_dir=False, parent=root)
            # "before" b.py -> dest_dir is root -> same as f1's parent
            assert self._is_valid_drop([root], f1, f2, "before") is False

    def test_valid_drop_into_subfolder(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = TreeItem(name="root", path=Path(tmp), is_dir=True)
            sub = TreeItem(name="sub", path=Path(tmp) / "sub", is_dir=True, parent=root)
            f = TreeItem(name="a.py", path=Path(tmp) / "a.py", is_dir=False, parent=root)
            os.makedirs(Path(tmp) / "sub", exist_ok=True)
            assert self._is_valid_drop([root], f, sub, "into") is True

    def test_drop_folder_into_itself(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = TreeItem(name="root", path=Path(tmp), is_dir=True)
            sub = TreeItem(name="sub", path=Path(tmp) / "sub", is_dir=True, parent=root)
            child = TreeItem(name="child", path=Path(tmp) / "sub" / "child", is_dir=True, parent=sub)
            os.makedirs(Path(tmp) / "sub" / "child", exist_ok=True)
            # Can't drop sub into its own child
            assert self._is_valid_drop([root], sub, child, "into") is False

    def test_cross_workspace_drop_rejected(self):
        with tempfile.TemporaryDirectory() as tmp1, tempfile.TemporaryDirectory() as tmp2:
            root1 = TreeItem(name="r1", path=Path(tmp1), is_dir=True)
            root2 = TreeItem(name="r2", path=Path(tmp2), is_dir=True)
            f = TreeItem(name="a.py", path=Path(tmp1) / "a.py", is_dir=False, parent=root1)
            assert self._is_valid_drop([root1, root2], f, root2, "into") is False

    def test_none_source(self):
        root = TreeItem(name="root", path=Path("/tmp/root"), is_dir=True)
        assert self._is_valid_drop([root], None, root, "into") is False

    def test_none_target(self):
        root = TreeItem(name="root", path=Path("/tmp/root"), is_dir=True)
        f = TreeItem(name="a.py", path=Path("/tmp/root/a.py"), is_dir=False)
        assert self._is_valid_drop([root], f, None, "before") is False
