"""Shared utility functions used across the IDE.

Consolidates duplicate helpers (color conversion, font sanitisation,
directory helpers, word navigation) so every module uses a single implementation.
"""

import sys

# ── Re-exports from extracted modules ─────────────────────────
# Many files do ``from shared.utils import <name>``; keep those working.
from shared.color_utils import (  # noqa: F401
    blend_hex_colors,
    contrast_color,
    contrast_ratio,
    ensure_text_contrast,
    hex_to_gdk_rgba,
    hex_to_rgb,
    hex_to_rgb_float,
    hex_to_rgba,
    hex_to_rgba_css,
    relative_luminance,
    tuple_to_gdk_rgba,
)
from shared.unicode_width import (  # noqa: F401
    display_width,
)

# ── Word navigation helpers (treat _ as word char) ─────────────


def _is_word_char(ch):
    return ch.isalnum() or ch == "_"


def move_word_backward(text_iter):
    """Move a Gtk.TextIter backward by one word, treating _ as word char.
    Returns the new iter position."""
    target = text_iter.copy()
    # Skip whitespace
    while not target.is_start():
        prev = target.copy()
        prev.backward_char()
        ch = prev.get_char()
        if ch in (" ", "\t", "\n"):
            target.backward_char()
        else:
            break
    # Skip same-class characters
    if not target.is_start():
        probe = target.copy()
        probe.backward_char()
        first_is_word = _is_word_char(probe.get_char())
        while not target.is_start():
            prev = target.copy()
            prev.backward_char()
            ch = prev.get_char()
            if ch in (" ", "\t", "\n"):
                break
            if _is_word_char(ch) != first_is_word:
                break
            target.backward_char()
    return target


def move_word_forward(text_iter):
    """Move a Gtk.TextIter forward by one word, treating _ as word char.
    Returns the new iter position."""
    target = text_iter.copy()
    # Skip whitespace
    while not target.is_end():
        ch = target.get_char()
        if ch in (" ", "\t", "\n"):
            target.forward_char()
        else:
            break
    # Skip same-class characters
    if not target.is_end():
        first_is_word = _is_word_char(target.get_char())
        while not target.is_end():
            ch = target.get_char()
            if ch in (" ", "\t", "\n"):
                break
            if _is_word_char(ch) != first_is_word:
                break
            target.forward_char()
    return target


def handle_word_nav_keypress(buffer, keyval, state):
    """Handle Option+Left/Right/Backspace word navigation for a Gtk.TextBuffer.

    Returns True if the key was handled, False otherwise.
    Only active on macOS. Treats _ as a word character.
    """
    if sys.platform != "darwin":
        return False

    try:
        from gi.repository import Gdk
    except ImportError:
        return False

    is_alt = bool(state & Gdk.ModifierType.ALT_MASK)
    is_shift = bool(state & Gdk.ModifierType.SHIFT_MASK)
    is_cmd = bool(state & Gdk.ModifierType.META_MASK)

    if not is_alt or is_cmd:
        return False

    cursor = buffer.get_insert()
    it = buffer.get_iter_at_mark(cursor)

    if keyval == Gdk.KEY_Left:
        target = move_word_backward(it)
        if is_shift:
            buffer.move_mark(cursor, target)
        else:
            buffer.place_cursor(target)
        return True

    if keyval == Gdk.KEY_Right:
        target = move_word_forward(it)
        if is_shift:
            buffer.move_mark(cursor, target)
        else:
            buffer.place_cursor(target)
        return True

    if keyval == Gdk.KEY_BackSpace:
        line_start = it.copy()
        line_start.set_line_offset(0)
        if it.equal(line_start):
            if it.get_line() == 0:
                return True
            prev = it.copy()
            prev.backward_char()
            buffer.begin_user_action()
            buffer.delete(prev, it)
            buffer.end_user_action()
            return True
        target = move_word_backward(it)
        # Clamp to line start
        if target.compare(line_start) < 0:
            target = line_start
        buffer.begin_user_action()
        buffer.delete(target, it)
        buffer.end_user_action()
        return True

    return False


# ── Plain-string word boundary helpers (for VTE terminal) ──────


def find_word_boundary_left(text, pos):
    """Find position after moving backward one word in plain text.
    Treats _ as a word character."""
    if pos <= 0:
        return 0
    i = pos
    # Skip whitespace
    while i > 0 and text[i - 1] in (" ", "\t"):
        i -= 1
    # Skip same-class characters
    if i > 0:
        first_is_word = _is_word_char(text[i - 1])
        while i > 0:
            ch = text[i - 1]
            if ch in (" ", "\t"):
                break
            if _is_word_char(ch) != first_is_word:
                break
            i -= 1
    return i


def find_word_boundary_right(text, pos):
    """Find position after moving forward one word in plain text.
    Treats _ as a word character."""
    length = len(text)
    if pos >= length:
        return length
    i = pos
    # Skip whitespace
    while i < length and text[i] in (" ", "\t"):
        i += 1
    # Skip same-class characters
    if i < length:
        first_is_word = _is_word_char(text[i])
        while i < length:
            ch = text[i]
            if ch in (" ", "\t"):
                break
            if _is_word_char(ch) != first_is_word:
                break
            i += 1
    return i


# ── Font helpers ────────────────────────────────────────────────


