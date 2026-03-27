"""
Python builtin completions for Zen IDE autocomplete.

Provides Python keyword and builtin completions via PythonBuiltinsMixin.
"""

import keyword

from editor.autocomplete import CompletionItem, CompletionKind
from editor.autocomplete.tree_sitter_provider import (
    _parse,
    py_extract_definitions,
    py_extract_imports,
)

# Python builtins
PYTHON_BUILTINS = [
    "abs",
    "all",
    "any",
    "ascii",
    "bin",
    "bool",
    "breakpoint",
    "bytearray",
    "bytes",
    "callable",
    "chr",
    "classmethod",
    "compile",
    "complex",
    "delattr",
    "dict",
    "dir",
    "divmod",
    "enumerate",
    "eval",
    "exec",
    "filter",
    "float",
    "format",
    "frozenset",
    "getattr",
    "globals",
    "hasattr",
    "hash",
    "help",
    "hex",
    "id",
    "input",
    "int",
    "isinstance",
    "issubclass",
    "iter",
    "len",
    "list",
    "locals",
    "map",
    "max",
    "memoryview",
    "min",
    "next",
    "object",
    "oct",
    "open",
    "ord",
    "pow",
    "print",
    "property",
    "range",
    "repr",
    "reversed",
    "round",
    "set",
    "setattr",
    "slice",
    "sorted",
    "staticmethod",
    "str",
    "sum",
    "super",
    "tuple",
    "type",
    "vars",
    "zip",
    "__import__",
    "Exception",
    "ValueError",
    "TypeError",
    "KeyError",
    "IndexError",
    "AttributeError",
    "ImportError",
    "RuntimeError",
    "StopIteration",
    "FileNotFoundError",
    "PermissionError",
    "OSError",
    "IOError",
    "None",
    "True",
    "False",
    "Ellipsis",
    "NotImplemented",
]


class PythonBuiltinsMixin:
    """Mixin providing Python keyword and builtin completions."""

    def get_completions(self, buffer_text, file_path=None):
        """Get Python keyword, builtin, import, and symbol completions."""
        completions = []
        completions.extend(CompletionItem(kw, CompletionKind.KEYWORD) for kw in keyword.kwlist)
        completions.extend(CompletionItem(b, CompletionKind.BUILTIN) for b in PYTHON_BUILTINS)

        source, tree = _parse(buffer_text, "python")
        if tree is not None:
            imports = py_extract_imports(source, tree)
            if file_path:
                self._enrich_imports(imports, source, tree, file_path)
            completions.extend(imports)
            completions.extend(py_extract_definitions(source, tree))
        return completions
