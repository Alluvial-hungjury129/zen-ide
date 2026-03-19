"""Tests for editor/semantic_highlight.py - regex patterns, keyword filtering,
and iterator-safety regression tests.

The iterator-safety tests verify that semantic highlighting never uses the
``iter_forward_to_context_class_toggle`` API (which triggers lazy
re-highlighting inside GtkSourceView and produces stale-iterator GTK
warnings that cannot be avoided from Python).  Instead, only the safe
``iter_has_context_class`` API should be used for string/comment detection.
"""

import inspect
import textwrap

from editor.semantic_highlight import (
    _PYTHON_KEYWORDS,
    _RE_CLASS_USAGE,
    _RE_FUNC_CALL,
    _RE_METHOD_CALL,
    TAG_CLASS_USAGE,
    TAG_FUNC_CALL,
    TAG_PARAM,
    TAG_PROPERTY,
    TAG_SELF,
    _apply_semantic_tags,
    _is_inside_string_or_comment,
)

# ---------------------------------------------------------------------------
# Fake GTK objects for buffer-level tests
# ---------------------------------------------------------------------------


class _FakeIter:
    """Minimal GtkTextIter stand-in."""

    def __init__(self, text, offset):
        self._text = text
        self._offset = max(0, min(len(text), offset))

    def get_offset(self):
        return self._offset


class _FakeTag:
    """Minimal GtkTextTag stand-in."""

    def __init__(self, name):
        self.name = name


class _FakeTagTable:
    """Tag table that returns pre-created tags by name."""

    def __init__(self, tags):
        self._tags = {t.name: t for t in tags}

    def lookup(self, name):
        return self._tags.get(name)


class _FakeLanguage:
    def __init__(self, lang_id):
        self._id = lang_id

    def get_id(self):
        return self._id


class _FakeBuffer:
    """Minimal GtkSourceBuffer stand-in with context-class support.

    Parameters
    ----------
    text : str
        Buffer content.
    string_ranges : list[tuple[int, int]]
        Offset ranges considered inside a "string" context.
    comment_ranges : list[tuple[int, int]]
        Offset ranges considered inside a "comment" context.
    lang_id : str
        Language identifier (default "python3").
    """

    def __init__(self, text, *, string_ranges=None, comment_ranges=None, lang_id="python3"):
        self.text = text
        self._string_ranges = string_ranges or []
        self._comment_ranges = comment_ranges or []
        self._lang_id = lang_id
        self._tags = [
            _FakeTag(TAG_CLASS_USAGE),
            _FakeTag(TAG_FUNC_CALL),
            _FakeTag(TAG_PARAM),
            _FakeTag(TAG_SELF),
            _FakeTag(TAG_PROPERTY),
        ]
        self._tag_table = _FakeTagTable(self._tags)
        self.applied_tags = []  # list of (tag_name, start, end)

    # --- iter / text API ---

    def get_iter_at_offset(self, offset):
        return (True, _FakeIter(self.text, offset))

    def get_start_iter(self):
        return _FakeIter(self.text, 0)

    def get_end_iter(self):
        return _FakeIter(self.text, len(self.text))

    def get_text(self, start_iter, end_iter, _include_hidden):
        return self.text[start_iter.get_offset() : end_iter.get_offset()]

    # --- tag API ---

    def get_tag_table(self):
        return self._tag_table

    def apply_tag(self, tag, start_iter, end_iter):
        self.applied_tags.append((tag.name, start_iter.get_offset(), end_iter.get_offset()))

    def remove_tag_by_name(self, _name, _start, _end):
        pass

    # --- language API ---

    def get_language(self):
        return _FakeLanguage(self._lang_id)

    # --- context-class API (the safe one) ---

    def iter_has_context_class(self, it, ctx):
        offset = it.get_offset()
        ranges = self._string_ranges if ctx == "string" else self._comment_ranges
        return any(s <= offset < e for s, e in ranges)

    def ensure_highlight(self, _start, _end):
        pass


# ---------------------------------------------------------------------------
# Original regex / keyword tests
# ---------------------------------------------------------------------------


class TestClassUsagePattern:
    """Test PascalCase identifier matching."""

    def test_matches_pascal_case(self):
        assert _RE_CLASS_USAGE.search("MyClass") is not None

    def test_matches_multi_word(self):
        assert _RE_CLASS_USAGE.search("ServicingProcessor") is not None

    def test_no_match_all_caps(self):
        """ALL_CAPS should NOT match (avoids constants)."""
        m = _RE_CLASS_USAGE.search("MY_CONSTANT")
        if m:
            assert m.group(1) != "MY_CONSTANT"

    def test_no_match_lowercase(self):
        m = _RE_CLASS_USAGE.search("myvar")
        assert m is None

    def test_matches_in_context(self):
        m = _RE_CLASS_USAGE.search("x = MyClass()")
        assert m is not None
        assert m.group(1) == "MyClass"


