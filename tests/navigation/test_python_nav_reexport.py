"""Tests for Python navigation re-export resolution in Case 2b (local variable from imported class)."""

from navigation.code_navigation_py import PythonNavigationMixin


class StubMixin(PythonNavigationMixin):
    """Minimal stub to test PythonNavigationMixin methods in isolation."""

    def __init__(self):
        self.opened_files = []
        self._pending_navigate_symbol = None
        self._pending_file_path = None
        self._navigation_timeout_id = None
        self.get_workspace_folders = None

    def open_file_callback(self, path, line):
        self.opened_files.append((path, line))
        return True

    def _schedule_pending_navigation(self):
        pass


class TestResolveReexportInInit:
    """Test _resolve_reexport_in_init follows re-exports."""

    def test_resolves_simple_reexport(self, tmp_path):
        pkg_dir = tmp_path / "mypkg"
        pkg_dir.mkdir()
        init = pkg_dir / "__init__.py"
        init.write_text("from .core import MyClass\n")
        core = pkg_dir / "core.py"
        core.write_text("class MyClass:\n    pass\n")

        stub = StubMixin()
        result = stub._resolve_reexport_in_init(str(init), "MyClass", str(tmp_path / "app.py"))
        assert result == str(core)

    def test_returns_none_when_no_reexport(self, tmp_path):
        pkg_dir = tmp_path / "mypkg"
        pkg_dir.mkdir()
        init = pkg_dir / "__init__.py"
        init.write_text("VERSION = '1.0'\n")

        stub = StubMixin()
        result = stub._resolve_reexport_in_init(str(init), "MyClass", str(tmp_path / "app.py"))
        assert result is None


class TestFindVariableClass:
    """Test _find_variable_class resolves local variable types."""

    def test_finds_constructor_assignment(self):
        stub = StubMixin()
        content = "handler = DBItemHandler(table, parse_decimal=False)\n"
        assert stub._find_variable_class(content, "handler") == "DBItemHandler"

    def test_returns_none_for_unknown_var(self):
        stub = StubMixin()
        content = "x = 42\n"
        assert stub._find_variable_class(content, "handler") is None

    def test_finds_self_assignment(self):
        stub = StubMixin()
        content = "        self.client = HttpClient(base_url)\n"
        # _find_variable_class matches self.client = HttpClient(...)
        assert stub._find_variable_class(content, "self.client") == "HttpClient"


class TestCase2bReexportNavigation:
    """Integration test: local var → imported class → re-export → actual source file."""

    def test_navigates_to_reexported_class_method(self, tmp_path):
        """When clicking handler.fetch_item, should navigate to the actual source,
        not __init__.py, when the class is re-exported."""
        # Setup package structure
        pkg_dir = tmp_path / "mypkg"
        pkg_dir.mkdir()

        init_file = pkg_dir / "__init__.py"
        init_file.write_text("from .impl import MyHandler\n")

        impl_file = pkg_dir / "impl.py"
        impl_file.write_text("class MyHandler:\n    def do_thing(self):\n        pass\n")

        # Simulate _open_module finding __init__.py but not the method
        stub = StubMixin()
        stub.get_workspace_folders = lambda: [str(tmp_path)]

        # Test _resolve_reexport_in_init finds impl.py from __init__.py
        result = stub._resolve_reexport_in_init(str(init_file), "MyHandler", str(tmp_path / "app.py"))
        assert result == str(impl_file)

        # Test that _find_module_init locates the __init__.py
        init_result = stub._find_module_init("mypkg", str(tmp_path / "app.py"))
        assert init_result == str(init_file)


