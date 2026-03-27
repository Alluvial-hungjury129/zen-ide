"""Tests for dot-access/member completions in editor/autocomplete/python_provider.py."""

from editor.autocomplete.python_completion_provider import PythonCompletionProvider
from editor.autocomplete.tree_sitter_provider import (
    py_extract_class_members,
    py_find_enclosing_class,
    py_resolve_chain,
    py_resolve_variable_type,
)
from tests.editor.autocomplete.conftest import _py


class TestFindEnclosingClass:
    """Test enclosing class detection."""

    def test_finds_class(self):
        text = "class Foo:\n    def bar(self):\n        self."
        source, tree = _py(text)
        byte_offset = len(text.encode("utf-8"))
        result = py_find_enclosing_class(source, tree, byte_offset)
        assert result == "Foo"

    def test_no_class(self):
        text = "def standalone():\n    pass"
        source, tree = _py(text)
        byte_offset = len(text.encode("utf-8"))
        result = py_find_enclosing_class(source, tree, byte_offset)
        assert result is None


class TestExtractClassMembers:
    """Test class member extraction."""

    def test_extracts_methods(self):
        text = "class Foo:\n    def bar(self):\n        pass\n    def baz(self) -> int:\n        pass"
        source, tree = _py(text)
        items = py_extract_class_members(source, tree, "Foo")
        names = [i.name for i in items]
        assert "bar" in names
        assert "baz" in names

    def test_excludes_private(self):
        text = "class Foo:\n    def _private(self):\n        pass\n    def public(self):\n        pass"
        source, tree = _py(text)
        items = py_extract_class_members(source, tree, "Foo")
        names = [i.name for i in items]
        assert "_private" not in names
        assert "public" in names

    def test_extracts_attributes(self):
        text = "class Foo:\n    count = 0\n    name = 'test'"
        source, tree = _py(text)
        items = py_extract_class_members(source, tree, "Foo")
        names = [i.name for i in items]
        assert "count" in names
        assert "name" in names


class TestGetClassBodyText:
    """Test class body traversal via tree-sitter (replaces text extraction)."""

    def test_extracts_body(self):
        text = "class Foo:\n    x = 1\n    def bar(self):\n        pass\n\nclass Other:\n    pass"
        source, tree = _py(text)
        items = py_extract_class_members(source, tree, "Foo", include_private=True)
        names = [i.name for i in items]
        assert "x" in names
        assert "bar" in names

    def test_class_not_found(self):
        text = "class Foo:\n    pass"
        source, tree = _py(text)
        items = py_extract_class_members(source, tree, "Bar")
        assert items == []


class TestResolveVariableType:
    """Test variable type resolution from assignments."""

    def test_constructor_call(self):
        text = "client = OnboardingClient(config)"
        source, tree = _py(text)
        assert py_resolve_variable_type(source, tree, "client") == "OnboardingClient"

    def test_module_constructor_call(self):
        text = "client = clients.OnboardingClient(config)"
        source, tree = _py(text)
        assert py_resolve_variable_type(source, tree, "client") == "OnboardingClient"

    def test_type_annotation(self):
        text = "client: OnboardingClient = create_client()"
        source, tree = _py(text)
        assert py_resolve_variable_type(source, tree, "client") == "OnboardingClient"

    def test_no_match(self):
        text = "x = 42"
        source, tree = _py(text)
        assert py_resolve_variable_type(source, tree, "x") is None

    def test_not_found(self):
        text = "other = Foo()"
        source, tree = _py(text)
        assert py_resolve_variable_type(source, tree, "client") is None


