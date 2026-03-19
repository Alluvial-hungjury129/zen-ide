"""SketchTab — adapter that lets a SketchPad live inside the editor notebook.

Provides the same duck-typed interface as EditorTab (file_path, modified,
save_file, get_title, reload_file, etc.) so editor_view treats it like
any other tab.
"""

import os
import time

SKETCH_EXTENSION = ".zen_sketch"


class SketchTab:
    """Wraps a SketchPad widget so it can be managed as a regular editor tab."""

    def __init__(self, file_path: str):
        from sketch_pad import SketchPad

        self.file_path = file_path
        self.is_new = not os.path.isfile(file_path) if file_path else True
        self.modified = False
        self.original_content = ""
        self._is_sketch = True
        self._last_internal_save_time = 0.0

        self.widget = SketchPad()
        self.widget.set_hexpand(True)
        self.widget.set_vexpand(True)

        # SketchPad exposes _drawing_area for focus (used in focus tracking)
        self._drawing_area = self.widget._drawing_area

        # Callback set by EditorView (not used for sketch tabs)
        self.on_diagnostics_changed = None

        # Wire up change tracking
        self._setup_change_tracking()

    def _setup_change_tracking(self):
        """Connect to the canvas history to detect modifications."""
        canvas = self.widget._canvas_widget
        original_snapshot = canvas._snapshot_history

        def tracked_snapshot():
            original_snapshot()
            self._check_modified()

        canvas._snapshot_history = tracked_snapshot

    def _check_modified(self):
        """Compare current content with original to set modified state."""
        current = self.widget.get_content()
        was_modified = self.modified
        self.modified = current != self.original_content
        if self.modified != was_modified and hasattr(self, "_tab_button"):
            self._tab_button.set_modified(self.modified)

    # --- EditorTab-compatible interface ---

    def load_file(self, file_path: str) -> bool:
        """Load a .zen_sketch file."""
        if not file_path or not os.path.isfile(file_path):
            return False
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            if content.strip():
                self.widget.load_content(content)
            self.original_content = self.widget.get_content()
            self.file_path = file_path
            self.is_new = False
            self.modified = False
            return True
        except Exception:
            return False

    def save_file(self, file_path: str = None) -> bool:
        """Save sketch content to file."""
        path = file_path or self.file_path
        if not path:
            return False
        try:
            content = self.widget.get_content()
            self._last_internal_save_time = time.monotonic()
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            self.original_content = content
            self.file_path = path
            self.modified = False
            self.is_new = False
            return True
        except Exception:
            return False

    def reload_file(self) -> bool:
        """Reload sketch from disk."""
        if not self.file_path or not os.path.isfile(self.file_path):
            return False
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                content = f.read()
            current = self.widget.get_content()
            if content.strip() == current.strip():
                return True
            if content.strip():
                self.widget.load_content(content)
            self.original_content = self.widget.get_content()
            self.modified = False
            return True
        except Exception:
            return False

    def get_title(self) -> str:
        """Get the tab title."""
        if self.file_path:
            return os.path.basename(self.file_path)
        return "Untitled Sketch"

    def undo(self):
        self.widget.undo()
        self._check_modified()

    def redo(self):
        self.widget.redo()
        self._check_modified()
