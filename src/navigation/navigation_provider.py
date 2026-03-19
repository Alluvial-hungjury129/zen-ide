"""
Abstract base class for navigation providers.

Each provider implements language-specific logic for:
- Parsing imports
- Finding symbol definitions in file content
- Reporting which languages/extensions it supports
"""

from abc import ABC, abstractmethod
from typing import Dict, Optional


class NavigationProvider(ABC):
    """Base class for code navigation backends."""

    @abstractmethod
    def supports_language(self, file_ext: str) -> bool:
        """Return True if this provider can handle files with the given extension."""

    @abstractmethod
    def parse_imports(self, content: str, file_ext: str) -> Dict[str, str]:
        """Parse import statements and return {alias: module_path} mapping."""

    @abstractmethod
    def find_symbol_in_content(self, content: str, symbol: str, file_ext: str) -> Optional[int]:
        """Find symbol definition in content. Returns 1-based line number or None."""
