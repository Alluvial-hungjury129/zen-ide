"""
Clipboard and copy-paste logic for the tree view.
"""

import shutil
from pathlib import Path

from gi.repository import Gdk


class TreeClipboardMixin:
    """Mixin providing clipboard / copy-paste operations for TreeView."""

    _copied_item_paths: list[Path] | None = None

    def _action_copy_path(self, item):
        """Copy path to clipboard."""
        clipboard = Gdk.Display.get_default().get_clipboard()
        selection = self._get_action_items(item)
        path_str = "\n".join(str(selected.path) for selected in selection)
        clipboard.set(path_str)
        from shared.utils import copy_to_system_clipboard

        copy_to_system_clipboard(path_str)

    def _action_copy_item(self, item):
        """Copy item path to internal clipboard for paste/duplicate."""
        selection = [selected for selected in self._get_action_items(item) if selected.path.exists()]
        self._copied_item_paths = [selected.path for selected in selection]
        if not self._copied_item_paths:
            return

        if len(self._copied_item_paths) == 1:
            pass
        else:
            pass

    def _action_paste_item(self, item):
        """Paste copied item into the target location.

        If target is the same folder as the source, duplicate with ' copy' suffix.
        If target is a different folder, copy the file/folder there.
        """
        copied_paths = [path for path in (self._copied_item_paths or []) if path.exists()]
        if not copied_paths:
            return

        target_dir = item.path if item.is_dir else item.path.parent

        try:
            for src in copied_paths:
                dest = self._generate_copy_name(src, target_dir)
                if src.is_dir():
                    shutil.copytree(src, dest)
                else:
                    shutil.copy2(src, dest)
            self.refresh()
            if len(copied_paths) == 1:
                pass
            else:
                pass
        except Exception:
            pass

    def _generate_copy_name(self, src: Path, target_dir: Path) -> Path:
        """Generate a copy name: 'file copy.txt', 'file copy 2.txt', etc."""
        name = src.name
        is_dir = src.is_dir()

        if is_dir:
            base = name
            ext = ""
        else:
            # Split at the first dot for dotfiles, last dot otherwise
            if name.startswith("."):
                base = name
                ext = ""
            else:
                stem = src.stem
                ext = src.suffix
                base = stem

        candidate = target_dir / name
        if not candidate.exists():
            return candidate

        # Try "base copy.ext"
        copy_name = f"{base} copy{ext}"
        candidate = target_dir / copy_name
        if not candidate.exists():
            return candidate

        # Try "base copy N.ext" starting from 2
        n = 2
        while True:
            copy_name = f"{base} copy {n}{ext}"
            candidate = target_dir / copy_name
            if not candidate.exists():
                return candidate
            n += 1
