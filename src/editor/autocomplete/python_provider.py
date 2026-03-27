"""
Python completion provider for Zen IDE autocomplete.

Provides Python-specific completions: keywords, builtins, imports, symbols,
module path resolution, and dot-access member completions.

Uses tree-sitter for AST-based symbol extraction (functions, classes,
variables, imports, class members, signatures).  Filesystem-based module
resolution and venv introspection remain unchanged.
"""

import glob as glob_module
import sysconfig
from pathlib import Path

# Re-export the PYTHON_BUILTINS list so external code that imported it
# from this module continues to work.
from editor.autocomplete.python_builtins import (
    PYTHON_BUILTINS,  # noqa: F401
    PythonBuiltinsMixin,
)
from editor.autocomplete.python_imports import PythonImportsMixin
from editor.autocomplete.python_members import PythonMembersMixin
from editor.autocomplete.tree_sitter_provider import (
    _parse,
    py_extract_file_symbols,
)


class PythonCompletionProvider(PythonBuiltinsMixin, PythonImportsMixin, PythonMembersMixin):
    """Python-specific completion provider."""

    # --- Private helpers (shared across mixins) ---

    def _parse_symbols(self, py_file):
        """Parse a Python file and extract top-level symbol names using tree-sitter.

        For __init__.py files, also follows relative re-exports.
        """
        try:
            text = py_file.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return []

        m_source, m_tree = _parse(text, "python")
        if m_tree is None:
            return []

        result = py_extract_file_symbols(m_source, m_tree)
        if isinstance(result, tuple):
            symbols, reexports = result
        else:
            return result

        # Resolve re-exported symbols from sibling files
        if reexports:
            pkg_dir = py_file.parent
            resolved_modules: dict[str, dict] = {}
            for name, rel_module in reexports.items():
                if name in symbols:
                    continue
                if rel_module not in resolved_modules:
                    sibling = pkg_dir / f"{rel_module}.py"
                    if sibling.is_file():
                        resolved_modules[rel_module] = {item.name: item for item in self._parse_symbols(sibling)}
                    else:
                        resolved_modules[rel_module] = {}
                if name in resolved_modules.get(rel_module, {}):
                    symbols[name] = resolved_modules[rel_module][name]

        return sorted(symbols.values(), key=lambda x: x.name)

    def _follow_reexport_ts(self, source, tree, class_name, module_path, file_path):
        """Follow re-exports in __init__.py using tree-sitter."""
        from editor.autocomplete.tree_sitter_provider import _node_text

        root = tree.root_node
        for child in root.children:
            if child.type != "import_from_statement":
                continue
            module_node = child.child_by_field_name("module_name")
            if not module_node:
                continue
            mod_text = _node_text(source, module_node)
            if not mod_text.startswith(".") or mod_text.startswith(".."):
                continue
            # Check if class_name is among the imported names
            for imp in child.children:
                name = None
                if imp.type == "dotted_name" and imp != module_node:
                    name = _node_text(source, imp)
                elif imp.type == "aliased_import":
                    orig = imp.child_by_field_name("name")
                    if orig:
                        name = _node_text(source, orig)
                if name == class_name:
                    rel_module = mod_text.lstrip(".")
                    sub_path = f"{module_path}.{rel_module}"
                    return self._read_module_text(sub_path, file_path)
        return None

    def _find_venv_site_packages(self, file_path):
        """Find virtualenv site-packages directories for the project."""
        venv_names = [".venv", "venv"]
        current = Path(file_path).parent
        while current != current.parent:
            for venv_name in venv_names:
                venv_path = current / venv_name
                if venv_path.is_dir():
                    for sp in glob_module.glob(str(venv_path / "lib" / "python*" / "site-packages")):
                        if Path(sp).is_dir():
                            return [Path(sp)]
            if (current / ".git").exists():
                break
            current = current.parent
        return []

    _stdlib_path: Path | None = None
    _stdlib_path_resolved: bool = False

    @classmethod
    def _get_stdlib_path(cls):
        """Return the Python stdlib directory, cached across calls."""
        if not cls._stdlib_path_resolved:
            try:
                stdlib = sysconfig.get_paths().get("stdlib")
                cls._stdlib_path = Path(stdlib) if stdlib and Path(stdlib).is_dir() else None
            except Exception:
                cls._stdlib_path = None
            cls._stdlib_path_resolved = True
        return cls._stdlib_path

    @staticmethod
    def _check_module_candidates(base_dir, rel_path):
        """Check for .py, .pyi, and stub-package variants of a module path under base_dir."""
        for ext in (".py", ".pyi"):
            candidate = base_dir / f"{rel_path}{ext}"
            if candidate.is_file():
                return candidate
        for init in ("__init__.py", "__init__.pyi"):
            candidate = base_dir / rel_path / init
            if candidate.is_file():
                return candidate
        # Check <pkg>-stubs directories (PEP 561 stub-only packages)
        parts = Path(rel_path).parts
        if parts:
            stub_dir = base_dir / f"{parts[0]}-stubs"
            if stub_dir.is_dir():
                stub_rel = Path(*parts[1:]) if len(parts) > 1 else Path()
                for ext in (".py", ".pyi"):
                    candidate = stub_dir / f"{stub_rel}{ext}" if str(stub_rel) != "." else stub_dir / f"__init__{ext}"
                    if candidate.is_file():
                        return candidate
                for init in ("__init__.py", "__init__.pyi"):
                    candidate = stub_dir / stub_rel / init
                    if candidate.is_file():
                        return candidate
        return None

    def _find_module_file(self, rel_path, file_path):
        """Find the .py/.pyi file for a module, searching project dirs, venv, stubs, then stdlib."""
        current = Path(file_path).parent
        searched = set()
        while current != current.parent:
            for root in (current, current / "src"):
                if root in searched or not root.is_dir():
                    continue
                searched.add(root)
                result = self._check_module_candidates(root, rel_path)
                if result:
                    return result
            if (current / ".git").exists():
                break
            current = current.parent
        # Fallback: search venv site-packages
        for sp in self._find_venv_site_packages(file_path):
            result = self._check_module_candidates(sp, rel_path)
            if result:
                return result
        # Fallback: search Python stdlib
        stdlib_dir = self._get_stdlib_path()
        if stdlib_dir:
            result = self._check_module_candidates(stdlib_dir, rel_path)
            if result:
                return result
        return None

    def _read_module_text(self, module_path, file_path):
        """Read the source text of a Python module file."""
        rel_path = module_path.replace(".", "/")
        py_file = self._find_module_file(rel_path, file_path)
        if py_file:
            try:
                return py_file.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                return None
        return None
