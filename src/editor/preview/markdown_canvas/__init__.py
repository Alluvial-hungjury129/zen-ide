"""markdown_canvas package -- MarkdownCanvas split into mixins.

Re-exports the public API so that existing imports continue to work:
    from editor.preview.markdown_canvas import MarkdownCanvas
    from editor.preview.markdown_canvas import _estimate_block_lines
"""

from .core import MarkdownCanvas
from .scroll_sync import _estimate_block_lines

__all__ = ["MarkdownCanvas", "_estimate_block_lines"]
