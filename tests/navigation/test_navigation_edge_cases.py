"""Regression tests for Python navigation edge cases.

Covers: empty/None inputs, pattern matching traps (comments, strings, whitespace),
import handling (relative, aliases, parenthesized, multiline), variable/class
detection (qualified, underscored, nested), file system robustness (symlinks,
missing files, permissions), and package structure edge cases.
"""

import os
import stat

from navigation.code_navigation_py import PythonNavigationMixin


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
        assert _stub._parse_python_imports("") == {}

    def test_parse_imports_whitespace_only(self):
        assert _stub._parse_python_imports("   \n\n  \t  ") == {}

    def test_parse_imports_no_imports(self):
        assert _stub._parse_python_imports("x = 1\nprint(x)\n") == {}

    def test_find_symbol_empty_content(self):
        assert _stub._find_python_symbol_in_content("", "foo") is None

    def test_find_symbol_none_symbol_in_valid_content(self):
        assert _stub._find_python_symbol_in_content("x = 1", "nonexistent") is None

    def test_find_variable_class_empty_content(self):
        assert _stub._find_variable_class("", "x") is None

    def test_find_variable_class_whitespace_content(self):
        assert _stub._find_variable_class("  \n  ", "x") is None

    def test_find_self_attr_class_empty_content(self):
        assert _stub._find_self_attr_class("", "x") is None

    def test_find_self_attr_class_whitespace_content(self):
        assert _stub._find_self_attr_class("  \n  ", "x") is None

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
        result = _stub._parse_python_imports(content)
        assert "os" not in result
        assert "sys" in result

    def test_ignores_inline_comment_after_import(self):
        content = "import os  # we use os for paths\n"
        result = _stub._parse_python_imports(content)
        assert "os" in result

    def test_ignores_commented_from_import(self):
        content = "# from os.path import join\nfrom sys import argv\n"
        result = _stub._parse_python_imports(content)
        assert "join" not in result
        assert "argv" in result

    # --- String literals that look like imports ---
    def test_string_literal_not_parsed_as_import(self):
        content = 'x = "import os"\nimport sys\n'
        result = _stub._parse_python_imports(content)
        assert "sys" in result

    def test_docstring_with_import_example(self):
        content = '"""Example:\n    import fake_module\n"""\nimport real_module\n'
        result = _stub._parse_python_imports(content)
        assert "real_module" in result

    # --- Whitespace variants ---
    def test_leading_whitespace_on_import(self):
        content = "    import os\n"
        result = _stub._parse_python_imports(content)
        assert "os" in result

    def test_tabs_before_import(self):
        content = "\timport os\n"
        result = _stub._parse_python_imports(content)
        assert "os" in result

    def test_trailing_whitespace_on_import(self):
        content = "import os   \n"
        result = _stub._parse_python_imports(content)
        assert "os" in result

    # --- Symbol search traps ---
    def test_symbol_in_comment_not_matched_as_definition(self):
        content = "# class Foo:\nclass Bar:\n    pass\n"
        assert _stub._find_python_symbol_in_content(content, "Bar") == 2
        # Foo in comment — should not match as class def (it starts with #)
        # The regex looks for ^class, so "# class Foo:" won't match ^class
        assert _stub._find_python_symbol_in_content(content, "Foo") is None

    def test_symbol_in_string_literal(self):
        content = 'name = "MyClass"\nclass MyClass:\n    pass\n'
        # Should find the actual class def, not the string
        assert _stub._find_python_symbol_in_content(content, "MyClass") == 2

    def test_symbol_assignment_matches_first_occurrence(self):
        content = "x = 1\nx = 2\n"
        assert _stub._find_python_symbol_in_content(content, "x") == 1


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Import Handling — all flavours
# ═══════════════════════════════════════════════════════════════════════════════
class TestImportHandling:
    """Comprehensive import parsing: relative, absolute, aliases, multiline."""

    # --- Relative imports ---
    def test_single_dot_import(self):
        result = _stub._parse_python_imports("from . import utils")
        assert "utils" in result
        assert result["utils"] == "..utils"

    def test_single_dot_named_import(self):
        result = _stub._parse_python_imports("from .module import func")
        assert "func" in result
        assert result["func"] == ".module.func"

    def test_double_dot_import(self):
        result = _stub._parse_python_imports("from ..shared import config")
        assert "config" in result
        assert result["config"] == "..shared.config"

    def test_triple_dot_import(self):
        result = _stub._parse_python_imports("from ...base import Base")
        assert "Base" in result
        assert result["Base"] == "...base.Base"

    def test_relative_deep_import(self):
        result = _stub._parse_python_imports("from ..pkg.module import Symbol")
        assert "Symbol" in result
        assert result["Symbol"] == "..pkg.module.Symbol"

    # --- Absolute imports ---
    def test_dotted_absolute_import(self):
        result = _stub._parse_python_imports("import os.path")
        assert result["path"] == "os.path"

    def test_deeply_dotted_import(self):
        result = _stub._parse_python_imports("import a.b.c.d")
        assert result["d"] == "a.b.c.d"

    # --- Aliases ---
    def test_import_as(self):
        result = _stub._parse_python_imports("import numpy as np")
        assert result["np"] == "numpy"
        assert "numpy" not in result

    def test_from_import_as(self):
        result = _stub._parse_python_imports("from os.path import join as pjoin")
        assert result["pjoin"] == "os.path.join"
        assert "join" not in result

    def test_multiple_aliases(self):
        result = _stub._parse_python_imports("from typing import List as L, Dict as D, Optional as Opt")
        assert result["L"] == "typing.List"
        assert result["D"] == "typing.Dict"
        assert result["Opt"] == "typing.Optional"

    # --- Multiple imports on same line ---
    def test_multiple_from_imports(self):
        result = _stub._parse_python_imports("from os.path import join, dirname, exists")
        assert "join" in result
        assert "dirname" in result
        assert "exists" in result

    # --- Parenthesized (multiline) imports ---
    def test_parenthesized_import(self):
        content = "from os.path import (\n    join,\n    dirname,\n    exists,\n)\n"
        result = _stub._parse_python_imports(content)
        assert "join" in result
        assert "dirname" in result
        assert "exists" in result

    def test_parenthesized_import_with_aliases(self):
        content = "from typing import (\n    List as L,\n    Dict as D,\n)\n"
        result = _stub._parse_python_imports(content)
        assert result["L"] == "typing.List"
        assert result["D"] == "typing.Dict"

    def test_parenthesized_import_with_comments(self):
        content = "from os.path import (\n    join,  # for joining\n    # dirname,  # skip\n    exists,\n)\n"
        result = _stub._parse_python_imports(content)
        assert "join" in result
        assert "dirname" not in result
        # Known limitation: inline comment after comma causes the next symbol
        # to be grouped with the comment text. `exists` follows `# skip` in
        # the same comma-delimited chunk, so it gets dropped.
        # TODO: fix parser to split by newline first, then by comma
        assert "exists" not in result  # documents current behaviour

    def test_parenthesized_import_no_inline_comments(self):
        """Parenthesized import without inline comments works correctly."""
        content = "from os.path import (\n    join,\n    dirname,\n    exists,\n)\n"
        result = _stub._parse_python_imports(content)
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
        result = _stub._parse_python_imports(content)
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
        assert _stub._find_variable_class("client = vault.Client(url)", "client") == "vault.Client"

    def test_unqualified_class(self):
        assert _stub._find_variable_class("x = MyClass()", "x") == "MyClass"

    def test_lowercase_function_not_matched(self):
        assert _stub._find_variable_class("x = some_factory()", "x") is None

    def test_private_underscore_class(self):
        assert _stub._find_variable_class("x = _Private()", "x") is None

    def test_dunder_class(self):
        # __Dunder starts with _, not uppercase -> should not match
        assert _stub._find_variable_class("x = __Dunder()", "x") is None

    def test_class_with_underscore_suffix(self):
        assert _stub._find_variable_class("x = MyClass_()", "x") == "MyClass_"

    def test_class_with_numbers(self):
        assert _stub._find_variable_class("x = Http2Client()", "x") == "Http2Client"

    def test_deeply_qualified_class(self):
        assert _stub._find_variable_class("c = a.b.Client()", "c") == "a.b.Client"

    def test_assignment_with_keyword_args(self):
        assert _stub._find_variable_class("db = Database(host='localhost', port=5432)", "db") == "Database"

    def test_no_parens_not_constructor(self):
        # No parentheses — not a constructor call
        assert _stub._find_variable_class("x = MyClass", "x") is None

    def test_wrong_variable_not_matched(self):
        assert _stub._find_variable_class("x = MyClass()", "y") is None

    # --- _find_self_attr_class ---
    def test_self_attr_qualified(self):
        assert _stub._find_self_attr_class("self.c = vault.Client(url)", "c") == "vault.Client"

    def test_self_attr_unqualified(self):
        assert _stub._find_self_attr_class("self.svc = MyService()", "svc") == "MyService"

    def test_self_attr_lowercase_not_matched(self):
        assert _stub._find_self_attr_class("self.x = factory()", "x") is None

    def test_self_attr_wrong_attr_not_matched(self):
        assert _stub._find_self_attr_class("self.foo = Bar()", "baz") is None

    def test_self_attr_among_many(self):
        content = (
            "class Svc:\n"
            "    def __init__(self):\n"
            "        self.a = Alpha()\n"
            "        self.b = Beta()\n"
            "        self.c = Gamma()\n"
        )
        assert _stub._find_self_attr_class(content, "a") == "Alpha"
        assert _stub._find_self_attr_class(content, "b") == "Beta"
        assert _stub._find_self_attr_class(content, "c") == "Gamma"

    def test_self_attr_no_args(self):
        assert _stub._find_self_attr_class("self.p = Processor()", "p") == "Processor"

    def test_self_attr_with_string_arg(self):
        assert _stub._find_self_attr_class('self.db = DBClient("host")', "db") == "DBClient"


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Symbol Search (_find_python_symbol_in_content)
# ═══════════════════════════════════════════════════════════════════════════════
class TestSymbolSearchEdgeCases:
    """Edge cases for finding symbol definitions in content."""

    def test_class_with_parent(self):
        content = "class Child(Parent):\n    pass\n"
        assert _stub._find_python_symbol_in_content(content, "Child") == 1

    def test_class_with_multiple_parents(self):
        content = "class Multi(Base1, Base2, Mixin):\n    pass\n"
        assert _stub._find_python_symbol_in_content(content, "Multi") == 1

    def test_function_with_decorators(self):
        content = "@decorator\ndef my_func():\n    pass\n"
        assert _stub._find_python_symbol_in_content(content, "my_func") == 2

    def test_indented_method(self):
        content = "class A:\n    def method(self):\n        pass\n"
        assert _stub._find_python_symbol_in_content(content, "method") == 2

    def test_double_indented_method(self):
        content = "class A:\n    class B:\n        def deep(self):\n            pass\n"
        assert _stub._find_python_symbol_in_content(content, "deep") == 3

    def test_variable_with_type_hint(self):
        content = "count: int = 0\n"
        # The regex looks for `count =` but `: int =` has a colon before the `=`
        # `count: int = 0` should still match via the `symbol =` pattern
        # since there's whitespace before the `=`... but actually the regex
        # requires `count\s*=` which doesn't match `count: int = 0` due to `: int`
        # This documents current behavior
        result = _stub._find_python_symbol_in_content(content, "count")
        # Will be None because `count: int = 0` doesn't match `count\s*=`
        # (there's `: int` between the symbol and `=`)
        assert result is None

    def test_async_function(self):
        content = "async def fetch_data():\n    pass\n"
        # The regex looks for `def fetch_data` — "async def" has `def` in it
        # but the pattern is `^\s*def\s+` which won't match `async def`
        result = _stub._find_python_symbol_in_content(content, "fetch_data")
        assert result is None

    def test_underscore_function(self):
        content = "def _private_helper():\n    pass\n"
        assert _stub._find_python_symbol_in_content(content, "_private_helper") == 1

    def test_dunder_method(self):
        content = "class A:\n    def __init__(self):\n        pass\n"
        assert _stub._find_python_symbol_in_content(content, "__init__") == 2

    def test_constant_all_caps(self):
        content = "MAX_RETRIES = 5\n"
        assert _stub._find_python_symbol_in_content(content, "MAX_RETRIES") == 1

    def test_multiline_content_correct_line_number(self):
        content = "import os\n\n\n# comment\nclass MyClass:\n    pass\n"
        assert _stub._find_python_symbol_in_content(content, "MyClass") == 5


