"""Tests for symbol completions in editor/autocomplete/python_provider.py."""

from editor.autocomplete.python_provider import PythonCompletionProvider
from editor.autocomplete.tree_sitter_provider import (
    _find_class_node,
    _is_dataclass_node,
    py_extract_class_members,
    py_extract_definitions,
    py_extract_init_signature,
)
from tests.editor.autocomplete.conftest import _py


class TestGetSymbols:
    """Test local symbol extraction."""

    def test_class_definition(self):
        source, tree = _py("class MyClass:\n    pass")
        items = py_extract_definitions(source, tree)
        names = [i.name for i in items]
        assert "MyClass" in names

    def test_function_definition(self):
        source, tree = _py("def hello(name: str) -> str:\n    pass")
        items = py_extract_definitions(source, tree)
        names = [i.name for i in items]
        assert "hello" in names

    def test_function_with_signature(self):
        source, tree = _py("def greet(name: str) -> str:\n    pass")
        items = py_extract_definitions(source, tree)
        funcs = [i for i in items if i.name == "greet"]
        assert len(funcs) == 1
        assert "greet" in funcs[0].signature

    def test_variable_assignment(self):
        source, tree = _py("MY_CONST = 42")
        items = py_extract_definitions(source, tree)
        names = [i.name for i in items]
        assert "MY_CONST" in names

    def test_dunder_excluded(self):
        source, tree = _py("__all__ = ['foo']")
        items = py_extract_definitions(source, tree)
        names = [i.name for i in items]
        assert "__all__" not in names


class TestNormalizeMultilineDefs:
    """Test that multi-line defs are handled correctly via tree-sitter."""

    def test_single_line_unchanged(self):
        source, tree = _py("def foo(x): pass")
        items = py_extract_definitions(source, tree)
        assert any(i.name == "foo" for i in items)

    def test_multiline_joined(self):
        text = "def foo(\n    x,\n    y\n):\n    pass"
        source, tree = _py(text)
        items = py_extract_definitions(source, tree)
        funcs = [i for i in items if i.name == "foo"]
        assert len(funcs) == 1
        assert "x" in funcs[0].signature
        assert "y" in funcs[0].signature


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


class TestPeekDocstring:
    """Test docstring extraction from function/class definitions via tree-sitter."""

    def test_triple_quoted_docstring(self):
        text = 'class C:\n    def foo(self):\n        """This is foo."""\n        pass'
        source, tree = _py(text)
        items = py_extract_class_members(source, tree, "C", include_private=True)
        item = next(i for i in items if i.name == "foo")
        assert item.docstring == "This is foo."

    def test_single_quoted_docstring(self):
        text = "class C:\n    def bar(self):\n        '''Bar doc.'''\n        pass"
        source, tree = _py(text)
        items = py_extract_class_members(source, tree, "C", include_private=True)
        item = next(i for i in items if i.name == "bar")
        assert item.docstring == "Bar doc."

    def test_multiline_docstring(self):
        text = 'class C:\n    def baz(self):\n        """\n        Baz description.\n        """\n        pass'
        source, tree = _py(text)
        items = py_extract_class_members(source, tree, "C", include_private=True)
        item = next(i for i in items if i.name == "baz")
        assert item.docstring == "Baz description."

    def test_multiline_docstring_content_after_quote(self):
        text = 'class C:\n    def qux(self):\n        """Qux description.\n        More info.\n        """\n        pass'
        source, tree = _py(text)
        items = py_extract_class_members(source, tree, "C", include_private=True)
        item = next(i for i in items if i.name == "qux")
        assert item.docstring == "Qux description."

    def test_hash_comment_above_def(self):
        """Tree-sitter extracts actual docstrings, not comments above defs."""
        text = "class C:\n    # Calculate the sum of values\n    def calc_sum(self, values):\n        pass"
        source, tree = _py(text)
        items = py_extract_class_members(source, tree, "C", include_private=True)
        item = next(i for i in items if i.name == "calc_sum")
        assert item.docstring == ""

    def test_hash_comment_with_blank_line(self):
        """Tree-sitter extracts actual docstrings, not comments."""
        text = "class C:\n    # Helper function\n\n    def helper(self):\n        pass"
        source, tree = _py(text)
        items = py_extract_class_members(source, tree, "C", include_private=True)
        item = next(i for i in items if i.name == "helper")
        assert item.docstring == ""

    def test_docstring_preferred_over_comment(self):
        text = 'class C:\n    # Above comment\n    def foo(self):\n        """Docstring wins."""\n        pass'
        source, tree = _py(text)
        items = py_extract_class_members(source, tree, "C", include_private=True)
        item = next(i for i in items if i.name == "foo")
        assert item.docstring == "Docstring wins."

    def test_no_docstring_no_comment(self):
        text = "class C:\n    x = 1\n    def foo(self):\n        pass"
        source, tree = _py(text)
        items = py_extract_class_members(source, tree, "C", include_private=True)
        item = next(i for i in items if i.name == "foo")
        assert item.docstring == ""

    def test_first_def_at_index_zero(self):
        text = "def first():\n    pass"
        source, tree = _py(text)
        items = py_extract_definitions(source, tree)
        item = next(i for i in items if i.name == "first")
        assert item.docstring == ""


