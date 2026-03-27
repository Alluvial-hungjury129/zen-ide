"""Colour conversion and manipulation utilities.

Provides hex-to-RGB/RGBA conversions, CSS colour strings, blending,
WCAG luminance / contrast helpers, and Gdk.RGBA interop.
"""

# ── Colour helpers ──────────────────────────────────────────────


def hex_to_rgb(hex_color: str) -> tuple:
    """Convert hex color to RGB tuple with ints in 0-255 range.

    Returns (38, 38, 38) for malformed input.
    """
    if not hex_color:
        return (38, 38, 38)

    h = hex_color.lstrip("#")
    if len(h) != 6:
        return (38, 38, 38)

    try:
        return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return (38, 38, 38)


def hex_to_rgb_float(hex_color: str) -> tuple:
    """Convert hex color to (r, g, b) floats in 0-1 range.

    Returns (0.15, 0.15, 0.15) for malformed input.
    """
    if not hex_color:
        return (0.15, 0.15, 0.15)

    h = hex_color.lstrip("#")
    if len(h) == 6:
        try:
            return (
                int(h[0:2], 16) / 255.0,
                int(h[2:4], 16) / 255.0,
                int(h[4:6], 16) / 255.0,
            )
        except ValueError:
            return (0.15, 0.15, 0.15)
    return (0.15, 0.15, 0.15)


def hex_to_rgba(hex_color: str, alpha: float = 1.0) -> tuple:
    """Convert hex color to RGBA tuple with floats in 0-1 range.

    Returns (0.15, 0.15, 0.15, alpha) for malformed input.
    """
    if not hex_color:
        return (0.15, 0.15, 0.15, alpha)

    h = hex_color.lstrip("#")
    if len(h) != 6:
        return (0.15, 0.15, 0.15, alpha)

    try:
        r = int(h[0:2], 16) / 255.0
        g = int(h[2:4], 16) / 255.0
        b = int(h[4:6], 16) / 255.0
        return (r, g, b, alpha)
    except ValueError:
        return (0.15, 0.15, 0.15, alpha)


def hex_to_gdk_rgba(hex_color: str, alpha: float = 1.0):
    """Convert hex color string to a ``Gdk.RGBA`` with optional *alpha*.

    Falls back to mid-gray on malformed input.
    """
    from gi.repository import Gdk

    r, g, b, a = hex_to_rgba(hex_color, alpha)
    c = Gdk.RGBA()
    c.red, c.green, c.blue, c.alpha = r, g, b, a
    return c


def tuple_to_gdk_rgba(color_tuple, alpha: float | None = None):
    """Convert an ``(r, g, b[, a])`` float tuple to a ``Gdk.RGBA``.

    If *alpha* is given it overrides any alpha in the tuple.
    """
    from gi.repository import Gdk

    c = Gdk.RGBA()
    c.red, c.green, c.blue = color_tuple[0], color_tuple[1], color_tuple[2]
    if alpha is not None:
        c.alpha = alpha
    elif len(color_tuple) >= 4:
        c.alpha = color_tuple[3]
    else:
        c.alpha = 1.0
    return c


def hex_to_rgba_css(hex_color: str, alpha: float = 1.0) -> str:
    """Convert hex color to CSS ``rgba(r, g, b, a)`` string.

    Returns a fallback gray color for malformed input.
    """
    if not hex_color:
        return f"rgba(38, 38, 38, {alpha})"  # fallback gray

    h = hex_color.lstrip("#")
    if len(h) != 6:
        return f"rgba(38, 38, 38, {alpha})"  # fallback gray

    try:
        r = int(h[0:2], 16)
        g = int(h[2:4], 16)
        b = int(h[4:6], 16)
        return f"rgba({r}, {g}, {b}, {alpha})"
    except ValueError:
        return f"rgba(38, 38, 38, {alpha})"  # fallback gray


def blend_hex_colors(start_hex: str, end_hex: str, amount: float) -> str:
    """Blend *start_hex* toward *end_hex* by *amount* in the 0-1 range.

    Returns fallback color for malformed input.
    """
    if not start_hex or not end_hex:
        return "#262626"  # fallback gray

    amount = max(0.0, min(1.0, amount))
    start = hex_to_rgb(start_hex)
    end = hex_to_rgb(end_hex)
    blended = tuple(round(s + (e - s) * amount) for s, e in zip(start, end, strict=False))
    return "#{:02x}{:02x}{:02x}".format(*blended)


def relative_luminance(hex_color: str) -> float:
    """Return the WCAG relative luminance for *hex_color*."""

    def _linearize(channel: int) -> float:
        value = channel / 255.0
        if value <= 0.04045:
            return value / 12.92
        return ((value + 0.055) / 1.055) ** 2.4

    r, g, b = hex_to_rgb(hex_color)
    return (0.2126 * _linearize(r)) + (0.7152 * _linearize(g)) + (0.0722 * _linearize(b))


def contrast_ratio(color_a: str, color_b: str) -> float:
    """Return the WCAG contrast ratio between two colors."""
    luminance_a = relative_luminance(color_a)
    luminance_b = relative_luminance(color_b)
    lighter = max(luminance_a, luminance_b)
    darker = min(luminance_a, luminance_b)
    return (lighter + 0.05) / (darker + 0.05)


def contrast_color(bg_hex: str) -> str:
    """Return black or white text color for best contrast on *bg_hex*.

    Uses a threshold of 0.6 (rather than 0.5) to favor white text
    on medium-dark colors for better readability.
    """
    r, g, b = hex_to_rgb(bg_hex)
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return "#000000" if luminance > 0.6 else "#ffffff"


def ensure_text_contrast(bg_hex: str, fg_hex: str, min_ratio: float = 4.5) -> str:
    """Adjust *bg_hex* just enough to reach *min_ratio* against *fg_hex*."""
    if contrast_ratio(bg_hex, fg_hex) >= min_ratio:
        return blend_hex_colors(bg_hex, bg_hex, 0.0)

    target_hex = "#000000" if relative_luminance(fg_hex) > 0.5 else "#ffffff"
    adjusted = bg_hex
    for step in range(1, 11):
        adjusted = blend_hex_colors(bg_hex, target_hex, step / 10)
        if contrast_ratio(adjusted, fg_hex) >= min_ratio:
            return adjusted
    return adjusted
