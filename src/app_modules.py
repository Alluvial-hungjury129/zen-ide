"""App modules — ZenIDEApp (GTK Application) and module registration/management."""

import os
import sys
import time

from gi.repository import Gdk, Gio, GLib, Gtk


class ZenIDEApp(Gtk.Application):
    """GTK4 Application for Zen IDE."""

    def __init__(self):
        super().__init__(
            application_id="com.zenide.app",
            flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE | Gio.ApplicationFlags.HANDLES_OPEN,
        )
        self._pending_workspace = None
        self._pending_file = None
        self._pending_new_file = None
        self._pending_dir = None
        self._icon_paintable = None

        # On Linux, install the icon and set default icon name BEFORE any
        # window is created.  The window manager reads the icon at window
        # creation time — doing it later in a deferred callback is too late.
        if sys.platform == "linux":
            self._setup_app_icon_early()

    def _setup_app_icon_early(self):
        """Install the app icon into the icon theme BEFORE any window is created.

        On Linux, the window manager reads the icon at window-creation time
        via _NET_WM_ICON (X11) or the xdg-icon-theme (Wayland).  If the
        icon isn't installed and ``set_default_icon_name`` hasn't been called
        yet, the WM falls back to a generic icon and won't update it later.

        This method:
        1. Copies zen_icon.png into ~/.local/share/icons/hicolor/ at multiple
           standard sizes (48, 64, 128, 256) so icon lookups at any DPI work.
        2. Also installs into /usr/share/pixmaps/ as a universal fallback
           (some older DEs/WMs check pixmaps before the icon theme).
        3. Calls Gtk.Window.set_default_icon_name("zen-ide") so every
           GtkWindow created afterwards gets the correct _NET_WM_ICON.
        4. Installs the .desktop file for the current user.
        """
        src_dir = os.path.dirname(os.path.abspath(__file__))
        repo_root = os.path.dirname(src_dir)
        icon_path = os.path.join(repo_root, "zen_icon.png")

        if not os.path.exists(icon_path):
            return

        try:
            import shutil

            # Install icon at multiple sizes in the user's hicolor theme.
            # Many DEs (Cinnamon, KDE, XFCE) require the icon in the hicolor
            # theme hierarchy — /usr/share/pixmaps alone isn't always enough.
            for size in (48, 64, 128, 256):
                icon_dir = os.path.expanduser(f"~/.local/share/icons/hicolor/{size}x{size}/apps")
                os.makedirs(icon_dir, exist_ok=True)
                dest = os.path.join(icon_dir, "zen-ide.png")
                if not os.path.exists(dest) or os.path.getmtime(icon_path) > os.path.getmtime(dest):
                    shutil.copy2(icon_path, dest)

            # Also install a scalable/symbolic copy at the base apps/ level
            # (some compositors look here for SVG/PNG fallback)
            base_dir = os.path.expanduser("~/.local/share/icons/hicolor/scalable/apps")
            os.makedirs(base_dir, exist_ok=True)
            base_dest = os.path.join(base_dir, "zen-ide.png")
            if not os.path.exists(base_dest) or os.path.getmtime(icon_path) > os.path.getmtime(base_dest):
                shutil.copy2(icon_path, base_dest)

            # Install into ~/.local/share/pixmaps as a universal fallback
            pixmaps_dir = os.path.expanduser("~/.local/share/pixmaps")
            os.makedirs(pixmaps_dir, exist_ok=True)
            pixmaps_dest = os.path.join(pixmaps_dir, "zen-ide.png")
            if not os.path.exists(pixmaps_dest) or os.path.getmtime(icon_path) > os.path.getmtime(pixmaps_dest):
                shutil.copy2(icon_path, pixmaps_dest)

            # Install the .desktop file for the current user
            desktop_src = os.path.join(repo_root, "zen-ide.desktop")
            if os.path.exists(desktop_src):
                desktop_dir = os.path.expanduser("~/.local/share/applications")
                os.makedirs(desktop_dir, exist_ok=True)
                desktop_dest = os.path.join(desktop_dir, "zen-ide.desktop")
                if not os.path.exists(desktop_dest) or os.path.getmtime(desktop_src) > os.path.getmtime(desktop_dest):
                    shutil.copy2(desktop_src, desktop_dest)

            # Update the icon theme cache so the DE picks up the new icon
            # immediately (without requiring a logout).  Errors are silenced —
            # the cache will be rebuilt on next login anyway.
            try:
                import subprocess

                hicolor_dir = os.path.expanduser("~/.local/share/icons/hicolor")
                subprocess.Popen(
                    ["gtk-update-icon-cache", "-f", "-t", hicolor_dir],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except FileNotFoundError:
                pass  # gtk-update-icon-cache not installed

        except Exception:
            pass  # Non-fatal — worst case the generic icon is shown

        # Tell GTK4 that every window should use this icon.  This must be
        # called BEFORE any Gtk.Window is instantiated — it sets the
        # _NET_WM_ICON property on X11 and the app_id icon on Wayland.
        Gtk.Window.set_default_icon_name("zen-ide")

    def _setup_app_icon(self):
        """Set the application icon from zen_icon.png (deferred call for texture + macOS)."""
        # Look for icon relative to this file's location
        src_dir = os.path.dirname(os.path.abspath(__file__))
        repo_root = os.path.dirname(src_dir)

        # Use zen_icon.png
        icon_path = os.path.join(repo_root, "zen_icon.png")

        # Load the icon as texture for direct use (About dialog, etc.)
        if os.path.exists(icon_path):
            try:
                self._icon_paintable = Gdk.Texture.new_from_filename(icon_path)
            except Exception:
                pass

        # Defer macOS dock icon (AppKit import is ~120ms — do it after first paint)
        if sys.platform == "darwin":
            GLib.idle_add(self._set_macos_dock_icon, icon_path)

    def _set_macos_dock_icon(self, icon_path):
        """Set the dock icon on macOS using AppKit and bring app to foreground."""
        try:
            from AppKit import NSApplication, NSImage

            ns_app = NSApplication.sharedApplication()
            # Bring the app to foreground on startup
            ns_app.activateIgnoringOtherApps_(True)

            if os.path.exists(icon_path):
                image = NSImage.alloc().initWithContentsOfFile_(icon_path)
                if image:
                    ns_app.setApplicationIconImage_(image)
        except ImportError:
            pass  # pyobjc not installed
        except Exception:
            pass
        return False  # Don't repeat (GLib.idle_add)

    def get_icon_paintable(self):
        """Get the app icon as a paintable for windows."""
        return self._icon_paintable

    def do_command_line(self, command_line):
        """Handle command line arguments."""
        args = command_line.get_arguments()
        if len(args) > 1:
            path = os.path.abspath(args[1])
            if path.endswith((".zen-workspace", ".code-workspace")) and os.path.isfile(path):
                self._pending_workspace = path
            elif os.path.isdir(path):
                self._pending_dir = path
            elif os.path.isfile(path):
                self._pending_file = path
            else:
                # File doesn't exist — open as a new unsaved file with that name
                self._pending_new_file = path
        self.activate()
        return 0

    def do_open(self, files, n_files, hint):
        """Handle files opened via macOS 'Open With' or drag-and-drop."""
        for gfile in files:
            path = gfile.get_path()
            if path and os.path.isfile(path):
                self._pending_file = os.path.abspath(path)
                break
        self.activate()

    def do_activate(self):
        """Called when the application is activated.

        Two distinct paths:
        1. **First launch** — no window exists: create ZenIDEWindow, set CLI
           hints (``_cli_file``, etc.) that ``_on_window_mapped`` consumes,
           and defer file opening until the editor is realized.
        2. **Re-activation** — window already exists (second ``zen file.py``
           via D-Bus): open the file/workspace/dir directly in the running
           window without touching panel visibility.
        """
        # Import here to avoid circular import — zen_ide imports app_modules,
        # and ZenIDEWindow is defined in zen_ide.
        import zen_ide

        win = self.props.active_window
        is_first_launch = win is None

        if is_first_launch:
            # Heavy modules (editor, treeview, fonts) already preloaded by
            # background threads at module level — no imports needed here.

            # Start timing from our code (excludes GTK framework overhead in app.run())
            zen_ide._STARTUP_TIME = time.monotonic()
            win = zen_ide.ZenIDEWindow(self)

            # Set CLI arguments BEFORE present() — present() triggers the "map"
            # signal which runs _init_workspace synchronously, so these must be
            # available by then.
            if self._pending_file:
                win._cli_file = self._pending_file
                win.tree_view.set_visible(False)
                win.bottom_paned.set_visible(False)

            if self._pending_new_file:
                win._cli_new_file = self._pending_new_file
                win.tree_view.set_visible(False)
                win.bottom_paned.set_visible(False)

            if self._pending_workspace:
                win._cli_workspace = self._pending_workspace
                self._pending_workspace = None

            if self._pending_dir:
                win._cli_dir = self._pending_dir
                self._pending_dir = None

            win.present()

            # Defer main thread poll and housekeeping to after first paint
            from shared.main_thread import start_main_thread_poll

            start_main_thread_poll()
            GLib.idle_add(zen_ide._run_startup_housekeeping)

            # Open single file after present (editor needs to be mapped first)
            if self._pending_file:
                path = self._pending_file
                self._pending_file = None
                GLib.idle_add(lambda: win.editor_view.open_file(path) and False)

            # Create new file tab for non-existent file path from CLI
            if self._pending_new_file:
                path = self._pending_new_file
                self._pending_new_file = None
                GLib.idle_add(lambda: win.editor_view.open_or_create_file(path) and False)
        else:
            # Re-activation: open pending items in the existing window.
            if self._pending_file:
                path = self._pending_file
                self._pending_file = None
                win.editor_view.open_file(path)

            if self._pending_new_file:
                path = self._pending_new_file
                self._pending_new_file = None
                win.editor_view.open_or_create_file(path)

            if self._pending_workspace:
                ws = self._pending_workspace
                self._pending_workspace = None
                win._load_workspace_file(ws)

            if self._pending_dir:
                d = self._pending_dir
                self._pending_dir = None
                from shared.git_ignore_utils import collect_global_patterns
                from shared.settings import set_setting

                collect_global_patterns([d])
                win.tree_view.load_workspace([d])
                win.set_title(f"Zen IDE — {os.path.basename(d)}")
                set_setting("workspace.workspace_file", "")
                set_setting("workspace.folders", [d])
                win._show_all_panels()

            # Raise the existing window to the foreground
            win.present()
