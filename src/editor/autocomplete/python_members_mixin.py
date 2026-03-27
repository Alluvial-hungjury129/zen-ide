"""
Python member/attribute completions for Zen IDE autocomplete.

Provides dot-access member completions and call parameter completions
via PythonMembersMixin.
"""

import re

from editor.autocomplete import CompletionItem, CompletionKind
from editor.autocomplete.tree_sitter_provider import (
    _parse,
    py_extract_file_symbols,
    py_extract_self_members,
    py_find_enclosing_class,
    py_find_function_signature,
    py_find_method_signature,
    py_resolve_chain,
    py_resolve_variable_type,
)


class PythonMembersMixin:
    """Mixin providing dot-access member and call parameter completions."""

    def get_call_parameter_completions(self, buffer, cursor_iter, file_path, buffer_text):
        """Get parameter completions when cursor is inside a function call.

        Detects the enclosing function call, resolves its signature, and returns
        CompletionItems for remaining (unspecified) parameters.
        """
        ctx = self._detect_call_context(buffer, cursor_iter)
        if not ctx:
            return []

        func_chain, specified_kwargs, positional_count = ctx

        source, tree = _parse(buffer_text, "python")
        sig = self._resolve_function_signature(
            func_chain, file_path, buffer_text, source, tree, cursor_offset=cursor_iter.get_offset()
        )
        if not sig:
            return []

        params = self._parse_params_with_defaults(sig)
        if not params:
            return []

        # Skip params covered by positional arguments
        remaining = params[positional_count:]

        # Remove already-specified keyword arguments
        remaining = [(name, default) for name, default in remaining if name not in specified_kwargs]

        completions = []
        for name, default in remaining:
            insert = f"{name}={default}" if default is not None else f"{name}="
            completions.append(
                CompletionItem(
                    name=name,
                    kind=CompletionKind.PARAMETER,
                    signature=sig,
                    insert_text=insert,
                )
            )
        return completions

    def _detect_call_context(self, buffer, cursor_iter):
        """Detect if cursor is inside a function call's parentheses.

        Returns (func_chain, specified_kwargs, positional_count) or None.
        """
        pos = cursor_iter.copy()
        depth = 0
        max_scan = 2000

        # Scan backward to find matching '('
        for _ in range(max_scan):
            if not pos.backward_char():
                return None
            ch = pos.get_char()
            if ch == ")":
                depth += 1
            elif ch == "(":
                if depth == 0:
                    break
                depth -= 1
        else:
            return None

        paren_pos = pos.copy()

        # Extract function name before '('
        func_end = paren_pos.copy()
        func_start = func_end.copy()
        while func_start.backward_char():
            ch = func_start.get_char()
            if not (ch.isalnum() or ch == "_" or ch == "."):
                func_start.forward_char()
                break
        func_chain = buffer.get_text(func_start, func_end, False)

        if not func_chain or not re.match(r"^[A-Za-z_][\w.]*$", func_chain):
            return None

        # Skip control-flow keywords
        first_part = func_chain.split(".")[0]
        skip_keywords = {
            "def",
            "class",
            "if",
            "elif",
            "while",
            "for",
            "with",
            "except",
            "return",
            "yield",
            "assert",
            "lambda",
            "not",
            "and",
            "or",
            "in",
            "is",
            "import",
            "from",
            "raise",
            "del",
            "global",
            "nonlocal",
            "pass",
        }
        if first_part in skip_keywords:
            return None

        # Extract args text between '(' and cursor
        after_paren = paren_pos.copy()
        after_paren.forward_char()
        args_text = buffer.get_text(after_paren, cursor_iter, False)

        # Parse specified arguments
        specified_kwargs = set()
        positional_count = 0
        args = self._split_call_args(args_text)
        for arg in args:
            if not arg:
                continue
            # Check if it's a keyword argument (name=value, but not ==, !=, <=, >=)
            eq_match = re.match(r"^([A-Za-z_]\w*)\s*=(?!=)", arg)
            if eq_match:
                specified_kwargs.add(eq_match.group(1))
            else:
                positional_count += 1

        return func_chain, specified_kwargs, positional_count

    @staticmethod
    def _split_call_args(args_text):
        """Split function call arguments at top-level commas.

        Handles nested parens, brackets, and string literals.
        """
        args = []
        current = []
        depth = 0
        in_string = None
        escape = False

        for ch in args_text:
            if escape:
                current.append(ch)
                escape = False
                continue
            if ch == "\\":
                current.append(ch)
                escape = True
                continue
            if in_string:
                current.append(ch)
                if ch == in_string:
                    in_string = None
                continue
            if ch in ('"', "'"):
                in_string = ch
                current.append(ch)
                continue
            if ch in ("(", "[", "{"):
                depth += 1
                current.append(ch)
                continue
            if ch in (")", "]", "}"):
                depth -= 1
                current.append(ch)
                continue
            if ch == "," and depth == 0:
                args.append("".join(current).strip())
                current = []
                continue
            current.append(ch)

        remaining = "".join(current).strip()
        if remaining:
            args.append(remaining)
        return args

    def _resolve_function_signature(self, func_chain, file_path, buffer_text, source=None, tree=None, *, cursor_offset=None):
        """Resolve a function/method call chain to its signature string."""
        if source is None or tree is None:
            source, tree = _parse(buffer_text, "python")
        if tree is None:
            return None

        parts = func_chain.split(".")

        if len(parts) == 1:
            return self._find_local_or_imported_signature(parts[0], file_path, source, tree)

        method_name = parts[-1]
        first = parts[0]

        # Handle self/cls
        if first in ("self", "cls") and cursor_offset is not None:
            byte_offset = len(buffer_text[:cursor_offset].encode("utf-8"))
            class_name = py_find_enclosing_class(source, tree, byte_offset)
            if class_name:
                return py_find_method_signature(source, tree, class_name, method_name)
            return None

        # Try resolving variable type
        resolved_class = py_resolve_variable_type(source, tree, first)
        if resolved_class:
            sig = py_find_method_signature(source, tree, resolved_class, method_name)
            if sig:
                return sig
            sig = self._find_method_in_imported_class(resolved_class, method_name, source, tree, file_path)
            if sig:
                return sig

        # Try as a direct class reference
        sig = py_find_method_signature(source, tree, first, method_name)
        if sig:
            return sig

        # Try imported class.method
        sig = self._find_method_in_imported_class(first, method_name, source, tree, file_path)
        if sig:
            return sig

        return None

    def _find_local_or_imported_signature(self, func_name, file_path, source, tree):
        """Find function signature in local definitions or imports."""
        sig = py_find_function_signature(source, tree, func_name)
        if sig:
            return sig

        if not file_path:
            return None

        # Search imports for the function name
        module_info = self._find_import_module(source, tree, func_name)
        if module_info:
            module_path, original_name = module_info
            module_text = self._read_module_text(module_path, file_path)
            if module_text:
                m_source, m_tree = _parse(module_text, "python")
                if m_tree:
                    sig = py_find_function_signature(m_source, m_tree, original_name)
                    if sig and original_name != func_name:
                        sig = sig.replace(original_name, func_name, 1)
                    return sig
        return None

    def _find_method_in_imported_class(self, class_name, method_name, source, tree, file_path):
        """Find a method signature in an imported class."""
        if not file_path:
            return None

        module_info = self._find_import_module(source, tree, class_name)
        if not module_info:
            return None

        module_path, original_name = module_info
        module_text = self._read_module_text(module_path, file_path)

        if module_text:
            m_source, m_tree = _parse(module_text, "python")
            if m_tree:
                sig = py_find_method_signature(m_source, m_tree, original_name, method_name)
                if sig:
                    return sig
                # Follow re-exports
                sub_text = self._follow_reexport_ts(m_source, m_tree, original_name, module_path, file_path)
                if sub_text:
                    s_source, s_tree = _parse(sub_text, "python")
                    if s_tree:
                        sig = py_find_method_signature(s_source, s_tree, original_name, method_name)
                        if sig:
                            return sig

        # Try treating as submodule (e.g., gi.repository.Gtk)
        if original_name:
            sub_module_text = self._read_module_text(f"{module_path}.{original_name}", file_path)
            if sub_module_text:
                s_source, s_tree = _parse(sub_module_text, "python")
                if s_tree:
                    sig = py_find_method_signature(s_source, s_tree, class_name, method_name)
                    if sig:
                        return sig
        return None

    @staticmethod
    def _parse_params_with_defaults(sig_text):
        """Parse function signature into list of (param_name, default_value_or_None) tuples.

        Strips self/cls, *args, **kwargs, and positional-only markers.
        """
        m = re.search(r"\(([^)]*)\)", sig_text)
        if not m:
            return []
        params_str = m.group(1).strip()
        if not params_str:
            return []

        result = []
        for param in params_str.split(","):
            param = param.strip()
            if not param or param == "/":
                continue

            # Strip leading * or ** for *args/**kwargs
            bare = param.lstrip("*")
            name_part = bare.split(":")[0].split("=")[0].strip()

            if name_part in ("self", "cls", ""):
                continue
            # Skip bare * (keyword-only separator) and *args/**kwargs
            if param.startswith("*"):
                continue

            if "=" in param:
                eq_idx = param.index("=")
                name = param[:eq_idx].split(":")[0].strip()
                default = param[eq_idx + 1 :].strip()
            else:
                name = param.split(":")[0].strip()
                default = None

            if name and re.match(r"^[A-Za-z_]\w*$", name):
                result.append((name, default))
        return result

    def detect_dot_access_context(self, buffer, word_start_offset):
        """Detect if cursor is after 'Name.' or 'Name.Sub.' and return the full chain, or None."""
        pos = buffer.get_iter_at_offset(word_start_offset)
        dot_pos = pos.copy()
        if not dot_pos.backward_char():
            return None
        if dot_pos.get_char() != ".":
            return None
        chain_end = dot_pos.copy()
        chain_start = dot_pos.copy()
        while chain_start.backward_char():
            ch = chain_start.get_char()
            if not (ch.isalnum() or ch == "_" or ch == "."):
                chain_start.forward_char()
                break
        chain = buffer.get_text(chain_start, chain_end, False)
        if chain and re.match(r"^[A-Za-z_]\w*(\.[A-Za-z_]\w*)*$", chain):
            return chain
        return None

    def resolve_dot_completions(self, dot_chain, file_path, buffer_text, cursor_offset=None):
        """Resolve dot-access completions for a dotted chain (e.g., DBTables or DBTables.Cards)."""
        if not file_path:
            return []
        parts = dot_chain.split(".")
        first = parts[0]

        source, tree = _parse(buffer_text, "python")
        if tree is None:
            return []

        # Handle self/cls: resolve to enclosing class
        if first in ("self", "cls") and cursor_offset is not None:
            byte_offset = len(buffer_text[:cursor_offset].encode("utf-8"))
            class_name = py_find_enclosing_class(source, tree, byte_offset)
            if class_name:
                if len(parts) == 1:
                    return py_extract_self_members(source, tree, class_name)
                else:
                    chain = [class_name] + parts[1:]
                    return py_resolve_chain(source, tree, chain)
            return []

        # Try to resolve variable type from assignment
        resolved_class = py_resolve_variable_type(source, tree, first)
        if resolved_class and resolved_class != first:
            resolved_parts = [resolved_class] + parts[1:]
            local = py_resolve_chain(source, tree, resolved_parts)
            if local:
                return local
            first = resolved_class
            parts = resolved_parts

        # Check local classes first
        local = py_resolve_chain(source, tree, parts)
        if local:
            return local

        # Find module path from imports
        module_info = self._find_import_module(source, tree, first)
        if not module_info:
            return []

        module_path, original_name = module_info
        module_text = self._read_module_text(module_path, file_path)

        # If the module itself can't be found, try treating the imported name
        # as a submodule (e.g., ``from gi.repository import Gtk`` where Gtk is
        # a submodule, not a symbol in gi/repository/__init__.py).
        if not module_text and original_name:
            sub_module_text = self._read_module_text(f"{module_path}.{original_name}", file_path)
            if sub_module_text:
                s_source, s_tree = _parse(sub_module_text, "python")
                if s_tree:
                    if len(parts) == 1:
                        result = py_extract_file_symbols(s_source, s_tree)
                        if isinstance(result, tuple):
                            symbols, _ = result
                            return sorted(symbols.values(), key=lambda x: x.name)
                        return result
                    else:
                        return py_resolve_chain(s_source, s_tree, parts[1:])
            return []

        if not module_text:
            return []

        m_source, m_tree = _parse(module_text, "python")
        if m_tree is None:
            return []

        # Whole-module import (e.g., ``import threading``): original_name is None
        if original_name is None:
            if len(parts) == 1:
                # ``threading.`` → show all top-level symbols from the module
                result = py_extract_file_symbols(m_source, m_tree)
                if isinstance(result, tuple):
                    symbols, _ = result
                    return sorted(symbols.values(), key=lambda x: x.name)
                return result
            else:
                # ``threading.Thread.`` → resolve chain within the module
                return py_resolve_chain(m_source, m_tree, parts[1:])

        chain = [original_name] + parts[1:]
        result = py_resolve_chain(m_source, m_tree, chain)
        if result:
            return result

        # Try treating as submodule when resolution within module fails
        sub_module_text = self._read_module_text(f"{module_path}.{original_name}", file_path)
        if sub_module_text:
            s_source, s_tree = _parse(sub_module_text, "python")
            if s_tree:
                if len(parts) == 1:
                    result = py_extract_file_symbols(s_source, s_tree)
                    if isinstance(result, tuple):
                        symbols, _ = result
                        return sorted(symbols.values(), key=lambda x: x.name)
                    return result
                else:
                    return py_resolve_chain(s_source, s_tree, parts[1:])

        # Follow re-exports
        sub_text = self._follow_reexport_ts(m_source, m_tree, original_name, module_path, file_path)
        if sub_text:
            s_source, s_tree = _parse(sub_text, "python")
            if s_tree:
                return py_resolve_chain(s_source, s_tree, chain)
        return []
