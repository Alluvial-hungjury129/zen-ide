"""
System Monitor for Zen IDE (GTK4 version).

Displays real-time CPU, memory, disk, and process information.
"""

import gc
import os
import subprocess
import sys
import threading
import time
from typing import Callable, Optional

from gi.repository import GLib, Gtk

from fonts import get_font_settings
from icons import IconsManager
from shared.main_thread import main_thread_call
from shared.ui import ZenButton
from themes import get_theme


def get_process_memory_mb() -> float:
    """Get current process memory usage in MB."""
    try:
        import resource

        rusage = resource.getrusage(resource.RUSAGE_SELF)
        if sys.platform == "darwin":
            # macOS: ru_maxrss is in bytes
            return rusage.ru_maxrss / (1024 * 1024)
        else:
            # Linux: ru_maxrss is in KB
            return rusage.ru_maxrss / 1024
    except Exception:
        return 0.0


def get_system_memory_info() -> dict:
    """Get system memory information."""
    try:
        if sys.platform == "darwin":
            # macOS: use vm_stat
            result = subprocess.run(["vm_stat"], capture_output=True, text=True, timeout=2)
            if result.returncode == 0:
                lines = result.stdout.strip().split("\n")
                stats = {}
                for line in lines[1:]:
                    if ":" in line:
                        key, value = line.split(":", 1)
                        value = value.strip().rstrip(".")
                        try:
                            stats[key.strip()] = int(value)
                        except ValueError:
                            pass

                page_size = 4096
                pages_free = stats.get("Pages free", 0)
                pages_active = stats.get("Pages active", 0)
                pages_inactive = stats.get("Pages inactive", 0)
                pages_wired = stats.get("Pages wired down", 0)
                pages_compressed = stats.get("Pages occupied by compressor", 0)

                total_pages = pages_free + pages_active + pages_inactive + pages_wired + pages_compressed
                total_mb = (total_pages * page_size) / (1024 * 1024)
                used_mb = ((pages_active + pages_wired + pages_compressed) * page_size) / (1024 * 1024)
                free_mb = ((pages_free + pages_inactive) * page_size) / (1024 * 1024)

                # Get actual total from sysctl
                result2 = subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True, timeout=2)
                if result2.returncode == 0:
                    total_mb = int(result2.stdout.strip()) / (1024 * 1024)

                return {
                    "total_mb": total_mb,
                    "used_mb": used_mb,
                    "free_mb": free_mb,
                    "percent": (used_mb / total_mb * 100) if total_mb > 0 else 0,
                }
        else:
            # Linux: read /proc/meminfo
            with open("/proc/meminfo", "r") as f:
                meminfo = {}
                for line in f:
                    parts = line.split()
                    if len(parts) >= 2:
                        key = parts[0].rstrip(":")
                        value = int(parts[1])
                        meminfo[key] = value

                total_kb = meminfo.get("MemTotal", 0)
                free_kb = meminfo.get("MemFree", 0)
                buffers_kb = meminfo.get("Buffers", 0)
                cached_kb = meminfo.get("Cached", 0)

                available_kb = free_kb + buffers_kb + cached_kb
                used_kb = total_kb - available_kb

                return {
                    "total_mb": total_kb / 1024,
                    "used_mb": used_kb / 1024,
                    "free_mb": available_kb / 1024,
                    "percent": (used_kb / total_kb * 100) if total_kb > 0 else 0,
                }
    except Exception:
        pass
    return {"total_mb": 0, "used_mb": 0, "free_mb": 0, "percent": 0}


def get_cpu_usage() -> float:
    """Get CPU usage percentage (averaged over all cores)."""
    try:
        if sys.platform == "darwin":
            # macOS: use ps command
            result = subprocess.run(["ps", "-A", "-o", "%cpu"], capture_output=True, text=True, timeout=2)
            if result.returncode == 0:
                total = 0.0
                for line in result.stdout.strip().split("\n")[1:]:
                    try:
                        total += float(line.strip())
                    except ValueError:
                        pass
                cpu_count = os.cpu_count() or 1
                return min(100.0, total / cpu_count)
        else:
            # Linux: read /proc/stat
            with open("/proc/stat", "r") as f:
                line = f.readline()
                if line.startswith("cpu "):
                    parts = line.split()[1:]
                    values = [int(x) for x in parts]
                    total = sum(values)
                    idle = values[3] + values[4]
                    return ((total - idle) / total * 100) if total > 0 else 0
    except Exception:
        pass
    return 0.0


def get_disk_usage(path: str = "/") -> dict:
    """Get disk usage for a path."""
    try:
        st = os.statvfs(path)
        total = st.f_blocks * st.f_frsize
        free = st.f_bavail * st.f_frsize
        used = total - free
        return {
            "total_gb": total / (1024**3),
            "used_gb": used / (1024**3),
            "free_gb": free / (1024**3),
            "percent": (used / total * 100) if total > 0 else 0,
        }
    except Exception:
        return {"total_gb": 0, "used_gb": 0, "free_gb": 0, "percent": 0}


