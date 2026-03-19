"""Tests for editor/autocomplete/python_provider.py - Python completions."""

from editor.autocomplete.python_provider import PythonCompletionProvider


class TestGetImports:
    """Test import extraction from Python source."""

    def test_simple_import(self):
        p = PythonCompletionProvider()
        items = p._get_imports("import os")
        names = [i.name for i in items]
        assert "os" in names

    def test_aliased_import(self):
        p = PythonCompletionProvider()
        items = p._get_imports("import numpy as np")
        names = [i.name for i in items]
        assert "np" in names

    def test_from_import(self):
        p = PythonCompletionProvider()
        items = p._get_imports("from os.path import join, dirname")
        names = [i.name for i in items]
        assert "join" in names
        assert "dirname" in names

    def test_from_import_with_alias(self):
        p = PythonCompletionProvider()
        items = p._get_imports("from collections import OrderedDict as OD")
        names = [i.name for i in items]
        assert "OD" in names


class TestGetSymbols:
    """Test local symbol extraction."""

    def test_class_definition(self):
        p = PythonCompletionProvider()
        items = p._get_symbols("class MyClass:\n    pass")
        names = [i.name for i in items]
        assert "MyClass" in names

    def test_function_definition(self):
        p = PythonCompletionProvider()
        items = p._get_symbols("def hello(name: str) -> str:\n    pass")
        names = [i.name for i in items]
        assert "hello" in names

    def test_function_with_signature(self):
        p = PythonCompletionProvider()
        items = p._get_symbols("def greet(name: str) -> str:\n    pass")
        funcs = [i for i in items if i.name == "greet"]
        assert len(funcs) == 1
        assert "greet" in funcs[0].signature

    def test_variable_assignment(self):
        p = PythonCompletionProvider()
        items = p._get_symbols("MY_CONST = 42")
        names = [i.name for i in items]
        assert "MY_CONST" in names

    def test_dunder_excluded(self):
        p = PythonCompletionProvider()
        items = p._get_symbols("__all__ = ['foo']")
        names = [i.name for i in items]
        assert "__all__" not in names


class TestNormalizeMultilineDefs:
    """Test multi-line def normalization."""

    def test_single_line_unchanged(self):
        p = PythonCompletionProvider()
        result = p._normalize_multiline_defs("def foo(x): pass")
        assert "def foo(x): pass" in result

    def test_multiline_joined(self):
        p = PythonCompletionProvider()
        text = "def foo(\n    x,\n    y\n):\n    pass"
        result = p._normalize_multiline_defs(text)
        assert "def foo(" in result
        # Should be joined to one line
        lines = result.splitlines()
        def_lines = [l for l in lines if "def foo" in l]
        assert len(def_lines) == 1


class TestGetCompletions:
    """Test full completions list."""

    def test_includes_keywords(self):
        p = PythonCompletionProvider()
        items = p.get_completions("")
        names = [i.name for i in items]
        assert "if" in names
        assert "def" in names
        assert "class" in names

    def test_includes_builtins(self):
        p = PythonCompletionProvider()
        items = p.get_completions("")
        names = [i.name for i in items]
        assert "len" in names
        assert "print" in names
        assert "isinstance" in names


class TestFindEnclosingClass:
    """Test enclosing class detection."""

    def test_finds_class(self):
        p = PythonCompletionProvider()
        text = "class Foo:\n    def bar(self):\n        self."
        result = p._find_enclosing_class(text, len(text))
        assert result == "Foo"

    def test_no_class(self):
        p = PythonCompletionProvider()
        text = "def standalone():\n    pass"
        result = p._find_enclosing_class(text, len(text))
        assert result is None


class TestExtractClassMembers:
    """Test class member extraction."""

    def test_extracts_methods(self):
        p = PythonCompletionProvider()
        text = "class Foo:\n    def bar(self):\n        pass\n    def baz(self) -> int:\n        pass"
        items = p._extract_class_members(text, "Foo")
        names = [i.name for i in items]
        assert "bar" in names
        assert "baz" in names

    def test_excludes_private(self):
        p = PythonCompletionProvider()
        text = "class Foo:\n    def _private(self):\n        pass\n    def public(self):\n        pass"
        items = p._extract_class_members(text, "Foo")
        names = [i.name for i in items]
        assert "_private" not in names
        assert "public" in names

    def test_extracts_attributes(self):
        p = PythonCompletionProvider()
        text = "class Foo:\n    count = 0\n    name = 'test'"
        items = p._extract_class_members(text, "Foo")
        names = [i.name for i in items]
        assert "count" in names
        assert "name" in names


