"""Exit tracker for Zen IDE.

Installs signal handlers and faulthandler for clean shutdown and native crash
detection. Provides shutdown hooks for cleanup (e.g. AI process termination).
"""

import faulthandler
import os
import signal

_faulthandler_file = None  # Keep reference to prevent GC closing the file
_shutdown_hooks = []  # Callbacks to run before exit (signal or normal)


def register_shutdown_hook(callback):
    """Register a callback to be invoked on signal-based shutdown.

    Hooks run before the signal is re-raised. Keep them fast and safe.
    """
    _shutdown_hooks.append(callback)


def _run_shutdown_hooks():
    """Run all registered shutdown hooks (best-effort)."""
    for hook in _shutdown_hooks:
        try:
            hook()
        except Exception:
            pass


def _signal_handler(signum, frame):
    """Handle termination signals by running shutdown hooks and re-raising."""
    # Log the signal-based exit before running hooks
    import signal as sig_module

    sig_name = sig_module.Signals(signum).name if hasattr(sig_module, "Signals") else f"signal {signum}"
    try:
        from shared.crash_log import log_exit

        log_exit(f"Signal: {sig_name}", signal_num=signum)
    except Exception:
        pass

    _run_shutdown_hooks()
    # Re-raise with default handler
    signal.signal(signum, signal.SIG_DFL)
    os.kill(os.getpid(), signum)


def install_exit_tracker():
    """Install signal handlers and faulthandler for crash detection.

    Call at application startup, after crash_log handler is installed.
    """
    global _faulthandler_file

    # Enable faulthandler for native crashes (SIGSEGV, SIGABRT, SIGFPE, SIGBUS)
    # Write to a dedicated file so crash data survives and can be recovered
    # on next startup by collect_native_crash().
    from shared.crash_log import get_native_crash_log_path

    try:
        native_crash_path = get_native_crash_log_path()
        native_crash_path.parent.mkdir(parents=True, exist_ok=True)
        _faulthandler_file = open(native_crash_path, "w")
        faulthandler.enable(file=_faulthandler_file, all_threads=True)
    except Exception:
        # Don't let faulthandler setup crash the IDE
        _faulthandler_file = None

    # Register signal handlers for graceful termination signals
    for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        try:
            signal.signal(sig, _signal_handler)
        except (OSError, ValueError):
            pass  # Some signals can't be caught on all platforms
