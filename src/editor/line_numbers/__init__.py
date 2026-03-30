"""
Gutter renderers for breakpoints, line numbers, git diff markers, and code folding.

Four separate GtkSource.GutterRenderers inserted left-to-right:

  1. BreakpointGutterRenderer — red dots for breakpoints (click to toggle)
  2. LineNumberRenderer       — centered line numbers
  3. GitDiffGutterRenderer    — colored bars for git changes
  4. FoldChevronRenderer      — fold chevrons (click to toggle fold)
"""

from .breakpoint_renderer import BreakpointGutterRenderer
from .constants import (
    _BP_DIAMETER,
    _BP_LEFT_PAD,
    _CHEVRON_COLLAPSED,
    _CHEVRON_EXPANDED,
    _GIT_MARKER_WIDTH,
    _MIN_DIGITS,
    _NUM_PAD,
    _ZONE_WIDTH,
)
from .fold_chevron_renderer import FoldChevronRenderer
from .git_diff_renderer import GitDiffGutterRenderer
from .line_number_renderer import LineNumberRenderer

__all__ = [
    "BreakpointGutterRenderer",
    "LineNumberRenderer",
    "GitDiffGutterRenderer",
    "FoldChevronRenderer",
    "_BP_DIAMETER",
    "_BP_LEFT_PAD",
    "_CHEVRON_COLLAPSED",
    "_CHEVRON_EXPANDED",
    "_GIT_MARKER_WIDTH",
    "_MIN_DIGITS",
    "_NUM_PAD",
    "_ZONE_WIDTH",
]
