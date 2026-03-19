"""Regression tests for external file drop (Finder → tree view).

Covers:
- URI parsing (macOS double-encoded ``file%3A///`` URIs)
- Auto-rename when destination file already exists
- External drop validation
- Copy logic (files and directories)
- Drop cleanup / finish
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from treeview import TreeItem
from treeview.tree_panel_drag import (
    TreePanelDragMixin,
    parse_uri_list,
    unique_dest_path,
)


# ---------------------------------------------------------------------------
# parse_uri_list
# ---------------------------------------------------------------------------
class TestParseUriList:
    """Regression: macOS Finder sends URL-encoded URIs."""

    def test_standard_file_uri(self):
        data = "file:///Users/me/photo.png\r\n"
        assert parse_uri_list(data) == [Path("/Users/me/photo.png")]

    def test_macos_encoded_scheme(self):
        """Key regression: Finder sends file%3A/// instead of file:///."""
        data = "file%3A///Users/me/Desktop/stuff.png\r\n"
        assert parse_uri_list(data) == [Path("/Users/me/Desktop/stuff.png")]

    def test_encoded_path_with_spaces(self):
        data = "file:///Users/me/My%20Documents/report.pdf\r\n"
        assert parse_uri_list(data) == [Path("/Users/me/My Documents/report.pdf")]

    def test_fully_encoded_with_spaces(self):
        data = "file%3A///Users/me/My%20Folder/file.txt\r\n"
        assert parse_uri_list(data) == [Path("/Users/me/My Folder/file.txt")]

    def test_multiple_files(self):
        data = "file:///Users/me/a.png\r\nfile:///Users/me/b.txt\r\n"
        result = parse_uri_list(data)
        assert len(result) == 2
        assert result[0] == Path("/Users/me/a.png")
        assert result[1] == Path("/Users/me/b.txt")

    def test_ignores_comment_lines(self):
        data = "# comment\r\nfile:///Users/me/a.png\r\n"
        assert parse_uri_list(data) == [Path("/Users/me/a.png")]

    def test_ignores_blank_lines(self):
        data = "\r\nfile:///Users/me/a.png\r\n\r\n"
        assert parse_uri_list(data) == [Path("/Users/me/a.png")]

    def test_ignores_non_file_scheme(self):
        data = "http://example.com/file.txt\r\nfile:///Users/me/a.png\r\n"
        assert parse_uri_list(data) == [Path("/Users/me/a.png")]

    def test_empty_data(self):
        assert parse_uri_list("") == []

    def test_only_comments(self):
        assert parse_uri_list("# nothing here\r\n") == []

    def test_unix_line_endings(self):
        data = "file:///tmp/a.txt\nfile:///tmp/b.txt\n"
        assert len(parse_uri_list(data)) == 2


# ---------------------------------------------------------------------------
# unique_dest_path
# ---------------------------------------------------------------------------
class TestUniqueDestPath:
    """Regression: duplicate files must auto-rename, not skip."""

    def test_no_conflict(self):
        with tempfile.TemporaryDirectory() as d:
            result = unique_dest_path(Path(d), "photo.png")
            assert result == Path(d) / "photo.png"

    def test_single_conflict(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "photo.png").touch()
            result = unique_dest_path(Path(d), "photo.png")
            assert result == Path(d) / "photo (1).png"

    def test_multiple_conflicts(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "photo.png").touch()
            (Path(d) / "photo (1).png").touch()
            (Path(d) / "photo (2).png").touch()
            result = unique_dest_path(Path(d), "photo.png")
            assert result == Path(d) / "photo (3).png"

    def test_no_extension(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "Makefile").touch()
            result = unique_dest_path(Path(d), "Makefile")
            assert result == Path(d) / "Makefile (1)"

    def test_dotfile(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / ".gitignore").touch()
            result = unique_dest_path(Path(d), ".gitignore")
            assert result == Path(d) / ".gitignore (1)"


