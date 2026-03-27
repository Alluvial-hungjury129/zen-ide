"""Unicode terminal display-width utilities.

Calculates how many monospace columns a string occupies, handling
wide/fullwidth East Asian characters, zero-width marks, and emoji.
"""

import unicodedata

# ── Terminal display width ─────────────────────────────────────


# Per-codepoint width cache: avoids repeated unicodedata lookups for the same
# characters.  Tables and code blocks re-render the same box-drawing and
# formatting characters thousands of times; this cache turns O(n) unicode
# lookups into O(1) dict hits after the first encounter.
_char_width_cache: dict[int, int] = {}


def _char_display_width(cp: int, c: str) -> int:
    """Return the display width of a single codepoint, with caching."""
    cached = _char_width_cache.get(cp)
    if cached is not None:
        return cached
    # Zero-width categories and variation selectors
    if unicodedata.category(c) in ("Mn", "Me", "Cf") or 0xFE00 <= cp <= 0xFE0F or 0x1F3FB <= cp <= 0x1F3FF:
        _char_width_cache[cp] = 0
        return 0
    eaw = unicodedata.east_asian_width(c)
    w = 2 if eaw in ("W", "F") else 1
    _char_width_cache[cp] = w
    return w


def display_width(s: str) -> int:
    """Calculate terminal display width of a string, accounting for wide/emoji chars.

    Returns the number of monospace cells the string occupies.
    Wide (W) and fullwidth (F) East Asian characters count as 2;
    zero-width marks, format chars, and variation selectors are skipped.

    Fast-path: printable ASCII (0x20–0x7E) always has width 1, avoiding
    expensive ``unicodedata`` lookups for the vast majority of text.

    Uses a per-codepoint cache to avoid repeated unicodedata lookups for
    box-drawing characters, table borders, and other repeated glyphs
    commonly found in AI chat output.
    """
    w = 0
    cache = _char_width_cache
    for c in s:
        cp = ord(c)
        # Fast-path: printable ASCII is always width 1
        if 0x20 <= cp <= 0x7E:
            w += 1
            continue
        cached = cache.get(cp)
        if cached is not None:
            w += cached
            continue
        w += _char_display_width(cp, c)
    return w
