"""
JavaScript/TypeScript-specific tree-sitter completion extraction for Zen IDE.

Provides AST-based extraction of JS/TS definitions and imports.
"""

from editor.autocomplete.autocomplete import CompletionItem, CompletionKind
from editor.autocomplete.tree_sitter_provider import _node_text

# ---------------------------------------------------------------------------
# JavaScript / TypeScript — definitions & imports
# ---------------------------------------------------------------------------


def js_extract_definitions(source: bytes, tree, *, is_typescript: bool = False) -> list[CompletionItem]:
    """Extract top-level symbol definitions from JS/TS AST."""
    items: list[CompletionItem] = []
    root = tree.root_node

    for child in root.children:
        _js_extract_node(source, child, items, is_typescript=is_typescript)
    return items


def _js_extract_node(source: bytes, node, items: list, *, is_typescript: bool = False):
    """Process a single top-level node for JS/TS definitions."""
    # Unwrap export
    if node.type == "export_statement":
        decl = node.child_by_field_name("declaration")
        if decl:
            _js_extract_node(source, decl, items, is_typescript=is_typescript)
        return

    if node.type == "function_declaration":
        name_node = node.child_by_field_name("name")
        if name_node:
            name = _node_text(source, name_node)
            doc = _js_extract_jsdoc(source, node)
            items.append(CompletionItem(name, CompletionKind.FUNCTION, docstring=doc))

    elif node.type == "class_declaration":
        name_node = node.child_by_field_name("name")
        if name_node:
            items.append(CompletionItem(_node_text(source, name_node), CompletionKind.CLASS))

    elif node.type in ("lexical_declaration", "variable_declaration"):
        for declarator in node.children:
            if declarator.type == "variable_declarator":
                name_node = declarator.child_by_field_name("name")
                if name_node and name_node.type == "identifier":
                    items.append(CompletionItem(_node_text(source, name_node), CompletionKind.VARIABLE))

    elif is_typescript and node.type == "interface_declaration":
        name_node = node.child_by_field_name("name")
        if name_node:
            items.append(CompletionItem(_node_text(source, name_node), CompletionKind.PROPERTY))

    elif is_typescript and node.type == "type_alias_declaration":
        name_node = node.child_by_field_name("name")
        if name_node:
            items.append(CompletionItem(_node_text(source, name_node), CompletionKind.PROPERTY))

    elif is_typescript and node.type == "enum_declaration":
        name_node = node.child_by_field_name("name")
        if name_node:
            items.append(CompletionItem(_node_text(source, name_node), CompletionKind.PROPERTY))


def js_extract_imports(source: bytes, tree) -> list[CompletionItem]:
    """Extract imported symbol names from JS/TS AST."""
    items: list[CompletionItem] = []
    root = tree.root_node

    for child in root.children:
        if child.type != "import_statement":
            continue
        for clause in child.children:
            if clause.type == "import_clause":
                _js_import_clause(source, clause, items)
    return items


def _js_import_clause(source: bytes, clause, items: list):
    """Process an import clause for named/default/namespace imports."""
    for child in clause.children:
        if child.type == "identifier":
            # Default import: ``import Foo from '...'``
            items.append(CompletionItem(_node_text(source, child), CompletionKind.VARIABLE))

        elif child.type == "named_imports":
            for spec in child.children:
                if spec.type == "import_specifier":
                    alias = spec.child_by_field_name("alias")
                    name = spec.child_by_field_name("name")
                    node = alias or name
                    if node:
                        items.append(CompletionItem(_node_text(source, node), CompletionKind.VARIABLE))

        elif child.type == "namespace_import":
            for sub in child.children:
                if sub.type == "identifier":
                    items.append(CompletionItem(_node_text(source, sub), CompletionKind.VARIABLE))


def _js_extract_jsdoc(source: bytes, node) -> str:
    """Extract first description line from a JSDoc comment preceding a node."""
    prev = node.prev_sibling
    if not prev or prev.type != "comment":
        # Try parent's prev sibling (export_statement wraps)
        parent = node.parent
        if parent and parent.type == "export_statement":
            prev = parent.prev_sibling
        if not prev or prev.type != "comment":
            return ""
    text = _node_text(source, prev)
    if not text.startswith("/**"):
        return ""
    text = text[3:]
    if text.endswith("*/"):
        text = text[:-2]
    for line in text.split("\n"):
        line = line.strip().lstrip("* ").strip()
        if line and not line.startswith("@"):
            return line[:120]
    return ""