def get_python_info() -> dict:
    """Get Python interpreter information."""
    return {
        "version": sys.version.split()[0],
        "platform": sys.platform,
        "gc_counts": gc.get_count(),
        "gc_threshold": gc.get_threshold(),
        "objects_tracked": len(gc.get_objects()),
    }


def get_gtk_info() -> dict:
    """Get GTK information."""
    return {
        "version": f"{Gtk.get_major_version()}.{Gtk.get_minor_version()}.{Gtk.get_micro_version()}",
        "platform": sys.platform,
    }


class SystemMonitorPanel(Gtk.Box):
    """Panel displaying system resource usage."""

    def __init__(self, on_close: Optional[Callable] = None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self._on_close = on_close
        self._stop_event = threading.Event()
        self._update_interval = 2.0
        self._is_monitoring = False
        self._timeout_id = None

        self._setup_ui()
        self._apply_theme()

    def _setup_ui(self):
        """Create the UI layout."""
        # Header with title and close button
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        header.set_margin_start(10)
        header.set_margin_end(5)
        header.set_margin_top(5)
        header.set_margin_bottom(5)

        title = Gtk.Label(label="System Monitor")
        title.add_css_class("title-3")
        title.set_hexpand(True)
        title.set_halign(Gtk.Align.START)
        header.append(title)

        close_btn = ZenButton(icon=IconsManager.ERROR_X)
        close_btn.connect("clicked", self._on_close_click)
        header.append(close_btn)

        self.append(header)

        # Scrolled window for content
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        # Text view for stats
        self._stats_text = Gtk.TextView()
        self._stats_text.set_editable(False)
        self._stats_text.set_cursor_visible(False)
        self._stats_text.set_wrap_mode(Gtk.WrapMode.NONE)
        self._stats_text.set_left_margin(10)
        self._stats_text.set_right_margin(10)
        self._stats_text.set_top_margin(10)
        self._stats_text.set_bottom_margin(10)

        # Set font to match editor
        font_settings = get_font_settings("editor")
        font_family = font_settings["family"]
        font_size = font_settings.get("size", 13)

        self._font_css_provider = Gtk.CssProvider()
        css = f"""
            textview, textview text {{
                font-family: '{font_family}';
                font-size: {font_size}pt;
            }}
        """
        self._font_css_provider.load_from_data(css.encode())
        self._stats_text.get_style_context().add_provider(self._font_css_provider, Gtk.STYLE_PROVIDER_PRIORITY_USER)

        scroll.set_child(self._stats_text)
        self.append(scroll)

        # Footer with refresh interval selector
        footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        footer.set_margin_start(10)
        footer.set_margin_end(10)
        footer.set_margin_top(5)
        footer.set_margin_bottom(5)

        footer.append(Gtk.Label(label="Refresh:"))

        self._interval_dropdown = Gtk.DropDown.new_from_strings(["1s", "2s", "5s", "10s", "30s"])
        self._interval_dropdown.set_selected(1)  # Default 2s
        self._interval_dropdown.connect("notify::selected", self._on_interval_change)
        footer.append(self._interval_dropdown)

        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        footer.append(spacer)

        gc_btn = ZenButton(label="Run GC")
        gc_btn.connect("clicked", self._on_gc_click)
        footer.append(gc_btn)

        self.append(footer)

    def _apply_theme(self):
        """Apply current theme colors."""
        theme = get_theme()

        css_provider = Gtk.CssProvider()
        css = f"""
            .system-monitor-panel {{
                background-color: {theme.panel_bg};
            }}
            .system-monitor-panel textview {{
                background-color: {theme.panel_bg};
                color: {theme.fg_color};
            }}
            .system-monitor-panel textview text {{
                background-color: {theme.panel_bg};
                color: {theme.fg_color};
            }}
            .system-monitor-panel label {{
                color: {theme.fg_color};
            }}
        """
        css_provider.load_from_data(css.encode())

        self.add_css_class("system-monitor-panel")
        Gtk.StyleContext.add_provider_for_display(
            self.get_display(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_USER,
        )

    def _on_close_click(self, button):
        """Handle close button click."""
        self._stop_monitoring()
        if self._on_close:
            self._on_close()

    def _on_interval_change(self, dropdown, param):
        """Handle refresh interval change."""
        intervals = [1.0, 2.0, 5.0, 10.0, 30.0]
        idx = dropdown.get_selected()
        self._update_interval = intervals[idx]

        # Restart monitoring with new interval
        if self._is_monitoring:
            self._stop_monitoring()
            self._start_monitoring()

    def _on_gc_click(self, button):
        """Trigger garbage collection."""
        collected = gc.collect()

        dialog = Gtk.AlertDialog()
        dialog.set_message("GC Complete")
        dialog.set_detail(f"Objects collected: {collected}")
        dialog.set_buttons(["OK"])
        dialog.show(self.get_root())

        self._update_stats()

    def _start_monitoring(self):
        """Start the monitoring updates."""
        if self._is_monitoring:
            return
        self._is_monitoring = True
        self._stop_event.clear()
        self._schedule_update()
        self._update_stats()

    def _schedule_update(self):
        """Schedule the next stats update."""
        if self._is_monitoring and not self._stop_event.is_set():
            self._timeout_id = GLib.timeout_add(int(self._update_interval * 1000), self._on_timer_tick)

    def _on_timer_tick(self):
        """Called by GLib timer to update stats."""
        if not self._is_monitoring or self._stop_event.is_set():
            return False  # Stop the timer

        self._update_stats()
        return True  # Continue the timer

    def _stop_monitoring(self):
        """Stop the monitoring updates."""
        if not self._is_monitoring:
            return
        self._is_monitoring = False
        self._stop_event.set()

        if self._timeout_id:
            GLib.source_remove(self._timeout_id)
            self._timeout_id = None

    def show_panel(self):
        """Show the panel and start monitoring."""
        self.set_visible(True)
        self._start_monitoring()

    def hide_panel(self):
        """Hide the panel and stop monitoring."""
        self._stop_monitoring()
        self.set_visible(False)

    def _update_stats(self):
        """Update the stats display by running collection in background."""
        if not self._stats_text:
            return

        # Run data collection in a background thread to avoid blocking UI
        def collect_and_update():
            try:
                lines = []

                # Process Memory (fast, no subprocess)
                proc_mem = get_process_memory_mb()
                lines.append("═══ ZEN IDE PROCESS ═══")
                lines.append(f"Memory Usage:    {proc_mem:,.1f} MB")
                lines.append("")

                # System Memory (may use subprocess)
                mem = get_system_memory_info()
                lines.append("═══ SYSTEM MEMORY ═══")
                lines.append(f"Total:           {mem['total_mb']:,.0f} MB ({mem['total_mb'] / 1024:.1f} GB)")
                lines.append(f"Used:            {mem['used_mb']:,.0f} MB ({mem['percent']:.1f}%)")
                lines.append(f"Free:            {mem['free_mb']:,.0f} MB")
                lines.append(self._progress_bar(mem["percent"], 30))
                lines.append("")

                # CPU (may use subprocess)
                cpu = get_cpu_usage()
                lines.append("═══ CPU ═══")
                lines.append(f"Usage:           {cpu:.1f}%")
                lines.append(self._progress_bar(cpu, 30))
                lines.append("")

                # Disk (uses os.statvfs - fast)
                disk = get_disk_usage("/")
                lines.append("═══ DISK (/) ═══")
                lines.append(f"Total:           {disk['total_gb']:.1f} GB")
                lines.append(f"Used:            {disk['used_gb']:.1f} GB ({disk['percent']:.1f}%)")
                lines.append(f"Free:            {disk['free_gb']:.1f} GB")
                lines.append(self._progress_bar(disk["percent"], 30))
                lines.append("")

                # Python Info (fast, in-process)
                py_info = get_python_info()
                lines.append("═══ PYTHON ═══")
                lines.append(f"Version:         {py_info['version']}")
                lines.append(f"Platform:        {py_info['platform']}")
                lines.append(f"GC Counts:       {py_info['gc_counts']}")
                lines.append(f"GC Threshold:    {py_info['gc_threshold']}")
                lines.append(f"Objects:         {py_info['objects_tracked']:,}")
                lines.append("")

                # GTK Info (fast)
                gtk_info = get_gtk_info()
                lines.append("═══ GTK ═══")
                lines.append(f"Version:         {gtk_info['version']}")
                lines.append(f"Platform:        {gtk_info['platform']}")
                lines.append("")

                # Timestamp
                lines.append(f"Last updated: {time.strftime('%H:%M:%S')}")

                # Update UI on main thread
                text = "\n".join(lines)
                main_thread_call(self._set_stats_text, text)
            # Boundary catch: monitor collector must never crash the UI loop.
            except Exception as e:
                main_thread_call(self._set_stats_text, f"Error collecting stats: {e}")

        thread = threading.Thread(target=collect_and_update, daemon=True)
        thread.start()

    def _set_stats_text(self, text: str):
        """Set the stats text (called on main thread)."""
        if self._stats_text:
            buffer = self._stats_text.get_buffer()
            buffer.set_text(text)
        return False  # Don't repeat

    def _progress_bar(self, percent: float, width: int = 30) -> str:
        """Create a text-based progress bar."""
        filled = int(percent / 100 * width)
        empty = width - filled
        bar = "█" * filled + "░" * empty
        return f"[{bar}]"
