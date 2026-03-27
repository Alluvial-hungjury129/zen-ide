"""Cmd+hover underline and word navigation helpers for EditorTab."""

from gi.repository import Gtk, Pango

from themes import get_theme

from .core import _iter_at_line_offset


class EditorTabHoverMixin:
    """Mixin providing Cmd+hover underline and navigability detection for EditorTab."""

    def _setup_hover_underline(self):
        """Setup Cmd+hover underline for navigable symbols."""

        # Get theme accent color for the underline
        theme = get_theme()

        # Create underline tag for hover effect with theme accent color
        self._link_tag = self.buffer.create_tag(
            "navigable_link",
            underline=Pango.Underline.SINGLE,
            foreground=theme.accent_color,
        )

        # Track hover state using marks (survive buffer modifications)
        self._hover_underline_start_mark = None
        self._hover_underline_end_mark = None
        self._cmd_held = False

        # Motion controller for hover
        motion_controller = Gtk.EventControllerMotion()
        motion_controller.connect("motion", self._on_hover_motion)
        motion_controller.connect("leave", self._on_hover_leave)
        self.view.add_controller(motion_controller)

        # Key controller to track Cmd key press/release
        key_controller = Gtk.EventControllerKey()
        key_controller.connect("key-pressed", self._on_cmd_key_pressed)
        key_controller.connect("key-released", self._on_cmd_key_released)
        self.view.add_controller(key_controller)

    def _on_cmd_key_pressed(self, controller, keyval, keycode, state):
        """Track Cmd key press for hover underline."""
        import platform

        from gi.repository import Gdk

        # Check for Cmd (macOS) or Ctrl (other platforms)
        if platform.system() == "Darwin":
            if keyval in (Gdk.KEY_Meta_L, Gdk.KEY_Meta_R):
                self._cmd_held = True
        else:
            if keyval in (Gdk.KEY_Control_L, Gdk.KEY_Control_R):
                self._cmd_held = True
        return False

    def _on_cmd_key_released(self, controller, keyval, keycode, state):
        """Track Cmd key release for hover underline."""
        import platform

        from gi.repository import Gdk

        # Check for Cmd (macOS) or Ctrl (other platforms)
        if platform.system() == "Darwin":
            if keyval in (Gdk.KEY_Meta_L, Gdk.KEY_Meta_R):
                self._cmd_held = False
                self._clear_hover_underline()
        else:
            if keyval in (Gdk.KEY_Control_L, Gdk.KEY_Control_R):
                self._cmd_held = False
                self._clear_hover_underline()
        return False

    def _on_hover_motion(self, controller, x, y):
        """Handle mouse motion for Cmd+hover underline."""
        import platform

        from gi.repository import Gdk

        # Get modifier state
        state = controller.get_current_event_state()

        # Check for Cmd (macOS) or Ctrl (other platforms) modifier
        if platform.system() == "Darwin":
            is_cmd_held = bool(state & Gdk.ModifierType.META_MASK)
        else:
            is_cmd_held = bool(state & Gdk.ModifierType.CONTROL_MASK)

        self._cmd_held = is_cmd_held

        if not is_cmd_held:
            self._clear_hover_underline()
            # Show pointer cursor when hovering over diagnostic underlines
            if hasattr(self, "_diag_error_tag"):
                bx, by = self.view.window_to_buffer_coords(Gtk.TextWindowType.WIDGET, int(x), int(y))
                over, it = self.view.get_iter_at_location(bx, by)
                if over and (it.has_tag(self._diag_error_tag) or it.has_tag(self._diag_warning_tag)):
                    cursor = Gdk.Cursor.new_from_name("pointer", None)
                    self.view.set_cursor(cursor)
                    return
            self.view.set_cursor(None)
            return

        # Convert to buffer coordinates
        bx, by = self.view.window_to_buffer_coords(Gtk.TextWindowType.WIDGET, int(x), int(y))
        over_text, it = self.view.get_iter_at_location(bx, by)

        if not over_text:
            self._clear_hover_underline()
            self.view.set_cursor(None)
            return

        # Try file path detection first
        path_result = self._get_file_path_at_iter(it)
        if path_result:
            _path_str, s, e = path_result
            line_num = it.get_line()

            start = _iter_at_line_offset(self.buffer, line_num, s)
            end = _iter_at_line_offset(self.buffer, line_num, e)

            if (
                self._hover_underline_start_mark is not None
                and self.buffer.get_iter_at_mark(self._hover_underline_start_mark).equal(start)
                and self._hover_underline_end_mark is not None
                and self.buffer.get_iter_at_mark(self._hover_underline_end_mark).equal(end)
            ):
                return

            self._clear_hover_underline()
            # Rebuild iterators — _clear_hover_underline's remove_tag may
            # invalidate outstanding iterators on GtkSourceBuffer.
            start = _iter_at_line_offset(self.buffer, line_num, s)
            end = _iter_at_line_offset(self.buffer, line_num, e)
            self.buffer.apply_tag(self._link_tag, start, end)
            self._hover_underline_start_mark = self.buffer.create_mark(None, start, True)
            self._hover_underline_end_mark = self.buffer.create_mark(None, end, False)

            from gi.repository import Gdk

            cursor = Gdk.Cursor.new_from_name("pointer", None)
            self.view.set_cursor(cursor)
            return

        # Skip words inside strings or comments (not navigable).
        # iter_has_context_class can trigger lazy re-highlighting which
        # changes the buffer stamp and invalidates all outstanding iterators.
        # Store the offset so we can rebuild a fresh iterator afterwards.
        iter_offset = it.get_offset()
        if hasattr(self.buffer, "iter_has_context_class"):
            if self.buffer.iter_has_context_class(it, "string") or self.buffer.iter_has_context_class(
                self.buffer.get_iter_at_offset(iter_offset), "comment"
            ):
                self._clear_hover_underline()
                self.view.set_cursor(None)
                return

        # Rebuild iterator — iter_has_context_class above may have triggered
        # lazy re-highlighting that invalidated the previous iterator.
        it = self.buffer.get_iter_at_offset(iter_offset)

        # Get the word at position
        word = self._get_word_at_iter(it)
        if not word:
            self._clear_hover_underline()
            self.view.set_cursor(None)
            return

        # Check if word is navigable
        if not self._is_word_navigable(word):
            self._clear_hover_underline()
            self.view.set_cursor(None)
            return

        # Get word boundaries using identifier-aware logic (underscores included)
        line_start = it.copy()
        line_start.set_line_offset(0)
        line_end_iter = it.copy()
        if not line_end_iter.ends_line():
            line_end_iter.forward_to_line_end()
        line_content = self.buffer.get_text(line_start, line_end_iter, True)
        col = it.get_line_offset()

        s = col
        while s > 0 and (line_content[s - 1].isalnum() or line_content[s - 1] == "_"):
            s -= 1
        e = col
        while e < len(line_content) and (line_content[e].isalnum() or line_content[e] == "_"):
            e += 1

        line_num = it.get_line()
        start = _iter_at_line_offset(self.buffer, line_num, s)
        end = _iter_at_line_offset(self.buffer, line_num, e)

        # Check if we're already underlining this word
        if (
            self._hover_underline_start_mark is not None
            and self.buffer.get_iter_at_mark(self._hover_underline_start_mark).equal(start)
            and self._hover_underline_end_mark is not None
            and self.buffer.get_iter_at_mark(self._hover_underline_end_mark).equal(end)
        ):
            return

        # Clear previous underline and apply new one
        self._clear_hover_underline()
        # Rebuild iterators — _clear_hover_underline's remove_tag may
        # invalidate outstanding iterators on GtkSourceBuffer.
        start = _iter_at_line_offset(self.buffer, line_num, s)
        end = _iter_at_line_offset(self.buffer, line_num, e)
        self.buffer.apply_tag(self._link_tag, start, end)
        self._hover_underline_start_mark = self.buffer.create_mark(None, start, True)
        self._hover_underline_end_mark = self.buffer.create_mark(None, end, False)

        # Change cursor to pointing hand
        from gi.repository import Gdk

        cursor = Gdk.Cursor.new_from_name("pointer", None)
        self.view.set_cursor(cursor)

    def _on_hover_leave(self, controller):
        """Handle mouse leaving the view."""
        self._clear_hover_underline()
        self.view.set_cursor(None)

    def _clear_hover_underline(self):
        """Remove the hover underline tag."""
        if self._hover_underline_start_mark is not None and self._hover_underline_end_mark is not None:
            start = self.buffer.get_iter_at_mark(self._hover_underline_start_mark)
            end = self.buffer.get_iter_at_mark(self._hover_underline_end_mark)
            self.buffer.remove_tag(self._link_tag, start, end)
            self.buffer.delete_mark(self._hover_underline_start_mark)
            self.buffer.delete_mark(self._hover_underline_end_mark)
        self._hover_underline_start_mark = None
        self._hover_underline_end_mark = None

    # File path characters for path detection
    _FILE_PATH_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-.~/#")

    def _get_file_path_at_iter(self, it):
        """Get file path string and its (start_col, end_col) at iterator position, or None."""
        line_start = it.copy()
        line_start.set_line_offset(0)
        line_end = it.copy()
        if not line_end.ends_line():
            line_end.forward_to_line_end()

        line_content = self.buffer.get_text(line_start, line_end, True)
        col = it.get_line_offset()

        if col >= len(line_content) or line_content[col] not in self._FILE_PATH_CHARS:
            return None

        s = col
        e = col
        while s > 0 and line_content[s - 1] in self._FILE_PATH_CHARS:
            s -= 1
        while e < len(line_content) and line_content[e] in self._FILE_PATH_CHARS:
            e += 1

        path_str = line_content[s:e].rstrip(".")
        if not path_str or "/" not in path_str:
            return None

        return path_str, s, e

    def _get_word_at_iter(self, it):
        """Get the word at the given iterator position."""
        # Get line content
        line_start = it.copy()
        line_start.set_line_offset(0)
        line_end = it.copy()
        if not line_end.ends_line():
            line_end.forward_to_line_end()

        line_content = self.buffer.get_text(line_start, line_end, True)
        col = it.get_line_offset()

        if col >= len(line_content):
            return ""

        # Find word boundaries (identifier characters)
        start = col
        end = col

        while start > 0 and (line_content[start - 1].isalnum() or line_content[start - 1] == "_"):
            start -= 1

        while end < len(line_content) and (line_content[end].isalnum() or line_content[end] == "_"):
            end += 1

        if start < end:
            return line_content[start:end]
        return ""

    def _is_word_navigable(self, word: str) -> bool:
        """Check if a word is navigable (not a Python builtin, is an identifier)."""
        if not word or not word[0].isalpha() and word[0] != "_":
            return False

        # Python builtins that can't be navigated to
        UNNAVIGABLE_BUILTINS = {
            "str",
            "int",
            "float",
            "bool",
            "bytes",
            "list",
            "dict",
            "set",
            "tuple",
            "object",
            "type",
            "None",
            "True",
            "False",
            "super",
            "property",
            "staticmethod",
            "classmethod",
            "isinstance",
            "issubclass",
            "hasattr",
            "getattr",
            "setattr",
            "delattr",
            "len",
            "range",
            "enumerate",
            "zip",
            "map",
            "filter",
            "sorted",
            "reversed",
            "print",
            "open",
            "input",
            "format",
            "repr",
            "id",
            "hash",
            "callable",
            "iter",
            "next",
            "all",
            "any",
            "min",
            "max",
            "sum",
            "abs",
            "round",
            "pow",
            "divmod",
            "ord",
            "chr",
            "bin",
            "hex",
            "oct",
            "ascii",
            "eval",
            "exec",
            "compile",
            "globals",
            "locals",
            "vars",
            "dir",
            "help",
            "exit",
            "quit",
            "slice",
            "Exception",
            "BaseException",
            "ValueError",
            "TypeError",
            "KeyError",
            "IndexError",
            "AttributeError",
            "ImportError",
            "FileNotFoundError",
            "OSError",
            "RuntimeError",
            "StopIteration",
            "NotImplementedError",
            "self",
            "cls",
            "if",
            "else",
            "elif",
            "for",
            "while",
            "try",
            "except",
            "finally",
            "with",
            "as",
            "import",
            "from",
            "class",
            "def",
            "return",
            "yield",
            "raise",
            "pass",
            "break",
            "continue",
            "and",
            "or",
            "not",
            "in",
            "is",
            "lambda",
            "assert",
            "global",
            "nonlocal",
            "del",
            "async",
            "await",
        }

        return word not in UNNAVIGABLE_BUILTINS
