"""
sketch_pad.canvas — SketchCanvas split into focused modules.

Re-exports SketchCanvas so external code can use either:
    from sketch_pad.canvas import SketchCanvas
    from sketch_pad.canvas.core import SketchCanvas
"""

from .core import SketchCanvas

__all__ = ["SketchCanvas"]