# ═══════════════════════════════════════════════════════════════════════════════
# 6. File System — symlinks, missing files, permissions
# ═══════════════════════════════════════════════════════════════════════════════
class TestFileSystemEdgeCases:
    """File system robustness: non-existent files, symlinks, permission errors."""

    def test_resolve_reexport_nonexistent_init(self):
        result = _stub._resolve_reexport_in_init("/nonexistent/__init__.py", "Foo", "/some/file.py")
        assert result is None

    def test_resolve_reexport_target_module_missing(self, tmp_path):
        """__init__.py references a module that doesn't exist on disk."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        init = pkg / "__init__.py"
        init.write_text("from .missing_module import Foo\n")

        result = _stub._resolve_reexport_in_init(str(init), "Foo", str(tmp_path / "x.py"))
        assert result is None

    def test_open_module_nonexistent_directory(self, tmp_path):
        stub = _Stub()
        stub.get_workspace_folders = lambda: [str(tmp_path / "nonexistent")]
        result = stub._open_module("fake_module", str(tmp_path / "x.py"))
        assert result is False

    def test_find_module_init_nonexistent(self, tmp_path):
        stub = _Stub()
        stub.get_workspace_folders = lambda: [str(tmp_path)]
        result = stub._find_module_init("nonexistent_package", str(tmp_path / "x.py"))
        assert result is None

    def test_symlinked_module(self, tmp_path):
        """Navigation should follow symlinks to real files."""
        real_pkg = tmp_path / "real_pkg"
        real_pkg.mkdir()
        real_init = real_pkg / "__init__.py"
        real_init.write_text("from .core import Widget\n")
        core = real_pkg / "core.py"
        core.write_text("class Widget:\n    pass\n")

        # Symlink the package
        link_pkg = tmp_path / "link_pkg"
        os.symlink(str(real_pkg), str(link_pkg))

        stub = _Stub()
        link_init = link_pkg / "__init__.py"
        result = stub._resolve_reexport_in_init(str(link_init), "Widget", str(tmp_path / "x.py"))
        assert result is not None
        assert result.endswith("core.py")

    def test_resolve_reexport_unreadable_init(self, tmp_path):
        """Unreadable __init__.py should return None, not crash."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        init = pkg / "__init__.py"
        init.write_text("from .core import Foo\n")
        os.chmod(str(init), 0o000)

        try:
            result = _stub._resolve_reexport_in_init(str(init), "Foo", str(tmp_path / "x.py"))
            assert result is None
        finally:
            os.chmod(str(init), stat.S_IRUSR | stat.S_IWUSR)

    def test_open_module_relative_single_dot(self, tmp_path):
        """_open_module with relative path '.' should handle gracefully."""
        target = tmp_path / "utils.py"
        target.write_text("def helper(): pass\n")

        stub = _Stub()
        opened = []
        stub.open_file_callback = lambda path, line: opened.append(path) or True
        result = stub._open_module(".utils", str(tmp_path / "main.py"))
        assert result is True
        assert len(opened) == 1
        assert opened[0].endswith("utils.py")

    def test_open_module_relative_double_dot(self, tmp_path):
        """_open_module with '..' should navigate up one directory."""
        parent = tmp_path / "parent"
        child = parent / "child"
        child.mkdir(parents=True)
        target = parent / "sibling.py"
        target.write_text("x = 1\n")

        stub = _Stub()
        opened = []
        stub.open_file_callback = lambda path, line: opened.append(path) or True
        result = stub._open_module("..sibling", str(child / "main.py"))
        assert result is True
        assert opened[0].endswith("sibling.py")


