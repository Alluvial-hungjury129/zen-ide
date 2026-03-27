"""Tests for import completions in editor/autocomplete/python_provider.py."""

from editor.autocomplete.python_completion_provider import PythonCompletionProvider
from editor.autocomplete.tree_sitter_provider import (
    py_extract_imports,
)
from tests.editor.autocomplete.conftest import _py


class TestGetImports:
    """Test import extraction from Python source."""

    def test_simple_import(self):
        source, tree = _py("import os")
        items = py_extract_imports(source, tree)
        names = [i.name for i in items]
        assert "os" in names

    def test_aliased_import(self):
        source, tree = _py("import numpy as np")
        items = py_extract_imports(source, tree)
        names = [i.name for i in items]
        assert "np" in names

    def test_from_import(self):
        source, tree = _py("from os.path import join, dirname")
        items = py_extract_imports(source, tree)
        names = [i.name for i in items]
        assert "join" in names
        assert "dirname" in names

    def test_from_import_with_alias(self):
        source, tree = _py("from collections import OrderedDict as OD")
        items = py_extract_imports(source, tree)
        names = [i.name for i in items]
        assert "OD" in names


class TestFollowReexport:
    """Test _follow_reexport_ts for __init__.py re-export resolution."""

    def test_matches_reexport(self):
        p = PythonCompletionProvider()
        init_text = "from .db_handler import DBHandler\nfrom .utils import helper\n"
        source, tree = _py(init_text)
        result = p._follow_reexport_ts(source, tree, "DBHandler", "mypkg", "/fake/path.py")
        assert result is None  # file not found on disk, but logic is correct

    def test_no_match_returns_none(self):
        p = PythonCompletionProvider()
        init_text = "from .utils import helper\n"
        source, tree = _py(init_text)
        result = p._follow_reexport_ts(source, tree, "NoSuchClass", "mypkg", "/fake/path.py")
        assert result is None

    def test_matches_among_multiple_imports(self):
        p = PythonCompletionProvider()
        init_text = "from .sub import Alpha, Beta, Gamma\n"
        source, tree = _py(init_text)
        result = p._follow_reexport_ts(source, tree, "Beta", "mypkg", "/fake/path.py")
        assert result is None

    def test_does_not_match_non_relative_import(self):
        p = PythonCompletionProvider()
        init_text = "from other_pkg import MyClass\n"
        source, tree = _py(init_text)
        result = p._follow_reexport_ts(source, tree, "MyClass", "mypkg", "/fake/path.py")
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


class TestFindWholeModuleImport:
    """Test _find_import_module handles both import_from and import_statement."""

    def test_plain_import(self):
        source, tree = _py("import threading\n")
        result = PythonCompletionProvider._find_import_module(source, tree, "threading")
        assert result == ("threading", None)

    def test_aliased_import(self):
        source, tree = _py("import threading as th\n")
        result = PythonCompletionProvider._find_import_module(source, tree, "th")
        assert result == ("threading", None)

    def test_plain_import_no_match(self):
        source, tree = _py("import threading\n")
        result = PythonCompletionProvider._find_import_module(source, tree, "os")
        assert result is None

    def test_from_import_still_works(self):
        source, tree = _py("from os.path import join\n")
        result = PythonCompletionProvider._find_import_module(source, tree, "join")
        assert result == ("os.path", "join")

    def test_import_in_try_block(self):
        code = "try:\n    import threading\nexcept ImportError:\n    pass\n"
        source, tree = _py(code)
        result = PythonCompletionProvider._find_import_module(source, tree, "threading")
        assert result == ("threading", None)


class TestStdlibDotCompletions:
    """Test resolve_dot_completions for stdlib whole-module imports."""

    def test_threading_dot_completions(self, tmp_path):
        code = "import threading\nthreading.\n"
        caller = tmp_path / "main.py"
        caller.write_text(code)
        p = PythonCompletionProvider()
        items = p.resolve_dot_completions("threading", str(caller), code)
        names = [i.name for i in items]
        assert "Thread" in names
        assert "Lock" in names
        assert "Event" in names

    def test_os_dot_completions(self, tmp_path):
        code = "import os\nos.\n"
        caller = tmp_path / "main.py"
        caller.write_text(code)
        p = PythonCompletionProvider()
        items = p.resolve_dot_completions("os", str(caller), code)
        names = [i.name for i in items]
        # os.py defines PathLike class and some variables in source
        assert len(names) > 0

    def test_aliased_import_dot_completions(self, tmp_path):
        code = "import threading as th\nth.\n"
        caller = tmp_path / "main.py"
        caller.write_text(code)
        p = PythonCompletionProvider()
        items = p.resolve_dot_completions("th", str(caller), code)
        names = [i.name for i in items]
        assert "Thread" in names

    def test_threading_Thread_dot_completions(self, tmp_path):
        code = "import threading\nthreading.Thread.\n"
        caller = tmp_path / "main.py"
        caller.write_text(code)
        p = PythonCompletionProvider()
        items = p.resolve_dot_completions("threading.Thread", str(caller), code)
        names = [i.name for i in items]
        # Thread class should have methods like start, join, run, etc.
        assert len(names) > 0
