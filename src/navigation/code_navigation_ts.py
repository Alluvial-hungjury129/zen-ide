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
import re
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

    def _handle_ts_click(self, buffer, view, file_path, click_iter) -> bool:
        """Handle Cmd+Click for TypeScript/JavaScript files."""
        word = self._get_word_at_iter(buffer, click_iter)
        if not word:
            return False

        if word in self._TS_BUILTINS:
            return False

        content = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), True)
        imports = self._parse_ts_imports(content)

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
            member_line = self._find_ts_member_in_content(content, container, member)
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
        line_num = self._find_ts_symbol_in_content(content, word)
        if line_num:
            self._navigate_to_line(buffer, view, line_num, symbol=word)
            return True

        # Case 3: Search workspace files
        return self._search_ts_workspace(word, file_path)

    def _parse_ts_imports(self, content: str) -> dict:
        """Parse TypeScript/JavaScript import statements."""
        imports = {}

        # ES module imports: import ... from 'module'
        for match in re.finditer(
            r"""^import\s+(.+?)\s+from\s+['"]([^'"]+)['"]""",
            content,
            re.MULTILINE,
        ):
            clause = match.group(1).strip()
            source = match.group(2)
            self._parse_ts_import_clause(clause, source, imports)

        # CommonJS: const { x } = require('module')
        for match in re.finditer(
            r"""(?:const|let|var)\s+(\{[^}]+\}|\w+)\s*=\s*require\s*\(\s*['"]([^'"]+)['"]\s*\)""",
            content,
            re.MULTILINE,
        ):
            clause = match.group(1).strip()
            source = match.group(2)
            if clause.startswith("{"):
                inner = clause.strip("{}")
                for item in inner.split(","):
                    item = item.strip()
                    if not item:
                        continue
                    as_match = re.match(r"(\w+)\s*:\s*(\w+)", item)
                    if as_match:
                        imports[as_match.group(2)] = source
                    else:
                        name_match = re.match(r"(\w+)", item)
                        if name_match:
                            imports[name_match.group(1)] = source
            else:
                imports[clause] = source

        # Re-exports: export { x } from 'module'
        for match in re.finditer(
            r"""^export\s+\{([^}]+)\}\s+from\s+['"]([^'"]+)['"]""",
            content,
            re.MULTILINE,
        ):
            inner = match.group(1)
            source = match.group(2)
            for item in inner.split(","):
                item = item.strip()
                if not item:
                    continue
                as_match = re.match(r"(\w+)\s+as\s+(\w+)", item)
                if as_match:
                    imports[as_match.group(2)] = source
                else:
                    name_match = re.match(r"(\w+)", item)
                    if name_match:
                        imports[name_match.group(1)] = source

        return imports

    def _parse_ts_import_clause(self, clause: str, source: str, imports: dict):
        """Parse the clause part of an ES module import statement."""
        # import * as name from 'source'
        ns_match = re.match(r"\*\s+as\s+(\w+)", clause)
        if ns_match:
            imports[ns_match.group(1)] = source
            return

        # Split by comma outside braces
        brace_depth = 0
        parts = []
        current = []
        for ch in clause:
            if ch == "{":
                brace_depth += 1
                current.append(ch)
            elif ch == "}":
                brace_depth -= 1
                current.append(ch)
            elif ch == "," and brace_depth == 0:
                parts.append("".join(current).strip())
                current = []
            else:
                current.append(ch)
        if current:
            parts.append("".join(current).strip())

        for part in parts:
            part = part.strip()
            if not part:
                continue

            # Named imports: { a, b as c }
            brace_match = re.match(r"\{(.+)\}", part, re.DOTALL)
            if brace_match:
                inner = brace_match.group(1)
                for item in inner.split(","):
                    item = item.strip()
                    if not item:
                        continue
                    as_match = re.match(r"(\w+)\s+as\s+(\w+)", item)
                    if as_match:
                        imports[as_match.group(2)] = source
                    else:
                        name_match = re.match(r"(\w+)", item)
                        if name_match:
                            imports[name_match.group(1)] = source
                continue

            # Namespace: * as name
            ns_match = re.match(r"\*\s+as\s+(\w+)", part)
            if ns_match:
                imports[ns_match.group(1)] = source
                continue

            # Default import: just an identifier
            id_match = re.match(r"^(\w+)$", part)
            if id_match:
                imports[id_match.group(1)] = source

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

    def _find_ts_symbol_in_content(self, content: str, symbol: str) -> Optional[int]:
        """Find a TypeScript/JavaScript symbol definition. Returns 1-based line number."""
        patterns = [
            rf"^\s*(?:export\s+)?(?:async\s+)?function\s+{re.escape(symbol)}\s*[<(]",
            rf"^\s*(?:export\s+)?(?:abstract\s+)?class\s+{re.escape(symbol)}\b",
            rf"^\s*(?:export\s+)?interface\s+{re.escape(symbol)}\b",
            rf"^\s*(?:export\s+)?type\s+{re.escape(symbol)}\b",
            rf"^\s*(?:export\s+)?(?:const\s+)?enum\s+{re.escape(symbol)}\b",
            rf"^\s*(?:export\s+)?(?:const|let|var)\s+{re.escape(symbol)}\b",
            rf"^\s+(?:(?:public|private|protected|static|async|readonly)\s+)*{re.escape(symbol)}\s*[\(<]",
            rf"^\s*export\s+default\s+(?:async\s+)?function\s+{re.escape(symbol)}\b",
            rf"^\s*export\s+default\s+class\s+{re.escape(symbol)}\b",
        ]

        for pattern in patterns:
            match = re.search(pattern, content, re.MULTILINE)
            if match:
                matched_text = match.group()
                symbol_offset = matched_text.find(symbol)
                if symbol_offset >= 0:
                    pos = match.start() + symbol_offset
                else:
                    pos = match.start()
                return content[:pos].count("\n") + 1

        return None

    def _find_ts_member_in_content(self, content: str, container: str, member: str) -> Optional[int]:
        """Find a member inside a TS container (enum, class, namespace).

        Returns 1-based line number of the member definition.
        """
        lines = content.split("\n")

        container_re = re.compile(
            rf"^\s*(?:export\s+)?(?:declare\s+)?(?:const\s+)?(?:enum|class|namespace|abstract\s+class)\s+{re.escape(container)}\b"
        )
        member_re = re.compile(rf"\b{re.escape(member)}\b")

        in_container = False
        brace_depth = 0

        for i, line in enumerate(lines):
            if not in_container:
                if container_re.match(line):
                    in_container = True
                    brace_depth += line.count("{") - line.count("}")
                    continue
            else:
                brace_depth += line.count("{") - line.count("}")
                if member_re.search(line):
                    return i + 1
                if brace_depth <= 0:
                    in_container = False

        return None

    def _find_member_in_file(self, file_path: str, container: str, member: str) -> Optional[int]:
        """Read a file and find a member inside a container."""
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            return self._find_ts_member_in_content(content, container, member)
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
            member_line = self._find_ts_member_in_content(content, container, member)
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
            line_num = self._find_ts_symbol_in_content(content, symbol)
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
