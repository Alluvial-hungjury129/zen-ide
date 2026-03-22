"""
Navigation provider system for Zen IDE.

Supports pluggable backends: Tree-sitter (Python, TS/JS) and Terraform.
Language-specific code navigation: Python, TypeScript/JavaScript, Terraform.
"""

from navigation.navigation_provider import NavigationProvider
from navigation.tree_sitter_tf_provider import TreeSitterTfProvider

__all__ = ["NavigationProvider", "TreeSitterTfProvider"]