class TestFuncCallPattern:
    """Test function call pattern matching."""

    def test_matches_function_call(self):
        m = _RE_FUNC_CALL.search("len(x)")
        assert m is not None
        assert m.group(1) == "len"

    def test_matches_underscore_function(self):
        m = _RE_FUNC_CALL.search("_private_func()")
        assert m is not None

    def test_matches_with_space(self):
        m = _RE_FUNC_CALL.search("my_func ()")
        assert m is not None

    def test_no_match_class(self):
        """PascalCase should NOT match as function call."""
        m = _RE_FUNC_CALL.search("MyClass()")
        if m:
            assert m.group(1) != "MyClass"


class TestMethodCallPattern:
    """Test method call pattern matching."""

    def test_matches_method(self):
        m = _RE_METHOD_CALL.search("obj.method()")
        assert m is not None
        assert m.group(1) == "method"

    def test_matches_chained(self):
        matches = list(_RE_METHOD_CALL.finditer("a.foo().bar()"))
        assert len(matches) == 2

    def test_matches_with_args(self):
        m = _RE_METHOD_CALL.search("self.process(data)")
        assert m is not None
        assert m.group(1) == "process"


class TestPythonKeywords:
    """Test keyword set completeness."""

    def test_contains_if(self):
        assert "if" in _PYTHON_KEYWORDS

    def test_contains_def(self):
        assert "def" in _PYTHON_KEYWORDS

    def test_contains_class(self):
        assert "class" in _PYTHON_KEYWORDS

    def test_contains_return(self):
        assert "return" in _PYTHON_KEYWORDS

    def test_contains_import(self):
        assert "import" in _PYTHON_KEYWORDS

    def test_contains_async(self):
        assert "async" in _PYTHON_KEYWORDS


class TestTagNames:
    """Test tag name constants."""

    def test_class_tag(self):
        assert TAG_CLASS_USAGE == "zen-class-usage"

    def test_func_tag(self):
        assert TAG_FUNC_CALL == "zen-func-call"


# ---------------------------------------------------------------------------
# Iterator-safety regression tests
# ---------------------------------------------------------------------------


class TestNoToggleAPIUsage:
    """Ensure iter_forward_to_context_class_toggle is never called.

    This API triggers lazy re-highlighting inside GtkSourceView that
    invalidates iterators mid-call, producing GTK warnings that cannot
    be fixed from Python.  Only iter_has_context_class should be used.
    """

    def test_source_does_not_call_toggle_api(self):
        """The module source must not contain any call to the toggle API."""
        import editor.semantic_highlight as mod

        source = inspect.getsource(mod)
        # Remove docstrings/comments that legitimately mention the API
        lines = source.splitlines()
        code_lines = [
            ln
            for ln in lines
            if not ln.lstrip().startswith("#") and not ln.lstrip().startswith('"""') and not ln.lstrip().startswith("``")
        ]
        code_text = "\n".join(code_lines)
        assert "iter_forward_to_context_class_toggle" not in code_text, (
            "iter_forward_to_context_class_toggle must not be called — it triggers stale-iterator GTK warnings"
        )


class TestIsInsideStringOrComment:
    """Test _is_inside_string_or_comment with mock buffer."""

    def test_plain_code_not_excluded(self):
        buf = _FakeBuffer("x = MyClass()")
        assert _is_inside_string_or_comment(buf, 4) is False

    def test_inside_string(self):
        # 'hello' starts at offset 4 through 11
        buf = _FakeBuffer('x = "hello"', string_ranges=[(4, 11)])
        assert _is_inside_string_or_comment(buf, 5) is True

    def test_inside_comment(self):
        buf = _FakeBuffer("x = 1  # note", comment_ranges=[(7, 14)])
        assert _is_inside_string_or_comment(buf, 9) is True

    def test_outside_string(self):
        buf = _FakeBuffer('x = "hello"\ny = 1', string_ranges=[(4, 11)])
        # offset 14 is in 'y = 1'
        assert _is_inside_string_or_comment(buf, 14) is False

    def test_offset_zero_in_docstring(self):
        """Regression: zen_ide.py starts with a docstring at offset 0."""
        buf = _FakeBuffer('"""Module docstring."""\nx = 1', string_ranges=[(0, 23)])
        assert _is_inside_string_or_comment(buf, 0) is True

    def test_no_context_class_support(self):
        """Buffer without iter_has_context_class should return False."""

        class _PlainBuffer:
            def get_iter_at_offset(self, offset):
                return (True, _FakeIter("x = 1", offset))

        assert _is_inside_string_or_comment(_PlainBuffer(), 0) is False

    def test_rebuilds_iterator_between_checks(self):
        """Verify a fresh iterator is used for the comment check.

        If the iterator is NOT rebuilt after the string check, a stale
        iterator could produce incorrect results or GTK warnings.
        """
        call_log = []

        class _TrackingBuffer(_FakeBuffer):
            def get_iter_at_offset(self, offset):
                call_log.append(("get_iter", offset))
                return super().get_iter_at_offset(offset)

            def iter_has_context_class(self, it, ctx):
                call_log.append(("has_ctx", ctx, it.get_offset()))
                return super().iter_has_context_class(it, ctx)

        buf = _TrackingBuffer("x = 1")
        _is_inside_string_or_comment(buf, 2)

        # Should see: get_iter(2), has_ctx("string", 2), get_iter(2), has_ctx("comment", 2)
        get_iter_calls = [c for c in call_log if c[0] == "get_iter"]
        assert len(get_iter_calls) >= 2, (
            f"Iterator must be rebuilt between string and comment checks to avoid stale-iterator bugs. Calls: {call_log}"
        )