def sanitize_font_for_vte(font_family: str) -> str:
    """Sanitize font family for VTE terminal.

    VTE requires true monospace fonts. Proportional fonts (like "Propo"
    variants) render with incorrect character widths (double-spaced).
    This converts problematic font variants to their monospace equivalents.
    """
    if not font_family:
        return ""

    # Convert "Propo" (proportional) variants to "Mono" variants
    if " Propo" in font_family:
        return font_family.replace(" Propo", " Mono")

    # For Nerd Fonts without "Mono" suffix, add it for fixed-width icon glyphs
    # Exception: SauceCodePro Nerd Font is already monospace for code/text
    if "Nerd Font" in font_family and "Nerd Font Mono" not in font_family and "Nerd Font Propo" not in font_family:
        if "SauceCodePro" not in font_family:
            return font_family.replace("Nerd Font", "Nerd Font Mono")

    return font_family


# ── Filesystem helpers ──────────────────────────────────────────


def ensure_parent_dir(file_path) -> None:
    """Ensure the parent directory of *file_path* exists."""
    from pathlib import Path

    Path(file_path).parent.mkdir(parents=True, exist_ok=True)


# ── Clipboard helpers ──────────────────────────────────────────


def copy_to_system_clipboard(text: str) -> None:
    """Write text directly to the OS clipboard (pbcopy / xclip).

    GTK4 uses lazy content providers that die with the process.
    Call this alongside every GTK clipboard.set() so the OS holds
    a concrete copy that survives app exit.
    """
    import subprocess
    import sys

    if not text:
        return
    try:
        if sys.platform == "darwin":
            p = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
            p.communicate(text.encode("utf-8"), timeout=2)
        else:
            p = subprocess.Popen(
                ["xclip", "-selection", "clipboard"],
                stdin=subprocess.PIPE,
            )
            p.communicate(text.encode("utf-8"), timeout=2)
    except Exception:
        pass


def persist_clipboard() -> None:
    """No-op kept for backward compatibility."""
    pass


# ── Animation helpers ──────────────────────────────────────────

# Track active paned animations so we can cancel when a new one starts
_paned_animations: dict[int, int] = {}  # widget id -> GLib source id


def animate_paned(paned, target: int, duration_ms: int = None, on_done=None):
    """Animate a Gtk.Paned to *target* position with ease-out cubic.

    Cancels any in-flight animation on the same paned widget.
    Calls *on_done()* after the animation finishes (if provided).
    """
    from gi.repository import GLib

    from constants import PANED_ANIM_DURATION_MS, PANED_ANIM_FRAME_INTERVAL_MS

    if duration_ms is None:
        duration_ms = PANED_ANIM_DURATION_MS

    widget_id = id(paned)

    # Cancel any running animation on this paned
    if widget_id in _paned_animations:
        GLib.source_remove(_paned_animations[widget_id])
        del _paned_animations[widget_id]

    start = paned.get_position()
    distance = target - start

    if abs(distance) < 2:
        paned.set_position(target)
        if on_done:
            on_done()
        return

    start_time = GLib.get_monotonic_time() / 1000.0  # ms

    def step():
        elapsed = GLib.get_monotonic_time() / 1000.0 - start_time
        progress = min(1.0, elapsed / duration_ms)
        eased = 1 - pow(1 - progress, 3)  # cubic ease-out
        paned.set_position(int(start + distance * eased))

        if progress >= 1.0:
            paned.set_position(target)
            _paned_animations.pop(widget_id, None)
            if on_done:
                on_done()
            return False
        return True

    _paned_animations[widget_id] = GLib.timeout_add(PANED_ANIM_FRAME_INTERVAL_MS, step)


# ── Environment helpers ────────────────────────────────────────


def ensure_full_path(env: dict) -> dict:
    """Ensure PATH in *env* includes common binary directories.

    macOS app bundles launched from Finder inherit a minimal PATH that
    lacks directories like ``/opt/homebrew/bin`` or NVM bin paths.  CLI
    tools such as ``copilot`` and ``claude`` are Node.js scripts with a
    ``#!/usr/bin/env node`` shebang, so ``node`` must be on PATH even
    when the CLI itself is invoked via an absolute path.
    """
    import os

    extra_dirs: list[str] = [
        "/opt/homebrew/bin",
        "/usr/local/bin",
        os.path.expanduser("~/.npm-global/bin"),
        os.path.expanduser("~/.local/bin"),
    ]

    # Add NVM bin directories (newest version first)
    nvm_dir = os.path.expanduser("~/.nvm/versions/node")
    if os.path.isdir(nvm_dir):
        try:
            versions = sorted(os.listdir(nvm_dir), reverse=True)
            extra_dirs.extend(os.path.join(nvm_dir, v, "bin") for v in versions if v.startswith("v"))
        except OSError:
            pass

    current = env.get("PATH", "").split(":")
    current_set = set(current)
    additions = [d for d in extra_dirs if d not in current_set]
    if additions:
        env["PATH"] = ":".join(current + additions)

    return env


def get_pango_font_map():
    """Get the default Pango font map.

    In Pango 1.52+, ``Pango.FontMap.get_default()`` no longer exists on the
    base class.  This helper obtains the font map through a lightweight
    ``Gtk.Label`` Pango context, which works on all GTK 4 / Pango versions
    without needing ``PangoCairo`` (which is banned per rendering standards).

    The result is cached after the first call.
    """
    cached = getattr(get_pango_font_map, "_cached", None)
    if cached is not None:
        return cached

    from gi.repository import Gtk

    font_map = Gtk.Label().get_pango_context().get_font_map()
    get_pango_font_map._cached = font_map
    return font_map


def get_resource_path(filename: str) -> str:
    """Resolve path to a bundled resource, works in both dev and PyInstaller."""
    import os
    import sys

    if getattr(sys, "frozen", False):
        return os.path.join(sys._MEIPASS, filename)
    # Dev mode: resources are at repo root
    shared_dir = os.path.dirname(os.path.abspath(__file__))
    src_dir = os.path.dirname(shared_dir)
    repo_root = os.path.dirname(src_dir)
    return os.path.join(repo_root, filename)