class TestResolveChainInTextNoFalsePositive:
    """Test that py_resolve_chain doesn't return wrong methods for variables."""

    def test_variable_at_top_level_returns_empty(self):
        """A variable assignment at top level should NOT return all methods from the file."""
        text = (
            "from clients import OnboardingClient\n"
            "\n"
            "class Handler:\n"
            "    def process(self):\n"
            "        pass\n"
            "\n"
            "onboarding_client = OnboardingClient()\n"
        )
        source, tree = _py(text)
        result = py_resolve_chain(source, tree, ["onboarding_client"])
        assert result == []

    def test_enum_member_inside_class_still_works(self):
        """Attribute access on a class returns its members."""
        text = "class Status:\n    ACTIVE = 'active'\n    INACTIVE = 'inactive'\n    def label(self) -> str:\n        pass\n"
        source, tree = _py(text)
        # Resolve ["Status"] to get the class members
        result = py_resolve_chain(source, tree, ["Status"])
        names = [i.name for i in result]
        assert "label" in names
        assert "ACTIVE" in names


# ---------------------------------------------------------------------------
# Parameter completion tests
# ---------------------------------------------------------------------------


class TestSplitCallArgs:
    """Test argument splitting for function calls."""

    def test_simple_args(self):
        p = PythonCompletionProvider()
        assert p._split_call_args("a, b, c") == ["a", "b", "c"]

    def test_empty(self):
        p = PythonCompletionProvider()
        assert p._split_call_args("") == []

    def test_nested_parens(self):
        p = PythonCompletionProvider()
        result = p._split_call_args("func(x, y), b")
        assert result == ["func(x, y)", "b"]

    def test_string_with_comma(self):
        p = PythonCompletionProvider()
        result = p._split_call_args('"hello, world", b')
        assert result == ['"hello, world"', "b"]

    def test_keyword_args(self):
        p = PythonCompletionProvider()
        result = p._split_call_args("a, key=True, other=3")
        assert result == ["a", "key=True", "other=3"]

    def test_nested_brackets(self):
        p = PythonCompletionProvider()
        result = p._split_call_args("[1, 2], {a: b}")
        assert result == ["[1, 2]", "{a: b}"]


class TestParseParamsWithDefaults:
    """Test parameter parsing from function signatures."""

    def test_simple_params(self):
        p = PythonCompletionProvider()
        result = p._parse_params_with_defaults("func(a, b, c)")
        assert result == [("a", None), ("b", None), ("c", None)]

    def test_strips_self(self):
        p = PythonCompletionProvider()
        result = p._parse_params_with_defaults("method(self, a, b)")
        assert result == [("a", None), ("b", None)]

    def test_strips_cls(self):
        p = PythonCompletionProvider()
        result = p._parse_params_with_defaults("method(cls, a)")
        assert result == [("a", None)]

    def test_default_values(self):
        p = PythonCompletionProvider()
        result = p._parse_params_with_defaults("func(a, b=True, c=None)")
        assert result == [("a", None), ("b", "True"), ("c", "None")]

    def test_type_annotations(self):
        p = PythonCompletionProvider()
        result = p._parse_params_with_defaults("func(a: int, b: str = 'hello')")
        assert result == [("a", None), ("b", "'hello'")]

    def test_skips_star_args(self):
        p = PythonCompletionProvider()
        result = p._parse_params_with_defaults("func(a, *args, **kwargs)")
        assert result == [("a", None)]

    def test_keyword_only_after_star(self):
        p = PythonCompletionProvider()
        result = p._parse_params_with_defaults("func(a, *, key=True)")
        assert result == [("a", None), ("key", "True")]

    def test_empty_params(self):
        p = PythonCompletionProvider()
        result = p._parse_params_with_defaults("func()")
        assert result == []

    def test_self_only(self):
        p = PythonCompletionProvider()
        result = p._parse_params_with_defaults("method(self)")
        assert result == []

    def test_positional_only_separator(self):
        p = PythonCompletionProvider()
        result = p._parse_params_with_defaults("func(a, /, b)")
        assert result == [("a", None), ("b", None)]