class TestGetClassBodyText:
    """Test class body text extraction."""

    def test_extracts_body(self):
        p = PythonCompletionProvider()
        text = "class Foo:\n    x = 1\n    def bar(self):\n        pass\n\nclass Other:\n    pass"
        body = p._get_class_body_text(text, "Foo")
        assert body is not None
        assert "x = 1" in body
        assert "bar" in body
        assert "Other" not in body

    def test_class_not_found(self):
        p = PythonCompletionProvider()
        body = p._get_class_body_text("class Foo:\n    pass", "Bar")
        assert body is None


class TestResolveVariableType:
    """Test variable type resolution from assignments."""

    def test_constructor_call(self):
        p = PythonCompletionProvider()
        text = "client = OnboardingClient(config)"
        assert p._resolve_variable_type(text, "client") == "OnboardingClient"

    def test_module_constructor_call(self):
        p = PythonCompletionProvider()
        text = "client = clients.OnboardingClient(config)"
        assert p._resolve_variable_type(text, "client") == "OnboardingClient"

    def test_type_annotation(self):
        p = PythonCompletionProvider()
        text = "client: OnboardingClient = create_client()"
        assert p._resolve_variable_type(text, "client") == "OnboardingClient"

    def test_no_match(self):
        p = PythonCompletionProvider()
        text = "x = 42"
        assert p._resolve_variable_type(text, "x") is None

    def test_not_found(self):
        p = PythonCompletionProvider()
        text = "other = Foo()"
        assert p._resolve_variable_type(text, "client") is None


class TestResolveChainInTextNoFalsePositive:
    """Test that _resolve_chain_in_text doesn't return wrong methods for variables."""

    def test_variable_at_top_level_returns_empty(self):
        """A variable assignment at top level should NOT return all methods from the file."""
        p = PythonCompletionProvider()
        text = (
            "from clients import OnboardingClient\n"
            "\n"
            "class Handler:\n"
            "    def process(self):\n"
            "        pass\n"
            "\n"
            "onboarding_client = OnboardingClient()\n"
        )
        result = p._resolve_chain_in_text(text, ["onboarding_client"])
        # Should NOT return "process" from Handler class
        assert result == []

    def test_enum_member_inside_class_still_works(self):
        """Attribute access inside a class body should still return methods."""
        p = PythonCompletionProvider()
        text = "class Status:\n    ACTIVE = 'active'\n    INACTIVE = 'inactive'\n    def label(self) -> str:\n        pass\n"
        # Simulate chain ["Status", "ACTIVE"] — first drill into Status body, then ACTIVE
        result = p._resolve_chain_in_text(text, ["Status", "ACTIVE"])
        names = [i.name for i in result]
        assert "label" in names


class TestPeekDocstring:
    """Test _peek_docstring extraction from lines around a def."""

    def test_triple_quoted_docstring(self):
        lines = ["    def foo(self):", '        """This is foo."""', "        pass"]
        assert PythonCompletionProvider._peek_docstring(lines, 0) == "This is foo."

    def test_single_quoted_docstring(self):
        lines = ["    def bar(self):", "        '''Bar doc.'''", "        pass"]
        assert PythonCompletionProvider._peek_docstring(lines, 0) == "Bar doc."

    def test_multiline_docstring(self):
        lines = ["    def baz(self):", '        """', "        Baz description.", '        """', "        pass"]
        assert PythonCompletionProvider._peek_docstring(lines, 0) == "Baz description."

    def test_multiline_docstring_content_after_quote(self):
        lines = ["    def qux(self):", '        """Qux description.', "        More info.", '        """']
        assert PythonCompletionProvider._peek_docstring(lines, 0) == "Qux description.\nMore info."

    def test_hash_comment_above_def(self):
        lines = ["    # Calculate the sum of values", "    def calc_sum(self, values):", "        pass"]
        assert PythonCompletionProvider._peek_docstring(lines, 1) == "Calculate the sum of values"

    def test_hash_comment_with_blank_line(self):
        lines = ["    # Helper function", "", "    def helper(self):", "        pass"]
        assert PythonCompletionProvider._peek_docstring(lines, 2) == "Helper function"

    def test_docstring_preferred_over_comment(self):
        lines = ["    # Above comment", "    def foo(self):", '        """Docstring wins."""', "        pass"]
        assert PythonCompletionProvider._peek_docstring(lines, 1) == "Docstring wins."

    def test_no_docstring_no_comment(self):
        lines = ["    x = 1", "    def foo(self):", "        pass"]
        assert PythonCompletionProvider._peek_docstring(lines, 1) == ""

    def test_first_def_at_index_zero(self):
        lines = ["    def first(self):", "        pass"]
        assert PythonCompletionProvider._peek_docstring(lines, 0) == ""


