"""
Autocomplete for Zen IDE.

Ctrl+Space triggered code completions with language-aware suggestions.
Uses a NvimPopup (anchored, non-modal) positioned at the cursor with keyboard navigation.

Language-specific providers live in separate modules:
- python_provider.py — Python completions
- js_provider.py — JavaScript/TypeScript completions
- terraform_provider.py — Terraform/HCL completions
"""

from dataclasses import dataclass
from enum import Enum as PyEnum
from pathlib import Path

from gi.repository import Gdk, GLib, Gtk

from constants import AUTOCOMPLETE_AUTO_TRIGGER_CHARS, AUTOCOMPLETE_AUTO_TRIGGER_DELAY_MS
from icons import Icons
from shared.settings import get_setting


class CompletionKind(PyEnum):
    FUNCTION = "function"
    CLASS = "class"
    PROPERTY = "property"
    KEYWORD = "keyword"
    BUILTIN = "builtin"
    SNIPPET = "snippet"
    VARIABLE = "variable"
    PARAMETER = "parameter"


COMPLETION_ICONS = {
    CompletionKind.FUNCTION: Icons.KIND_FUNCTION,
    CompletionKind.CLASS: Icons.KIND_CLASS,
    CompletionKind.PROPERTY: Icons.KIND_PROPERTY,
    CompletionKind.KEYWORD: Icons.KIND_KEYWORD,
    CompletionKind.BUILTIN: Icons.KIND_BUILTIN,
    CompletionKind.SNIPPET: Icons.KIND_SNIPPET,
    CompletionKind.VARIABLE: Icons.KIND_VARIABLE,
    CompletionKind.PARAMETER: Icons.KIND_PARAMETER,
}


@dataclass
class CompletionItem:
    name: str
    kind: CompletionKind
    signature: str = ""
    docstring: str = ""
    insert_text: str = ""


