"""Tests for PythonNavigationMixin — pure parsing logic (no GTK)."""

from navigation.code_navigation_py import PythonNavigationMixin


# Create a minimal instance to call the methods
class _Stub(PythonNavigationMixin):
    def __init__(self):
        self.get_workspace_folders = None
        self.open_file_callback = None
        self._pending_navigate_symbol = None
        self._pending_file_path = None


_stub = _Stub()


# ---------------------------------------------------------------------------
# _parse_python_imports
# ---------------------------------------------------------------------------
class TestParsePythonImports:
    def test_import_module(self):
        result = _stub._ts_py.parse_imports("import os")
        assert result == {"os": "os"}

    def test_import_dotted(self):
        result = _stub._ts_py.parse_imports("import os.path")
        assert result == {"path": "os.path"}

    def test_import_as(self):
        result = _stub._ts_py.parse_imports("import numpy as np")
        assert result == {"np": "numpy"}

    def test_from_import(self):
        result = _stub._ts_py.parse_imports("from os.path import join")
        assert result == {"join": "os.path.join"}

    def test_from_import_as(self):
        result = _stub._ts_py.parse_imports("from os.path import join as pjoin")
        assert result == {"pjoin": "os.path.join"}

    def test_from_import_multiple(self):
        result = _stub._ts_py.parse_imports("from os.path import join, exists")
        assert result == {"join": "os.path.join", "exists": "os.path.exists"}

    def test_relative_import(self):
        result = _stub._ts_py.parse_imports("from .utils import helper")
        assert result == {"helper": ".utils.helper"}

    def test_double_relative_import(self):
        result = _stub._ts_py.parse_imports("from ..shared import config")
        assert result == {"config": "..shared.config"}

    def test_multiple_imports(self):
        content = "import os\nimport sys\nfrom pathlib import Path"
        result = _stub._ts_py.parse_imports(content)
        assert "os" in result
        assert "sys" in result
        assert "Path" in result

    def test_ignores_comments(self):
        content = "# import fake\nimport real"
        result = _stub._ts_py.parse_imports(content)
        assert "real" in result
        assert "fake" not in result

    def test_empty_content(self):
        assert _stub._ts_py.parse_imports("") == {}


# ---------------------------------------------------------------------------
# _find_python_symbol_in_content
# ---------------------------------------------------------------------------
class TestFindPythonSymbolInContent:
    def test_find_class(self):
        content = "import os\n\nclass MyClass:\n    pass"
        assert _stub._ts_py.find_symbol_in_content(content, "MyClass") == 3

    def test_find_function(self):
        content = "def foo():\n    pass"
        assert _stub._ts_py.find_symbol_in_content(content, "foo") == 1

    def test_find_method(self):
        content = "class A:\n    def method(self):\n        pass"
        assert _stub._ts_py.find_symbol_in_content(content, "method") == 2

    def test_find_variable(self):
        content = "x = 42"
        assert _stub._ts_py.find_symbol_in_content(content, "x") == 1

    def test_not_found_returns_none(self):
        content = "x = 1\ny = 2"
        assert _stub._ts_py.find_symbol_in_content(content, "z") is None

    def test_class_with_parent(self):
        content = "class Child(Parent):\n    pass"
        assert _stub._ts_py.find_symbol_in_content(content, "Child") == 1

    def test_empty_content(self):
        assert _stub._ts_py.find_symbol_in_content("", "foo") is None


# ---------------------------------------------------------------------------
# _find_variable_class
# ---------------------------------------------------------------------------
class TestFindVariableClass:
    def test_simple_assignment(self):
        content = "    obj = MyClass(arg1, arg2)"
        assert _stub._ts_py.find_variable_class(content, "obj") == "MyClass"

    def test_no_match(self):
        content = "x = 42"
        assert _stub._ts_py.find_variable_class(content, "x") is None

    def test_lowercase_not_matched(self):
        content = "obj = some_func()"
        assert _stub._ts_py.find_variable_class(content, "obj") is None

    def test_not_found(self):
        assert _stub._ts_py.find_variable_class("a = B()", "z") is None

    def test_qualified_class(self):
        content = "client = vault.Client(url)"
        assert _stub._ts_py.find_variable_class(content, "client") == "vault.Client"


# ---------------------------------------------------------------------------
# _find_self_attr_class
# ---------------------------------------------------------------------------
class TestFindSelfAttrClass:
    def test_simple_self_attr(self):
        content = "        self.utils = MyUtils(config)"
        assert _stub._ts_py.find_self_attr_class(content, "utils") == "MyUtils"

    def test_self_attr_qualified(self):
        content = "        self.client = vault.Client(url)"
        assert _stub._ts_py.find_self_attr_class(content, "client") == "vault.Client"

    def test_self_attr_not_found(self):
        assert _stub._ts_py.find_self_attr_class("self.x = 42", "x") is None

    def test_self_attr_lowercase_rhs_not_matched(self):
        content = "        self.handler = some_factory()"
        assert _stub._ts_py.find_self_attr_class(content, "handler") is None

    def test_self_attr_in_init(self):
        content = (
            "class StreamProcessor:\n"
            "    def __init__(self):\n"
            "        self.revolve_utils = RevolveUtils(self.logger)\n"
            "        self.db = DBClient(host, port)\n"
        )
        assert _stub._ts_py.find_self_attr_class(content, "revolve_utils") == "RevolveUtils"
        assert _stub._ts_py.find_self_attr_class(content, "db") == "DBClient"

    def test_self_attr_no_args(self):
        content = "        self.processor = Processor()"
        assert _stub._ts_py.find_self_attr_class(content, "processor") == "Processor"

    def test_self_attr_multiline_content(self):
        content = (
            "import os\n"
            "class Foo:\n"
            "    def __init__(self):\n"
            "        self.bar = SomeClass(a, b)\n"
            "    def run(self):\n"
            "        self.bar.do_stuff()\n"
        )
        assert _stub._ts_py.find_self_attr_class(content, "bar") == "SomeClass"

    def test_wrong_attr_not_matched(self):
        content = "        self.foo = MyClass()"
        assert _stub._ts_py.find_self_attr_class(content, "bar") is None