class TestSelfAttrMethodNavigation:
    """Integration tests for self.attr.method() navigation (Case 2b).

    When clicking `can_process_statement` in `self.revolve_utils.can_process_statement()`,
    the navigation should resolve `self.revolve_utils = RevolveUtils(...)` in __init__,
    find `RevolveUtils` in imports, resolve through re-export, and navigate to the
    actual source file.
    """

    def test_self_attr_resolves_via_reexport(self, tmp_path):
        """self.utils.method() → self.utils = MyUtils(...) → from mypkg import MyUtils
        → mypkg/__init__.py re-exports from .impl → navigate to impl.py"""
        pkg_dir = tmp_path / "mypkg"
        pkg_dir.mkdir()
        init_file = pkg_dir / "__init__.py"
        init_file.write_text("from .impl import MyUtils\n")
        impl_file = pkg_dir / "impl.py"
        impl_file.write_text("class MyUtils:\n    def do_work(self):\n        pass\n")

        stub = StubMixin()
        stub.get_workspace_folders = lambda: [str(tmp_path)]

        # Step 1: _find_self_attr_class resolves the class name
        content = (
            "from mypkg import MyUtils\n"
            "\n"
            "class Processor:\n"
            "    def __init__(self):\n"
            "        self.utils = MyUtils(config)\n"
            "    def run(self):\n"
            "        self.utils.do_work()\n"
        )
        class_name = stub._find_self_attr_class(content, "utils")
        assert class_name == "MyUtils"

        # Step 2: class is in imports
        imports = stub._parse_python_imports(content)
        assert "MyUtils" in imports
        assert imports["MyUtils"] == "mypkg.MyUtils"

        # Step 3: resolve through re-export
        init_result = stub._find_module_init("mypkg", str(tmp_path / "app.py"))
        assert init_result == str(init_file)

        actual_source = stub._resolve_reexport_in_init(str(init_file), "MyUtils", str(tmp_path / "app.py"))
        assert actual_source == str(impl_file)

    def test_self_attr_direct_module_no_reexport(self, tmp_path):
        """self.client.fetch() → self.client = HttpClient(...) → from http_client import HttpClient
        → http_client.py exists directly (no re-export)."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        mod_file = src_dir / "http_client.py"
        mod_file.write_text("class HttpClient:\n    def fetch(self):\n        pass\n")

        stub = StubMixin()
        stub.get_workspace_folders = lambda: [str(tmp_path)]

        content = (
            "from http_client import HttpClient\n"
            "\n"
            "class App:\n"
            "    def __init__(self):\n"
            "        self.client = HttpClient(base_url)\n"
        )
        class_name = stub._find_self_attr_class(content, "client")
        assert class_name == "HttpClient"

        imports = stub._parse_python_imports(content)
        assert imports["HttpClient"] == "http_client.HttpClient"

    def test_self_attr_not_class_instantiation(self):
        """self.data = get_data() — lowercase RHS should not resolve."""
        stub = StubMixin()
        content = "class Proc:\n    def __init__(self):\n        self.data = get_data()\n"
        assert stub._find_self_attr_class(content, "data") is None

    def test_self_attr_with_multiple_attrs(self):
        """Multiple self.attr assignments — each should resolve independently."""
        stub = StubMixin()
        content = (
            "class Service:\n"
            "    def __init__(self):\n"
            "        self.repo = Repository(db)\n"
            "        self.cache = CacheClient(redis_url)\n"
            "        self.logger = Logger(name)\n"
        )
        assert stub._find_self_attr_class(content, "repo") == "Repository"
        assert stub._find_self_attr_class(content, "cache") == "CacheClient"
        assert stub._find_self_attr_class(content, "logger") == "Logger"


class TestAbsoluteImportReexport:
    """Test re-export resolution for absolute imports in __init__.py."""

    def test_resolves_absolute_reexport_same_package(self, tmp_path):
        """from themes.theme_manager import get_theme (absolute, same package)."""
        pkg_dir = tmp_path / "themes"
        pkg_dir.mkdir()
        init = pkg_dir / "__init__.py"
        init.write_text("from themes.theme_manager import get_theme\n")
        manager = pkg_dir / "theme_manager.py"
        manager.write_text("def get_theme():\n    pass\n")

        stub = StubMixin()
        result = stub._resolve_reexport_in_init(str(init), "get_theme", str(tmp_path / "app.py"))
        assert result == str(manager)

    def test_resolves_absolute_reexport_multiline(self, tmp_path):
        """from themes.theme_manager import (... get_theme ...) multiline."""
        pkg_dir = tmp_path / "themes"
        pkg_dir.mkdir()
        init = pkg_dir / "__init__.py"
        init.write_text("from themes.theme_manager import (\n    get_setting,\n    get_theme,\n    set_theme,\n)\n")
        manager = pkg_dir / "theme_manager.py"
        manager.write_text("def get_theme():\n    pass\n")

        stub = StubMixin()
        result = stub._resolve_reexport_in_init(str(init), "get_theme", str(tmp_path / "app.py"))
        assert result == str(manager)

    def test_resolves_absolute_reexport_different_package(self, tmp_path):
        """from shared.utils import hex_to_rgb (absolute, different package)."""
        themes_dir = tmp_path / "themes"
        themes_dir.mkdir()
        shared_dir = tmp_path / "shared"
        shared_dir.mkdir()

        init = themes_dir / "__init__.py"
        init.write_text("from shared.utils import hex_to_rgb\n")
        utils = shared_dir / "utils.py"
        utils.write_text("def hex_to_rgb(h):\n    pass\n")

        stub = StubMixin()
        result = stub._resolve_reexport_in_init(str(init), "hex_to_rgb", str(tmp_path / "app.py"))
        assert result == str(utils)
