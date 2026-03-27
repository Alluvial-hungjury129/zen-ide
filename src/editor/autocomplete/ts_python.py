"""
Python-specific tree-sitter completion extraction for Zen IDE.

Provides AST-based extraction of Python definitions, imports, signatures,
and docstrings.  Class member extraction, enclosing class detection,
chain resolution, and file symbol extraction live in ts_python_members.py
and are re-exported here for convenience.
"""

from editor.autocomplete.autocomplete import CompletionItem, CompletionKind
from editor.autocomplete.tree_sitter_provider import _node_text, _top_level_children

# ---------------------------------------------------------------------------
# Python — signature & docstring extraction
# ---------------------------------------------------------------------------


def py_extract_signature(source: bytes, func_node) -> str:
    """Build a human-readable signature from a ``function_definition`` node."""
    name_node = func_node.child_by_field_name("name")
    params_node = func_node.child_by_field_name("parameters")
    return_type = func_node.child_by_field_name("return_type")

    name = _node_text(source, name_node) if name_node else "?"
    params = _node_text(source, params_node) if params_node else "()"
    sig = f"{name}{params}"
    if return_type:
        sig += f" → {_node_text(source, return_type)}"
    return sig


def py_extract_docstring(source: bytes, node) -> str:
    """Extract the first line of a docstring from a function/class body."""
    body = node.child_by_field_name("body")
    if not body or body.child_count == 0:
        return ""

    first_stmt = body.children[0]
    if first_stmt.type != "expression_statement" or first_stmt.child_count == 0:
        return ""
    expr = first_stmt.children[0]
    if expr.type != "string":
        return ""

    doc = _node_text(source, expr)
    for quote in ('"""', "'''"):
        if doc.startswith(quote) and doc.endswith(quote):
            doc = doc[3:-3].strip()
            return doc.split("\n")[0].strip()[:120]
    return ""


# ---------------------------------------------------------------------------
# Python — init / dataclass constructor
# ---------------------------------------------------------------------------


def _is_dataclass_node(source: bytes, class_node) -> bool:
    """Check whether *class_node* has a ``@dataclass`` decorator."""
    parent = class_node.parent
    if parent and parent.type == "decorated_definition":
        for child in parent.children:
            if child.type == "decorator":
                text = _node_text(source, child)
                if "dataclass" in text:
                    return True
    return False


def _extract_dataclass_fields(source: bytes, body_node) -> list[str]:
    """Extract ``name: Type`` fields from a dataclass body for the constructor signature."""
    fields = []
    for child in body_node.children:
        if child.type != "expression_statement" or child.child_count == 0:
            continue
        expr = child.children[0]
        if expr.type == "assignment":
            ann = expr.child_by_field_name("type")
            left = expr.child_by_field_name("left")
            if not left or left.type != "identifier" or not ann:
                continue
            ann_text = _node_text(source, ann)
            if ann_text.startswith("ClassVar"):
                continue
            right = expr.child_by_field_name("right")
            if right and right.type == "call":
                call_text = _node_text(source, right)
                if "init=False" in call_text or "init = False" in call_text:
                    continue
            name = _node_text(source, left)
            fields.append(f"{name}: {ann_text}")
        elif expr.type == "type":
            # Bare annotation: ``x: int``  (no default value)
            text = _node_text(source, expr).strip()
            if ":" in text:
                if not text.split(":")[-1].strip().startswith("ClassVar"):
                    fields.append(text)
    return fields


def py_extract_init_signature(source: bytes, class_node) -> str:
    """Extract ``ClassName(params)`` from ``__init__`` or ``@dataclass`` fields."""
    name_node = class_node.child_by_field_name("name")
    class_name = _node_text(source, name_node) if name_node else "?"

    body = class_node.child_by_field_name("body")
    if not body:
        return f"{class_name}()"

    # Look for explicit __init__
    for child in body.children:
        func = None
        if child.type == "function_definition":
            func = child
        elif child.type == "decorated_definition":
            for sub in child.children:
                if sub.type == "function_definition":
                    func = sub
                    break
        if func:
            fname = func.child_by_field_name("name")
            if fname and _node_text(source, fname) == "__init__":
                params = func.child_by_field_name("parameters")
                return f"{class_name}{_node_text(source, params)}" if params else f"{class_name}()"

    # Dataclass fields as constructor params
    if _is_dataclass_node(source, class_node):
        fields = _extract_dataclass_fields(source, body)
        if fields:
            return f"{class_name}({', '.join(fields)})"

    return f"{class_name}()"