class TestDetectCallContext:
    """Test function call context detection using GtkTextBuffer mock."""

    @staticmethod
    def _make_buffer(text, cursor_pos):
        """Create a mock buffer with text and cursor at given position."""
        from unittest.mock import MagicMock

        class FakeIter:
            def __init__(self, pos):
                self._pos = pos
                self._text = text

            def copy(self):
                return FakeIter(self._pos)

            def get_char(self):
                if 0 <= self._pos < len(self._text):
                    return self._text[self._pos]
                return "\0"

            def get_offset(self):
                return self._pos

            def backward_char(self):
                if self._pos > 0:
                    self._pos -= 1
                    return True
                return False

            def forward_char(self):
                if self._pos < len(self._text):
                    self._pos += 1
                    return True
                return False

        buf = MagicMock()

        def get_text(start, end, hidden):
            return text[start._pos : end._pos]

        buf.get_text = get_text
        cursor_iter = FakeIter(cursor_pos)
        return buf, cursor_iter

    def test_simple_call(self):
        p = PythonCompletionProvider()
        text = "func(a, "
        buf, cursor = self._make_buffer(text, len(text))
        result = p._detect_call_context(buf, cursor)
        assert result is not None
        func_chain, kwargs, pos_count = result
        assert func_chain == "func"
        assert pos_count == 1
        assert kwargs == set()

    def test_call_with_kwargs(self):
        p = PythonCompletionProvider()
        text = "func(a, key=True, "
        buf, cursor = self._make_buffer(text, len(text))
        result = p._detect_call_context(buf, cursor)
        func_chain, kwargs, pos_count = result
        assert func_chain == "func"
        assert pos_count == 1
        assert kwargs == {"key"}

    def test_method_call(self):
        p = PythonCompletionProvider()
        text = "self.get_item(card_id, "
        buf, cursor = self._make_buffer(text, len(text))
        result = p._detect_call_context(buf, cursor)
        func_chain, kwargs, pos_count = result
        assert func_chain == "self.get_item"
        assert pos_count == 1

    def test_nested_call(self):
        p = PythonCompletionProvider()
        text = "func(other(x), "
        buf, cursor = self._make_buffer(text, len(text))
        result = p._detect_call_context(buf, cursor)
        func_chain, kwargs, pos_count = result
        assert func_chain == "func"
        assert pos_count == 1

    def test_empty_call(self):
        p = PythonCompletionProvider()
        text = "func("
        buf, cursor = self._make_buffer(text, len(text))
        result = p._detect_call_context(buf, cursor)
        func_chain, kwargs, pos_count = result
        assert func_chain == "func"
        assert pos_count == 0
        assert kwargs == set()

    def test_skips_keywords(self):
        p = PythonCompletionProvider()
        text = "if ("
        buf, cursor = self._make_buffer(text, len(text))
        result = p._detect_call_context(buf, cursor)
        assert result is None

    def test_not_in_call(self):
        p = PythonCompletionProvider()
        text = "x = 42\n"
        buf, cursor = self._make_buffer(text, len(text))
        result = p._detect_call_context(buf, cursor)
        assert result is None

    def test_dotted_method_call(self):
        p = PythonCompletionProvider()
        text = "db_table.get_item(card_id, "
        buf, cursor = self._make_buffer(text, len(text))
        result = p._detect_call_context(buf, cursor)
        func_chain, kwargs, pos_count = result
        assert func_chain == "db_table.get_item"
        assert pos_count == 1


