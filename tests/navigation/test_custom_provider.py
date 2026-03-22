"""Tests for Python navigation provider (TreeSitterPyProvider).

Verifies the public API that was formerly exposed through CustomProvider.
"""

import pytest

try:
    from navigation.tree_sitter_py_provider import TreeSitterPyProvider

    _HAS_TS = True
except Exception:
    _HAS_TS = False

needs_ts = pytest.mark.skipif(not _HAS_TS, reason="tree-sitter not available")


@needs_ts
class TestSupportsLanguage:
    """Test file extension support."""

    def test_supports_py(self):
        p = TreeSitterPyProvider()
        assert p.supports_language(".py") is True

    def test_supports_pyw(self):
        p = TreeSitterPyProvider()
        assert p.supports_language(".pyw") is True

    def test_supports_pyi(self):
        p = TreeSitterPyProvider()
        assert p.supports_language(".pyi") is True

    def test_js_not_supported(self):
        p = TreeSitterPyProvider()
        assert p.supports_language(".js") is False


@needs_ts
class TestParseImports:
    """Test import statement parsing."""

    def test_simple_import(self):
        p = TreeSitterPyProvider()
        result = p.parse_imports("import os")
        assert result == {"os": "os"}

    def test_import_with_alias(self):
        p = TreeSitterPyProvider()
        result = p.parse_imports("import numpy as np")
        assert result == {"np": "numpy"}

    def test_from_import(self):
        p = TreeSitterPyProvider()
        result = p.parse_imports("from os.path import join")
        assert result == {"join": "os.path.join"}

    def test_from_import_with_alias(self):
        p = TreeSitterPyProvider()
        result = p.parse_imports("from collections import OrderedDict as OD")
        assert result == {"OD": "collections.OrderedDict"}

    def test_multiple_from_imports(self):
        p = TreeSitterPyProvider()
        result = p.parse_imports("from os.path import join, dirname")
        assert "join" in result
        assert "dirname" in result

    def test_dotted_import(self):
        p = TreeSitterPyProvider()
        result = p.parse_imports("import os.path")
        assert result == {"path": "os.path"}

    def test_relative_import(self):
        p = TreeSitterPyProvider()
        result = p.parse_imports("from .utils import helper")
        assert result == {"helper": ".utils.helper"}


@needs_ts
class TestFindSymbol:
    """Test symbol definition finding."""

    def test_find_class(self):
        p = TreeSitterPyProvider()
        content = "class MyClass:\n    pass"
        assert p.find_symbol_in_content(content, "MyClass") == 1

    def test_find_function(self):
        p = TreeSitterPyProvider()
        content = "def hello():\n    pass"
        assert p.find_symbol_in_content(content, "hello") == 1

    def test_find_indented_function(self):
        p = TreeSitterPyProvider()
        content = "class Foo:\n    def bar(self):\n        pass"
        assert p.find_symbol_in_content(content, "bar") == 2

    def test_find_variable(self):
        p = TreeSitterPyProvider()
        content = "MY_CONST = 42\nother = 1"
        assert p.find_symbol_in_content(content, "MY_CONST") == 1

    def test_symbol_not_found(self):
        p = TreeSitterPyProvider()
        content = "class Foo:\n    pass"
        assert p.find_symbol_in_content(content, "Bar") is None

    def test_class_on_later_line(self):
        p = TreeSitterPyProvider()
        content = "import os\n\nclass MyClass(Base):\n    pass"
        assert p.find_symbol_in_content(content, "MyClass") == 3
