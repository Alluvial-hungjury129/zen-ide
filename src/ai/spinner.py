"""Spinner for AI thinking/loading state."""


class Spinner:
    """A text-based spinner for displaying thinking/loading state."""

    def __init__(self):
        self._chars = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"  # Braille spinner characters
        self._pos = 0

    def spin(self) -> str:
        """Return the next spinner character."""
        char = self._chars[self._pos]
        self._pos = (self._pos + 1) % len(self._chars)
        return char

    def reset(self):
        """Reset spinner position."""
        self._pos = 0