class TestApplySemanticTagsExcludesStringsAndComments:
    """Test that _apply_semantic_tags skips tokens inside strings/comments."""

    def test_class_in_string_not_tagged(self):
        text = 'x = "MyClass"\n'
        # "MyClass" is at offsets 5..12 (inside quotes 4..13)
        buf = _FakeBuffer(text, string_ranges=[(4, 13)])
        _apply_semantic_tags(buf)
        class_tags = [(s, e) for name, s, e in buf.applied_tags if name == TAG_CLASS_USAGE]
        assert not class_tags, f"MyClass inside string should not be tagged: {class_tags}"

    def test_class_outside_string_is_tagged(self):
        text = "x = MyClass()\n"
        buf = _FakeBuffer(text)
        _apply_semantic_tags(buf)
        class_tags = [(s, e) for name, s, e in buf.applied_tags if name == TAG_CLASS_USAGE]
        assert any(s == 4 and e == 11 for s, e in class_tags), f"MyClass at offset 4 should be tagged: {class_tags}"

    def test_func_call_in_comment_not_tagged(self):
        text = "# foo()\nbar()\n"
        # comment region covers '# foo()' → offsets 0..7
        buf = _FakeBuffer(text, comment_ranges=[(0, 7)])
        _apply_semantic_tags(buf)
        func_tags = [(s, e) for name, s, e in buf.applied_tags if name == TAG_FUNC_CALL]
        # 'bar' should be tagged (offset 8..11), 'foo' should NOT
        tagged_names = [text[s:e] for s, e in func_tags]
        assert "foo" not in tagged_names, f"foo() in comment should not be tagged: {func_tags}"
        assert "bar" in tagged_names, f"bar() outside comment should be tagged: {func_tags}"

    def test_self_in_string_not_tagged(self):
        text = 'x = "self.value"\nself.real\n'
        # string region covers offsets 4..16
        buf = _FakeBuffer(text, string_ranges=[(4, 16)])
        _apply_semantic_tags(buf)
        self_tags = [(s, e) for name, s, e in buf.applied_tags if name == TAG_SELF]
        for s, e in self_tags:
            assert s >= 17, f"self inside string should not be tagged: offset {s}"

    def test_no_language_returns_early(self):
        """Buffer with no language should not crash or apply tags."""
        buf = _FakeBuffer("MyClass()\n")
        buf.get_language = lambda: None
        _apply_semantic_tags(buf)
        assert buf.applied_tags == []

    def test_unsupported_language_returns_early(self):
        buf = _FakeBuffer("MyClass()\n", lang_id="markdown")
        _apply_semantic_tags(buf)
        assert buf.applied_tags == []


class TestStartupDocstringRegression:
    """Regression test for the specific startup scenario that triggered
    the original GTK warning: loading a Python file that starts with a
    docstring (e.g. zen_ide.py).

    The old code used iter_forward_to_context_class_toggle to scan for
    string/comment boundaries, which triggered lazy re-highlighting and
    produced stale-iterator warnings.  The fix uses per-match
    iter_has_context_class checks instead.
    """

    def test_file_starting_with_docstring(self):
        text = textwrap.dedent('''\
            """Module docstring."""
            import os

            class MyApp:
                def run(self):
                    pass
        ''')
        docstring_end = text.index('"""', 3) + 3  # end of closing """
        buf = _FakeBuffer(text, string_ranges=[(0, docstring_end)])
        _apply_semantic_tags(buf)

        # "MyApp" (PascalCase) should be tagged
        class_tags = [text[s:e] for name, s, e in buf.applied_tags if name == TAG_CLASS_USAGE]
        assert "MyApp" in class_tags

        # Nothing inside the docstring should be tagged
        for tag_name, s, e in buf.applied_tags:
            assert s >= docstring_end, f"Tag {tag_name} at [{s}:{e}] = {text[s:e]!r} is inside the docstring"
