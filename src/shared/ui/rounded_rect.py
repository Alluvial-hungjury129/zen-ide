"""Utility for building uniform Gsk.RoundedRect clips."""

from gi.repository import Graphene, Gsk


class RoundedRect:
    @staticmethod
    def build(x, y, w, h, radius):
        """Return a Gsk.RoundedRect with uniform corner radius."""
        rect = Graphene.Rect().init(x, y, w, h)
        size = Graphene.Size().init(radius, radius)
        rounded = Gsk.RoundedRect()
        rounded.init(rect, size, size, size, size)
        return rounded
