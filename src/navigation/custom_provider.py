"""
Custom (regex-based) navigation provider.

Extracted from the original CodeNavigation implementation.
Supports Python files using regex pattern matching.
"""

import re
from typing import Dict, Optional

from navigation.navigation_provider import NavigationProvider


class CustomProvider(NavigationProvider):
    """Regex-based navigation provider. Supports Python."""

    SUPPORTED_EXTENSIONS = {".py", ".pyw", ".pyi"}

    def supports_language(self, file_ext: str) -> bool:
        return file_ext.lower() in self.SUPPORTED_EXTENSIONS

    def parse_imports(self, content: str, file_ext: str) -> Dict[str, str]:
        if file_ext.lower() not in self.SUPPORTED_EXTENSIONS:
            return {}
        return self._parse_python_imports(content)

    def find_symbol_in_content(self, content: str, symbol: str, file_ext: str) -> Optional[int]:
        if file_ext.lower() not in self.SUPPORTED_EXTENSIONS:
            return None
        return self._find_symbol_python(content, symbol)

    def _parse_python_imports(self, content: str) -> Dict[str, str]:
        """Parse Python import statements and return mapping of names to module paths."""
        imports = {}

        for match in re.finditer(r"^import\s+(\w+(?:\.\w+)*)(?:\s+as\s+(\w+))?", content, re.MULTILINE):
            module = match.group(1)
            alias = match.group(2) or module.split(".")[-1]
            imports[alias] = module

        for match in re.finditer(
            r"^from\s+(\.+\w*(?:\.\w+)*|\w+(?:\.\w+)*)\s+import\s+(.+?)$",
            content,
            re.MULTILINE,
        ):
            module = match.group(1)
            import_part = match.group(2).strip()

            if import_part.startswith("("):
                paren_match = re.search(r"\(([^)]+)\)", content[match.start() :], re.DOTALL)
                if paren_match:
                    import_part = paren_match.group(1)

            for item in import_part.split(","):
                item = item.strip()
                if not item or item.startswith("#"):
                    continue

                as_match = re.match(r"(\w+)\s+as\s+(\w+)", item)
                if as_match:
                    name = as_match.group(1)
                    alias = as_match.group(2)
                else:
                    name_match = re.match(r"(\w+)", item)
                    if name_match:
                        name = name_match.group(1)
                        alias = name
                    else:
                        continue
                imports[alias] = f"{module}.{name}"

        return imports

    def _find_symbol_python(self, content: str, symbol: str) -> Optional[int]:
        """Find symbol definition in Python content. Returns 1-based line number."""
        patterns = [
            rf"^class\s+{re.escape(symbol)}\s*[:\(]",
            rf"^\s*def\s+{re.escape(symbol)}\s*\(",
            rf"^{re.escape(symbol)}\s*=",
        ]

        for pattern in patterns:
            match = re.search(pattern, content, re.MULTILINE)
            if match:
                matched_text = match.group()
                symbol_offset = matched_text.find(symbol)
                if symbol_offset >= 0:
                    pos = match.start() + symbol_offset
                else:
                    pos = match.start()
                return content[:pos].count("\n") + 1

        return None
