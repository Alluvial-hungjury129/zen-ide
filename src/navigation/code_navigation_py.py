"""
Python-specific code navigation for Zen IDE.
Handles Cmd+Click go-to-definition for Python files.

Supports:
- Navigation to imported symbols
- Navigation to local definitions (classes, functions, variables)
- Re-export following for package __init__.py files
- Cross-workspace navigation
"""

import glob as glob_module
import os
import re
import sys
from typing import Optional


class PythonNavigationMixin:
    """Python-specific navigation methods mixed into CodeNavigation."""

    UNNAVIGABLE_BUILTINS = {
        "str",
        "int",
        "float",
        "bool",
        "bytes",
        "list",
        "dict",
        "set",
        "tuple",
        "object",
        "type",
        "None",
        "True",
        "False",
        "super",
        "property",
        "staticmethod",
        "classmethod",
        "isinstance",
        "issubclass",
        "hasattr",
        "getattr",
        "setattr",
        "delattr",
        "len",
        "range",
        "enumerate",
        "zip",
        "map",
        "filter",
        "sorted",
        "reversed",
        "print",
        "open",
        "input",
        "format",
        "repr",
        "id",
        "hash",
        "callable",
        "iter",
        "next",
        "all",
        "any",
        "min",
        "max",
        "sum",
        "abs",
        "round",
        "pow",
        "divmod",
        "ord",
        "chr",
        "bin",
        "hex",
        "oct",
        "ascii",
        "eval",
        "exec",
        "compile",
        "globals",
        "locals",
        "vars",
        "dir",
        "help",
        "exit",
        "quit",
        "slice",
        "Exception",
        "BaseException",
        "ValueError",
        "TypeError",
        "KeyError",
        "IndexError",
        "AttributeError",
        "ImportError",
        "FileNotFoundError",
        "OSError",
        "RuntimeError",
        "StopIteration",
        "NotImplementedError",
    }

    def _handle_python_click(self, buffer, view, file_path, click_iter) -> bool:
        """Handle Cmd+Click for Python files."""
        word = self._get_word_at_iter(buffer, click_iter)
        if not word:
            return False

        if word in self.UNNAVIGABLE_BUILTINS:
            return False

        content = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), True)
        imports = self._parse_python_imports(content)
        chain = self._get_chain_at_iter(buffer, click_iter)
        parts = chain.split(".") if chain else [word]

        # Case 1: Clicked word is directly imported
        if word in imports:
            return self._navigate_to_import(word, imports[word], file_path)

        # Case 2: First part of chain is imported (e.g., LogGateway in LogGateway.debug)
        if parts[0] in imports and parts[0] != word:
            module_path = imports[parts[0]]

            if self._open_module(module_path, file_path, navigate_to=word):
                return True

            module_parts = module_path.rsplit(".", 1)
            if len(module_parts) == 2:
                actual_module = module_parts[0]
                class_name = module_parts[1]

                init_file = self._find_module_init(actual_module, file_path)
                if init_file:
                    actual_source = self._resolve_reexport_in_init(init_file, class_name, file_path)
                    if actual_source:
                        self._pending_navigate_symbol = word
                        self._pending_file_path = actual_source
                        self.open_file_callback(actual_source, None)
                        self._schedule_pending_navigation()
                        return True

                if self._open_module(actual_module, file_path, navigate_to=word):
                    return True

        # Case 2b: self.attr.method() - resolve self attributes to their class
        if len(parts) >= 3 and parts[0] == "self":
            attr_name = parts[1]
            class_name = self._find_self_attr_class(content, attr_name)
            if class_name and class_name in imports:
                module_path = imports[class_name]
                module_parts = module_path.rsplit(".", 1)
                if len(module_parts) == 2:
                    actual_module = module_parts[0]
                    class_symbol = module_parts[1]

                    init_file = self._find_module_init(actual_module, file_path)
                    if init_file:
                        actual_source = self._resolve_reexport_in_init(init_file, class_symbol, file_path)
                        if actual_source:
                            self._pending_navigate_symbol = word
                            self._pending_file_path = actual_source
                            self.open_file_callback(actual_source, None)
                            self._schedule_pending_navigation()
                            return True

                    if self._open_module(actual_module, file_path, navigate_to=word):
                        return True

                if self._open_module(module_path, file_path, navigate_to=word):
                    return True

        # Case 2c: Local variable instantiated from an imported class
        if len(parts) > 1 and parts[0] not in imports:
            class_name = self._find_variable_class(content, parts[0])
            if class_name:
                # Handle qualified class (e.g., client = vault.Client(...))
                if "." in class_name:
                    qualifier, actual_class = class_name.rsplit(".", 1)
                    if qualifier in imports:
                        module_path = imports[qualifier]
                        init_file = self._find_module_init(module_path, file_path)
                        if init_file:
                            actual_source = self._resolve_reexport_in_init(init_file, actual_class, file_path)
                            if actual_source:
                                self._pending_navigate_symbol = word
                                self._pending_file_path = actual_source
                                self.open_file_callback(actual_source, None)
                                self._schedule_pending_navigation()
                                return True
                        if self._open_module(module_path, file_path, navigate_to=word):
                            return True

                # Handle unqualified class (e.g., client = Client(...))
                elif class_name in imports:
                    module_path = imports[class_name]
                    module_parts = module_path.rsplit(".", 1)
                    if len(module_parts) == 2:
                        actual_module = module_parts[0]
                        class_symbol = module_parts[1]

                        init_file = self._find_module_init(actual_module, file_path)
                        if init_file:
                            actual_source = self._resolve_reexport_in_init(init_file, class_symbol, file_path)
                            if actual_source:
                                self._pending_navigate_symbol = word
                                self._pending_file_path = actual_source
                                self.open_file_callback(actual_source, None)
                                self._schedule_pending_navigation()
                                return True

                        if self._open_module(actual_module, file_path, navigate_to=word):
                            return True

        # Case 2d: Direct constructor call chained with method
        if word not in imports:
            line_iter = click_iter.copy()
            line_iter.set_line_offset(0)
            line_end_iter = click_iter.copy()
            if not line_end_iter.ends_line():
                line_end_iter.forward_to_line_end()
            line_text = buffer.get_text(line_iter, line_end_iter, True)
            ctor_match = re.search(rf"([A-Z][a-zA-Z0-9_]*)\s*\(.*?\)\.{re.escape(word)}", line_text)
            if ctor_match:
                class_name = ctor_match.group(1)
                if class_name in imports:
                    module_path = imports[class_name]
                    module_parts = module_path.rsplit(".", 1)
                    if len(module_parts) == 2:
                        actual_module = module_parts[0]
                        init_file = self._find_module_init(actual_module, file_path)
                        if init_file:
                            actual_source = self._resolve_reexport_in_init(init_file, class_name, file_path)
                            if actual_source:
                                self._pending_navigate_symbol = word
                                self._pending_file_path = actual_source
                                self.open_file_callback(actual_source, None)
                                self._schedule_pending_navigation()
                                return True
                        if self._open_module(actual_module, file_path, navigate_to=word):
                            return True

        # Case 2e: Parameter of enclosing function
        click_line = click_iter.get_line() + 1  # 1-based
        param_line = self._find_param_declaration_line(content, word, click_line)
        if param_line:
            self._navigate_to_line(buffer, view, param_line, symbol=word)
            return True

        # Case 3: Local definition in current file
        line_num = self._find_python_symbol_in_content(content, word)
        if line_num:
            self._navigate_to_line(buffer, view, line_num, symbol=word)
            return True

        return False

    def _parse_python_imports(self, content: str) -> dict:
        """Parse Python import statements and return mapping of names to module paths."""
        imports = {}

        for match in re.finditer(r"^\s*import\s+(\w+(?:\.\w+)*)(?:\s+as\s+(\w+))?", content, re.MULTILINE):
            module = match.group(1)
            alias = match.group(2) or module.split(".")[-1]
            imports[alias] = module

        for match in re.finditer(
            r"^\s*from\s+(\.+\w*(?:\.\w+)*|\w+(?:\.\w+)*)\s+import\s+(.+?)$",
            content,
            re.MULTILINE,
        ):
            module = match.group(1)
            import_part = match.group(2).strip()

            if import_part.startswith("("):
                paren_match = re.search(r"\(([^)]+)\)", content[match.start() :], re.DOTALL)
                if paren_match:
                    import_part = paren_match.group(1)

            for item in import_part.split(","):
                item = item.strip()
                if not item or item.startswith("#"):
                    continue

                as_match = re.match(r"(\w+)\s+as\s+(\w+)", item)
                if as_match:
                    name = as_match.group(1)
                    alias = as_match.group(2)
                else:
                    name_match = re.match(r"(\w+)", item)
                    if name_match:
                        name = name_match.group(1)
                        alias = name
                    else:
                        continue
                imports[alias] = f"{module}.{name}"

        return imports

    def _navigate_to_import(self, symbol: str, module_path: str, current_file: str) -> bool:
        """Navigate to an imported symbol."""
        if self._open_module(module_path, current_file, navigate_to=symbol):
            return True

        module_parts = module_path.rsplit(".", 1)
        if len(module_parts) == 2:
            actual_module = module_parts[0]
            symbol_name = module_parts[1]

            init_file = self._find_module_init(actual_module, current_file)
            if init_file:
                actual_source = self._resolve_reexport_in_init(init_file, symbol_name, current_file)
                if actual_source:
                    self._pending_navigate_symbol = symbol_name
                    self._pending_file_path = actual_source
                    self.open_file_callback(actual_source, None)
                    self._schedule_pending_navigation()
                    return True

            if self._open_module(actual_module, current_file, navigate_to=symbol_name):
                return True

        return False

    def _open_module(self, module_path: str, current_file: str, navigate_to: str = None) -> bool:
        """Try to open a Python module file."""
        if not current_file:
            return False

        current_dir = os.path.dirname(current_file)

        # Handle relative imports
        if module_path.startswith("."):
            dots = len(module_path) - len(module_path.lstrip("."))
            rest = module_path.lstrip(".")

            target_dir = current_dir
            for _ in range(dots - 1):
                target_dir = os.path.dirname(target_dir)

            if rest:
                rel_path = rest.replace(".", os.sep)
                target = os.path.join(target_dir, rel_path)
            else:
                target = target_dir

            for candidate in [target + ".py", os.path.join(target, "__init__.py")]:
                if os.path.exists(candidate):
                    self._pending_navigate_symbol = navigate_to
                    self._pending_file_path = candidate
                    self.open_file_callback(candidate, None)
                    if navigate_to:
                        self._schedule_pending_navigation()
                    return True
            return False

        rel_path = module_path.replace(".", os.sep)
        first_part = module_path.split(".")[0]

        search_dirs = [current_dir]

        check_dir = current_dir
        while check_dir and len(check_dir) > 1:
            if os.path.basename(check_dir) == first_part:
                parent = os.path.dirname(check_dir)
                if parent not in search_dirs:
                    search_dirs.insert(0, parent)
                break
            candidate = os.path.join(check_dir, first_part)
            if os.path.isdir(candidate) and check_dir not in search_dirs:
                search_dirs.insert(0, check_dir)
                break
            check_dir = os.path.dirname(check_dir)

        if self.get_workspace_folders:
            try:
                for ws_folder in self.get_workspace_folders() or []:
                    if ws_folder and ws_folder not in search_dirs:
                        search_dirs.append(ws_folder)
                        module_dir = os.path.join(ws_folder, first_part)
                        if os.path.isdir(module_dir):
                            parent = os.path.dirname(module_dir)
                            if parent not in search_dirs:
                                search_dirs.append(parent)
            except Exception:
                pass

        for sp in self._find_venv_site_packages(current_file):
            if sp not in search_dirs:
                search_dirs.append(sp)

        for path in sys.path:
            if path and os.path.isdir(path) and path not in search_dirs:
                search_dirs.append(path)

        for base_dir in search_dirs:
            target = os.path.join(base_dir, rel_path)

            if os.path.exists(target + ".py"):
                self._pending_navigate_symbol = navigate_to
                self._pending_file_path = target + ".py"
                self.open_file_callback(target + ".py", None)
                if navigate_to:
                    self._schedule_pending_navigation()
                return True

            init_file = os.path.join(target, "__init__.py")
            if os.path.exists(init_file):
                self._pending_navigate_symbol = navigate_to
                self._pending_file_path = init_file
                self.open_file_callback(init_file, None)
                if navigate_to:
                    self._schedule_pending_navigation()
                return True

        return False

    def _find_module_init(self, module_path: str, current_file: str) -> Optional[str]:
        """Find the __init__.py file for a module path."""
        if not current_file:
            return None

        current_dir = os.path.dirname(current_file)
        rel_path = module_path.replace(".", os.sep)
        first_part = module_path.split(".")[0]

        search_dirs = [current_dir]

        check_dir = current_dir
        while check_dir and len(check_dir) > 1:
            candidate = os.path.join(check_dir, first_part)
            if os.path.isdir(candidate) and check_dir not in search_dirs:
                search_dirs.insert(0, check_dir)
                break
            check_dir = os.path.dirname(check_dir)

        if self.get_workspace_folders:
            try:
                for ws_folder in self.get_workspace_folders() or []:
                    if ws_folder:
                        search_dirs.append(ws_folder)
                        module_dir = os.path.join(ws_folder, first_part)
                        if os.path.isdir(module_dir):
                            search_dirs.append(os.path.dirname(module_dir))
            except Exception:
                pass

        for sp in self._find_venv_site_packages(current_file):
            if sp not in search_dirs:
                search_dirs.append(sp)

        for search_dir in search_dirs:
            init_file = os.path.join(search_dir, rel_path, "__init__.py")
            if os.path.exists(init_file):
                return init_file

        return None

    def _resolve_reexport_in_init(self, init_file: str, symbol: str, current_file: str) -> Optional[str]:
        """Check if a symbol in __init__.py is re-exported from another module."""
        try:
            with open(init_file, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except (OSError, IOError):
            return None

        init_dir = os.path.dirname(init_file)

        # Match both relative imports (from .xxx) and absolute imports (from xxx.yyy)
        pattern = rf"^from\s+(\.+[a-zA-Z0-9_]*(?:\.[a-zA-Z0-9_]+)*|[a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z0-9_]+)*)\s+import\s+(?:\([^)]*\b{re.escape(symbol)}\b[^)]*\)|[^(\n]*\b{re.escape(symbol)}\b)"
        match = re.search(pattern, content, re.MULTILINE)

        if match:
            module_ref = match.group(1)

            if module_ref.startswith("."):
                # Relative import
                dots = len(module_ref) - len(module_ref.lstrip("."))
                module_path = module_ref.lstrip(".")

                target_dir = init_dir
                for _ in range(dots - 1):
                    target_dir = os.path.dirname(target_dir)

                if module_path:
                    rel_path = module_path.replace(".", os.sep)
                    target_base = os.path.join(target_dir, rel_path)
                else:
                    target_base = target_dir
            else:
                # Absolute import - strip package name if it matches this package
                package_name = os.path.basename(init_dir)
                module_parts = module_ref.split(".")
                if module_parts[0] == package_name and len(module_parts) > 1:
                    rest = os.sep.join(module_parts[1:])
                    target_base = os.path.join(init_dir, rest)
                else:
                    parent_dir = os.path.dirname(init_dir)
                    target_base = os.path.join(parent_dir, module_ref.replace(".", os.sep))

            if os.path.exists(target_base + ".py"):
                return target_base + ".py"

            if os.path.exists(os.path.join(target_base, "__init__.py")):
                return os.path.join(target_base, "__init__.py")

            # Fallback for absolute imports: walk up ancestor directories
            # to find where the module path resolves (handles nested packages
            # like `from shared.settings.settings_manager import get_setting`
            # inside `shared/settings/__init__.py`)
            if not module_ref.startswith("."):
                rel = module_ref.replace(".", os.sep)
                ancestor = init_dir
                while ancestor and len(ancestor) > 1:
                    ancestor = os.path.dirname(ancestor)
                    candidate = os.path.join(ancestor, rel)
                    if os.path.exists(candidate + ".py"):
                        return candidate + ".py"
                    if os.path.exists(os.path.join(candidate, "__init__.py")):
                        return os.path.join(candidate, "__init__.py")

        return None

    def _find_variable_class(self, content: str, var_name: str) -> Optional[str]:
        """Find the class a variable is instantiated from.
        Returns the class name, possibly qualified (e.g., 'vault.Client')."""
        pattern = rf"^\s*{re.escape(var_name)}\s*=\s*((?:[a-zA-Z_][a-zA-Z0-9_]*\.)*[A-Z][a-zA-Z0-9_]*)\s*\("
        match = re.search(pattern, content, re.MULTILINE)
        if match:
            return match.group(1)
        return None

    def _find_self_attr_class(self, content: str, attr_name: str) -> Optional[str]:
        """Find the class a self.attr is instantiated from (e.g., self.utils = MyClass(...))."""
        pattern = rf"self\.{re.escape(attr_name)}\s*=\s*((?:[a-zA-Z_][a-zA-Z0-9_]*\.)*[A-Z][a-zA-Z0-9_]*)\s*\("
        match = re.search(pattern, content, re.MULTILINE)
        if match:
            return match.group(1)
        return None

    def _find_venv_site_packages(self, current_file: str) -> list:
        """Find virtualenv site-packages directories for the project."""
        venv_names = [".venv", "venv"]
        site_packages = []
        checked = set()

        check_dir = os.path.dirname(current_file)
        while check_dir and len(check_dir) > 1:
            if check_dir in checked:
                break
            checked.add(check_dir)
            for venv_name in venv_names:
                venv_path = os.path.join(check_dir, venv_name)
                if os.path.isdir(venv_path):
                    for sp in glob_module.glob(os.path.join(venv_path, "lib", "python*", "site-packages")):
                        if os.path.isdir(sp):
                            site_packages.append(sp)
                    if site_packages:
                        return site_packages
            check_dir = os.path.dirname(check_dir)

        if self.get_workspace_folders:
            try:
                for ws_folder in self.get_workspace_folders() or []:
                    if ws_folder and ws_folder not in checked:
                        for venv_name in venv_names:
                            venv_path = os.path.join(ws_folder, venv_name)
                            if os.path.isdir(venv_path):
                                for sp in glob_module.glob(os.path.join(venv_path, "lib", "python*", "site-packages")):
                                    if os.path.isdir(sp):
                                        site_packages.append(sp)
            except Exception:
                pass

        return site_packages

    def _find_python_symbol_in_content(self, content: str, symbol: str) -> Optional[int]:
        """Find Python symbol definition in content. Returns 1-based line number."""
        patterns = [
            rf"^class\s+{re.escape(symbol)}\s*[:\(]",
            rf"^\s*def\s+{re.escape(symbol)}\s*\(",
            rf"^\s*{re.escape(symbol)}\s*=",
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

    def _find_param_declaration_line(self, content: str, word: str, click_line: int) -> Optional[int]:
        """Find the line where *word* is declared as a parameter of the enclosing function.

        Scans backwards from *click_line* to find the nearest ``def`` statement,
        extracts the full (possibly multi-line) signature, and checks whether
        *word* appears as a parameter name.  Returns the 1-based line number
        where the parameter token appears, or ``None``.
        """
        lines = content.split("\n")
        if click_line < 1 or click_line > len(lines):
            return None

        # Walk backwards to find the enclosing def
        def_line_idx = None
        for i in range(click_line - 1, -1, -1):
            stripped = lines[i].lstrip()
            if stripped.startswith("def "):
                def_line_idx = i
                break
            # Stop at class / module boundary so we don't cross scopes
            if stripped.startswith("class ") and i < click_line - 1:
                return None

        if def_line_idx is None:
            return None

        # Collect the full signature (may span multiple lines until the closing paren)
        sig_lines: list[tuple[int, str]] = []  # (0-based line idx, text)
        paren_depth = 0
        found_open = False
        for i in range(def_line_idx, min(def_line_idx + 50, len(lines))):
            line_text = lines[i]
            sig_lines.append((i, line_text))
            for ch in line_text:
                if ch == "(":
                    paren_depth += 1
                    found_open = True
                elif ch == ")":
                    paren_depth -= 1
            if found_open and paren_depth <= 0:
                break

        # Search for the word as a parameter name in each signature line
        param_pat = re.compile(rf"(?<![.\w]){re.escape(word)}(?![.\w])")
        for line_idx, line_text in sig_lines:
            if line_idx == def_line_idx:
                # Skip the 'def name' portion to avoid matching the function name
                paren_pos = line_text.find("(")
                if paren_pos >= 0:
                    search_text = line_text[paren_pos:]
                else:
                    continue
            else:
                search_text = line_text

            if param_pat.search(search_text):
                # Don't navigate if already on the declaration line
                if line_idx + 1 == click_line:
                    return None
                return line_idx + 1  # 1-based

        return None
