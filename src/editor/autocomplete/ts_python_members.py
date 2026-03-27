"""
Python class member and symbol extraction for Zen IDE tree-sitter completions.

Provides class member extraction, self-member resolution, enclosing class detection,
variable type resolution, function/method signature lookup, file symbol extraction,
and chain resolution.
"""

from editor.autocomplete.autocomplete import CompletionItem, CompletionKind
from editor.autocomplete.tree_sitter_provider import _node_text, _top_level_children
from editor.autocomplete.ts_python import py_extract_docstring, py_extract_init_signature, py_extract_signature

# ---------------------------------------------------------------------------
# Python — class members
# ---------------------------------------------------------------------------


def py_extract_class_members(source: bytes, tree, class_name: str, *, include_private: bool = False) -> list[CompletionItem]:
    """Extract public methods and class-level attributes from a named class."""
    class_node = _find_class_node(source, tree.root_node, class_name)
    if class_node is None:
        return []
    return _extract_members_from_class(source, class_node, include_private=include_private)


def py_extract_self_members(source: bytes, tree, class_name: str) -> list[CompletionItem]:
    """Extract all members accessible via ``self.`` (methods + attributes)."""
    class_node = _find_class_node(source, tree.root_node, class_name)
    if class_node is None:
        return []

    members: dict[str, CompletionItem] = {}
    body = class_node.child_by_field_name("body")
    if not body:
        return []

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
            if not fname:
                continue
            name = _node_text(source, fname)
            # Skip dunder methods
            if name.startswith("__") and name.endswith("__"):
                continue
            sig = py_extract_signature(source, func)
            doc = py_extract_docstring(source, func)
            members[name] = CompletionItem(name, CompletionKind.FUNCTION, sig, doc)

            # Scan body for self.attr = ... assignments
            _collect_self_attrs(source, func, members)
            continue

        # Class-level attributes
        if child.type == "expression_statement" and child.child_count > 0:
            expr = child.children[0]
            if expr.type == "assignment":
                left = expr.child_by_field_name("left")
                if left and left.type == "identifier":
                    name = _node_text(source, left)
                    if name not in members:
                        members[name] = CompletionItem(name, CompletionKind.PROPERTY)

        # Nested class
        nested_cls = child if child.type == "class_definition" else None
        if child.type == "decorated_definition":
            for sub in child.children:
                if sub.type == "class_definition":
                    nested_cls = sub
                    break
        if nested_cls:
            n_node = nested_cls.child_by_field_name("name")
            if n_node:
                name = _node_text(source, n_node)
                members[name] = CompletionItem(name, CompletionKind.CLASS)

    return sorted(members.values(), key=lambda x: x.name)


def _collect_self_attrs(source: bytes, func_node, members: dict):
    """Walk a function body for ``self.attr = ...`` assignments."""
    body = func_node.child_by_field_name("body")
    if not body:
        return
    _walk_for_self_attrs(source, body, members)


def _walk_for_self_attrs(source: bytes, node, members: dict):
    """Recursively find ``self.X = ...`` patterns."""
    for child in node.children:
        if child.type == "expression_statement" and child.child_count > 0:
            expr = child.children[0]
            if expr.type == "assignment":
                left = expr.child_by_field_name("left")
                if left and left.type == "attribute":
                    obj = left.child_by_field_name("object")
                    attr = left.child_by_field_name("attribute")
                    if obj and attr and _node_text(source, obj) in ("self", "cls"):
                        name = _node_text(source, attr)
                        if name not in members:
                            members[name] = CompletionItem(name, CompletionKind.PROPERTY)
        # Recurse into blocks (if, for, with, try)
        if child.type in (
            "block",
            "if_statement",
            "for_statement",
            "while_statement",
            "with_statement",
            "try_statement",
            "except_clause",
            "else_clause",
            "elif_clause",
            "finally_clause",
        ):
            _walk_for_self_attrs(source, child, members)


