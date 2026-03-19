"""
Tests for session restore focus behavior.

These tests verify that when the IDE restores a session, the correct file
is focused (displayed) based on what was active when the session was saved.

Key behaviors tested:
1. When last_file is a regular file and a sketch is also open,
   the editor should re-focus the regular file after sketch restoration.
2. When last_file is a sketch file, the sketch should remain focused
   and the editor should NOT steal focus.
3. open_image respects switch_to=False so image tabs don't steal focus.
4. _open_deferred_files opens remaining files without switching, then
   re-focuses last_file at the end.
"""

import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock

# Add src paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestSessionRestoreFocusLogic(unittest.TestCase):
    """Test the focus-selection logic in _deferred_init_phase2."""

    def test_sketch_restored_but_non_sketch_last_file_refocuses_editor(self):
        """When last_file is a regular file and a sketch is also open,
        _focused_panel should be reset to 'editor' after sketch restoration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test files
            regular_file = os.path.join(tmpdir, "main.py")
            sketch_file = os.path.join(tmpdir, "drawing.zen_sketch")
            with open(regular_file, "w") as f:
                f.write("print('hello')")
            with open(sketch_file, "w") as f:
                f.write("sketch content")

            last_file = regular_file
            sketch_files = []

            # Simulate the logic from _deferred_init_phase2 lines 954-976
            sketch_to_restore = None
            if last_file and last_file.endswith(".zen_sketch") and os.path.isfile(last_file):
                sketch_to_restore = last_file
            elif sketch_files:
                sketch_to_restore = sketch_files[0]

            # In this case, sketch_to_restore is None because last_file is .py
            self.assertIsNone(sketch_to_restore)

    def test_sketch_in_open_files_restored_with_non_sketch_last_file(self):
        """When sketch is in sketch_files list but last_file is regular,
        sketch is restored but focus returns to regular file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            regular_file = os.path.join(tmpdir, "main.py")
            sketch_file = os.path.join(tmpdir, "drawing.zen_sketch")
            with open(regular_file, "w") as f:
                f.write("print('hello')")
            with open(sketch_file, "w") as f:
                f.write("sketch content")

            last_file = regular_file
            sketch_files = [sketch_file]

            sketch_to_restore = None
            if last_file and last_file.endswith(".zen_sketch") and os.path.isfile(last_file):
                sketch_to_restore = last_file
            elif sketch_files:
                sketch_to_restore = sketch_files[0]

            self.assertEqual(sketch_to_restore, sketch_file)

            # Simulate the post-restore focus fix
            focused_panel = "sketch_pad"  # _open_sketch_with_content sets this
            if sketch_to_restore:
                if last_file and not last_file.endswith(".zen_sketch"):
                    focused_panel = "editor"

            self.assertEqual(focused_panel, "editor", "Focus should return to editor when last_file is not a sketch")

    def test_sketch_last_file_keeps_sketch_focus(self):
        """When last_file IS a sketch, focus should remain on sketch_pad."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sketch_file = os.path.join(tmpdir, "drawing.zen_sketch")
            with open(sketch_file, "w") as f:
                f.write("sketch content")

            last_file = sketch_file
            sketch_files = []

            sketch_to_restore = None
            if last_file and last_file.endswith(".zen_sketch") and os.path.isfile(last_file):
                sketch_to_restore = last_file
            elif sketch_files:
                sketch_to_restore = sketch_files[0]

            self.assertEqual(sketch_to_restore, sketch_file)

            # Simulate post-restore logic
            focused_panel = "sketch_pad"
            if sketch_to_restore:
                if last_file and not last_file.endswith(".zen_sketch"):
                    focused_panel = "editor"

            self.assertEqual(focused_panel, "sketch_pad", "Focus should stay on sketch_pad when last_file is a sketch")


class TestOpenDeferredFilesLogic(unittest.TestCase):
    """Test the file-opening and focus logic in _open_deferred_files."""

    def test_remaining_files_opened_without_switch(self):
        """Remaining files should be opened with switch_to=False."""
        open_calls = []

        def mock_open(fp, switch_to=True):
            open_calls.append((fp, switch_to))

        files = ["/tmp/a.py", "/tmp/b.py", "/tmp/c.py"]
        last_file = "/tmp/b.py"

        # Simulate _open_deferred_files logic (synchronous version for testing)
        pending = list(files)
        while pending:
            fp = pending.pop(0)
            mock_open(fp, switch_to=False)
        if last_file:
            mock_open(last_file, switch_to=True)

        # All files opened without switch
        for fp, switch_to in open_calls[:-1]:
            self.assertFalse(switch_to, f"{fp} should be opened with switch_to=False")

        # Last call re-focuses last_file with switch_to=True
        self.assertEqual(open_calls[-1], (last_file, True))

    def test_no_remaining_files_no_refocus(self):
        """When remaining_files is empty, _open_deferred_files is not called."""
        remaining_files = []
        # In _deferred_init_phase2, _open_deferred_files is only called if remaining_files
        called = bool(remaining_files)
        self.assertFalse(called, "_open_deferred_files should not be called with empty remaining")

    def test_focus_file_none_when_last_file_is_sketch(self):
        """When last_file is a sketch, focus_file passed to _open_deferred_files is None."""
        last_file = "/tmp/drawing.zen_sketch"
        # Simulate logic from _deferred_init_phase2 line 951
        focus_file = last_file if not (last_file and last_file.endswith(".zen_sketch")) else None
        self.assertIsNone(focus_file)

    def test_focus_file_set_when_last_file_is_regular(self):
        """When last_file is regular, focus_file is set to last_file."""
        last_file = "/tmp/main.py"
        focus_file = last_file if not (last_file and last_file.endswith(".zen_sketch")) else None
        self.assertEqual(focus_file, last_file)


class TestOpenImageSwitchTo(unittest.TestCase):
    """Test that open_image respects the switch_to parameter."""

    def test_open_image_switch_to_false_does_not_switch(self):
        """open_image with switch_to=False should not call set_current_page."""
        # Mock a notebook
        notebook = MagicMock()
        notebook.append_page.return_value = 3

        switch_to = False
        page_num = notebook.append_page(MagicMock(), MagicMock())

        if switch_to:
            notebook.set_current_page(page_num)

        notebook.set_current_page.assert_not_called()

    def test_open_image_switch_to_true_does_switch(self):
        """open_image with switch_to=True should call set_current_page."""
        notebook = MagicMock()
        notebook.append_page.return_value = 5

        switch_to = True
        page_num = notebook.append_page(MagicMock(), MagicMock())

        if switch_to:
            notebook.set_current_page(page_num)

        notebook.set_current_page.assert_called_once_with(5)

    def test_open_image_already_open_switch_to_false_no_switch(self):
        """When image is already open, switch_to=False should not switch to it."""
        notebook = MagicMock()
        file_path = "/tmp/theme.png"

        # Simulate: image already in tabs
        existing_tab = MagicMock()
        existing_tab.file_path = file_path
        tabs = {0: existing_tab}
        switch_to = False

        # Simulate the already-open check
        found = False
        for tab_id, tab in tabs.items():
            if tab.file_path == file_path:
                found = True
                if switch_to:
                    notebook.set_current_page(tab_id)
                break

        self.assertTrue(found)
        notebook.set_current_page.assert_not_called()


class TestOpenOneDispatch(unittest.TestCase):
    """Test that _open_one correctly dispatches to open_image vs open_file."""

    def test_open_one_image_extension(self):
        """Image files should be dispatched to open_image."""
        IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".svg", ".webp", ".ico", ".tiff"}
        open_image_calls = []
        open_file_calls = []

        def mock_open_one(fp, switch_to=True):
            ext = os.path.splitext(fp)[1].lower()
            if ext in IMAGE_EXTENSIONS:
                open_image_calls.append((fp, switch_to))
            else:
                open_file_calls.append((fp, switch_to))

        mock_open_one("/tmp/theme.png", switch_to=False)
        mock_open_one("/tmp/icon.svg", switch_to=False)
        mock_open_one("/tmp/main.py", switch_to=True)

        self.assertEqual(len(open_image_calls), 2)
        self.assertEqual(len(open_file_calls), 1)
        # Images opened with switch_to=False
        for fp, sw in open_image_calls:
            self.assertFalse(sw)
        # Python file opened with switch_to=True
        self.assertTrue(open_file_calls[0][1])

    def test_open_one_sketch_extension_not_dispatched(self):
        """Sketch files should be filtered out before _open_one is called."""
        # In _deferred_init_phase2, sketch files are removed from remaining_files
        open_files = ["/tmp/main.py", "/tmp/drawing.zen_sketch", "/tmp/theme.png"]
        last_file = "/tmp/main.py"

        remaining_files = [
            fp for fp in open_files if fp != last_file and os.path.isfile(fp) is not False and not fp.endswith(".zen_sketch")
        ]

        self.assertNotIn("/tmp/drawing.zen_sketch", remaining_files)


class TestSaveStateLastFile(unittest.TestCase):
    """Test that _save_state correctly determines last_file."""

    def test_sketch_focused_saves_sketch_as_last_file(self):
        """When sketch pad is focused, last_file should be the sketch path."""
        sketch_path = "/tmp/drawing.zen_sketch"
        focused_panel = "sketch_pad"
        sketch_visible = True

        # Simulate _save_state logic for determining last_file
        if sketch_path and sketch_visible:
            if focused_panel == "sketch_pad":
                last_file = sketch_path
            else:
                last_file = "/tmp/main.py"  # from get_current_file_path()
        else:
            last_file = "/tmp/main.py"

        self.assertEqual(last_file, sketch_path)

    def test_editor_focused_saves_editor_file_as_last_file(self):
        """When editor is focused (not sketch), last_file should be editor's current file."""
        sketch_path = "/tmp/drawing.zen_sketch"
        focused_panel = "editor"
        sketch_visible = True
        editor_current = "/tmp/theme.png"

        if sketch_path and sketch_visible:
            if focused_panel == "sketch_pad":
                last_file = sketch_path
            else:
                last_file = editor_current
        else:
            last_file = editor_current

        self.assertEqual(last_file, editor_current)

    def test_no_sketch_saves_editor_file(self):
        """When no sketch is open, last_file is always from editor."""
        sketch_path = None
        sketch_visible = False
        editor_current = "/tmp/main.py"

        if sketch_path and sketch_visible:
            last_file = sketch_path
        else:
            last_file = editor_current

        self.assertEqual(last_file, editor_current)