# ---------------------------------------------------------------------------
# Python — top-level definitions
# ---------------------------------------------------------------------------


def py_extract_definitions(source: bytes, tree) -> list[CompletionItem]:
    """Extract top-level function, class, and variable definitions."""
    items: list[CompletionItem] = []
    root = tree.root_node

    for node in _top_level_children(root, "function_definition"):
        name_node = node.child_by_field_name("name")
        if not name_node:
            continue
        name = _node_text(source, name_node)
        sig = py_extract_signature(source, node)
        doc = py_extract_docstring(source, node)
        items.append(CompletionItem(name, CompletionKind.FUNCTION, sig, doc))

    for node in _top_level_children(root, "class_definition"):
        name_node = node.child_by_field_name("name")
        if not name_node:
            continue
        name = _node_text(source, name_node)
        doc = py_extract_docstring(source, node)
        init_sig = py_extract_init_signature(source, node)
        items.append(CompletionItem(name, CompletionKind.CLASS, init_sig, doc))

    # Top-level assignments: ``name = ...``
    for child in root.children:
        if child.type != "expression_statement" or child.child_count == 0:
            continue
        expr = child.children[0]
        if expr.type != "assignment":
            continue
        left = expr.child_by_field_name("left")
        if left and left.type == "identifier":
            name = _node_text(source, left)
            if name not in ("_", "__all__", "__version__"):
                items.append(CompletionItem(name, CompletionKind.VARIABLE))

    return items


# ---------------------------------------------------------------------------
# Python — imports
# ---------------------------------------------------------------------------


def py_extract_imports(source: bytes, tree) -> list[CompletionItem]:
    """Extract imported symbol names from the AST."""
    items: list[CompletionItem] = []
    root = tree.root_node

    for child in root.children:
        if child.type == "import_statement":
            _py_import_stmt(source, child, items)
        elif child.type == "import_from_statement":
            _py_import_from_stmt(source, child, items)
        # Handle imports inside try/except blocks
        elif child.type == "try_statement":
            for body_child in child.children:
                if body_child.type == "block":
                    for stmt in body_child.children:
                        if stmt.type == "import_statement":
                            _py_import_stmt(source, stmt, items)
                        elif stmt.type == "import_from_statement":
                            _py_import_from_stmt(source, stmt, items)
                elif body_child.type == "except_clause":
                    for stmt in body_child.children:
                        if stmt.type == "block":
                            for inner in stmt.children:
                                if inner.type == "import_statement":
                                    _py_import_stmt(source, inner, items)
                                elif inner.type == "import_from_statement":
                                    _py_import_from_stmt(source, inner, items)

    return items


def _py_import_stmt(source: bytes, node, items: list):
    """Process ``import X`` or ``import X as Y``."""
    for child in node.children:
        if child.type == "dotted_name":
            parts = _node_text(source, child).split(".")
            items.append(CompletionItem(parts[-1], CompletionKind.VARIABLE))
        elif child.type == "aliased_import":
            alias_node = child.child_by_field_name("alias")
            if alias_node:
                items.append(CompletionItem(_node_text(source, alias_node), CompletionKind.VARIABLE))
            else:
                name_node = child.child_by_field_name("name")
                if name_node:
                    parts = _node_text(source, name_node).split(".")
                    items.append(CompletionItem(parts[-1], CompletionKind.VARIABLE))


def _py_import_from_stmt(source: bytes, node, items: list):
    """Process ``from X import a, b as c``."""
    for child in node.children:
        if child.type == "dotted_name" and child != node.child_by_field_name("module_name"):
            items.append(CompletionItem(_node_text(source, child), CompletionKind.VARIABLE))
        elif child.type == "aliased_import":
            alias_node = child.child_by_field_name("alias")
            name_node = child.child_by_field_name("name")
            if alias_node:
                items.append(CompletionItem(_node_text(source, alias_node), CompletionKind.VARIABLE))
            elif name_node:
                items.append(CompletionItem(_node_text(source, name_node), CompletionKind.VARIABLE))


# ---------------------------------------------------------------------------
# Re-exports from ts_python_members — class members, signatures, etc.
# ---------------------------------------------------------------------------

from editor.autocomplete.ts_python_members import (  # noqa: E402, F401
    _collect_self_attrs,
    _extract_members_from_class,
    _find_class_node,
    _walk_for_self_attrs,
    py_extract_class_members,
    py_extract_file_symbols,
    py_extract_self_members,
    py_find_enclosing_class,
    py_find_function_signature,
    py_find_method_signature,
    py_resolve_chain,
    py_resolve_variable_type,
)
