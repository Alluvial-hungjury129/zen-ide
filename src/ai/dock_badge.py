"""
Dock Badge Manager — macOS dock icon badge for AI agent status.

Shows a badge on the dock icon when AI agents are running,
and bounces the dock icon when they finish (to attract attention).
No-op on non-macOS platforms.
"""

import sys

_active_ai_count = 0


def _is_macos() -> bool:
    return sys.platform == "darwin"


def set_ai_badge():
    """Show 'AI' badge on the macOS dock icon."""
    global _active_ai_count
    _active_ai_count += 1

    if not _is_macos():
        return

    try:
        from AppKit import NSApplication

        ns_app = NSApplication.sharedApplication()
        dock_tile = ns_app.dockTile()
        dock_tile.setBadgeLabel_("AI")
        dock_tile.display()
    except ImportError:
        pass  # pyobjc not installed
    except Exception:
        pass


def clear_ai_badge():
    """Clear dock badge and bounce dock icon to signal completion."""
    global _active_ai_count
    _active_ai_count = max(0, _active_ai_count - 1)

    if _active_ai_count > 0:
        return  # Other AI sessions still running

    if not _is_macos():
        return

    try:
        from AppKit import NSApplication, NSInformationalRequest

        ns_app = NSApplication.sharedApplication()
        dock_tile = ns_app.dockTile()
        dock_tile.setBadgeLabel_(None)
        dock_tile.display()

        # Bounce dock icon to attract attention (informational = single bounce)
        ns_app.requestUserAttention_(NSInformationalRequest)
    except ImportError:
        pass  # pyobjc not installed
    except Exception:
        pass
