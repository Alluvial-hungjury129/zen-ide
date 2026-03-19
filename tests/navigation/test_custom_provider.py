"""Tests for navigation/custom_provider.py - regex-based Python navigation."""

from navigation.custom_provider import CustomProvider


class TestSupportsLanguage:
    """Test file extension support."""

    def test_supports_py(self):
        p = CustomProvider()
        assert p.supports_language(".py") is True

    def test_supports_pyw(self):
        p = CustomProvider()
        assert p.supports_language(".pyw") is True

    def test_supports_pyi(self):
        p = CustomProvider()
        assert p.supports_language(".pyi") is True

    def test_case_insensitive(self):
        p = CustomProvider()
        assert p.supports_language(".PY") is True

    def test_js_not_supported(self):
        p = CustomProvider()
        assert p.supports_language(".js") is False


class TestParseImports:
    """Test import statement parsing."""

    def test_simple_import(self):
        p = CustomProvider()
        result = p.parse_imports("import os", ".py")
        assert result == {"os": "os"}

    def test_import_with_alias(self):
        p = CustomProvider()
        result = p.parse_imports("import numpy as np", ".py")
        assert result == {"np": "numpy"}

    def test_from_import(self):
        p = CustomProvider()
        result = p.parse_imports("from os.path import join", ".py")
        assert result == {"join": "os.path.join"}

    def test_from_import_with_alias(self):
        p = CustomProvider()
        result = p.parse_imports("from collections import OrderedDict as OD", ".py")
        assert result == {"OD": "collections.OrderedDict"}

    def test_multiple_from_imports(self):
        p = CustomProvider()
        result = p.parse_imports("from os.path import join, dirname", ".py")
        assert "join" in result
        assert "dirname" in result

    def test_dotted_import(self):
        p = CustomProvider()
        result = p.parse_imports("import os.path", ".py")
        assert result == {"path": "os.path"}

    def test_relative_import(self):
        p = CustomProvider()
        result = p.parse_imports("from .utils import helper", ".py")
        assert result == {"helper": ".utils.helper"}

    def test_unsupported_ext_returns_empty(self):
        p = CustomProvider()
        result = p.parse_imports("import os", ".js")
        assert result == {}


class TestFindSymbol:
    """Test symbol definition finding."""

    def test_find_class(self):
        p = CustomProvider()
        content = "class MyClass:\n    pass"
        assert p.find_symbol_in_content(content, "MyClass", ".py") == 1

    def test_find_function(self):
        p = CustomProvider()
        content = "def hello():\n    pass"
        assert p.find_symbol_in_content(content, "hello", ".py") == 1

    def test_find_indented_function(self):
        p = CustomProvider()
        content = "class Foo:\n    def bar(self):\n        pass"
        assert p.find_symbol_in_content(content, "bar", ".py") == 2

    def test_find_variable(self):
        p = CustomProvider()
        content = "MY_CONST = 42\nother = 1"
        assert p.find_symbol_in_content(content, "MY_CONST", ".py") == 1

    def test_symbol_not_found(self):
        p = CustomProvider()
        content = "class Foo:\n    pass"
        assert p.find_symbol_in_content(content, "Bar", ".py") is None

    def test_class_on_later_line(self):
        p = CustomProvider()
        content = "import os\n\nclass MyClass(Base):\n    pass"
        assert p.find_symbol_in_content(content, "MyClass", ".py") == 3

    def test_unsupported_ext_returns_none(self):
        p = CustomProvider()
        assert p.find_symbol_in_content("class Foo:", "Foo", ".js") is None
