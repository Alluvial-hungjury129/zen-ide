"""Python navigation edge cases — empty/None inputs, pattern matching traps,
import handling, and variable/class detection.

Covers:
- Empty/None inputs for all public helpers
- Pattern matching traps (comments, strings, whitespace)
- Import handling (relative, absolute, aliases, parenthesized, multiline)
- Variable/class detection (qualified, underscored, nested)
"""

from navigation.python_navigation_mixin import PythonNavigationMixin


class _Stub(PythonNavigationMixin):
    def __init__(self):
        self.get_workspace_folders = None
        self.open_file_callback = None
        self._pending_navigate_symbol = None
        self._pending_file_path = None
        self._navigation_timeout_id = None

    def _schedule_pending_navigation(self):
        pass


_stub = _Stub()


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Empty / None Cases
# ═══════════════════════════════════════════════════════════════════════════════
class TestEmptyNoneCases:
    """Ensure all public helpers handle degenerate input gracefully."""

    def test_parse_imports_empty(self):
        assert _stub._ts_py.parse_imports("") == {}

    def test_parse_imports_whitespace_only(self):
        assert _stub._ts_py.parse_imports("   \n\n  \t  ") == {}

    def test_parse_imports_no_imports(self):
        assert _stub._ts_py.parse_imports("x = 1\nprint(x)\n") == {}

    def test_find_symbol_empty_content(self):
        assert _stub._ts_py.find_symbol_in_content("", "foo") is None

    def test_find_symbol_none_symbol_in_valid_content(self):
        assert _stub._ts_py.find_symbol_in_content("x = 1", "nonexistent") is None

    def test_find_variable_class_empty_content(self):
        assert _stub._ts_py.find_variable_class("", "x") is None

    def test_find_variable_class_whitespace_content(self):
        assert _stub._ts_py.find_variable_class("  \n  ", "x") is None

    def test_find_self_attr_class_empty_content(self):
        assert _stub._ts_py.find_self_attr_class("", "x") is None

    def test_find_self_attr_class_whitespace_content(self):
        assert _stub._ts_py.find_self_attr_class("  \n  ", "x") is None

    def test_resolve_reexport_empty_init(self, tmp_path):
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        init = pkg / "__init__.py"
        init.write_text("")

        assert _stub._resolve_reexport_in_init(str(init), "Foo", str(tmp_path / "x.py")) is None

    def test_find_module_init_none_current_file(self):
        assert _stub._find_module_init("os", None) is None

    def test_open_module_none_current_file(self):
        assert _stub._open_module("os", None) is False


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Pattern Matching — comments, strings, whitespace traps
# ═══════════════════════════════════════════════════════════════════════════════
class TestPatternMatchingTraps:
    """Imports in comments/strings should not be parsed; real imports should be
    detected regardless of whitespace quirks."""

    # --- Comments ---
    def test_ignores_commented_import(self):
        content = "# import os\nimport sys\n"
        result = _stub._ts_py.parse_imports(content)
        assert "os" not in result
        assert "sys" in result

    def test_ignores_inline_comment_after_import(self):
        content = "import os  # we use os for paths\n"
        result = _stub._ts_py.parse_imports(content)
        assert "os" in result

    def test_ignores_commented_from_import(self):
        content = "# from os.path import join\nfrom sys import argv\n"
        result = _stub._ts_py.parse_imports(content)
        assert "join" not in result
        assert "argv" in result

    # --- String literals that look like imports ---
    def test_string_literal_not_parsed_as_import(self):
        content = 'x = "import os"\nimport sys\n'
        result = _stub._ts_py.parse_imports(content)
        assert "sys" in result

    def test_docstring_with_import_example(self):
        content = '"""Example:\n    import fake_module\n"""\nimport real_module\n'
        result = _stub._ts_py.parse_imports(content)
        assert "real_module" in result

    # --- Whitespace variants ---
    def test_leading_whitespace_on_import(self):
        content = "    import os\n"
        result = _stub._ts_py.parse_imports(content)
        assert "os" in result

    def test_tabs_before_import(self):
        content = "\timport os\n"
        result = _stub._ts_py.parse_imports(content)
        assert "os" in result

    def test_trailing_whitespace_on_import(self):
        content = "import os   \n"
        result = _stub._ts_py.parse_imports(content)
        assert "os" in result

    # --- Symbol search traps ---
    def test_symbol_in_comment_not_matched_as_definition(self):
        content = "# class Foo:\nclass Bar:\n    pass\n"
        assert _stub._ts_py.find_symbol_in_content(content, "Bar") == 2
        # Foo in comment — should not match as class def (it starts with #)
        # The regex looks for ^class, so "# class Foo:" won't match ^class
        assert _stub._ts_py.find_symbol_in_content(content, "Foo") is None

    def test_symbol_in_string_literal(self):
        content = 'name = "MyClass"\nclass MyClass:\n    pass\n'
        # Should find the actual class def, not the string
        assert _stub._ts_py.find_symbol_in_content(content, "MyClass") == 2

    def test_symbol_assignment_matches_first_occurrence(self):
        content = "x = 1\nx = 2\n"
        assert _stub._ts_py.find_symbol_in_content(content, "x") == 1


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Import Handling — all flavours
# ═══════════════════════════════════════════════════════════════════════════════
class TestImportHandling:
    """Comprehensive import parsing: relative, absolute, aliases, multiline."""

    # --- Relative imports ---
    def test_single_dot_import(self):
        result = _stub._ts_py.parse_imports("from . import utils")
        assert "utils" in result
        assert result["utils"] == "..utils"

    def test_single_dot_named_import(self):
        result = _stub._ts_py.parse_imports("from .module import func")
        assert "func" in result
        assert result["func"] == ".module.func"

    def test_double_dot_import(self):
        result = _stub._ts_py.parse_imports("from ..shared import config")
        assert "config" in result
        assert result["config"] == "..shared.config"

    def test_triple_dot_import(self):
        result = _stub._ts_py.parse_imports("from ...base import Base")
        assert "Base" in result
        assert result["Base"] == "...base.Base"

    def test_relative_deep_import(self):
        result = _stub._ts_py.parse_imports("from ..pkg.module import Symbol")
        assert "Symbol" in result
        assert result["Symbol"] == "..pkg.module.Symbol"

    # --- Absolute imports ---
    def test_dotted_absolute_import(self):
        result = _stub._ts_py.parse_imports("import os.path")
        assert result["path"] == "os.path"

    def test_deeply_dotted_import(self):
        result = _stub._ts_py.parse_imports("import a.b.c.d")
        assert result["d"] == "a.b.c.d"

    # --- Aliases ---
    def test_import_as(self):
        result = _stub._ts_py.parse_imports("import numpy as np")
        assert result["np"] == "numpy"
        assert "numpy" not in result

    def test_from_import_as(self):
        result = _stub._ts_py.parse_imports("from os.path import join as pjoin")
        assert result["pjoin"] == "os.path.join"
        assert "join" not in result

    def test_multiple_aliases(self):
        result = _stub._ts_py.parse_imports("from typing import List as L, Dict as D, Optional as Opt")
        assert result["L"] == "typing.List"
        assert result["D"] == "typing.Dict"
        assert result["Opt"] == "typing.Optional"

    # --- Multiple imports on same line ---
    def test_multiple_from_imports(self):
        result = _stub._ts_py.parse_imports("from os.path import join, dirname, exists")
        assert "join" in result
        assert "dirname" in result
        assert "exists" in result

    # --- Parenthesized (multiline) imports ---
    def test_parenthesized_import(self):
        content = "from os.path import (\n    join,\n    dirname,\n    exists,\n)\n"
        result = _stub._ts_py.parse_imports(content)
        assert "join" in result
        assert "dirname" in result
        assert "exists" in result

    def test_parenthesized_import_with_aliases(self):
        content = "from typing import (\n    List as L,\n    Dict as D,\n)\n"
        result = _stub._ts_py.parse_imports(content)
        assert result["L"] == "typing.List"
        assert result["D"] == "typing.Dict"

    def test_parenthesized_import_with_comments(self):
        content = "from os.path import (\n    join,  # for joining\n    # dirname,  # skip\n    exists,\n)\n"
        result = _stub._ts_py.parse_imports(content)
        assert "join" in result
        assert "dirname" not in result
        # Tree-sitter correctly parses imports even with inline comments
        assert "exists" in result

    def test_parenthesized_import_no_inline_comments(self):
        """Parenthesized import without inline comments works correctly."""
        content = "from os.path import (\n    join,\n    dirname,\n    exists,\n)\n"
        result = _stub._ts_py.parse_imports(content)
        assert "join" in result
        assert "dirname" in result
        assert "exists" in result

    # --- Mixed imports in one file ---
    def test_complex_mixed_imports(self):
        content = (
            "import os\n"
            "import sys\n"
            "import json as J\n"
            "from pathlib import Path\n"
            "from os.path import join, dirname\n"
            "from .utils import helper\n"
            "from ..shared import config\n"
        )
        result = _stub._ts_py.parse_imports(content)
        assert result["os"] == "os"
        assert result["sys"] == "sys"
        assert result["J"] == "json"
        assert result["Path"] == "pathlib.Path"
        assert result["join"] == "os.path.join"
        assert result["dirname"] == "os.path.dirname"
        assert result["helper"] == ".utils.helper"
        assert result["config"] == "..shared.config"


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Variable / Class Detection
# ═══════════════════════════════════════════════════════════════════════════════
class TestVariableClassDetection:
    """_find_variable_class and _find_self_attr_class edge cases."""

    # --- _find_variable_class ---
    def test_qualified_class(self):
        assert _stub._ts_py.find_variable_class("client = vault.Client(url)", "client") == "vault.Client"

    def test_unqualified_class(self):
        assert _stub._ts_py.find_variable_class("x = MyClass()", "x") == "MyClass"

    def test_lowercase_function_not_matched(self):
        assert _stub._ts_py.find_variable_class("x = some_factory()", "x") is None

    def test_private_underscore_class(self):
        assert _stub._ts_py.find_variable_class("x = _Private()", "x") is None

    def test_dunder_class(self):
        # __Dunder starts with _, not uppercase -> should not match
        assert _stub._ts_py.find_variable_class("x = __Dunder()", "x") is None

    def test_class_with_underscore_suffix(self):
        assert _stub._ts_py.find_variable_class("x = MyClass_()", "x") == "MyClass_"

    def test_class_with_numbers(self):
        assert _stub._ts_py.find_variable_class("x = Http2Client()", "x") == "Http2Client"

    def test_deeply_qualified_class(self):
        assert _stub._ts_py.find_variable_class("c = a.b.Client()", "c") == "a.b.Client"

    def test_assignment_with_keyword_args(self):
        assert _stub._ts_py.find_variable_class("db = Database(host='localhost', port=5432)", "db") == "Database"

    def test_no_parens_not_constructor(self):
        # No parentheses — not a constructor call
        assert _stub._ts_py.find_variable_class("x = MyClass", "x") is None

    def test_wrong_variable_not_matched(self):
        assert _stub._ts_py.find_variable_class("x = MyClass()", "y") is None

    # --- _find_self_attr_class ---
    def test_self_attr_qualified(self):
        assert _stub._ts_py.find_self_attr_class("self.c = vault.Client(url)", "c") == "vault.Client"

    def test_self_attr_unqualified(self):
        assert _stub._ts_py.find_self_attr_class("self.svc = MyService()", "svc") == "MyService"

    def test_self_attr_lowercase_not_matched(self):
        assert _stub._ts_py.find_self_attr_class("self.x = factory()", "x") is None

    def test_self_attr_wrong_attr_not_matched(self):
        assert _stub._ts_py.find_self_attr_class("self.foo = Bar()", "baz") is None

    def test_self_attr_among_many(self):
        content = (
            "class Svc:\n"
            "    def __init__(self):\n"
            "        self.a = Alpha()\n"
            "        self.b = Beta()\n"
            "        self.c = Gamma()\n"
        )
        assert _stub._ts_py.find_self_attr_class(content, "a") == "Alpha"
        assert _stub._ts_py.find_self_attr_class(content, "b") == "Beta"
        assert _stub._ts_py.find_self_attr_class(content, "c") == "Gamma"

    def test_self_attr_no_args(self):
        assert _stub._ts_py.find_self_attr_class("self.p = Processor()", "p") == "Processor"

    def test_self_attr_with_string_arg(self):
        assert _stub._ts_py.find_self_attr_class('self.db = DBClient("host")', "db") == "DBClient"
