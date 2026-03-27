"""Tests for completion filtering — _update_filter, Python docstring extraction, JS JSDoc extraction.

Covers:
- _update_filter: prefix-based filtering, case-insensitive, max items
- Python docstring extraction from tree-sitter AST
- JS JSDoc comment extraction for JS/TS completions
"""

from unittest.mock import MagicMock, patch

from editor.autocomplete.autocomplete import Autocomplete, CompletionItem, CompletionKind

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_autocomplete(**overrides):
    """Create an Autocomplete with mocked GTK dependencies for unit testing."""
    with patch.object(Autocomplete, "__init__", lambda self, *a, **kw: None):
        ac = Autocomplete.__new__(Autocomplete)

    ac._completions = []
    ac._filtered = []
    ac._selected_idx = 0
    ac._word_start_offset = 0
    ac._inserting = False
    ac._auto_trigger_timer = None
    ac._last_buffer_len = 0
    ac._changed_handler = None
    ac._dismiss_guard = False
    ac._dismiss_guard_timer = None
    ac._focus_suppress_idle = None

    ac._buffer = MagicMock()
    ac._view = MagicMock()
    ac._popup = MagicMock()
    ac._listbox = MagicMock()
    ac._sig_box = MagicMock()
    ac._sig_sep = MagicMock()
    ac._sig_buffer = MagicMock()
    ac._sig_view = MagicMock()
    ac._hbox = MagicMock()
    ac._tab = MagicMock()
    ac._python_provider = MagicMock()
    ac._js_provider = MagicMock()
    ac._terraform_provider = MagicMock()
    ac._css_provider = None

    for k, v in overrides.items():
        setattr(ac, k, v)
    return ac


# ---------------------------------------------------------------------------
# _update_filter
# ---------------------------------------------------------------------------


class TestUpdateFilter:
    """Test that _update_filter correctly filters completions."""

    def test_filters_by_prefix(self):
        ac = _make_autocomplete()
        ac._completions = [
            CompletionItem("process", CompletionKind.FUNCTION),
            CompletionItem("print", CompletionKind.BUILTIN),
            CompletionItem("open", CompletionKind.BUILTIN),
        ]

        with patch("editor.autocomplete.completion_popup_mixin.get_theme"):
            ac._update_filter("pr")

        names = [c.name for c in ac._filtered]
        assert "process" in names
        assert "print" in names
        assert "open" not in names

    def test_empty_partial_returns_all(self):
        ac = _make_autocomplete()
        ac._completions = [
            CompletionItem("foo", CompletionKind.VARIABLE),
            CompletionItem("bar", CompletionKind.VARIABLE),
        ]

        with patch("editor.autocomplete.completion_popup_mixin.get_theme"):
            ac._update_filter("")

        assert len(ac._filtered) == 2

    def test_case_insensitive_filter(self):
        ac = _make_autocomplete()
        ac._completions = [CompletionItem("MyClass", CompletionKind.VARIABLE)]

        with patch("editor.autocomplete.completion_popup_mixin.get_theme"):
            ac._update_filter("myc")

        assert len(ac._filtered) == 1
        assert ac._filtered[0].name == "MyClass"

    def test_respects_max_items(self):
        from constants import AUTOCOMPLETE_MAX_ITEMS

        ac = _make_autocomplete()
        ac._completions = [CompletionItem(f"item_{i}", CompletionKind.VARIABLE) for i in range(50)]

        with patch("editor.autocomplete.completion_popup_mixin.get_theme"):
            ac._update_filter("item")

        assert len(ac._filtered) == AUTOCOMPLETE_MAX_ITEMS


# ---------------------------------------------------------------------------
# Python docstring extraction
# ---------------------------------------------------------------------------