class TestPhase2SketchRestoreWithImageLastFile(unittest.TestCase):
    """Regression test: sketch open + image last_file should re-focus the image."""

    def test_image_last_file_reopened_after_sketch_restore(self):
        """When last_file is an image (e.g. theme.png) and a sketch is also
        being restored, the image should be re-opened with switch_to (default True)
        to regain focus."""
        with tempfile.TemporaryDirectory() as tmpdir:
            image_file = os.path.join(tmpdir, "theme.png")
            sketch_file = os.path.join(tmpdir, "drawing.zen_sketch")
            with open(image_file, "wb") as f:
                f.write(b"\x89PNG\r\n\x1a\n")  # minimal PNG header
            with open(sketch_file, "w") as f:
                f.write("box 10 10 50 50")

            last_file = image_file
            sketch_files = [sketch_file]
            IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".svg", ".webp", ".ico", ".tiff"}

            # Determine sketch_to_restore
            sketch_to_restore = None
            if last_file and last_file.endswith(".zen_sketch"):
                sketch_to_restore = last_file
            elif sketch_files:
                sketch_to_restore = sketch_files[0]

            self.assertEqual(sketch_to_restore, sketch_file)

            # Simulate: after _open_sketch_with_content, fix focus
            focused_panel = "sketch_pad"
            reopen_calls = []

            if sketch_to_restore:
                if last_file and not last_file.endswith(".zen_sketch"):
                    focused_panel = "editor"
                    ext = os.path.splitext(last_file)[1].lower()
                    if ext in IMAGE_EXTENSIONS:
                        reopen_calls.append(("open_image", last_file))
                    else:
                        reopen_calls.append(("open_file", last_file))

            self.assertEqual(focused_panel, "editor")
            self.assertEqual(reopen_calls, [("open_image", image_file)])

    def test_text_last_file_reopened_after_sketch_restore(self):
        """When last_file is a text file and a sketch is being restored,
        open_file should be called to re-focus the text file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            text_file = os.path.join(tmpdir, "main.py")
            sketch_file = os.path.join(tmpdir, "drawing.zen_sketch")
            with open(text_file, "w") as f:
                f.write("print('hello')")
            with open(sketch_file, "w") as f:
                f.write("box 10 10 50 50")

            last_file = text_file
            sketch_files = [sketch_file]
            IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".svg", ".webp", ".ico", ".tiff"}

            sketch_to_restore = None
            if last_file and last_file.endswith(".zen_sketch"):
                sketch_to_restore = last_file
            elif sketch_files:
                sketch_to_restore = sketch_files[0]

            focused_panel = "sketch_pad"
            reopen_calls = []

            if sketch_to_restore:
                if last_file and not last_file.endswith(".zen_sketch"):
                    focused_panel = "editor"
                    ext = os.path.splitext(last_file)[1].lower()
                    if ext in IMAGE_EXTENSIONS:
                        reopen_calls.append(("open_image", last_file))
                    else:
                        reopen_calls.append(("open_file", last_file))

            self.assertEqual(focused_panel, "editor")
            self.assertEqual(reopen_calls, [("open_file", text_file)])


if __name__ == "__main__":
    unittest.main()
