"""Tests for exit_tracker module."""

from unittest.mock import MagicMock, patch

# Test shutdown hooks list management
from shared import exit_tracker


class TestShutdownHooks:
    """Test shutdown hook registration and execution."""

    def setup_method(self):
        """Reset global state before each test."""
        exit_tracker._shutdown_hooks.clear()

    def teardown_method(self):
        """Reset global state after each test."""
        exit_tracker._shutdown_hooks.clear()

    def test_register_shutdown_hook_adds_callback(self):
        """Registering a hook adds it to the list."""
        callback = MagicMock()
        exit_tracker.register_shutdown_hook(callback)
        assert callback in exit_tracker._shutdown_hooks

    def test_register_multiple_hooks(self):
        """Multiple hooks can be registered."""
        cb1 = MagicMock()
        cb2 = MagicMock()
        exit_tracker.register_shutdown_hook(cb1)
        exit_tracker.register_shutdown_hook(cb2)
        assert len(exit_tracker._shutdown_hooks) == 2
        assert cb1 in exit_tracker._shutdown_hooks
        assert cb2 in exit_tracker._shutdown_hooks

    def test_run_shutdown_hooks_calls_all(self):
        """All registered hooks are called."""
        cb1 = MagicMock()
        cb2 = MagicMock()
        exit_tracker._shutdown_hooks.extend([cb1, cb2])

        exit_tracker._run_shutdown_hooks()

        cb1.assert_called_once()
        cb2.assert_called_once()

    def test_run_shutdown_hooks_continues_on_exception(self):
        """Hook exceptions don't stop other hooks from running."""
        cb1 = MagicMock(side_effect=RuntimeError("boom"))
        cb2 = MagicMock()
        exit_tracker._shutdown_hooks.extend([cb1, cb2])

        # Should not raise
        exit_tracker._run_shutdown_hooks()

        cb1.assert_called_once()
        cb2.assert_called_once()

    def test_run_shutdown_hooks_empty_list(self):
        """Running with no hooks doesn't raise."""
        exit_tracker._run_shutdown_hooks()  # Should not raise


class TestSignalHandler:
    """Test signal handler behavior."""

    def setup_method(self):
        exit_tracker._shutdown_hooks.clear()

    def teardown_method(self):
        exit_tracker._shutdown_hooks.clear()

    def test_signal_handler_runs_hooks(self):
        """Signal handler runs shutdown hooks before re-raising."""
        cb = MagicMock()
        exit_tracker._shutdown_hooks.append(cb)

        with (
            patch.object(exit_tracker.signal, "signal") as mock_signal,
            patch.object(exit_tracker.os, "kill") as mock_kill,
            patch.object(exit_tracker.os, "getpid", return_value=12345),
        ):
            import signal

            exit_tracker._signal_handler(signal.SIGTERM, None)

            cb.assert_called_once()
            mock_signal.assert_called_once_with(signal.SIGTERM, signal.SIG_DFL)
            mock_kill.assert_called_once_with(12345, signal.SIGTERM)


class TestInstallExitTracker:
    """Test exit tracker installation."""

    def test_installs_faulthandler(self):
        """Faulthandler is enabled with crash log file."""
        with (
            patch("shared.exit_tracker.faulthandler") as mock_fh,
            patch("shared.crash_log.get_native_crash_log_path") as mock_path,
            patch("builtins.open", MagicMock()),
            patch.object(exit_tracker.signal, "signal"),
        ):
            mock_path_obj = MagicMock()
            mock_path_obj.parent.mkdir = MagicMock()
            mock_path.return_value = mock_path_obj

            exit_tracker.install_exit_tracker()

            mock_fh.enable.assert_called_once()

    def test_installs_signal_handlers(self):
        """Signal handlers are installed for SIGTERM, SIGINT, SIGHUP."""
        import signal

        with (
            patch("shared.exit_tracker.faulthandler"),
            patch("shared.crash_log.get_native_crash_log_path") as mock_path,
            patch("builtins.open", MagicMock()),
            patch.object(exit_tracker.signal, "signal") as mock_signal,
        ):
            mock_path_obj = MagicMock()
            mock_path_obj.parent.mkdir = MagicMock()
            mock_path.return_value = mock_path_obj

            exit_tracker.install_exit_tracker()

            # Check signal handlers were registered
            calls = mock_signal.call_args_list
            sigs = [c[0][0] for c in calls]
            assert signal.SIGTERM in sigs
            assert signal.SIGINT in sigs
            assert signal.SIGHUP in sigs

    def test_faulthandler_failure_doesnt_crash(self):
        """If faulthandler setup fails, installation continues."""
        with (
            patch("shared.exit_tracker.faulthandler") as mock_fh,
            patch("shared.crash_log.get_native_crash_log_path", side_effect=OSError("no path")),
            patch.object(exit_tracker.signal, "signal"),
        ):
            # Should not raise
            exit_tracker.install_exit_tracker()
            # Faulthandler.enable should NOT have been called due to path error
            mock_fh.enable.assert_not_called()

    def test_signal_registration_failure_doesnt_crash(self):
        """If signal registration fails, installation continues."""
        with (
            patch("shared.exit_tracker.faulthandler"),
            patch("shared.crash_log.get_native_crash_log_path") as mock_path,
            patch("builtins.open", MagicMock()),
            patch.object(exit_tracker.signal, "signal", side_effect=OSError("can't register")),
        ):
            mock_path_obj = MagicMock()
            mock_path_obj.parent.mkdir = MagicMock()
            mock_path.return_value = mock_path_obj

            # Should not raise
            exit_tracker.install_exit_tracker()