# ═══════════════════════════════════════════════════════════════════════════════
# 7. Package Structure
# ═══════════════════════════════════════════════════════════════════════════════
class TestPackageStructure:
    """Nested packages, namespace packages, and __init__.py variations."""

    def test_nested_package_reexport(self, tmp_path):
        """pkg/subpkg/__init__.py re-exports from pkg/subpkg/core.py."""
        pkg = tmp_path / "pkg" / "subpkg"
        pkg.mkdir(parents=True)
        (tmp_path / "pkg" / "__init__.py").write_text("")
        init = pkg / "__init__.py"
        init.write_text("from .core import Deep\n")
        core = pkg / "core.py"
        core.write_text("class Deep:\n    pass\n")

        result = _stub._resolve_reexport_in_init(str(init), "Deep", str(tmp_path / "x.py"))
        assert result == str(core)

    def test_init_with_multiple_reexports(self, tmp_path):
        """__init__.py with several from-imports, each target exists."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        init = pkg / "__init__.py"
        init.write_text("from .models import User\nfrom .views import render\nfrom .utils import slugify\n")
        (pkg / "models.py").write_text("class User: pass\n")
        (pkg / "views.py").write_text("def render(): pass\n")
        (pkg / "utils.py").write_text("def slugify(): pass\n")

        stub = _Stub()
        assert stub._resolve_reexport_in_init(str(init), "User", str(tmp_path / "x.py")) == str(pkg / "models.py")
        assert stub._resolve_reexport_in_init(str(init), "render", str(tmp_path / "x.py")) == str(pkg / "views.py")
        assert stub._resolve_reexport_in_init(str(init), "slugify", str(tmp_path / "x.py")) == str(pkg / "utils.py")

    def test_init_with_parenthesized_reexport(self, tmp_path):
        """Multiline parenthesized import in __init__.py."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        init = pkg / "__init__.py"
        init.write_text("from .core import (\n    Alpha,\n    Beta,\n    Gamma,\n)\n")
        core = pkg / "core.py"
        core.write_text("class Alpha: pass\nclass Beta: pass\nclass Gamma: pass\n")

        stub = _Stub()
        assert stub._resolve_reexport_in_init(str(init), "Alpha", str(tmp_path / "x.py")) == str(core)
        assert stub._resolve_reexport_in_init(str(init), "Beta", str(tmp_path / "x.py")) == str(core)
        assert stub._resolve_reexport_in_init(str(init), "Gamma", str(tmp_path / "x.py")) == str(core)

    def test_init_absolute_import_different_package(self, tmp_path):
        """__init__.py uses absolute import from a sibling package."""
        pkg_a = tmp_path / "pkg_a"
        pkg_b = tmp_path / "pkg_b"
        pkg_a.mkdir()
        pkg_b.mkdir()
        init_a = pkg_a / "__init__.py"
        init_a.write_text("from pkg_b.helpers import Util\n")
        (pkg_b / "__init__.py").write_text("")
        helpers = pkg_b / "helpers.py"
        helpers.write_text("class Util: pass\n")

        result = _stub._resolve_reexport_in_init(str(init_a), "Util", str(tmp_path / "x.py"))
        assert result == str(helpers)

    def test_find_module_init_nested(self, tmp_path):
        """_find_module_init should find __init__.py in nested packages."""
        nested = tmp_path / "a" / "b" / "c"
        nested.mkdir(parents=True)
        (tmp_path / "a" / "__init__.py").write_text("")
        (tmp_path / "a" / "b" / "__init__.py").write_text("")
        init = nested / "__init__.py"
        init.write_text("")

        stub = _Stub()
        stub.get_workspace_folders = lambda: [str(tmp_path)]
        result = stub._find_module_init("a.b.c", str(tmp_path / "main.py"))
        assert result == str(init)

    def test_open_module_finds_init(self, tmp_path):
        """_open_module should open __init__.py when module is a package."""
        pkg = tmp_path / "mypkg"
        pkg.mkdir()
        init = pkg / "__init__.py"
        init.write_text("VERSION = '1.0'\n")

        stub = _Stub()
        stub.get_workspace_folders = lambda: [str(tmp_path)]
        opened = []
        stub.open_file_callback = lambda path, line: opened.append(path) or True
        result = stub._open_module("mypkg", str(tmp_path / "main.py"))
        assert result is True
        assert str(init) in opened

    def test_open_module_prefers_py_over_package(self, tmp_path):
        """When both module.py and module/__init__.py exist, .py should win."""
        (tmp_path / "mod.py").write_text("x = 1\n")
        pkg = tmp_path / "mod"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("y = 2\n")

        stub = _Stub()
        stub.get_workspace_folders = lambda: [str(tmp_path)]
        opened = []
        stub.open_file_callback = lambda path, line: opened.append(path) or True
        result = stub._open_module("mod", str(tmp_path / "main.py"))
        assert result is True
        assert opened[0].endswith("mod.py")

    def test_init_reexport_to_sub_init(self, tmp_path):
        """__init__.py re-exports from a sub-package __init__.py."""
        outer = tmp_path / "outer"
        inner = outer / "inner"
        inner.mkdir(parents=True)
        outer_init = outer / "__init__.py"
        outer_init.write_text("from .inner import Widget\n")
        inner_init = inner / "__init__.py"
        inner_init.write_text("class Widget: pass\n")

        result = _stub._resolve_reexport_in_init(str(outer_init), "Widget", str(tmp_path / "x.py"))
        assert result == str(inner_init)