def _extract_members_from_class(source: bytes, class_node, *, include_private: bool = False) -> list[CompletionItem]:
    """Extract public (or all) methods and attributes from a class_definition node."""
    members: dict[str, CompletionItem] = {}
    body = class_node.child_by_field_name("body")
    if not body:
        return []

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
            if not fname:
                continue
            name = _node_text(source, fname)
            if not include_private and name.startswith("_"):
                continue
            sig = py_extract_signature(source, func)
            doc = py_extract_docstring(source, func)
            members[name] = CompletionItem(name, CompletionKind.FUNCTION, sig, doc)
            continue

        # Nested class
        nested_cls = child if child.type == "class_definition" else None
        if child.type == "decorated_definition":
            for sub in child.children:
                if sub.type == "class_definition":
                    nested_cls = sub
                    break
        if nested_cls:
            n_node = nested_cls.child_by_field_name("name")
            if n_node:
                name = _node_text(source, n_node)
                if not include_private and name.startswith("_"):
                    continue
                members[name] = CompletionItem(name, CompletionKind.CLASS)
            continue

        # Class attributes
        if child.type == "expression_statement" and child.child_count > 0:
            expr = child.children[0]
            if expr.type == "assignment":
                left = expr.child_by_field_name("left")
                if left and left.type == "identifier":
                    name = _node_text(source, left)
                    if not include_private and name.startswith("_"):
                        continue
                    members[name] = CompletionItem(name, CompletionKind.PROPERTY)

    return sorted(members.values(), key=lambda x: x.name)


# ---------------------------------------------------------------------------
# Python — enclosing class, variable type, function/method signatures
# ---------------------------------------------------------------------------


def py_find_enclosing_class(source: bytes, tree, byte_offset: int) -> str | None:
    """Return the name of the class containing *byte_offset*, or None."""
    node = tree.root_node
    # Clamp so cursor at end-of-file still matches the last enclosing node
    byte_offset = min(byte_offset, max(0, node.end_byte - 1))
    result = None

    while True:
        found_child = False
        for child in node.children:
            inner = child
            # Unwrap decorated_definition
            if child.type == "decorated_definition":
                for sub in child.children:
                    if sub.type in ("class_definition", "function_definition"):
                        inner = sub
                        break
            if inner.start_byte <= byte_offset <= inner.end_byte:
                if inner.type == "class_definition":
                    name_node = inner.child_by_field_name("name")
                    if name_node:
                        result = _node_text(source, name_node)
                node = inner
                found_child = True
                break
        if not found_child:
            break

    return result


def py_resolve_variable_type(source: bytes, tree, var_name: str) -> str | None:
    """Resolve a variable's class from ``var: Type = ...`` or ``var = ClassName(...)``."""
    root = tree.root_node
    for child in root.children:
        if child.type != "expression_statement" or child.child_count == 0:
            continue
        expr = child.children[0]
        if expr.type != "assignment":
            continue
        left = expr.child_by_field_name("left")
        if not left or left.type != "identifier" or _node_text(source, left) != var_name:
            continue
        # Prefer explicit type annotation over inferred type from RHS
        ann = expr.child_by_field_name("type")
        if ann:
            return _node_text(source, ann).split(".")[-1]
        right = expr.child_by_field_name("right")
        if right and right.type == "call":
            func = right.child_by_field_name("function")
            if func:
                text = _node_text(source, func)
                return text.split(".")[-1]
    return None


def py_find_function_signature(source: bytes, tree, func_name: str) -> str | None:
    """Find a top-level function's signature by name."""
    for node in _top_level_children(tree.root_node, "function_definition"):
        fname = node.child_by_field_name("name")
        if fname and _node_text(source, fname) == func_name:
            return py_extract_signature(source, node)
    # Check for class constructor
    for node in _top_level_children(tree.root_node, "class_definition"):
        cname = node.child_by_field_name("name")
        if cname and _node_text(source, cname) == func_name:
            return py_extract_init_signature(source, node)
    return None