# ---------------------------------------------------------------------------
# _resolve_reexport_in_init — nested package absolute imports
# ---------------------------------------------------------------------------
class TestResolveReexportInInit:
    """Verify that _resolve_reexport_in_init follows absolute imports
    inside nested package __init__.py files (e.g. shared/settings/)."""

    def test_nested_package_absolute_import(self, tmp_path):
        # Build a nested package: shared/settings/settings_manager.py
        pkg = tmp_path / "shared" / "settings"
        pkg.mkdir(parents=True)
        (tmp_path / "shared" / "__init__.py").write_text("")
        init_file = pkg / "__init__.py"
        init_file.write_text("from shared.settings.settings_manager import (\n    get_setting,\n    set_setting,\n)\n")
        target = pkg / "settings_manager.py"
        target.write_text("def get_setting(path, default=None): ...\n")

        result = _stub._resolve_reexport_in_init(str(init_file), "get_setting", str(tmp_path / "some_file.py"))
        assert result == str(target)

    def test_relative_import_still_works(self, tmp_path):
        pkg = tmp_path / "mypkg"
        pkg.mkdir()
        init_file = pkg / "__init__.py"
        init_file.write_text("from .core import Widget\n")
        target = pkg / "core.py"
        target.write_text("class Widget: ...\n")

        result = _stub._resolve_reexport_in_init(str(init_file), "Widget", str(tmp_path / "x.py"))
        assert result == str(target)

    def test_no_match_returns_none(self, tmp_path):
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        init_file = pkg / "__init__.py"
        init_file.write_text("from .foo import Bar\n")

        result = _stub._resolve_reexport_in_init(str(init_file), "Missing", str(tmp_path / "x.py"))
        assert result is None


# ---------------------------------------------------------------------------
# _open_module — .pyi stub file support
# ---------------------------------------------------------------------------
class TestOpenModulePyi:
    """Verify _open_module finds .pyi stub files when .py is absent."""

    def _make_nav(self, tmp_path):
        nav = _Stub()
        nav.get_workspace_folders = lambda: [str(tmp_path)]
        opened = []
        nav.open_file_callback = lambda path, _line: opened.append(path)
        nav._pending_navigate_symbol = None
        nav._pending_file_path = None
        nav._schedule_pending_navigation = lambda: None
        return nav, opened

    def test_opens_pyi_when_no_py(self, tmp_path):
        pkg = tmp_path / "mylib"
        pkg.mkdir()
        stub = pkg / "__init__.pyi"
        stub.write_text("class Foo: ...\n")
        nav, opened = self._make_nav(tmp_path)
        assert nav._open_module("mylib", str(tmp_path / "x.py")) is True
        assert opened[-1] == str(stub)

    def test_prefers_py_over_pyi(self, tmp_path):
        pkg = tmp_path / "mylib"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("class Foo: ...\n")
        (pkg / "__init__.pyi").write_text("class Foo: ...\n")
        nav, opened = self._make_nav(tmp_path)
        assert nav._open_module("mylib", str(tmp_path / "x.py")) is True
        assert opened[-1].endswith("__init__.py")

    def test_opens_module_pyi_file(self, tmp_path):
        stub = tmp_path / "utils.pyi"
        stub.write_text("def helper() -> None: ...\n")
        nav, opened = self._make_nav(tmp_path)
        assert nav._open_module("utils", str(tmp_path / "x.py")) is True
        assert opened[-1] == str(stub)


# ---------------------------------------------------------------------------
# _navigate_to_import — C extension module hierarchy walk-up
# ---------------------------------------------------------------------------
class TestNavigateToImportCExtFallback:
    """When a module segment is a C extension (.so), walk up the hierarchy."""

    def _make_nav(self, tmp_path):
        nav = _Stub()
        nav.get_workspace_folders = lambda: [str(tmp_path)]
        opened = []
        nav.open_file_callback = lambda path, _line: opened.append(path)
        nav._pending_navigate_symbol = None
        nav._pending_file_path = None
        nav._schedule_pending_navigation = lambda: None
        return nav, opened

    def test_walks_up_to_parent_init(self, tmp_path):
        """from pkg._binding import Cls → opens pkg/__init__.py when _binding is C ext."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        init = pkg / "__init__.py"
        init.write_text("from pkg._binding import Cls\nclass Cls: ...\n")
        nav, opened = self._make_nav(tmp_path)
        result = nav._navigate_to_import("Cls", "pkg._binding.Cls", str(tmp_path / "x.py"))
        assert result is True
        assert str(pkg) in opened[-1]

    def test_walks_up_to_parent_pyi(self, tmp_path):
        """from pkg._binding import Cls → opens pkg/__init__.pyi when only stubs exist."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        stub = pkg / "__init__.pyi"
        stub.write_text("class Cls: ...\n")
        nav, opened = self._make_nav(tmp_path)
        result = nav._navigate_to_import("Cls", "pkg._binding.Cls", str(tmp_path / "x.py"))
        assert result is True
        assert opened[-1] == str(stub)
