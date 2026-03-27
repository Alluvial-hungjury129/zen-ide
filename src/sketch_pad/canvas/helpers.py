"""
Shared helper functions for the canvas package.
"""


def _hex(color: str) -> tuple[float, float, float]:
    h = color.lstrip("#")
    if len(h) == 6:
        return (int(h[0:2], 16) / 255.0, int(h[2:4], 16) / 255.0, int(h[4:6], 16) / 255.0)
    return (0.8, 0.85, 0.95)
