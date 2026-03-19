from gi.repository import Gtk


class TreeCanvas(Gtk.DrawingArea):
    """DrawingArea that renders the tree using GtkSnapshot"""

    __gtype_name__ = "TreeCanvas"

    def __init__(self, panel):
        super().__init__()
        self._panel = panel

    def do_snapshot(self, snapshot):
        # Render via GtkSnapshot
        width = self.get_width()
        height = self.get_height()
        if width > 0 and height > 0:
            self._panel._on_snapshot(snapshot, width, height)