def py_find_method_signature(source: bytes, tree_or_root, class_name: str, method_name: str) -> str | None:
    """Find a method's signature within a class."""
    root = tree_or_root.root_node if hasattr(tree_or_root, "root_node") else tree_or_root
    class_node = _find_class_node(source, root, class_name)
    if class_node is None:
        return None
    body = class_node.child_by_field_name("body")
    if not body:
        return None
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
            if fname and _node_text(source, fname) == method_name:
                return py_extract_signature(source, func)
    return None


def py_extract_file_symbols(source: bytes, tree) -> list[CompletionItem]:
    """Extract all exportable symbols from a Python file (for import completions).

    Handles ``__init__.py`` re-exports by tracking ``from .sub import Name``.
    """
    symbols: dict[str, CompletionItem] = {}
    root = tree.root_node
    reexports: dict[str, str] = {}  # name -> relative_module

    for child in root.children:
        _actual = child
        if child.type == "decorated_definition":
            for sub in child.children:
                if sub.type in ("function_definition", "class_definition"):
                    _actual = sub
                    break

        if _actual.type == "function_definition":
            fname = _actual.child_by_field_name("name")
            if fname:
                name = _node_text(source, fname)
                sig = py_extract_signature(source, _actual)
                doc = py_extract_docstring(source, _actual)
                symbols[name] = CompletionItem(name, CompletionKind.FUNCTION, sig, doc)

        elif _actual.type == "class_definition":
            cname = _actual.child_by_field_name("name")
            if cname:
                name = _node_text(source, cname)
                doc = py_extract_docstring(source, _actual)
                init_sig = py_extract_init_signature(source, _actual)
                symbols[name] = CompletionItem(name, CompletionKind.CLASS, init_sig, doc)

        elif child.type == "expression_statement" and child.child_count > 0:
            expr = child.children[0]
            if expr.type == "assignment":
                left = expr.child_by_field_name("left")
                if left and left.type == "identifier":
                    name = _node_text(source, left)
                    if not name.startswith("_"):
                        symbols[name] = CompletionItem(name, CompletionKind.PROPERTY)

        elif child.type == "import_from_statement":
            # Track relative re-exports: ``from .sub import Name``
            module_node = child.child_by_field_name("module_name")
            if module_node:
                mod_text = _node_text(source, module_node)
                if mod_text.startswith(".") and not mod_text.startswith(".."):
                    rel_module = mod_text.lstrip(".")
                    for imp_child in child.children:
                        if imp_child.type == "dotted_name" and imp_child != module_node:
                            name = _node_text(source, imp_child)
                            if name not in symbols:
                                reexports[name] = rel_module
                        elif imp_child.type == "aliased_import":
                            alias = imp_child.child_by_field_name("alias")
                            orig = imp_child.child_by_field_name("name")
                            n = alias or orig
                            if n:
                                name = _node_text(source, n)
                                if name not in symbols:
                                    reexports[name] = rel_module

    return symbols, reexports


# ---------------------------------------------------------------------------
# Python — chain resolution helpers
# ---------------------------------------------------------------------------


def py_resolve_chain(source: bytes, tree, parts: list[str]) -> list[CompletionItem]:
    """Walk a dotted chain (e.g. [ClassName, SubClass]) and return members of the final class."""
    current_node = tree.root_node if hasattr(tree, "root_node") else tree
    current_source = source

    for i, part in enumerate(parts):
        class_node = _find_class_node(current_source, current_node, part)
        if class_node is None:
            return []
        if i == len(parts) - 1:
            return _extract_members_from_class(current_source, class_node)
        body = class_node.child_by_field_name("body")
        if not body:
            return []
        current_node = body

    return []


def _find_class_node(source: bytes, root, class_name: str):
    """Find a class_definition node by name under *root*."""
    for child in root.children:
        actual = child
        if child.type == "decorated_definition":
            for sub in child.children:
                if sub.type == "class_definition":
                    actual = sub
                    break
        if actual.type == "class_definition":
            name_node = actual.child_by_field_name("name")
            if name_node and _node_text(source, name_node) == class_name:
                return actual
    return None