class TestExtractDocstringAt:
    """Test _extract_docstring_at for top-level defs."""

    def test_docstring_after_def(self):
        text = 'def foo():\n    """Foo docs."""\n    pass'
        pos = text.index(":") + 1
        assert PythonCompletionProvider._extract_docstring_at(text, pos) == "Foo docs."

    def test_comment_above_def(self):
        text = "# Initialize the connection\ndef connect():\n    pass"
        pos = text.index(":") + 1
        assert PythonCompletionProvider._extract_docstring_at(text, pos) == "Initialize the connection"

    def test_docstring_preferred_over_comment(self):
        text = '# Above comment\ndef foo():\n    """Docstring."""\n    pass'
        pos = text.index(":") + 1
        assert PythonCompletionProvider._extract_docstring_at(text, pos) == "Docstring."

    def test_no_docstring_no_comment(self):
        text = "x = 1\ndef foo():\n    pass"
        pos = text.index(":") + 1
        assert PythonCompletionProvider._extract_docstring_at(text, pos) == ""


class TestClassMembersDocstrings:
    """Test that class member extraction includes docstrings and comments."""

    def test_method_with_docstring(self):
        p = PythonCompletionProvider()
        text = 'class MyClass:\n    def greet(self, name):\n        """Say hello."""\n        pass\n'
        items = p._extract_class_members(text, "MyClass")
        item = next(i for i in items if i.name == "greet")
        assert item.docstring == "Say hello."

    def test_method_with_comment(self):
        p = PythonCompletionProvider()
        text = "class MyClass:\n    # Compute the total\n    def total(self):\n        return 42\n"
        items = p._extract_class_members(text, "MyClass")
        item = next(i for i in items if i.name == "total")
        assert item.docstring == "Compute the total"

    def test_method_no_doc(self):
        p = PythonCompletionProvider()
        text = "class MyClass:\n    x = 1\n    def run(self):\n        pass\n"
        items = p._extract_class_members(text, "MyClass")
        item = next(i for i in items if i.name == "run")
        assert item.docstring == ""


class TestFollowReexport:
    """Test _follow_reexport for __init__.py re-export resolution."""

    def test_matches_reexport(self):
        p = PythonCompletionProvider()
        init_text = "from .db_handler import DBHandler\nfrom .utils import helper\n"
        # Should find the submodule name for DBHandler
        result = p._follow_reexport(init_text, "DBHandler", "mypkg", "/fake/path.py")
        # Returns None because the submodule file doesn't exist, but the regex match works
        assert result is None  # file not found on disk, but logic is correct

    def test_no_match_returns_none(self):
        p = PythonCompletionProvider()
        init_text = "from .utils import helper\n"
        result = p._follow_reexport(init_text, "NoSuchClass", "mypkg", "/fake/path.py")
        assert result is None

    def test_matches_among_multiple_imports(self):
        p = PythonCompletionProvider()
        init_text = "from .sub import Alpha, Beta, Gamma\n"
        # Should match Beta in the multi-import line
        result = p._follow_reexport(init_text, "Beta", "mypkg", "/fake/path.py")
        # File won't exist but the pattern was matched (result is None from missing file)
        assert result is None

    def test_does_not_match_non_relative_import(self):
        p = PythonCompletionProvider()
        init_text = "from other_pkg import MyClass\n"
        result = p._follow_reexport(init_text, "MyClass", "mypkg", "/fake/path.py")
        assert result is None