class TestPythonDocstringExtraction:
    """Test docstring extraction from Python code."""

    def setup_method(self):
        from editor.autocomplete.tree_sitter_provider import (
            _parse,
            py_extract_class_members,
            py_extract_definitions,
            py_extract_self_members,
        )

        self._parse = _parse
        self._defs = py_extract_definitions
        self._members = py_extract_class_members
        self._self_members = py_extract_self_members

    def _py(self, text):
        source, tree = self._parse(text, "python")
        assert tree is not None
        return source, tree

    def test_get_symbols_extracts_function_docstring(self):
        text = 'def greet(name: str):\n    """Say hello to someone."""\n    pass\n'
        source, tree = self._py(text)
        symbols = self._defs(source, tree)
        func = next(s for s in symbols if s.name == "greet")
        assert func.docstring == "Say hello to someone."

    def test_get_symbols_extracts_class_docstring(self):
        text = 'class MyService:\n    """Handles business logic."""\n    pass\n'
        source, tree = self._py(text)
        symbols = self._defs(source, tree)
        cls = next(s for s in symbols if s.name == "MyService")
        assert cls.docstring == "Handles business logic."

    def test_get_symbols_no_docstring(self):
        text = "def process(x):\n    return x + 1\n"
        source, tree = self._py(text)
        symbols = self._defs(source, tree)
        func = next(s for s in symbols if s.name == "process")
        assert func.docstring == ""

    def test_multiline_docstring_takes_first_line(self):
        text = 'def foo():\n    """First line.\n\n    More details here.\n    """\n    pass\n'
        source, tree = self._py(text)
        symbols = self._defs(source, tree)
        func = next(s for s in symbols if s.name == "foo")
        assert func.docstring == "First line."

    def test_single_quote_docstring(self):
        text = "def bar():\n    '''Single-quoted docstring.'''\n    pass\n"
        source, tree = self._py(text)
        symbols = self._defs(source, tree)
        func = next(s for s in symbols if s.name == "bar")
        assert func.docstring == "Single-quoted docstring."

    def test_extract_docstring_at_position(self):
        text = 'def hello():\n    """Greets the user."""\n    pass'
        source, tree = self._py(text)
        symbols = self._defs(source, tree)
        func = next(s for s in symbols if s.name == "hello")
        assert func.docstring == "Greets the user."

    def test_peek_docstring_single_line(self):
        text = 'def foo():\n    """A short docstring."""\n    pass'
        source, tree = self._py(text)
        symbols = self._defs(source, tree)
        func = next(s for s in symbols if s.name == "foo")
        assert func.docstring == "A short docstring."

    def test_peek_docstring_multiline(self):
        text = 'def foo():\n    """\n    The actual description.\n    """\n    pass'
        source, tree = self._py(text)
        symbols = self._defs(source, tree)
        func = next(s for s in symbols if s.name == "foo")
        assert func.docstring == "The actual description."

    def test_peek_docstring_content_after_opening_quote(self):
        text = 'def foo():\n    """Description starts here.\n    """\n    pass'
        source, tree = self._py(text)
        symbols = self._defs(source, tree)
        func = next(s for s in symbols if s.name == "foo")
        assert func.docstring == "Description starts here."

    def test_peek_docstring_no_docstring(self):
        text = "def foo():\n    return 42"
        source, tree = self._py(text)
        symbols = self._defs(source, tree)
        func = next(s for s in symbols if s.name == "foo")
        assert func.docstring == ""

    def test_extract_class_members_with_docstrings(self):
        text = (
            "class Calculator:\n"
            "    def add(self, a, b):\n"
            '        """Add two numbers."""\n'
            "        return a + b\n"
            "    def multiply(self, a, b):\n"
            "        return a * b\n"
        )
        source, tree = self._py(text)
        members = self._members(source, tree, "Calculator")
        add_item = next(m for m in members if m.name == "add")
        mul_item = next(m for m in members if m.name == "multiply")
        assert add_item.docstring == "Add two numbers."
        assert mul_item.docstring == ""

    def test_self_completions_with_docstrings(self):
        text = (
            "class Greeter:\n"
            "    def greet(self, name):\n"
            '        """Greet someone by name."""\n'
            "        pass\n"
            "    def farewell(self):\n"
            "        pass\n"
        )
        source, tree = self._py(text)
        members = self._self_members(source, tree, "Greeter")
        greet = next(m for m in members if m.name == "greet")
        farewell = next(m for m in members if m.name == "farewell")
        assert greet.docstring == "Greet someone by name."
        assert farewell.docstring == ""


# ---------------------------------------------------------------------------
# JS JSDoc extraction
# ---------------------------------------------------------------------------


class TestJsDocExtraction:
    """Test JSDoc comment extraction for JS/TS completions."""

    def setup_method(self):
        from editor.autocomplete.js_completion_provider import JsCompletionProvider

        self.provider = JsCompletionProvider()

    def test_jsdoc_before_function(self):
        text = "/** Fetches user data from the API. */\nfunction fetchUser(id) {}\n"
        symbols = self.provider._get_symbols(text)
        func = next(s for s in symbols if s.name == "fetchUser")
        assert func.docstring == "Fetches user data from the API."

    def test_multiline_jsdoc(self):
        text = (
            "/**\n"
            " * Calculate the sum of two numbers.\n"
            " * @param {number} a\n"
            " * @param {number} b\n"
            " */\n"
            "function sum(a, b) { return a + b; }\n"
        )
        symbols = self.provider._get_symbols(text)
        func = next(s for s in symbols if s.name == "sum")
        assert func.docstring == "Calculate the sum of two numbers."

    def test_no_jsdoc(self):
        text = "function plain() {}\n"
        symbols = self.provider._get_symbols(text)
        func = next(s for s in symbols if s.name == "plain")
        assert func.docstring == ""

    def test_regular_comment_not_jsdoc(self):
        text = "// This is not a JSDoc\nfunction notDoc() {}\n"
        symbols = self.provider._get_symbols(text)
        func = next(s for s in symbols if s.name == "notDoc")
        assert func.docstring == ""