class Autocomplete:
    """Handles autocompletion for GtkSourceView editors."""

    # Import mixin methods — done via __init_subclass__ to keep MRO clean.
    # We pull in methods from the two mixin modules after class creation (see bottom of file).

    def __init__(self, editor_tab):
        from editor.autocomplete.js_provider import JsCompletionProvider
        from editor.autocomplete.python_provider import PythonCompletionProvider
        from editor.autocomplete.terraform_provider import TerraformCompletionProvider

        self._tab = editor_tab
        self._view = editor_tab.view
        self._buffer = editor_tab.buffer
        self._popup = None  # NvimPopup, created lazily in _ensure_popup()
        self._listbox = None
        self._completions = []
        self._python_provider = PythonCompletionProvider()
        self._js_provider = JsCompletionProvider()
        self._terraform_provider = TerraformCompletionProvider()
        self._filtered = []
        self._selected_idx = 0
        self._word_start_offset = 0
        self._changed_handler = None
        self._inserting = False
        self._auto_trigger_timer = None
        self._last_buffer_len = self._buffer.get_char_count()
        self._tab_stop_marks = []  # list of (start_mark, end_mark) GtkTextMarks
        self._tab_stop_idx = -1
        self._dismiss_guard = False
        self._dismiss_guard_timer = None
        self._focus_suppress_idle = None
        self._hbox = None
        self._sig_box = None
        self._sig_sep = None
        self._sig_buffer = None
        self._sig_view = None
        self._css_provider = None
        self._setup_click_dismiss()
        self._setup_focus_dismiss()
        self._buffer.connect("changed", self._on_auto_trigger_change)

    def _on_auto_trigger_change(self, buffer):
        """Auto-trigger completions only when inserting new characters."""
        new_len = buffer.get_char_count()
        old_len = self._last_buffer_len
        self._last_buffer_len = new_len

        if self._inserting or self.is_visible():
            return

        # Only trigger on single-char insertions (typing), not bulk inserts (file load)
        # or deletions/replacements
        chars_added = new_len - old_len
        if chars_added < 1 or chars_added > 2:
            return

        if not get_setting("editor.auto_complete_on_type", False):
            return

        # Skip if cursor is inside a comment
        cursor_iter = buffer.get_iter_at_mark(buffer.get_insert())
        if buffer.iter_has_context_class(cursor_iter, "comment"):
            return

        if self._auto_trigger_timer:
            GLib.source_remove(self._auto_trigger_timer)
            self._auto_trigger_timer = None

        partial = self._get_word_at_cursor()
        if len(partial) >= AUTOCOMPLETE_AUTO_TRIGGER_CHARS:
            self._auto_trigger_timer = GLib.timeout_add(
                AUTOCOMPLETE_AUTO_TRIGGER_DELAY_MS,
                self._auto_trigger_show,
            )
            return

        # Trigger immediately when "." is typed after an identifier (e.g., obj.)
        if cursor_iter.get_offset() >= 2:
            dot_iter = cursor_iter.copy()
            dot_iter.backward_char()
            if dot_iter.get_char() == ".":
                before_dot = dot_iter.copy()
                before_dot.backward_char()
                ch = before_dot.get_char()
                if ch.isalnum() or ch == "_":
                    self._auto_trigger_timer = GLib.timeout_add(
                        AUTOCOMPLETE_AUTO_TRIGGER_DELAY_MS,
                        self._auto_trigger_show,
                    )
                    return

        # Trigger on "(" or "," for function call parameter completion
        if cursor_iter.get_offset() >= 2:
            prev_iter = cursor_iter.copy()
            prev_iter.backward_char()
            ch = prev_iter.get_char()
            if ch == "(":
                before = prev_iter.copy()
                before.backward_char()
                bc = before.get_char()
                if bc.isalnum() or bc == "_":
                    self._auto_trigger_timer = GLib.timeout_add(
                        AUTOCOMPLETE_AUTO_TRIGGER_DELAY_MS,
                        self._auto_trigger_show,
                    )
            elif ch == ",":
                self._auto_trigger_timer = GLib.timeout_add(
                    AUTOCOMPLETE_AUTO_TRIGGER_DELAY_MS,
                    self._auto_trigger_show,
                )

    def _auto_trigger_show(self):
        """Show completions from auto-trigger timer."""
        self._auto_trigger_timer = None
        if not self.is_visible():
            self.show()
        return GLib.SOURCE_REMOVE

    def _get_word_at_cursor(self):
        """Extract the partial identifier word ending at the cursor."""
        cursor_iter = self._buffer.get_iter_at_mark(self._buffer.get_insert())
        word_start = cursor_iter.copy()
        while word_start.backward_char():
            ch = word_start.get_char()
            if not (ch.isalnum() or ch == "_"):
                word_start.forward_char()
                break
        return self._buffer.get_text(word_start, cursor_iter, False)

    def show(self, force=False):
        """Show autocomplete popup at cursor position."""
        if not self._ensure_popup():
            return

        self._completions = []
        cursor_mark = self._buffer.get_insert()
        cursor_iter = self._buffer.get_iter_at_mark(cursor_mark)

        # Find word start
        word_start = cursor_iter.copy()
        while word_start.backward_char():
            ch = word_start.get_char()
            if not (ch.isalnum() or ch == "_"):
                word_start.forward_char()
                break
        # If we went all the way to buffer start without breaking, word_start is at pos 0

        self._word_start_offset = word_start.get_offset()
        partial = self._buffer.get_text(word_start, cursor_iter, False)

        # Get completions based on language
        file_path = self._tab.file_path

        # Check for Python import path context (from lib. → suggest modules in lib/)
        ext = Path(file_path).suffix.lower() if file_path else ""
        import_base = None
        from_import = False
        if ext in (".py", ".pyw", ".pyi"):
            cursor_iter_ctx = self._buffer.get_iter_at_mark(self._buffer.get_insert())
            import_base, from_import = self._python_provider.detect_import_context(self._buffer, cursor_iter_ctx)

        if import_base is not None:
            if from_import:
                # "from X import " → suggest symbols from X's .py file
                self._completions = self._python_provider.get_file_symbols(import_base, file_path)
            if not self._completions:
                # Also try submodules/subpackages (or fallback)
                self._completions = self._python_provider.get_module_completions(import_base, file_path)
            if not self._completions:
                self._completions = self._get_completions(file_path)
        else:
            # Check for dot-access context (e.g., DBTables.Cards.method)
            dot_context = False
            if ext in (".py", ".pyw", ".pyi"):
                dot_target = self._python_provider.detect_dot_access_context(self._buffer, self._word_start_offset)
                if dot_target:
                    dot_context = True
                    self._completions = self._python_provider.resolve_dot_completions(
                        dot_target,
                        file_path,
                        self._get_buffer_text(),
                        cursor_offset=self._word_start_offset,
                    )
            # Check for function call parameter context (e.g., func(arg1, |))
            if not self._completions and not dot_context and ext in (".py", ".pyw", ".pyi"):
                cursor_iter_call = self._buffer.get_iter_at_mark(self._buffer.get_insert())
                call_params = self._python_provider.get_call_parameter_completions(
                    self._buffer, cursor_iter_call, file_path, self._get_buffer_text()
                )
                if call_params:
                    self._completions = call_params
            # Only fall back to generic completions if NOT in a dot-access context;
            # unresolvable dot targets (e.g., "handle.") should show nothing —
            # unless the user explicitly forced completions via Ctrl+Space.
            if not self._completions and (not dot_context or force):
                self._completions = self._get_completions(file_path)

        if not self._completions:
            return

        # Filter and show
        self._update_filter(partial.lower())
        if not self._filtered:
            return

        # Skip if the only suggestion is exactly what's already typed (unless forced via Ctrl+Space)
        if not force and len(self._filtered) == 1 and self._filtered[0].name == partial:
            return

        # Skip if cursor is on a fold-affected line (Pango crash risk)
        fold_unsafe = getattr(self._view, "_fold_unsafe_lines", set())
        if cursor_iter.get_line() in fold_unsafe:
            return
        # Position popup below the cursor line (not covering it)
        loc = self._view.get_iter_location(cursor_iter)
        wx, wy = self._view.buffer_to_window_coords(Gtk.TextWindowType.WIDGET, loc.x, loc.y)
        rect = Gdk.Rectangle()
        rect.x = wx
        rect.y = wy + loc.height + 2
        rect.width = 1
        rect.height = 1
        self._popup.set_anchor_rect(rect)

        # Connect buffer changes for live filtering
        self._changed_handler = self._buffer.connect("changed", self._on_buffer_changed)

        # Guard against spurious dismiss events (focus loss, IM events) triggered by popup()
        self._dismiss_guard = True
        if self._dismiss_guard_timer:
            GLib.source_remove(self._dismiss_guard_timer)
        # Suppress editor focus effects during popup transition to prevent
        # cursor/line-highlight flicker from the transient focus bounce.
        self._view._suppress_focus_effects = True
        if self._focus_suppress_idle:
            GLib.source_remove(self._focus_suppress_idle)
            self._focus_suppress_idle = None
        self._popup.popup()
        # Clear suppression asynchronously — GTK focus events fire on the next
        # event-loop iteration (macOS NSWindow notifications), so the flag must
        # remain True until after they have been handled.
        self._focus_suppress_idle = GLib.idle_add(self._clear_focus_suppression)
        self._update_signature_preview()
        self._dismiss_guard_timer = GLib.timeout_add(500, self._clear_dismiss_guard)

    def _clear_dismiss_guard(self):
        """Allow dismiss after pending events from popup() have settled."""
        self._dismiss_guard = False
        self._dismiss_guard_timer = None
        return GLib.SOURCE_REMOVE

    def _clear_focus_suppression(self):
        """Re-enable editor focus effects after the popup focus bounce has settled."""
        self._view._suppress_focus_effects = False
        self._focus_suppress_idle = None
        return GLib.SOURCE_REMOVE

    def hide(self):
        """Hide the autocomplete popup."""
        self._dismiss_guard = False
        if self._dismiss_guard_timer:
            GLib.source_remove(self._dismiss_guard_timer)
            self._dismiss_guard_timer = None
        if self._focus_suppress_idle:
            GLib.source_remove(self._focus_suppress_idle)
            self._focus_suppress_idle = None
        self._view._suppress_focus_effects = False
        if self._changed_handler:
            self._buffer.disconnect(self._changed_handler)
            self._changed_handler = None
        if self._auto_trigger_timer:
            GLib.source_remove(self._auto_trigger_timer)
            self._auto_trigger_timer = None
        if self._sig_box:
            self._sig_box.set_visible(False)
        if self._sig_sep:
            self._sig_sep.set_visible(False)
        if self._popup and self._popup.get_visible():
            self._popup.popdown()

    def is_visible(self):
        """Check if the autocomplete popup is currently visible."""
        return self._popup is not None and self._popup.get_visible()

    def has_active_tab_stops(self):
        """Return True if there are active tab stops to navigate."""
        return 0 <= self._tab_stop_idx < len(self._tab_stop_marks)

    def clear_tab_stops(self):
        """Clear all tab stop marks."""
        for s_mark, e_mark in self._tab_stop_marks:
            self._buffer.delete_mark(s_mark)
            self._buffer.delete_mark(e_mark)
        self._tab_stop_marks = []
        self._tab_stop_idx = -1

    def advance_tab_stop(self):
        """Advance to the next tab stop, selecting it. Returns True if consumed."""
        if not self.has_active_tab_stops():
            return False

        self._tab_stop_idx += 1
        if self._tab_stop_idx >= len(self._tab_stop_marks):
            self.clear_tab_stops()
            return True

        s_mark, e_mark = self._tab_stop_marks[self._tab_stop_idx]
        s = self._buffer.get_iter_at_mark(s_mark)
        e = self._buffer.get_iter_at_mark(e_mark)
        self._buffer.select_range(s, e)
        return True

    def handle_key(self, keyval, state):
        """Handle key event when popup is visible. Returns True if consumed."""
        if keyval == Gdk.KEY_Escape:
            self.hide()
            return True

        if keyval == Gdk.KEY_Down:
            self._select_next()
            return True

        if keyval == Gdk.KEY_Up:
            self._select_prev()
            return True

        if keyval in (Gdk.KEY_Return, Gdk.KEY_Tab):
            self._insert_selected()
            return True

        # Let other keys pass through to the editor (typing continues)
        return False

    def _select_next(self):
        """Move selection down (wraps around)."""
        if self._filtered:
            self._selected_idx = (self._selected_idx + 1) % len(self._filtered)
            self._highlight_selected()

    def _select_prev(self):
        """Move selection up (wraps around)."""
        if self._filtered:
            self._selected_idx = (self._selected_idx - 1) % len(self._filtered)
            self._highlight_selected()

    def _insert_selected(self):
        """Insert the selected completion into the buffer."""
        if not self._filtered or self._selected_idx >= len(self._filtered):
            self.hide()
            return

        item = self._filtered[self._selected_idx]
        completion_text = item.insert_text or item.name
        self._inserting = True

        # Delete the partial word and insert the completion
        word_start_iter = self._buffer.get_iter_at_offset(self._word_start_offset)
        cursor_iter = self._buffer.get_iter_at_mark(self._buffer.get_insert())

        self._buffer.begin_user_action()
        self._buffer.delete(word_start_iter, cursor_iter)

        # For functions/constructors, auto-insert parentheses and parameter names
        if item.kind in (CompletionKind.FUNCTION, CompletionKind.CLASS):
            params_text = self._extract_params(item.signature)
            full_text = f"{completion_text}({params_text})"
            self._buffer.insert_at_cursor(full_text)

            # Build tab stops for each parameter, then select the first one
            if params_text:
                base_offset = self._word_start_offset + len(completion_text) + 1  # after '('
                self.clear_tab_stops()
                offset = 0
                for param in params_text.split(", "):
                    start = base_offset + offset
                    end = start + len(param)
                    s_iter = self._buffer.get_iter_at_offset(start)
                    e_iter = self._buffer.get_iter_at_offset(end)
                    # left_gravity=True for start mark, False for end mark
                    s_mark = self._buffer.create_mark(None, s_iter, True)
                    e_mark = self._buffer.create_mark(None, e_iter, False)
                    self._tab_stop_marks.append((s_mark, e_mark))
                    offset += len(param) + 2  # +2 for ", "
                # Add a final tab stop after the closing paren
                close_iter = self._buffer.get_iter_at_offset(self._word_start_offset + len(full_text))
                s_mark = self._buffer.create_mark(None, close_iter, True)
                e_mark = self._buffer.create_mark(None, close_iter, False)
                self._tab_stop_marks.append((s_mark, e_mark))
                self._tab_stop_idx = 0
                first_s, first_e = self._tab_stop_marks[0]
                self._buffer.select_range(
                    self._buffer.get_iter_at_mark(first_s),
                    self._buffer.get_iter_at_mark(first_e),
                )
            else:
                # Place cursor between empty parens
                cursor_offset = self._word_start_offset + len(completion_text) + 1
                cursor_pos = self._buffer.get_iter_at_offset(cursor_offset)
                self._buffer.place_cursor(cursor_pos)
                self.clear_tab_stops()
        else:
            self._buffer.insert_at_cursor(completion_text)

        self._buffer.end_user_action()

        self._inserting = False
        self.hide()


# ------------------------------------------------------------------ #
#  Mix in methods from split modules                                   #
# ------------------------------------------------------------------ #


def _apply_mixins():
    """Attach mixin methods to the Autocomplete class.

    This avoids multiple-inheritance MRO issues while keeping the
    public class name and import paths unchanged.
    """
    from editor.autocomplete.completion_popup import CompletionPopupMixin
    from editor.autocomplete.completion_ranking import CompletionRankingMixin

    for mixin_cls in (CompletionPopupMixin, CompletionRankingMixin):
        for name in dir(mixin_cls):
            if name.startswith("_") and not name.startswith("__"):
                if not hasattr(Autocomplete, name):
                    setattr(Autocomplete, name, getattr(mixin_cls, name))


_apply_mixins()
