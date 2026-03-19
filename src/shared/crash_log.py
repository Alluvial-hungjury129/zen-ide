"""Crash log mechanism for Zen IDE GTK.

Logs crashes to ~/.zen_ide/crash_log.txt with newest entries at the top.
"""

import sys
from pathlib import Path

# Crash log file location
CRASH_LOG_PATH = Path.home() / ".zen_ide" / "crash_log.txt"
# Separate file for faulthandler native crash output (recovered on next startup)
NATIVE_CRASH_LOG_PATH = Path.home() / ".zen_ide" / "native_crash.log"


def _ensure_dir():
    """Ensure the .zen_ide directory exists."""
    from shared.utils import ensure_parent_dir

    ensure_parent_dir(CRASH_LOG_PATH)


def log_crash(exc_type=None, exc_value=None, exc_tb=None):
    """Log a crash/exception to the crash log file.

    New crashes are prepended to the top of the file (no sorting).

    Args:
        exc_type: Exception type (from sys.exc_info())
        exc_value: Exception value
        exc_tb: Exception traceback
    """
    _ensure_dir()

    # Get exception info if not provided
    if exc_type is None:
        exc_type, exc_value, exc_tb = sys.exc_info()

    # Format the crash entry
    import traceback
    from datetime import datetime

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    separator = "=" * 60

    lines = [
        separator,
        f"CRASH: {timestamp}",
        separator,
    ]

    if exc_type is not None:
        lines.append(f"Exception: {exc_type.__name__}: {exc_value}")
        lines.append("")
        lines.append("Traceback:")
        tb_lines = traceback.format_exception(exc_type, exc_value, exc_tb)
        lines.extend(line.rstrip() for line in tb_lines)
    else:
        lines.append("No exception info available")

    lines.append("")  # Blank line after entry

    new_entry = "\n".join(lines) + "\n"

    # Prepend to file (read existing, write new + existing)
    existing_content = ""
    if CRASH_LOG_PATH.exists():
        try:
            existing_content = CRASH_LOG_PATH.read_text(encoding="utf-8")
        except Exception:
            pass  # If we can't read, just overwrite

    try:
        CRASH_LOG_PATH.write_text(new_entry + existing_content, encoding="utf-8")
    # Boundary catch: crash logging must never raise further.
    except Exception as e:
        # Last resort: print to stderr
        print(f"Failed to write crash log: {e}", file=sys.stderr)
        print(new_entry, file=sys.stderr)


def log_message(message: str):
    """Log a custom message to the crash log (for non-exception errors).

    New entries are prepended to the top of the file.

    Args:
        message: The message to log
    """
    _ensure_dir()

    from datetime import datetime

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    separator = "-" * 60

    new_entry = f"{separator}\n[{timestamp}] {message}\n\n"

    existing_content = ""
    if CRASH_LOG_PATH.exists():
        try:
            existing_content = CRASH_LOG_PATH.read_text(encoding="utf-8")
        except Exception:
            pass

    try:
        CRASH_LOG_PATH.write_text(new_entry + existing_content, encoding="utf-8")
    # Boundary catch: crash logging must never raise further.
    except Exception as e:
        print(f"Failed to write crash log: {e}", file=sys.stderr)


def install_crash_handler():
    """Install global exception handler to log uncaught exceptions.

    Call this at application startup to catch all unhandled exceptions.
    """
    original_hook = sys.excepthook

    def crash_handler(exc_type, exc_value, exc_tb):
        # Log the crash
        log_crash(exc_type, exc_value, exc_tb)
        # Call the original handler (prints to stderr)
        original_hook(exc_type, exc_value, exc_tb)

    sys.excepthook = crash_handler


def get_crash_log_path() -> Path:
    """Return the path to the crash log file."""
    return CRASH_LOG_PATH


def get_native_crash_log_path() -> Path:
    """Return the path to the native crash (faulthandler) log file."""
    return NATIVE_CRASH_LOG_PATH


def collect_native_crash() -> bool:
    """Collect native crash data from previous session's faulthandler output.

    On native crashes (SIGSEGV, SIGABRT, etc.), faulthandler writes a Python
    traceback to NATIVE_CRASH_LOG_PATH. This function recovers that data,
    formats it as a crash entry, and prepends it to the main crash log.

    Call this at startup BEFORE install_exit_tracker() reopens the file.

    Returns:
        True if a native crash was recovered, False otherwise.
    """
    if not NATIVE_CRASH_LOG_PATH.exists():
        return False

    try:
        content = NATIVE_CRASH_LOG_PATH.read_text(encoding="utf-8", errors="replace").strip()
        if not content:
            return False

        _ensure_dir()
        from datetime import datetime

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        separator = "=" * 60

        entry = (
            f"{separator}\n"
            f"NATIVE CRASH (recovered): {timestamp}\n"
            f"{separator}\n"
            f"The previous session crashed with a native signal (SIGSEGV, "
            f"SIGABRT, etc.).\n"
            f"Python traceback at time of crash:\n\n"
            f"{content}\n\n"
        )

        existing = ""
        if CRASH_LOG_PATH.exists():
            try:
                existing = CRASH_LOG_PATH.read_text(encoding="utf-8")
            except Exception:
                pass

        CRASH_LOG_PATH.write_text(entry + existing, encoding="utf-8")
        return True
    except Exception:
        return False


def log_exit(reason: str, signal_num: int | None = None):
    """Log an application exit to the crash log.

    Call this on normal exits, signal-based terminations, or any shutdown
    event to maintain a record of when and why the app stopped.

    Args:
        reason: Human-readable reason (e.g., "Normal exit", "Signal: SIGTERM")
        signal_num: Optional signal number if exit was due to a signal
    """
    _ensure_dir()

    from datetime import datetime

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    separator = "-" * 60

    lines = [separator, f"[{timestamp}] EXIT: {reason}"]
    if signal_num is not None:
        lines.append(f"Signal number: {signal_num}")
    lines.append("")

    new_entry = "\n".join(lines) + "\n"

    existing_content = ""
    if CRASH_LOG_PATH.exists():
        try:
            existing_content = CRASH_LOG_PATH.read_text(encoding="utf-8")
        except Exception:
            pass

    try:
        CRASH_LOG_PATH.write_text(new_entry + existing_content, encoding="utf-8")
    # Boundary catch: crash logging must never raise further.
    except Exception as e:
        print(f"Failed to write exit log: {e}", file=sys.stderr)


def clear_crash_log():
    """Clear the crash log file."""
    if CRASH_LOG_PATH.exists():
        try:
            CRASH_LOG_PATH.unlink()
        except Exception:
            pass
