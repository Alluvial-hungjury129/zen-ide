"""
CustomTreePanel drag-and-drop mixin.
"""

import shutil
from pathlib import Path
from urllib.parse import unquote, urlparse

from gi.repository import Gdk, GLib, Gtk


def parse_uri_list(data: str) -> list[Path]:
    """Parse ``text/uri-list`` data into a list of local file paths.

    Handles macOS Finder's habit of URL-encoding the *entire* URI
    (``file%3A///path`` instead of ``file:///path``).
    """
    paths: list[Path] = []
    for line in data.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        line = unquote(line)
        parsed = urlparse(line)
        if parsed.scheme == "file":
            paths.append(Path(unquote(parsed.path)))
    return paths


def unique_dest_path(dest_dir: Path, name: str) -> Path:
    """Return *dest_dir / name*, auto-renaming if it already exists.

    ``stuff.png`` → ``stuff (1).png`` → ``stuff (2).png`` …
    """
    dest = dest_dir / name
    if not dest.exists():
        return dest
    stem = Path(name).stem
    suffix = Path(name).suffix
    counter = 1
    while dest.exists():
        dest = dest_dir / f"{stem} ({counter}){suffix}"
        counter += 1
    return dest


class TreePanelDragMixin:
    """Mixin providing drag-and-drop methods for CustomTreePanel."""

    _DRAG_THRESHOLD = 8  # Minimum pixels before drag activates

    def _on_gesture_drag_begin(self, gesture, start_x, start_y):
        """Identify the source item when drag starts."""
        if self._is_scrolling:
            gesture.set_state(Gtk.EventSequenceState.DENIED)
            return
        item = self._get_item_at_y(start_y)
        if not item:
            gesture.set_state(Gtk.EventSequenceState.DENIED)
            return
        self._drag_source_item = item
        self._drag_start_y = start_y
        vadj = self.get_vadjustment()
        self._drag_start_scroll_y = vadj.get_value() if vadj else 0

    def _on_gesture_drag_update(self, gesture, offset_x, offset_y):
        """Update drop indicator during drag."""
        if not self._drag_source_item:
            return
        # Cancel drag if tree scrolled since press (scroll shifts coordinates)
        vadj = self.get_vadjustment()
        if vadj and abs(vadj.get_value() - self._drag_start_scroll_y) > 2:
            self._cleanup_drag_state()
            return
        if abs(offset_x) < self._DRAG_THRESHOLD and abs(offset_y) < self._DRAG_THRESHOLD:
            return
        self._drag_activated = True
        y = self._drag_start_y + offset_y
        item, position = self._compute_drop_position(y)
        if item and self._is_valid_drop(item, position):
            self._drop_target_item = item
            self._drop_position = position
        else:
            self._drop_target_item = None
            self._drop_position = None
        self._request_redraw()

    def _on_gesture_drag_end(self, gesture, offset_x, offset_y):
        """Perform file move when drag ends on a valid target."""
        if not self._drag_source_item or not self._drag_activated:
            self._cleanup_drag_state()
            return

        y = self._drag_start_y + offset_y
        item, position = self._compute_drop_position(y)

        if not item or not self._is_valid_drop(item, position):
            self._cleanup_drag_state()
            return

        src_path = self._drag_source_item.path
        if position == "into":
            dest_dir = item.path
        else:
            dest_dir = item.path.parent

        dest_path = dest_dir / src_path.name

        if dest_path.exists():
            self._cleanup_drag_state()
            return

        try:
            shutil.move(str(src_path), str(dest_path))
            self._cleanup_drag_state()
            self.tree_view.refresh()
        except Exception:
            self._cleanup_drag_state()

    def _cleanup_drag_state(self):
        """Reset all drag-and-drop state."""
        self._drag_source_item = None
        self._drop_target_item = None
        self._drop_position = None
        self._drag_activated = False
        self._request_redraw()

    def _compute_drop_position(self, y):
        """Compute drop target item and position from y coordinate."""
        item = self._get_item_at_y(y)
        if not item:
            return None, None
        # Calculate position within the row
        index = int(y / self.row_height)
        row_y = y - index * self.row_height
        fraction = row_y / self.row_height
        if item.is_dir:
            # For folders: top 25% = before, middle 50% = into, bottom 25% = after
            if fraction < 0.25:
                return item, "before"
            elif fraction > 0.75:
                return item, "after"
            else:
                return item, "into"
        else:
            # For files: top half = before, bottom half = after
            if fraction < 0.5:
                return item, "before"
            else:
                return item, "after"

    def _is_valid_drop(self, target_item, position):
        """Check if drop is valid (can't drop folder into itself or children)."""
        if not self._drag_source_item or not target_item:
            return False
        src = self._drag_source_item
        # Can't drop onto itself
        if src.path == target_item.path:
            return False
        # Determine destination directory
        if position == "into":
            dest_dir = target_item.path
        else:
            dest_dir = target_item.path.parent
        # Can't drop into same parent at same level (no-op)
        if src.path.parent == dest_dir:
            return False
        # Both source and destination must be within the same workspace root
        src_root = None
        dest_root = None
        for root in self.roots:
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
        # Can't drop a folder into itself or any descendant
        if src.is_dir:
            try:
                dest_dir.resolve().relative_to(src.path.resolve())
                return False
            except ValueError:
                pass
        return True

    # --- External file drop (from Finder/file manager) ---

    def _setup_external_drop_target(self):
        """Setup DropTargetAsync for accepting files from outside the IDE.

        Accepts all content formats (``None``) to maximise macOS
        compatibility.  Stores the ``Gdk.Drop`` reference early in
        ``drag-enter`` / ``drag-motion`` to prevent Python's GC from
        finalising the C object before macOS completes the drag protocol.
        On drop, tries ``Gdk.FileList`` via ``read_value_async`` first,
        then falls back to raw ``text/uri-list`` via ``read_async``.
        """
        drop_target = Gtk.DropTargetAsync.new(None, Gdk.DragAction.COPY)
        drop_target.connect("drag-enter", self._on_external_drag_enter)
        drop_target.connect("drag-motion", self._on_external_drop_motion)
        drop_target.connect("drag-leave", self._on_external_drop_leave)
        drop_target.connect("drop", self._on_external_drop)
        self.drawing_area.add_controller(drop_target)
        self._active_drop = None

    def _on_external_drag_enter(self, _drop_target, drop, x, y):
        """Store drop reference on enter to prevent Python GC."""
        self._active_drop = drop
        return Gdk.DragAction.COPY

    def _on_external_drop_motion(self, _drop_target, drop, x, y):
        """Update drop indicator during external drag."""
        self._active_drop = drop
        item, position = self._compute_drop_position(y)
        if item and self._is_valid_external_drop(item, position):
            self._drop_target_item = item
            self._drop_position = position
            self._request_redraw()
            return Gdk.DragAction.COPY
        self._drop_target_item = None
        self._drop_position = None
        self._request_redraw()
        return 0

    def _on_external_drop_leave(self, _drop_target, _drop):
        """Clear drop indicator when external drag leaves."""
        self._drop_target_item = None
        self._drop_position = None
        self._request_redraw()

    def _on_external_drop(self, _drop_target, drop, x, y):
        """Handle files dropped from outside the IDE."""
        self._pending_drop = drop

        item, position = self._compute_drop_position(y)
        if not item or not self._is_valid_external_drop(item, position):
            self._finish_external_drop(False)
            return True

        self._pending_drop_info = (item, position)

        # Strategy 1: Gdk.FileList (native file type)
        self._try_filelist_read()
        return True

    # -- read strategies ------------------------------------------------

    def _try_filelist_read(self):
        """Try reading drop data as ``Gdk.FileList``."""
        drop = self._pending_drop
        if not drop:
            self._finish_external_drop(False)
            return
        try:
            drop.read_value_async(
                Gdk.FileList.__gtype__,
                GLib.PRIORITY_DEFAULT,
                None,
                self._on_filelist_ready,
            )
        except Exception:
            self._try_uri_list_read()

    def _on_filelist_ready(self, drop, result, *_args):
        """Async callback for ``Gdk.FileList`` read."""
        try:
            value = drop.read_value_finish(result)
            if value is not None:
                files = value.get_files() if hasattr(value, "get_files") else []
                paths = [Path(f.get_path()) for f in files if f.get_path()]
                if paths:
                    self._copy_external_files(paths)
                    return
        except Exception:
            pass
        self._try_uri_list_read()

    def _try_uri_list_read(self):
        """Fallback: read drop data as ``text/uri-list``."""
        drop = self._pending_drop
        if not drop:
            self._finish_external_drop(False)
            return
        try:
            drop.read_async(
                ["text/uri-list"],
                GLib.PRIORITY_DEFAULT,
                None,
                self._on_uri_stream_ready,
            )
        except Exception:
            self._finish_external_drop(False)

    def _on_uri_stream_ready(self, drop, result, *_args):
        """Async callback: input stream opened for URI list data."""
        try:
            stream, _mime = drop.read_finish(result)
        except Exception:
            self._finish_external_drop(False)
            return

        self._pending_drop_stream = stream
        stream.read_bytes_async(
            65536,
            GLib.PRIORITY_DEFAULT,
            None,
            self._on_uri_bytes_read,
        )

    def _on_uri_bytes_read(self, stream, result, *_args):
        """Async callback: raw URI bytes received — parse and copy files."""
        try:
            gbytes = stream.read_bytes_finish(result)
            data = gbytes.get_data().decode("utf-8", errors="replace") if gbytes and gbytes.get_size() > 0 else ""
        except Exception:
            data = ""
        finally:
            try:
                stream.close(None)
            except Exception:
                pass

        if not data:
            self._finish_external_drop(False)
            return

        paths = parse_uri_list(data)

        if paths:
            self._copy_external_files(paths)
        else:
            self._finish_external_drop(False)

    # -- copy & finish --------------------------------------------------

    def _copy_external_files(self, paths):
        """Copy the given source paths into the drop target directory."""
        info = getattr(self, "_pending_drop_info", None)
        if not info or not paths:
            self._finish_external_drop(False)
            return

        item, position = info
        dest_dir = item.path if position == "into" else item.path.parent

        copied = False
        for src_path in paths:
            if not src_path.exists():
                continue
            dest_path = unique_dest_path(dest_dir, src_path.name)
            try:
                if src_path.is_dir():
                    shutil.copytree(str(src_path), str(dest_path))
                else:
                    shutil.copy2(str(src_path), str(dest_path))
                copied = True
            except Exception:
                pass

        self._finish_external_drop(copied)
        if copied:
            self.tree_view.refresh()

    def _finish_external_drop(self, success):
        """Complete the GDK drop protocol and clean up state."""
        drop = getattr(self, "_pending_drop", None)
        self._pending_drop = None
        self._pending_drop_info = None
        self._pending_drop_stream = None
        self._active_drop = None
        if drop:
            try:
                drop.finish(Gdk.DragAction.COPY if success else 0)
            except Exception:
                pass
        self._cleanup_drag_state()

    def _is_valid_external_drop(self, target_item, position):
        """Check if external drop target is valid (must be within workspace)."""
        if not target_item:
            return False
        if position == "into":
            dest_dir = target_item.path
            if not target_item.is_dir:
                return False
        else:
            dest_dir = target_item.path.parent
        for root in self.roots:
            root_resolved = root.path.resolve()
            try:
                dest_dir.resolve().relative_to(root_resolved)
                return True
            except ValueError:
                pass
        return False