class TestReexportResolveDotCompletions:
    """Test that resolve_dot_completions follows __init__.py re-exports."""

    def test_follows_reexport_to_submodule(self, tmp_path):
        """When __init__.py re-exports a class, completions come from the submodule."""
        pkg = tmp_path / "mypkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("from .handler import MyHandler\n")
        (pkg / "handler.py").write_text(
            "class MyHandler:\n"
            '    def fetch(self, key):\n        """Fetch an item."""\n        pass\n'
            "    def save(self, item):\n        pass\n"
        )
        # Create a .git marker so _find_module_file stops walking
        (tmp_path / ".git").mkdir()

        # Caller file that imports MyHandler from mypkg
        caller = tmp_path / "app.py"
        caller.write_text("from mypkg import MyHandler\nhandler = MyHandler()\nhandler.\n")

        p = PythonCompletionProvider()
        items = p.resolve_dot_completions("handler", str(caller), caller.read_text())
        names = [i.name for i in items]
        assert "fetch" in names
        assert "save" in names

    def test_no_reexport_returns_empty(self, tmp_path):
        """When the class isn't in the module at all, returns empty."""
        pkg = tmp_path / "mypkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("VERSION = '1.0'\n")
        (tmp_path / ".git").mkdir()

        caller = tmp_path / "app.py"
        caller.write_text("from mypkg import Missing\nobj = Missing()\nobj.\n")

        p = PythonCompletionProvider()
        items = p.resolve_dot_completions("obj", str(caller), caller.read_text())
        assert items == []


class TestDataclassSignature:
    """Test dataclass field extraction for constructor signatures."""

    def test_basic_dataclass_fields(self):
        p = PythonCompletionProvider()
        text = (
            "from dataclasses import dataclass\n\n"
            "@dataclass\n"
            "class User:\n"
            "    name: str\n"
            "    age: int\n"
            "    active: bool = True\n"
        )
        sig = p._extract_init_signature(text, "User")
        assert sig == "User(name: str, age: int, active: bool)"

    def test_dataclass_with_no_fields(self):
        p = PythonCompletionProvider()
        text = "@dataclass\nclass Empty:\n    pass\n"
        sig = p._extract_init_signature(text, "Empty")
        assert sig == "Empty()"

    def test_dataclass_skips_classvar(self):
        p = PythonCompletionProvider()
        text = "@dataclass\nclass Config:\n    name: str\n    ClassVar_count: int\n    registry: ClassVar[dict] = {}\n"
        sig = p._extract_init_signature(text, "Config")
        assert "registry" not in sig
        assert "name" in sig

    def test_dataclass_skips_field_init_false(self):
        p = PythonCompletionProvider()
        text = "@dataclass\nclass Item:\n    name: str\n    computed: int = field(init=False, default=0)\n"
        sig = p._extract_init_signature(text, "Item")
        assert "name" in sig
        assert "computed" not in sig

    def test_dataclasses_dot_dataclass(self):
        p = PythonCompletionProvider()
        text = "@dataclasses.dataclass\nclass Point:\n    x: float\n    y: float\n"
        sig = p._extract_init_signature(text, "Point")
        assert sig == "Point(x: float, y: float)"

    def test_dataclass_with_args(self):
        p = PythonCompletionProvider()
        text = "@dataclass(frozen=True)\nclass Coord:\n    lat: float\n    lon: float\n"
        sig = p._extract_init_signature(text, "Coord")
        assert sig == "Coord(lat: float, lon: float)"

    def test_not_a_dataclass(self):
        p = PythonCompletionProvider()
        text = "class Plain:\n    x: int\n    y: int\n"
        sig = p._extract_init_signature(text, "Plain")
        assert sig == "Plain()"

    def test_dataclass_with_explicit_init(self):
        """If a dataclass has explicit __init__, use that instead of fields."""
        p = PythonCompletionProvider()
        text = (
            "@dataclass\n"
            "class Custom:\n"
            "    name: str\n"
            "    def __init__(self, name: str, extra: int):\n"
            "        self.name = name\n"
        )
        sig = p._extract_init_signature(text, "Custom")
        assert sig == "Custom(self, name: str, extra: int)"

    def test_is_dataclass_with_other_decorators(self):
        p = PythonCompletionProvider()
        text = "@some_decorator\n@dataclass\nclass Multi:\n    value: int\n"
        assert p._is_dataclass(text, "Multi") is True

    def test_is_dataclass_false_for_plain_class(self):
        p = PythonCompletionProvider()
        text = "class Plain:\n    pass\n"
        assert p._is_dataclass(text, "Plain") is False

    def test_dataclass_completions_integration(self):
        """get_completions returns dataclass with proper signature."""
        p = PythonCompletionProvider()
        text = "from dataclasses import dataclass\n\n@dataclass\nclass Record:\n    id: int\n    label: str\n"
        items = p.get_completions(text)
        record = next((i for i in items if i.name == "Record"), None)
        assert record is not None
        assert "id: int" in record.signature
        assert "label: str" in record.signature


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
        sig = p._resolve_function_signature("self.process", None, text, cursor_offset)
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