# ---------------------------------------------------------------------------
# _is_valid_external_drop
# ---------------------------------------------------------------------------
class TestIsValidExternalDrop:
    def _make_mixin(self, workspace_root):
        """Create a minimal mixin with a single workspace root."""
        mixin = object.__new__(TreePanelDragMixin)
        root_item = TreeItem(
            name=workspace_root.name,
            path=workspace_root,
            is_dir=True,
        )
        mixin.roots = [root_item]
        return mixin

    def test_drop_into_directory(self, tmp_path):
        mixin = self._make_mixin(tmp_path)
        sub = tmp_path / "sub"
        sub.mkdir()
        target = TreeItem(name="sub", path=sub, is_dir=True)
        assert mixin._is_valid_external_drop(target, "into") is True

    def test_drop_after_file_in_workspace(self, tmp_path):
        mixin = self._make_mixin(tmp_path)
        f = tmp_path / "file.txt"
        f.touch()
        target = TreeItem(name="file.txt", path=f, is_dir=False)
        assert mixin._is_valid_external_drop(target, "after") is True

    def test_reject_into_file(self, tmp_path):
        mixin = self._make_mixin(tmp_path)
        f = tmp_path / "file.txt"
        f.touch()
        target = TreeItem(name="file.txt", path=f, is_dir=False)
        assert mixin._is_valid_external_drop(target, "into") is False

    def test_reject_outside_workspace(self, tmp_path):
        mixin = self._make_mixin(tmp_path)
        outside = Path("/tmp/outside_workspace")
        target = TreeItem(name="outside", path=outside, is_dir=True)
        assert mixin._is_valid_external_drop(target, "into") is False

    def test_reject_none_item(self, tmp_path):
        mixin = self._make_mixin(tmp_path)
        assert mixin._is_valid_external_drop(None, "into") is False


# ---------------------------------------------------------------------------
# _copy_external_files
# ---------------------------------------------------------------------------
class TestCopyExternalFiles:
    def _make_mixin(self, workspace_root, target_item, position):
        """Create a minimal mixin wired for copy."""
        mixin = object.__new__(TreePanelDragMixin)
        root_item = TreeItem(
            name=workspace_root.name,
            path=workspace_root,
            is_dir=True,
        )
        mixin.roots = [root_item]
        mixin._pending_drop = MagicMock()
        mixin._pending_drop_info = (target_item, position)
        mixin._pending_drop_stream = None
        mixin._active_drop = None
        mixin._drop_target_item = None
        mixin._drop_position = None
        mixin._drag_source_item = None
        mixin._drag_activated = False
        mixin._request_redraw = MagicMock()
        mixin.tree_view = MagicMock()
        return mixin

    def test_copy_single_file(self, tmp_path):
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        src_file = src_dir / "photo.png"
        src_file.write_bytes(b"\x89PNG")

        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()
        target = TreeItem(name="dest", path=dest_dir, is_dir=True)

        mixin = self._make_mixin(tmp_path, target, "into")
        mixin._copy_external_files([src_file])

        assert (dest_dir / "photo.png").exists()
        assert (dest_dir / "photo.png").read_bytes() == b"\x89PNG"

    def test_copy_auto_renames_on_conflict(self, tmp_path):
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        src_file = src_dir / "stuff.png"
        src_file.write_bytes(b"new")

        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()
        (dest_dir / "stuff.png").write_bytes(b"existing")

        target = TreeItem(name="dest", path=dest_dir, is_dir=True)
        mixin = self._make_mixin(tmp_path, target, "into")
        mixin._copy_external_files([src_file])

        assert (dest_dir / "stuff.png").read_bytes() == b"existing"
        assert (dest_dir / "stuff (1).png").exists()
        assert (dest_dir / "stuff (1).png").read_bytes() == b"new"

    def test_copy_increments_counter(self, tmp_path):
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        src_file = src_dir / "stuff.png"
        src_file.write_bytes(b"third")

        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()
        (dest_dir / "stuff.png").write_bytes(b"first")
        (dest_dir / "stuff (1).png").write_bytes(b"second")

        target = TreeItem(name="dest", path=dest_dir, is_dir=True)
        mixin = self._make_mixin(tmp_path, target, "into")
        mixin._copy_external_files([src_file])

        assert (dest_dir / "stuff (2).png").exists()
        assert (dest_dir / "stuff (2).png").read_bytes() == b"third"

    def test_copy_directory(self, tmp_path):
        src_dir = tmp_path / "src_folder"
        src_dir.mkdir()
        (src_dir / "inner.txt").write_text("hello")

        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()
        target = TreeItem(name="dest", path=dest_dir, is_dir=True)

        mixin = self._make_mixin(tmp_path, target, "into")
        mixin._copy_external_files([src_dir])

        assert (dest_dir / "src_folder" / "inner.txt").read_text() == "hello"

    def test_copy_to_parent_on_after_position(self, tmp_path):
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        src_file = src_dir / "photo.png"
        src_file.write_bytes(b"data")

        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()
        existing = dest_dir / "other.txt"
        existing.touch()
        target = TreeItem(name="other.txt", path=existing, is_dir=False)

        mixin = self._make_mixin(tmp_path, target, "after")
        mixin._copy_external_files([src_file])

        # "after" a file → copies into that file's parent directory
        assert (dest_dir / "photo.png").exists()

    def test_copy_missing_source_skipped(self, tmp_path):
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()
        target = TreeItem(name="dest", path=dest_dir, is_dir=True)

        mixin = self._make_mixin(tmp_path, target, "into")
        mixin._copy_external_files([Path("/nonexistent/file.txt")])

        # No files copied, but no crash
        assert list(dest_dir.iterdir()) == []

    def test_copy_multiple_files(self, tmp_path):
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "a.txt").write_text("aaa")
        (src_dir / "b.txt").write_text("bbb")

        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()
        target = TreeItem(name="dest", path=dest_dir, is_dir=True)

        mixin = self._make_mixin(tmp_path, target, "into")
        mixin._copy_external_files([src_dir / "a.txt", src_dir / "b.txt"])

        assert (dest_dir / "a.txt").read_text() == "aaa"
        assert (dest_dir / "b.txt").read_text() == "bbb"

    def test_refreshes_tree_after_copy(self, tmp_path):
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "f.txt").touch()

        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()
        target = TreeItem(name="dest", path=dest_dir, is_dir=True)

        mixin = self._make_mixin(tmp_path, target, "into")
        mixin._copy_external_files([src_dir / "f.txt"])

        mixin.tree_view.refresh.assert_called_once()


