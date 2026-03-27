"""Python navigation edge cases — symbol search, file system robustness.

Covers:
- Symbol search edge cases (decorators, indentation, async, dunder, constants)
- File system robustness (non-existent files, symlinks, permission errors)
"""

import os
import stat

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
# 5. Symbol Search (_find_python_symbol_in_content)
# ═══════════════════════════════════════════════════════════════════════════════
class TestSymbolSearchEdgeCases:
    """Edge cases for finding symbol definitions in content."""

    def test_class_with_parent(self):
        content = "class Child(Parent):\n    pass\n"
        assert _stub._ts_py.find_symbol_in_content(content, "Child") == 1

    def test_class_with_multiple_parents(self):
        content = "class Multi(Base1, Base2, Mixin):\n    pass\n"
        assert _stub._ts_py.find_symbol_in_content(content, "Multi") == 1

    def test_function_with_decorators(self):
        content = "@decorator\ndef my_func():\n    pass\n"
        assert _stub._ts_py.find_symbol_in_content(content, "my_func") == 2

    def test_indented_method(self):
        content = "class A:\n    def method(self):\n        pass\n"
        assert _stub._ts_py.find_symbol_in_content(content, "method") == 2

    def test_double_indented_method(self):
        content = "class A:\n    class B:\n        def deep(self):\n            pass\n"
        assert _stub._ts_py.find_symbol_in_content(content, "deep") == 3

    def test_variable_with_type_hint(self):
        content = "count: int = 0\n"
        # Tree-sitter correctly identifies type-hinted assignments
        result = _stub._ts_py.find_symbol_in_content(content, "count")
        assert result == 1

    def test_async_function(self):
        content = "async def fetch_data():\n    pass\n"
        # Tree-sitter correctly handles async function definitions
        result = _stub._ts_py.find_symbol_in_content(content, "fetch_data")
        assert result == 1

    def test_underscore_function(self):
        content = "def _private_helper():\n    pass\n"
        assert _stub._ts_py.find_symbol_in_content(content, "_private_helper") == 1

    def test_dunder_method(self):
        content = "class A:\n    def __init__(self):\n        pass\n"
        assert _stub._ts_py.find_symbol_in_content(content, "__init__") == 2

    def test_constant_all_caps(self):
        content = "MAX_RETRIES = 5\n"
        assert _stub._ts_py.find_symbol_in_content(content, "MAX_RETRIES") == 1

    def test_multiline_content_correct_line_number(self):
        content = "import os\n\n\n# comment\nclass MyClass:\n    pass\n"
        assert _stub._ts_py.find_symbol_in_content(content, "MyClass") == 5


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
