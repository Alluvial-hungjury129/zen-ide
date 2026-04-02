"""Test Discovery — extract test function/class names from source files.

Uses Tree-sitter for accurate AST-based extraction. Falls back to
simple regex scanning when Tree-sitter is unavailable.
"""

import os
import re
from dataclasses import dataclass


@dataclass
class DiscoveredTest:
    """A discovered test function or method."""

    name: str  # e.g. "test_no_params"
    class_name: str = ""  # e.g. "TestFeesFromQuotedUserRiskBand" (empty for module-level)
    line: int = 0  # 1-based line number

    @property
    def node_id(self) -> str:
        """Pytest node ID suffix: Class::method or just function."""
        if self.class_name:
            return f"{self.class_name}::{self.name}"
        return self.name

    @property
    def display_name(self) -> str:
        if self.class_name:
            return f"{self.class_name}::{self.name}"
        return self.name


def discover_tests(file_path: str) -> list[DiscoveredTest]:
    """Discover test functions/methods in a Python test file."""
    ext = os.path.splitext(file_path)[1].lower()
    if ext != ".py":
        return []

    try:
        with open(file_path, encoding="utf-8") as f:
            content = f.read()
    except OSError:
        return []

    tests = _discover_with_treesitter(content)
    if tests is None:
        tests = _discover_with_regex(content)
    return tests


def _discover_with_treesitter(content: str) -> list[DiscoveredTest] | None:
    """Use Tree-sitter to find test functions and methods."""
    try:
        from navigation.tree_sitter_core import TreeSitterCore

        if not TreeSitterCore.available():
            return None
    except ImportError:
        return None

    source_bytes = content.encode("utf-8")
    tree = TreeSitterCore.parse(source_bytes, "python")
    if tree is None:
        return None

    def _text(node) -> str:
        return source_bytes[node.start_byte : node.end_byte].decode("utf-8")

    def _is_test(name: str) -> bool:
        return name.startswith("test_") or name.startswith("test")

    def _unwrap(node):
        """Unwrap decorated_definition to its inner def/class."""
        if node.type == "decorated_definition":
            for child in node.children:
                if child.type in ("function_definition", "class_definition"):
                    return child
        return node

    def _scan_class_body(body, class_name: str) -> list[DiscoveredTest]:
        items = []
        for child in body.children:
            func = _unwrap(child)
            if func.type != "function_definition":
                continue
            name_node = func.child_by_field_name("name")
            if not name_node:
                continue
            name = _text(name_node)
            if _is_test(name):
                items.append(DiscoveredTest(name=name, class_name=class_name, line=name_node.start_point[0] + 1))
        return items

    tests = []
    for node in tree.root_node.children:
        actual = _unwrap(node)

        if actual.type == "function_definition":
            name_node = actual.child_by_field_name("name")
            if name_node:
                name = _text(name_node)
                if _is_test(name):
                    tests.append(DiscoveredTest(name=name, line=name_node.start_point[0] + 1))

        elif actual.type == "class_definition":
            cn = actual.child_by_field_name("name")
            if not cn:
                continue
            class_name = _text(cn)
            if not (class_name.startswith("Test") or class_name.endswith("Test")):
                continue
            body = actual.child_by_field_name("body")
            if body:
                tests.extend(_scan_class_body(body, class_name))

    return tests


_RE_TEST_FUNC = re.compile(r"^(?:class\s+(Test\w*)|(?:\s+)?def\s+(test\w*))", re.MULTILINE)


def _discover_with_regex(content: str) -> list[DiscoveredTest]:
    """Fallback regex-based test discovery."""
    tests = []
    current_class = ""
    for i, line in enumerate(content.splitlines(), 1):
        m = _RE_TEST_FUNC.match(line)
        if not m:
            continue
        if m.group(1):
            current_class = m.group(1)
        elif m.group(2):
            name = m.group(2)
            is_method = line.startswith((" ", "\t"))
            tests.append(
                DiscoveredTest(
                    name=name,
                    class_name=current_class if is_method else "",
                    line=i,
                )
            )
    return tests
