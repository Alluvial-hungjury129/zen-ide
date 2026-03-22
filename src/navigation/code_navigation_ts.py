"""
TypeScript/JavaScript-specific code navigation for Zen IDE.
Handles Cmd+Click go-to-definition for TS/JS files.

Supports:
- Navigation to imported symbols (ES modules, CommonJS)
- Navigation to local definitions (functions, classes, variables, interfaces, types)
- Cross-file navigation within workspace
- TypeScript path aliases from tsconfig.json
"""

import json
import os
from typing import Optional

_TS_EXTENSIONS = [".ts", ".tsx", ".js", ".jsx", ".d.ts"]
_TS_INDEX_FILES = ["index.ts", "index.tsx", "index.js", "index.jsx"]


class TypeScriptNavigationMixin:
    """TypeScript/JavaScript-specific navigation methods mixed into CodeNavigation."""

    _TS_BUILTINS = {
        "console",
        "window",
        "document",
        "global",
        "process",
        "setTimeout",
        "setInterval",
        "clearTimeout",
        "clearInterval",
        "Promise",
        "Array",
        "Object",
        "String",
        "Number",
        "Boolean",
        "Map",
        "Set",
        "WeakMap",
        "WeakSet",
        "Symbol",
        "BigInt",
        "Error",
        "TypeError",
        "RangeError",
        "SyntaxError",
        "JSON",
        "Math",
        "Date",
        "RegExp",
        "parseInt",
        "parseFloat",
        "isNaN",
        "isFinite",
        "undefined",
        "null",
        "NaN",
        "Infinity",
        "void",
        "never",
        "unknown",
        "any",
        "true",
        "false",
        "require",
        "module",
        "exports",
    }

    @property
    def _ts_js(self):
        """Lazy-loaded Tree-sitter TS/JS provider."""
        if not hasattr(self, "_ts_ts_provider"):
            from .tree_sitter_ts_provider import TreeSitterTsProvider

            self._ts_ts_provider = TreeSitterTsProvider()
        return self._ts_ts_provider

    def _handle_ts_click(self, buffer, view, file_path, click_iter) -> bool:
        """Handle Cmd+Click for TypeScript/JavaScript files."""
        word = self._get_word_at_iter(buffer, click_iter)
        if not word:
            return False

        if word in self._TS_BUILTINS:
            return False

        content = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), True)
        imports = self._ts_js.parse_imports(content)

        # Detect dotted access (e.g., EnumName.Member)
        chain = self._get_chain_at_iter(buffer, click_iter)
        parts = chain.split(".") if chain else []
        if len(parts) >= 2 and parts[-1] == word:
            container = parts[-2]
            member = word

            # Container is imported — resolve and find member in source file
            if container in imports:
                source = imports[container]
                resolved = self._resolve_ts_module(source, file_path)
                if resolved:
                    member_line = self._find_member_in_file(resolved, container, member)
                    if member_line:
                        self._pending_navigate_symbol = member
                        self._pending_file_path = resolved
                        self._pending_navigate_line = member_line
                        self.open_file_callback(resolved, None)
                        self._schedule_pending_navigation()
                        return True

            # Container defined locally — find member in current file
            member_line = self._ts_js.find_member_in_content(content, container, member)
            if member_line:
                self._navigate_to_line(buffer, view, member_line, symbol=member)
                return True

            # Search workspace for container.member
            if self._search_ts_workspace_member(container, member, file_path):
                return True

        # Case 1: Word is directly imported
        if word in imports:
            source = imports[word]
            return self._navigate_to_ts_import(word, source, file_path)

        # Case 2: Local definition in current file
        line_num = self._ts_js.find_symbol_in_content(content, word)
        if line_num:
            self._navigate_to_line(buffer, view, line_num, symbol=word)
            return True

        # Case 3: Search workspace files
        return self._search_ts_workspace(word, file_path)

    def _resolve_ts_module(self, source: str, current_file: str) -> Optional[str]:
        """Resolve a TypeScript/JavaScript module source to a file path."""
        current_dir = os.path.dirname(current_file)

        # Relative imports
        if source.startswith("."):
            base = os.path.normpath(os.path.join(current_dir, source))
            return self._try_resolve_ts_file(base)

        # Try tsconfig path aliases
        resolved = self._try_tsconfig_paths(source, current_file)
        if resolved:
            return resolved

        # Try node_modules
        return self._try_node_modules(source, current_file)

    def _try_resolve_ts_file(self, base: str) -> Optional[str]:
        """Try to resolve a base path to an actual TS/JS file."""
        if os.path.isfile(base):
            return base

        for ext in _TS_EXTENSIONS:
            candidate = base + ext
            if os.path.isfile(candidate):
                return candidate

        if os.path.isdir(base):
            for idx in _TS_INDEX_FILES:
                candidate = os.path.join(base, idx)
                if os.path.isfile(candidate):
                    return candidate

        return None

    def _try_tsconfig_paths(self, source: str, current_file: str) -> Optional[str]:
        """Try to resolve using tsconfig.json path aliases."""
        tsconfig = self._find_tsconfig(current_file)
        if not tsconfig:
            return None

        try:
            with open(tsconfig, "r", encoding="utf-8") as f:
                config = json.load(f)
        except (OSError, json.JSONDecodeError):
            return None

        compiler_options = config.get("compilerOptions", {})
        base_url = compiler_options.get("baseUrl", ".")
        paths = compiler_options.get("paths", {})
        tsconfig_dir = os.path.dirname(tsconfig)
        base_dir = os.path.normpath(os.path.join(tsconfig_dir, base_url))

        for pattern, targets in paths.items():
            if pattern.endswith("/*"):
                prefix = pattern[:-2]
                if source.startswith(prefix + "/"):
                    rest = source[len(prefix) + 1 :]
                    for target in targets:
                        if target.endswith("/*"):
                            target_base = target[:-2]
                            resolved_base = os.path.normpath(os.path.join(base_dir, target_base, rest))
                            result = self._try_resolve_ts_file(resolved_base)
                            if result:
                                return result
            elif pattern == source:
                for target in targets:
                    resolved_base = os.path.normpath(os.path.join(base_dir, target))
                    result = self._try_resolve_ts_file(resolved_base)
                    if result:
                        return result

        # Try baseUrl resolution
        resolved_base = os.path.normpath(os.path.join(base_dir, source))
        return self._try_resolve_ts_file(resolved_base)

    def _find_tsconfig(self, current_file: str) -> Optional[str]:
        """Find the nearest tsconfig.json."""
        check_dir = os.path.dirname(current_file)
        while check_dir and len(check_dir) > 1:
            candidate = os.path.join(check_dir, "tsconfig.json")
            if os.path.isfile(candidate):
                return candidate
            parent = os.path.dirname(check_dir)
            if parent == check_dir:
                break
            check_dir = parent
        return None

    def _try_node_modules(self, source: str, current_file: str) -> Optional[str]:
        """Try to resolve a module from node_modules."""
        check_dir = os.path.dirname(current_file)
        while check_dir and len(check_dir) > 1:
            nm = os.path.join(check_dir, "node_modules", source)
            if os.path.isdir(nm):
                pkg = os.path.join(nm, "package.json")
                if os.path.isfile(pkg):
                    try:
                        with open(pkg, "r", encoding="utf-8") as f:
                            pkg_data = json.load(f)
                        for field in ["types", "typings", "main"]:
                            entry = pkg_data.get(field)
                            if entry:
                                resolved = os.path.normpath(os.path.join(nm, entry))
                                if os.path.isfile(resolved):
                                    return resolved
                    except (OSError, json.JSONDecodeError):
                        pass
                for idx in _TS_INDEX_FILES:
                    candidate = os.path.join(nm, idx)
                    if os.path.isfile(candidate):
                        return candidate
            result = self._try_resolve_ts_file(os.path.join(check_dir, "node_modules", source))
            if result:
                return result
            parent = os.path.dirname(check_dir)
            if parent == check_dir:
                break
            check_dir = parent
        return None

    def _navigate_to_ts_import(self, symbol: str, source: str, current_file: str) -> bool:
        """Navigate to an imported symbol's source file."""
        resolved = self._resolve_ts_module(source, current_file)
        if not resolved:
            return False

        self._pending_navigate_symbol = symbol
        self._pending_file_path = resolved
        self.open_file_callback(resolved, None)
        self._schedule_pending_navigation()
        return True

    def _find_member_in_file(self, file_path: str, container: str, member: str) -> Optional[int]:
        """Read a file and find a member inside a container."""
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            return self._ts_js.find_member_in_content(content, container, member)
        except (OSError, IOError):
            return None

    def _search_ts_workspace_member(self, container: str, member: str, current_file: str) -> bool:
        """Search workspace files for a member inside a container (enum/class/namespace)."""
        ts_extensions = {".ts", ".tsx", ".js", ".jsx"}
        folders = []
        if self.get_workspace_folders:
            folders = self.get_workspace_folders() or []
        if not folders:
            folders = [os.path.dirname(current_file)]

        for folder in folders:
            if self._search_ts_dir_member(folder, container, member, current_file, ts_extensions):
                return True
        return False

    def _search_ts_dir_member(
        self, directory: str, container: str, member: str, current_file: str, extensions: set, depth: int = 0
    ) -> bool:
        """Recursively search a directory for a member inside a container."""
        if depth > 5:
            return False

        try:
            entries = os.listdir(directory)
        except OSError:
            return False

        skip_dirs = {"node_modules", ".git", "dist", "build", ".next", "__pycache__", ".venv", "coverage", ".turbo"}

        files = []
        dirs = []
        for entry in entries:
            full = os.path.join(directory, entry)
            if os.path.isfile(full):
                ext = os.path.splitext(entry)[1].lower()
                if ext in extensions and full != current_file:
                    files.append(full)
            elif os.path.isdir(full) and entry not in skip_dirs and not entry.startswith("."):
                dirs.append(full)

        for f in files:
            try:
                with open(f, "r", encoding="utf-8", errors="replace") as fh:
                    content = fh.read()
            except (OSError, IOError):
                continue
            member_line = self._ts_js.find_member_in_content(content, container, member)
            if member_line:
                self._pending_navigate_symbol = member
                self._pending_file_path = f
                self._pending_navigate_line = member_line
                self.open_file_callback(f, None)
                self._schedule_pending_navigation()
                return True

        for d in dirs:
            if self._search_ts_dir_member(d, container, member, current_file, extensions, depth + 1):
                return True

        return False

    def _search_ts_workspace(self, symbol: str, current_file: str) -> bool:
        """Search workspace files for a TypeScript/JavaScript symbol definition."""
        ts_extensions = {".ts", ".tsx", ".js", ".jsx"}
        folders = []
        if self.get_workspace_folders:
            folders = self.get_workspace_folders() or []
        if not folders:
            folders = [os.path.dirname(current_file)]

        for folder in folders:
            if self._search_ts_dir(folder, symbol, current_file, ts_extensions):
                return True
        return False

    def _search_ts_dir(self, directory: str, symbol: str, current_file: str, extensions: set, depth: int = 0) -> bool:
        """Recursively search a directory for a symbol definition."""
        if depth > 5:
            return False

        try:
            entries = os.listdir(directory)
        except OSError:
            return False

        skip_dirs = {"node_modules", ".git", "dist", "build", ".next", "__pycache__", ".venv", "coverage", ".turbo"}

        files = []
        dirs = []
        for entry in entries:
            full = os.path.join(directory, entry)
            if os.path.isfile(full):
                ext = os.path.splitext(entry)[1].lower()
                if ext in extensions and full != current_file:
                    files.append(full)
            elif os.path.isdir(full) and entry not in skip_dirs and not entry.startswith("."):
                dirs.append(full)

        for f in files:
            try:
                with open(f, "r", encoding="utf-8", errors="replace") as fh:
                    content = fh.read()
            except (OSError, IOError):
                continue
            line_num = self._ts_js.find_symbol_in_content(content, symbol)
            if line_num:
                self._pending_navigate_symbol = symbol
                self._pending_file_path = f
                self._pending_navigate_line = line_num
                self.open_file_callback(f, None)
                self._schedule_pending_navigation()
                return True

        for d in dirs:
            if self._search_ts_dir(d, symbol, current_file, extensions, depth + 1):
                return True

        return False
