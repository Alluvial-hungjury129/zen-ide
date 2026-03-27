"""Python navigation edge cases — package structure and virtualenv discovery.

Covers:
- Nested packages, namespace packages, and __init__.py variations
- _find_venv_site_packages edge cases
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
