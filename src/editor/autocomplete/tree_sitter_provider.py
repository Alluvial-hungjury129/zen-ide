"""
Tree-sitter based completion extraction for Zen IDE.

Provides AST-based extraction functions used by the language-specific
completion providers (Python, JS/TS).  All tree-sitter imports are
deferred to the functions that use them to preserve startup performance.

Language-specific logic lives in:
- ts_python.py — Python completions
- ts_javascript.py — JavaScript/TypeScript completions

All public symbols are re-exported here for backward compatibility.
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _node_text(source: bytes, node) -> str:
    """Extract UTF-8 text spanned by a tree-sitter node."""
    return source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


def _top_level_children(root, type_name: str):
    """Yield direct children of *root* that match *type_name*."""
    for child in root.children:
        if child.type == type_name:
            yield child
        elif child.type == "decorated_definition":
            for sub in child.children:
                if sub.type == type_name:
                    yield sub


def _parse(source_text: str, lang: str):
    """Parse source text and return (source_bytes, tree) or (None, None)."""
    from navigation.tree_sitter_core import TreeSitterCore

    source_bytes = source_text.encode("utf-8")
    tree = TreeSitterCore.parse(source_bytes, lang)
    if tree is None:
        return None, None
    return source_bytes, tree


# ---------------------------------------------------------------------------
# Re-exports — Python
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Re-exports — JavaScript / TypeScript
# ---------------------------------------------------------------------------
from editor.autocomplete.ts_javascript import (  # noqa: E402, F401
    _js_extract_jsdoc,
    _js_extract_node,
    _js_import_clause,
    js_extract_definitions,
    js_extract_imports,
)
from editor.autocomplete.ts_python import (  # noqa: E402, F401
    _collect_self_attrs,
    _extract_dataclass_fields,
    _extract_members_from_class,
    _find_class_node,
    _is_dataclass_node,
    _py_import_from_stmt,
    _py_import_stmt,
    _walk_for_self_attrs,
    py_extract_class_members,
    py_extract_definitions,
    py_extract_docstring,
    py_extract_file_symbols,
    py_extract_imports,
    py_extract_init_signature,
    py_extract_self_members,
    py_extract_signature,
    py_find_enclosing_class,
    py_find_function_signature,
    py_find_method_signature,
    py_resolve_chain,
    py_resolve_variable_type,
)