# ---------------------------------------------------------------------------
# _finish_external_drop
# ---------------------------------------------------------------------------
class TestFinishExternalDrop:
    def _make_mixin(self):
        mixin = object.__new__(TreePanelDragMixin)
        mixin._pending_drop = MagicMock()
        mixin._pending_drop_info = ("item", "into")
        mixin._pending_drop_stream = MagicMock()
        mixin._active_drop = MagicMock()
        mixin._drop_target_item = MagicMock()
        mixin._drop_position = "into"
        mixin._drag_source_item = None
        mixin._drag_activated = False
        mixin._request_redraw = MagicMock()
        return mixin

    def test_clears_state_on_success(self):
        mixin = self._make_mixin()
        mixin._finish_external_drop(True)

        assert mixin._pending_drop is None
        assert mixin._pending_drop_info is None
        assert mixin._pending_drop_stream is None
        assert mixin._active_drop is None

    def test_clears_state_on_failure(self):
        mixin = self._make_mixin()
        mixin._finish_external_drop(False)

        assert mixin._pending_drop is None
        assert mixin._pending_drop_info is None

    def test_calls_drop_finish_with_action_on_success(self):
        mixin = self._make_mixin()
        drop = mixin._pending_drop
        mixin._finish_external_drop(True)

        from gi.repository import Gdk

        drop.finish.assert_called_once_with(Gdk.DragAction.COPY)

    def test_calls_drop_finish_with_zero_on_failure(self):
        mixin = self._make_mixin()
        drop = mixin._pending_drop
        mixin._finish_external_drop(False)

        drop.finish.assert_called_once_with(0)

    def test_handles_no_pending_drop(self):
        mixin = self._make_mixin()
        mixin._pending_drop = None
        # Should not raise
        mixin._finish_external_drop(False)
