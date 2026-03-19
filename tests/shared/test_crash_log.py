"""Tests for shared/crash_log.py - crash logging mechanism."""

from pathlib import Path
from unittest.mock import patch

from shared.crash_log import (
    clear_crash_log,
    collect_native_crash,
    get_crash_log_path,
    get_native_crash_log_path,
    log_crash,
    log_exit,
    log_message,
)


class TestLogCrash:
    """Test crash entry formatting and prepending."""

    def test_log_crash_creates_entry(self, tmp_path):
        crash_log = tmp_path / "crash_log.txt"
        with patch("shared.crash_log.CRASH_LOG_PATH", crash_log), patch("shared.crash_log._ensure_dir"):
            try:
                raise ValueError("test error")
            except ValueError:
                import sys

                log_crash(*sys.exc_info())

            content = crash_log.read_text()
            assert "CRASH:" in content
            assert "ValueError" in content
            assert "test error" in content

    def test_log_crash_prepends(self, tmp_path):
        crash_log = tmp_path / "crash_log.txt"
        crash_log.write_text("OLD ENTRY\n")
        with patch("shared.crash_log.CRASH_LOG_PATH", crash_log), patch("shared.crash_log._ensure_dir"):
            try:
                raise RuntimeError("new")
            except RuntimeError:
                import sys

                log_crash(*sys.exc_info())

            content = crash_log.read_text()
            # New entry should be before old
            assert content.index("RuntimeError") < content.index("OLD ENTRY")


class TestLogMessage:
    """Test custom message logging."""

    def test_log_message_writes(self, tmp_path):
        crash_log = tmp_path / "crash_log.txt"
        with patch("shared.crash_log.CRASH_LOG_PATH", crash_log), patch("shared.crash_log._ensure_dir"):
            log_message("something happened")

            content = crash_log.read_text()
            assert "something happened" in content


class TestCollectNativeCrash:
    """Test native crash recovery."""

    def test_no_file_returns_false(self, tmp_path):
        native_path = tmp_path / "native_crash.log"
        with patch("shared.crash_log.NATIVE_CRASH_LOG_PATH", native_path):
            assert collect_native_crash() is False

    def test_empty_file_returns_false(self, tmp_path):
        native_path = tmp_path / "native_crash.log"
        native_path.write_text("")
        with patch("shared.crash_log.NATIVE_CRASH_LOG_PATH", native_path):
            assert collect_native_crash() is False

    def test_recovers_native_crash(self, tmp_path):
        native_path = tmp_path / "native_crash.log"
        crash_log = tmp_path / "crash_log.txt"
        native_path.write_text("Fatal Python error: Segmentation fault\nThread 0x...")
        with (
            patch("shared.crash_log.NATIVE_CRASH_LOG_PATH", native_path),
            patch("shared.crash_log.CRASH_LOG_PATH", crash_log),
            patch("shared.crash_log._ensure_dir"),
        ):
            result = collect_native_crash()
            assert result is True
            content = crash_log.read_text()
            assert "NATIVE CRASH" in content
            assert "Segmentation fault" in content


class TestClearCrashLog:
    """Test clearing crash log."""

    def test_clear_removes_file(self, tmp_path):
        crash_log = tmp_path / "crash_log.txt"
        crash_log.write_text("some crashes")
        with patch("shared.crash_log.CRASH_LOG_PATH", crash_log):
            clear_crash_log()
            assert not crash_log.exists()

    def test_clear_noop_if_no_file(self, tmp_path):
        crash_log = tmp_path / "crash_log.txt"
        with patch("shared.crash_log.CRASH_LOG_PATH", crash_log):
            clear_crash_log()  # Should not raise


class TestPaths:
    """Test path accessors."""

    def test_crash_log_path(self):
        path = get_crash_log_path()
        assert isinstance(path, Path)
        assert "crash_log" in str(path)

    def test_native_crash_log_path(self):
        path = get_native_crash_log_path()
        assert isinstance(path, Path)
        assert "native_crash" in str(path)


class TestLogExit:
    """Test exit logging."""

    def test_log_exit_creates_entry(self, tmp_path):
        crash_log = tmp_path / "crash_log.txt"
        with patch("shared.crash_log.CRASH_LOG_PATH", crash_log), patch("shared.crash_log._ensure_dir"):
            log_exit("Normal exit")

            content = crash_log.read_text()
            assert "EXIT: Normal exit" in content

    def test_log_exit_with_signal(self, tmp_path):
        crash_log = tmp_path / "crash_log.txt"
        with patch("shared.crash_log.CRASH_LOG_PATH", crash_log), patch("shared.crash_log._ensure_dir"):
            log_exit("Signal: SIGTERM", signal_num=15)

            content = crash_log.read_text()
            assert "EXIT: Signal: SIGTERM" in content
            assert "Signal number: 15" in content

    def test_log_exit_prepends(self, tmp_path):
        crash_log = tmp_path / "crash_log.txt"
        crash_log.write_text("OLD ENTRY\n")
        with patch("shared.crash_log.CRASH_LOG_PATH", crash_log), patch("shared.crash_log._ensure_dir"):
            log_exit("Test exit")

            content = crash_log.read_text()
            # New entry should be before old
            assert content.index("EXIT: Test exit") < content.index("OLD ENTRY")
