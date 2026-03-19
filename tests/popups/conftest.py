"""Shared fixtures and helpers for popup tests."""

import ast
import os

POPUP_SRC = os.path.join(os.path.dirname(__file__), "..", "..", "src", "popups")


def read_popup_source(filename: str) -> str:
    """Read a source file from the popups directory."""
    path = os.path.join(POPUP_SRC, filename)
    with open(path) as f:
        return f.read()


def parse_popup_source(filename: str) -> ast.Module:
    """Parse a popup source file into an AST."""
    return ast.parse(read_popup_source(filename))


def find_class(tree: ast.Module, class_name: str) -> ast.ClassDef | None:
    """Find a class definition by name in an AST."""
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return node
    return None


def find_method(class_node: ast.ClassDef, method_name: str) -> ast.FunctionDef | None:
    """Find a method definition by name in a class AST node."""
    for node in ast.walk(class_node):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == method_name:
            return node
    return None


def class_inherits(tree: ast.Module, class_name: str, base_name: str) -> bool:
    """Check if a class inherits from a given base class."""
    cls = find_class(tree, class_name)
    if cls is None:
        return False
    for base in cls.bases:
        if isinstance(base, ast.Name) and base.id == base_name:
            return True
        if isinstance(base, ast.Attribute) and base.attr == base_name:
            return True
    return False


def method_uses_modulo(method_node: ast.FunctionDef) -> bool:
    """Check if a method uses the modulo (%) operator."""
    for child in ast.walk(method_node):
        if isinstance(child, ast.BinOp) and isinstance(child.op, ast.Mod):
            return True
    return False
