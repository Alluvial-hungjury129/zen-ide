"""
TypeScript/JavaScript navigation provider using Tree-sitter AST queries.

Replaces regex-based symbol finding and import parsing with
structural AST queries for accurate navigation.
"""

from typing import Dict, Optional

from .navigation_provider import NavigationProvider


class TreeSitterTsProvider(NavigationProvider):
    """TypeScript/JavaScript code navigation backed by Tree-sitter."""

    _ts_def_query = None
    _js_def_query = None
    _imp_query = None

    _TS_EXTS = {".ts", ".tsx"}
    _JS_EXTS = {".js", ".jsx"}

    _IDENT_TYPES = {"identifier", "property_identifier", "type_identifier", "shorthand_property_identifier"}

    def supports_language(self, file_ext: str) -> bool:
        return file_ext in self._TS_EXTS or file_ext in self._JS_EXTS

    def _lang_for_ext(self, file_ext: str) -> str:
        if file_ext == ".tsx":
            return "tsx"
        if file_ext in self._TS_EXTS:
            return "typescript"
        return "javascript"

    def _ensure_queries(self):
        if self._ts_def_query is None:
            from .tree_sitter_core import TreeSitterCore
            from .tree_sitter_queries import JS_DEFINITIONS, TS_DEFINITIONS, TS_IMPORTS

            self._ts_def_query = TreeSitterCore.query("typescript", TS_DEFINITIONS)
            self._tsx_def_query = TreeSitterCore.query("tsx", TS_DEFINITIONS)
            self._js_def_query = TreeSitterCore.query("javascript", JS_DEFINITIONS)
            self._imp_query = TreeSitterCore.query("typescript", TS_IMPORTS)
            self._tsx_imp_query = TreeSitterCore.query("tsx", TS_IMPORTS)
            self._js_imp_query = TreeSitterCore.query("javascript", TS_IMPORTS)

    def _get_def_query(self, file_ext: str):
        self._ensure_queries()
        if file_ext == ".tsx":
            return self._tsx_def_query
        if file_ext in self._TS_EXTS:
            return self._ts_def_query
        return self._js_def_query

    def _get_imp_query(self, file_ext: str):
        self._ensure_queries()
        if file_ext == ".tsx":
            return self._tsx_imp_query
        if file_ext in self._TS_EXTS:
            return self._imp_query
        return self._js_imp_query

    @staticmethod
    def _walk(node):
        """Yield all descendant nodes depth-first."""
        yield node
        for child in node.children:
            yield from TreeSitterTsProvider._walk(child)

    def find_symbol_in_content(self, content: str, symbol: str, file_ext: str = ".ts") -> Optional[int]:
        """Find a symbol definition in TS/JS source. Returns 1-based line number or None."""
        from .tree_sitter_core import TreeSitterCore

        lang = self._lang_for_ext(file_ext)
        tree = TreeSitterCore.parse(content.encode("utf-8"), lang)
        if tree is None:
            return None

        def_query = self._get_def_query(file_ext)
        matches = TreeSitterCore.run_query(tree, def_query)
        seen = set()
        for _, captures in matches:
            for name_node in captures.get("name", []):
                if name_node.text.decode("utf-8") == symbol:
                    line = name_node.start_point[0] + 1
                    if line not in seen:
                        return line
                    seen.add(line)
        return None

    def parse_imports(self, content: str, file_ext: str = ".ts") -> Dict[str, str]:
        """Parse TS/JS imports into {name_or_alias: module_source} mapping."""
        from .tree_sitter_core import TreeSitterCore

        lang = self._lang_for_ext(file_ext)
        tree = TreeSitterCore.parse(content.encode("utf-8"), lang)
        if tree is None:
            return {}

        imp_query = self._get_imp_query(file_ext)
        matches = TreeSitterCore.run_query(tree, imp_query)
        result = {}
        for _, captures in matches:
            name_nodes = captures.get("name", [])
            module_nodes = captures.get("module", [])

            if not module_nodes or not name_nodes:
                continue

            # Strip quotes from module source string
            module_text = module_nodes[0].text.decode("utf-8").strip("'\"")
            for name_node in name_nodes:
                name = name_node.text.decode("utf-8")
                result[name] = module_text
        return result

    def find_member_in_content(self, content: str, container: str, member: str, file_ext: str = ".ts") -> Optional[int]:
        """Find a member inside a TS container (enum, class, namespace).

        Returns 1-based line number of the member definition, or ``None``.
        """
        from .tree_sitter_core import TreeSitterCore

        lang = self._lang_for_ext(file_ext)
        tree = TreeSitterCore.parse(content.encode("utf-8"), lang)
        if tree is None:
            return None

        container_node = self._find_named_container(tree.root_node, container)
        if container_node is None:
            return None

        name_field = container_node.child_by_field_name("name")
        for node in self._walk(container_node):
            if node.type in self._IDENT_TYPES and node.text.decode("utf-8") == member:
                # Skip the container's own name node
                if node is name_field:
                    continue
                return node.start_point[0] + 1

        return None

    @staticmethod
    def _find_named_container(root, name):
        """Find a top-level declaration node whose ``name`` field matches."""
        for node in root.children:
            name_node = node.child_by_field_name("name")
            if name_node and name_node.text.decode("utf-8") == name:
                return node
            # Check exported declarations
            if node.type == "export_statement":
                decl = node.child_by_field_name("declaration")
                if decl:
                    name_node = decl.child_by_field_name("name")
                    if name_node and name_node.text.decode("utf-8") == name:
                        return decl
        return None