# ═══════════════════════════════════════════════════════════════════════════════
# 8. _find_venv_site_packages
# ═══════════════════════════════════════════════════════════════════════════════
class TestFindVenvSitePackages:
    """Edge cases for virtualenv discovery."""

    def test_no_venv_returns_empty(self, tmp_path):
        stub = _Stub()
        result = stub._find_venv_site_packages(str(tmp_path / "some" / "file.py"))
        assert result == []

    def test_finds_venv_site_packages(self, tmp_path):
        sp = tmp_path / ".venv" / "lib" / "python3.13" / "site-packages"
        sp.mkdir(parents=True)

        stub = _Stub()
        result = stub._find_venv_site_packages(str(tmp_path / "main.py"))
        assert len(result) >= 1
        assert str(sp) in result

    def test_workspace_folder_venv(self, tmp_path):
        ws = tmp_path / "workspace"
        ws.mkdir()
        sp = ws / "venv" / "lib" / "python3.11" / "site-packages"
        sp.mkdir(parents=True)

        stub = _Stub()
        stub.get_workspace_folders = lambda: [str(ws)]
        # current_file is outside workspace, so it falls back to workspace scan
        result = stub._find_venv_site_packages(str(tmp_path / "other" / "file.py"))
        assert any(str(sp) in p for p in result)
