"""Completion ranking, filtering, and document word extraction mixin.

Handles completion provider dispatch, document word extraction,
import noise filtering, parameter extraction, and live buffer filtering.
"""

from __future__ import annotations

import re
from pathlib import Path

from editor.autocomplete.autocomplete import CompletionItem, CompletionKind


class CompletionRankingMixin:
    """Mixin providing completion ranking/sorting logic for the Autocomplete class.

    Expects the host class to define:
    - self._view, self._buffer, self._tab
    - self._python_provider, self._js_provider, self._terraform_provider
    - self._completions, self._filtered, self._selected_idx
    - self._word_start_offset, self._inserting
    - self._dismiss_guard, self._changed_handler, self._auto_trigger_timer
    - self._last_buffer_len
    - self._sig_box, self._sig_sep
    - self.hide(), self.is_visible()
    - self._update_filter(partial)
    """

    def _on_buffer_changed(self, buffer):
        """Handle buffer changes for live filtering."""
        self._last_buffer_len = buffer.get_char_count()
        if self._inserting or self._dismiss_guard:
            return

        # Re-extract the current prefix
        cursor_iter = self._buffer.get_iter_at_mark(self._buffer.get_insert())
        cursor_offset = cursor_iter.get_offset()

        # If cursor moved before word start, close popup
        if cursor_offset < self._word_start_offset:
            self.hide()
            return

        word_start_iter = self._buffer.get_iter_at_offset(self._word_start_offset)
        partial = self._buffer.get_text(word_start_iter, cursor_iter, False)

        # If partial contains non-word characters, close popup
        if partial and not re.match(r"^[a-zA-Z_]\w*$", partial):
            self.hide()
            return

        self._update_filter(partial.lower())

        if not self._filtered:
            self.hide()
            return

        # Dismiss if the only remaining suggestion exactly matches what's typed
        if len(self._filtered) == 1 and self._filtered[0].name == partial:
            self.hide()

    def _get_completions(self, file_path):
        """Get completion suggestions based on file type."""
        completions = []
        ext = Path(file_path).suffix.lower() if file_path else ""
        buffer_text = self._get_buffer_text()

        if ext in (".py", ".pyw", ".pyi"):
            completions.extend(self._python_provider.get_completions(buffer_text, file_path))
        elif ext in (".js", ".jsx", ".ts", ".tsx", ".mjs"):
            completions.extend(self._js_provider.get_completions(buffer_text))
        elif ext in (".tf", ".tfvars"):
            completions.extend(self._terraform_provider.get_completions(buffer_text, file_path))

        # Include document words for languages without full buffer symbol extraction
        if ext not in (".tf", ".tfvars"):
            completions.extend(self._get_document_words())

        # Deduplicate by name, keeping first occurrence (most specific kind)
        seen = {}
        for item in completions:
            if item.name not in seen:
                seen[item.name] = item
        return sorted(seen.values(), key=lambda x: x.name.lower())

    def _get_document_words(self):
        """Extract unique words from the document."""
        words = set()
        text = self._get_buffer_text()
        cursor_offset = self._buffer.get_iter_at_mark(self._buffer.get_insert()).get_offset()
        import_noise = self._get_import_noise(text)

        for m in re.finditer(r"\b([a-zA-Z_]\w{2,})\b", text):
            if m.start() <= cursor_offset <= m.end():
                continue
            word = m.group(1)
            if word not in import_noise:
                words.add(word)

        return [CompletionItem(w, CompletionKind.VARIABLE) for w in words]

    def _get_import_noise(self, text):
        """Get module path tokens from import lines that shouldn't be suggested."""
        noise = set()
        for line in text.splitlines():
            stripped = line.strip()
            # "from foo.bar import X" -> only intermediate path tokens (foo) are noise
            # Last segment (bar) is kept — it often matches variable names in code
            m = re.match(r"^from\s+([\w.]+)\s+import\b", stripped)
            if m:
                parts = m.group(1).split(".")
                for part in parts[:-1]:
                    noise.add(part)
                # "import", "from" keywords themselves
                noise.add("from")
                noise.add("import")
                continue
            # "import foo.bar" or "import foo as f" -> only keywords are noise
            # (the module name IS usable for plain import)
            m = re.match(r"^import\s+", stripped)
            if m:
                noise.add("import")
        return noise

    def _get_buffer_text(self):
        """Get full text from the buffer."""
        start = self._buffer.get_start_iter()
        end = self._buffer.get_end_iter()
        return self._buffer.get_text(start, end, False)

    @staticmethod
    def _extract_params(signature):
        """Extract clean parameter names from a function signature.

        Strips self/cls and type annotations, preserving default values.
        e.g. 'my_func(self, a: int, b: str = "x") → bool' → 'a, b="x"'
             'func()' → ''
        """
        if not signature:
            return ""
        m = re.search(r"\(([^)]*)\)", signature)
        if not m:
            return ""
        params_str = m.group(1).strip()
        if not params_str:
            return ""
        params = [p.strip() for p in params_str.split(",")]
        # Filter out self/cls, strip type annotations but keep defaults
        cleaned = []
        for p in params:
            name = p.split(":")[0].split("=")[0].strip()
            if name in ("self", "cls"):
                continue
            if not name:
                continue
            # Extract default value if present
            if "=" in p:
                eq_idx = p.index("=")
                default = p[eq_idx + 1 :].strip()
                cleaned.append(f"{name}={default}")
            else:
                cleaned.append(name)
        return ", ".join(cleaned)