class TestExtractDocstringAt:
    """Test docstring extraction from top-level definitions via tree-sitter."""

    def test_docstring_after_def(self):
        text = 'def foo():\n    """Foo docs."""\n    pass'
        source, tree = _py(text)
        items = py_extract_definitions(source, tree)
        item = next(i for i in items if i.name == "foo")
        assert item.docstring == "Foo docs."

    def test_comment_above_def(self):
        """Tree-sitter only extracts actual docstrings, not comments above defs."""
        text = "# Initialize the connection\ndef connect():\n    pass"
        source, tree = _py(text)
        items = py_extract_definitions(source, tree)
        item = next(i for i in items if i.name == "connect")
        assert item.docstring == ""

    def test_docstring_preferred_over_comment(self):
        text = '# Above comment\ndef foo():\n    """Docstring."""\n    pass'
        source, tree = _py(text)
        items = py_extract_definitions(source, tree)
        item = next(i for i in items if i.name == "foo")
        assert item.docstring == "Docstring."

    def test_no_docstring_no_comment(self):
        text = "x = 1\ndef foo():\n    pass"
        source, tree = _py(text)
        items = py_extract_definitions(source, tree)
        item = next(i for i in items if i.name == "foo")
        assert item.docstring == ""


class TestClassMembersDocstrings:
    """Test that class member extraction includes docstrings."""

    def test_method_with_docstring(self):
        text = 'class MyClass:\n    def greet(self, name):\n        """Say hello."""\n        pass\n'
        source, tree = _py(text)
        items = py_extract_class_members(source, tree, "MyClass")
        item = next(i for i in items if i.name == "greet")
        assert item.docstring == "Say hello."

    def test_method_with_comment(self):
        """Tree-sitter only extracts actual docstrings, not comments."""
        text = "class MyClass:\n    # Compute the total\n    def total(self):\n        return 42\n"
        source, tree = _py(text)
        items = py_extract_class_members(source, tree, "MyClass")
        item = next(i for i in items if i.name == "total")
        assert item.docstring == ""

    def test_method_no_doc(self):
        text = "class MyClass:\n    x = 1\n    def run(self):\n        pass\n"
        source, tree = _py(text)
        items = py_extract_class_members(source, tree, "MyClass")
        item = next(i for i in items if i.name == "run")
        assert item.docstring == ""


class TestDataclassSignature:
    """Test dataclass field extraction for constructor signatures."""

    @staticmethod
    def _init_sig(text, class_name):
        """Parse text and extract init signature for the named class."""
        source, tree = _py(text)
        class_node = _find_class_node(source, tree.root_node, class_name)
        if class_node is None:
            return f"{class_name}()"
        return py_extract_init_signature(source, class_node)

    def test_basic_dataclass_fields(self):
        text = (
            "from dataclasses import dataclass\n\n"
            "@dataclass\n"
            "class User:\n"
            "    name: str\n"
            "    age: int\n"
            "    active: bool = True\n"
        )
        sig = self._init_sig(text, "User")
        assert sig == "User(name: str, age: int, active: bool)"

    def test_dataclass_with_no_fields(self):
        text = "@dataclass\nclass Empty:\n    pass\n"
        sig = self._init_sig(text, "Empty")
        assert sig == "Empty()"

    def test_dataclass_skips_classvar(self):
        text = "@dataclass\nclass Config:\n    name: str\n    ClassVar_count: int\n    registry: ClassVar[dict] = {}\n"
        sig = self._init_sig(text, "Config")
        assert "registry" not in sig
        assert "name" in sig

    def test_dataclass_skips_field_init_false(self):
        text = "@dataclass\nclass Item:\n    name: str\n    computed: int = field(init=False, default=0)\n"
        sig = self._init_sig(text, "Item")
        assert "name" in sig
        assert "computed" not in sig

    def test_dataclasses_dot_dataclass(self):
        text = "@dataclasses.dataclass\nclass Point:\n    x: float\n    y: float\n"
        sig = self._init_sig(text, "Point")
        assert sig == "Point(x: float, y: float)"

    def test_dataclass_with_args(self):
        text = "@dataclass(frozen=True)\nclass Coord:\n    lat: float\n    lon: float\n"
        sig = self._init_sig(text, "Coord")
        assert sig == "Coord(lat: float, lon: float)"

    def test_not_a_dataclass(self):
        text = "class Plain:\n    x: int\n    y: int\n"
        sig = self._init_sig(text, "Plain")
        assert sig == "Plain()"

    def test_dataclass_with_explicit_init(self):
        """If a dataclass has explicit __init__, use that instead of fields."""
        text = (
            "@dataclass\n"
            "class Custom:\n"
            "    name: str\n"
            "    def __init__(self, name: str, extra: int):\n"
            "        self.name = name\n"
        )
        sig = self._init_sig(text, "Custom")
        assert sig == "Custom(self, name: str, extra: int)"

    def test_is_dataclass_with_other_decorators(self):
        text = "@some_decorator\n@dataclass\nclass Multi:\n    value: int\n"
        source, tree = _py(text)
        class_node = _find_class_node(source, tree.root_node, "Multi")
        assert _is_dataclass_node(source, class_node) is True

    def test_is_dataclass_false_for_plain_class(self):
        text = "class Plain:\n    pass\n"
        source, tree = _py(text)
        class_node = _find_class_node(source, tree.root_node, "Plain")
        assert _is_dataclass_node(source, class_node) is False

    def test_dataclass_completions_integration(self):
        """get_completions returns dataclass with proper signature."""
        p = PythonCompletionProvider()
        text = "from dataclasses import dataclass\n\n@dataclass\nclass Record:\n    id: int\n    label: str\n"
        items = p.get_completions(text)
        record = next((i for i in items if i.name == "Record"), None)
        assert record is not None
        assert "id: int" in record.signature
        assert "label: str" in record.signature
