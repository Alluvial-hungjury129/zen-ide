"""
Python import completions for Zen IDE autocomplete.

Provides import detection, module scanning, and symbol extraction
via PythonImportsMixin.
"""

import re
from pathlib import Path

from editor.autocomplete import CompletionItem, CompletionKind


class PythonImportsMixin:
    """Mixin providing Python import-related completions."""

    def detect_import_context(self, buffer, cursor_iter):
        """Detect if cursor is on a Python from/import line.

        Returns (base_path, from_import) tuple:
        - base_path: dotted module path (e.g., 'lib' for 'from lib.'),
          empty string for top-level, or None if not in import context.
        - from_import: True if in 'from X import' context (need symbols, not submodules).
        Handles indented imports (e.g., inside try/except blocks).
        """
        line_start = cursor_iter.copy()
        line_start.set_line_offset(0)
        line_text = buffer.get_text(line_start, cursor_iter, False)

        # from X import Y: "from lib import " or "from lib.sub import na"
        m = re.match(r"^\s*from\s+([\w.]+)\s+import\s+\w*$", line_text)
        if m:
            return m.group(1), True

        # Dotted path: "from lib." or "from lib.sub.mo" or "import os.pa"
        m = re.match(r"^\s*(?:from|import)\s+((?:[\w]+\.)+)\w*$", line_text)
        if m:
            return m.group(1).rstrip("."), False

        # Top-level: "from " or "from li" or "import " or "import os"
        m = re.match(r"^\s*(?:from|import)\s+\w*$", line_text)
        if m:
            return "", False

        return None, False

    def get_file_symbols(self, module_path, file_path):
        """Extract top-level symbols (classes, functions, constants) from a Python module file.

        Resolves module_path (e.g., 'lib.db_tables') to a .py file by walking
        up parent directories and venv site-packages, then parses it for exportable names.
        Also scans stub-package directories for available submodules.
        """
        if not file_path or not module_path:
            return []

        rel_path = module_path.replace(".", "/")
        py_file = self._find_module_file(rel_path, file_path)
        if py_file:
            return self._parse_symbols(py_file)

        # If no module file found, scan for submodules in stub directories
        # (e.g., gi.repository → gi-stubs/repository/*.pyi)
        parts = rel_path.split("/")
        if parts:
            for sp in self._find_venv_site_packages(file_path):
                stub_dir = sp / f"{parts[0]}-stubs"
                if stub_dir.is_dir():
                    sub_dir = stub_dir / "/".join(parts[1:]) if len(parts) > 1 else stub_dir
                    if sub_dir.is_dir():
                        symbols = []
                        try:
                            for entry in sub_dir.iterdir():
                                name = entry.name
                                if name.startswith("_") or name == "__pycache__":
                                    continue
                                if entry.is_file() and name.endswith(".pyi"):
                                    symbols.append(CompletionItem(name[:-4], CompletionKind.CLASS))
                                elif entry.is_dir() and (entry / "__init__.pyi").is_file():
                                    symbols.append(CompletionItem(name, CompletionKind.PROPERTY))
                        except OSError:
                            pass
                        if symbols:
                            return sorted(symbols, key=lambda x: x.name)

        return []

    def get_module_completions(self, base_module_path, file_path):
        """Scan filesystem for Python modules/packages at the given import path.

        Walks up every parent directory from the file (stopping at .git root)
        and checks each level for the target module path. This handles projects
        where imports resolve relative to a root that isn't the immediate parent.
        """
        if not file_path:
            return []

        modules = set()
        rel_path = base_module_path.replace(".", "/") if base_module_path else ""
        current = Path(file_path).parent
        searched = set()

        while current != current.parent:
            for root in (current, current / "src"):
                if root in searched or not root.is_dir():
                    continue
                searched.add(root)
                dir_path = root / rel_path if rel_path else root
                if not dir_path.is_dir():
                    continue
                try:
                    for entry in dir_path.iterdir():
                        name = entry.name
                        if name.startswith(".") or name == "__pycache__":
                            continue
                        if entry.is_dir():
                            modules.add(name)
                        elif entry.is_file() and name.endswith(".py") and name != "__init__.py":
                            modules.add(name[:-3])
                except OSError:
                    pass

            if (current / ".git").exists():
                break
            current = current.parent

        # Also search venv site-packages (including stub packages)
        if rel_path:
            rel_parts = rel_path.split("/")
            for sp in self._find_venv_site_packages(file_path):
                for search_dir in [sp / rel_path, sp / f"{rel_parts[0]}-stubs" / "/".join(rel_parts[1:])]:
                    if not search_dir.is_dir():
                        continue
                    try:
                        for entry in search_dir.iterdir():
                            name = entry.name
                            if name.startswith(".") or name.startswith("_") or name == "__pycache__":
                                continue
                            if entry.is_dir():
                                modules.add(name)
                            elif entry.is_file():
                                if name.endswith(".py") and name != "__init__.py":
                                    modules.add(name[:-3])
                                elif name.endswith(".pyi") and name != "__init__.pyi":
                                    modules.add(name[:-4])
                    except OSError:
                        pass

        return sorted([CompletionItem(m, CompletionKind.PROPERTY) for m in modules], key=lambda x: x.name)

    @staticmethod
    def _find_import_module(source, tree, name):
        """Find the module path and original name for an imported symbol.

        Returns (module_path, original_name) or None.
        For ``from X import Y``: returns ``("X", "Y")``.
        For ``import X`` (whole-module): returns ``("X", None)``.
        """
        root = tree.root_node
        from editor.autocomplete.tree_sitter_provider import _node_text

        for child in root.children:
            if child.type == "import_from_statement":
                module_node = child.child_by_field_name("module_name")
                if not module_node:
                    continue
                module_path = _node_text(source, module_node)
                if module_path.startswith("."):
                    continue
                for imp in child.children:
                    if imp.type == "dotted_name" and imp != module_node:
                        if _node_text(source, imp) == name:
                            return module_path, name
                    elif imp.type == "aliased_import":
                        alias = imp.child_by_field_name("alias")
                        orig = imp.child_by_field_name("name")
                        if alias and _node_text(source, alias) == name:
                            return module_path, _node_text(source, orig) if orig else name
                        if not alias and orig and _node_text(source, orig) == name:
                            return module_path, name
            elif child.type == "import_statement":
                result = PythonImportsMixin._find_whole_module_import(source, child, name)
                if result:
                    return result
            # Handle try/except blocks containing imports
            elif child.type == "try_statement":
                for body_child in child.children:
                    block = body_child if body_child.type == "block" else None
                    if body_child.type == "except_clause":
                        for sub in body_child.children:
                            if sub.type == "block":
                                block = sub
                    if block:
                        for stmt in block.children:
                            if stmt.type == "import_from_statement":
                                result = PythonImportsMixin._find_import_in_stmt(source, stmt, name)
                                if result:
                                    return result
                            elif stmt.type == "import_statement":
                                result = PythonImportsMixin._find_whole_module_import(source, stmt, name)
                                if result:
                                    return result
        return None

    @staticmethod
    def _find_import_in_stmt(source, stmt, name):
        """Check a single import_from_statement for an imported name."""
        from editor.autocomplete.tree_sitter_provider import _node_text

        module_node = stmt.child_by_field_name("module_name")
        if not module_node:
            return None
        module_path = _node_text(source, module_node)
        if module_path.startswith("."):
            return None
        for imp in stmt.children:
            if imp.type == "dotted_name" and imp != module_node:
                if _node_text(source, imp) == name:
                    return module_path, name
            elif imp.type == "aliased_import":
                alias = imp.child_by_field_name("alias")
                orig = imp.child_by_field_name("name")
                if alias and _node_text(source, alias) == name:
                    return module_path, _node_text(source, orig) if orig else name
                if not alias and orig and _node_text(source, orig) == name:
                    return module_path, name
        return None

    @staticmethod
    def _find_whole_module_import(source, stmt, name):
        """Check an import_statement for a whole-module import matching *name*.

        Handles ``import threading`` and ``import threading as th``.
        Returns ``(module_path, None)`` where ``None`` signals a whole-module import.
        """
        from editor.autocomplete.tree_sitter_provider import _node_text

        for child in stmt.children:
            if child.type == "dotted_name":
                if _node_text(source, child) == name:
                    return name, None
            elif child.type == "aliased_import":
                alias = child.child_by_field_name("alias")
                orig = child.child_by_field_name("name")
                if alias and _node_text(source, alias) == name:
                    return _node_text(source, orig) if orig else name, None
                if not alias and orig and _node_text(source, orig) == name:
                    return name, None
        return None

    def _enrich_imports(self, imports, source, tree, file_path):
        """Enrich imported symbols with kind, signature, and docstring from source files."""
        from editor.autocomplete.tree_sitter_provider import _node_text

        # Build map: module_path → list of (original, alias)
        module_names: dict[str, list[tuple[str, str]]] = {}
        root = tree.root_node
        for child in root.children:
            if child.type != "import_from_statement":
                continue
            module_node = child.child_by_field_name("module_name")
            if not module_node:
                continue
            mod_path = _node_text(source, module_node)
            if mod_path.startswith("."):
                continue
            for imp in child.children:
                if imp.type == "dotted_name" and imp != module_node:
                    name = _node_text(source, imp)
                    module_names.setdefault(mod_path, []).append((name, name))
                elif imp.type == "aliased_import":
                    alias_n = imp.child_by_field_name("alias")
                    orig_n = imp.child_by_field_name("name")
                    orig = _node_text(source, orig_n) if orig_n else ""
                    alias = _node_text(source, alias_n) if alias_n else orig
                    if alias:
                        module_names.setdefault(mod_path, []).append((orig, alias))

        import_by_alias = {item.name: item for item in imports}
        for mod_path, names in module_names.items():
            rel_path = mod_path.replace(".", "/")
            py_file = self._find_module_file(rel_path, file_path)
            if not py_file:
                continue
            symbols = self._parse_symbols(py_file)
            sym_map = {item.name: item for item in symbols}
            for original, alias in names:
                if original in sym_map and alias in import_by_alias:
                    src = sym_map[original]
                    item = import_by_alias[alias]
                    item.kind = src.kind
                    item.signature = src.signature
                    item.docstring = src.docstring