class TestResolveFunctionSignature:
    """Test function signature resolution."""

    def test_local_function(self):
        p = PythonCompletionProvider()
        text = "def get_item(card_id, strong_consistent_read=False):\n    pass\n"
        sig = p._resolve_function_signature("get_item", None, text)
        assert sig is not None
        assert "card_id" in sig
        assert "strong_consistent_read=False" in sig

    def test_local_method_via_self(self):
        p = PythonCompletionProvider()
        text = (
            "class MyService:\n"
            "    def process(self, item_id: str, retry: bool = True) -> dict:\n"
            "        pass\n"
            "    def run(self):\n"
            "        self.process(x, "
        )
        cursor_offset = len(text)
        sig = p._resolve_function_signature("self.process", None, text, cursor_offset=cursor_offset)
        assert sig is not None
        assert "item_id" in sig
        assert "retry" in sig

    def test_local_class_constructor(self):
        p = PythonCompletionProvider()
        text = "class Config:\n    def __init__(self, host: str, port: int = 8080):\n        pass\n"
        sig = p._resolve_function_signature("Config", None, text)
        assert sig is not None
        assert "host" in sig
        assert "port" in sig

    def test_multiline_function(self):
        p = PythonCompletionProvider()
        text = "def fetch(\n    url: str,\n    timeout: int = 30,\n    verify: bool = True\n) -> dict:\n    pass\n"
        sig = p._resolve_function_signature("fetch", None, text)
        assert sig is not None
        assert "url" in sig
        assert "timeout" in sig
        assert "verify" in sig

    def test_resolved_variable_type(self):
        p = PythonCompletionProvider()
        text = (
            "class Client:\n"
            "    def connect(self, host: str, port: int = 443):\n"
            "        pass\n\n"
            "client = Client()\n"
            "client.connect("
        )
        sig = p._resolve_function_signature("client.connect", None, text)
        assert sig is not None
        assert "host" in sig
        assert "port" in sig


class TestCallParameterCompletionsEndToEnd:
    """End-to-end tests for parameter completions using buffer mock."""

    @staticmethod
    def _make_buffer(text, cursor_pos):
        return TestDetectCallContext._make_buffer(text, cursor_pos)

    def test_suggests_remaining_params(self):
        p = PythonCompletionProvider()
        code = "def get_item(card_id, strong_consistent_read=False):\n    pass\n\nget_item(card_id, "
        buf, cursor = self._make_buffer(code, len(code))
        items = p.get_call_parameter_completions(buf, cursor, None, code)
        assert len(items) == 1
        assert items[0].name == "strong_consistent_read"
        assert items[0].insert_text == "strong_consistent_read=False"

    def test_no_params_when_all_specified(self):
        p = PythonCompletionProvider()
        code = "def greet(name, greeting='Hello'):\n    pass\n\ngreet(name, greeting='Hi', "
        buf, cursor = self._make_buffer(code, len(code))
        items = p.get_call_parameter_completions(buf, cursor, None, code)
        assert len(items) == 0

    def test_empty_call_shows_all_params(self):
        p = PythonCompletionProvider()
        code = "def fetch(url, timeout=30, verify=True):\n    pass\n\nfetch("
        buf, cursor = self._make_buffer(code, len(code))
        items = p.get_call_parameter_completions(buf, cursor, None, code)
        names = [i.name for i in items]
        assert "url" in names
        assert "timeout" in names
        assert "verify" in names

    def test_skips_positional_args(self):
        p = PythonCompletionProvider()
        code = "def fetch(url, timeout=30, verify=True):\n    pass\n\nfetch(my_url, "
        buf, cursor = self._make_buffer(code, len(code))
        items = p.get_call_parameter_completions(buf, cursor, None, code)
        names = [i.name for i in items]
        assert "url" not in names
        assert "timeout" in names
        assert "verify" in names

    def test_param_has_correct_kind(self):
        from editor.autocomplete import CompletionKind

        p = PythonCompletionProvider()
        code = "def func(a, b=1):\n    pass\n\nfunc("
        buf, cursor = self._make_buffer(code, len(code))
        items = p.get_call_parameter_completions(buf, cursor, None, code)
        assert all(i.kind == CompletionKind.PARAMETER for i in items)

    def test_required_param_insert_text_has_equals(self):
        p = PythonCompletionProvider()
        code = "def func(a, b):\n    pass\n\nfunc("
        buf, cursor = self._make_buffer(code, len(code))
        items = p.get_call_parameter_completions(buf, cursor, None, code)
        a_item = next(i for i in items if i.name == "a")
        assert a_item.insert_text == "a="
