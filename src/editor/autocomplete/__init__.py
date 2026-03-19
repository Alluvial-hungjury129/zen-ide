"""Autocomplete package — re-exports the public API."""

from editor.autocomplete.autocomplete import Autocomplete, CompletionItem, CompletionKind

__all__ = ["Autocomplete", "CompletionItem", "CompletionKind"]
