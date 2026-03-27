"""Shared fixtures and helpers for autocomplete tests."""

from editor.autocomplete.tree_sitter_provider import _parse


def _py(text):
    """Parse Python text and return (source_bytes, tree)."""
    source, tree = _parse(text, "python")
    assert tree is not None, f"Failed to parse: {text[:60]}"
    return source, tree
