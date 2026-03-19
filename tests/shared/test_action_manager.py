"""Tests for action_manager.py - ActionManager."""

from unittest.mock import patch

from main.action_manager import ActionManager


class TestGetModKeys:
    """Platform-specific modifier key detection."""

    @patch("main.action_manager.platform.system", return_value="Darwin")
    def test_macos_keys(self, _mock):
        mod, mod_shift = ActionManager.get_mod_keys()
        assert mod == "<Meta>"
        assert mod_shift == "<Meta><Shift>"

    @patch("main.action_manager.platform.system", return_value="Linux")
    def test_linux_keys(self, _mock):
        mod, mod_shift = ActionManager.get_mod_keys()
        assert mod == "<Control>"
        assert mod_shift == "<Control><Shift>"

    @patch("main.action_manager.platform.system", return_value="Windows")
    def test_windows_keys(self, _mock):
        mod, mod_shift = ActionManager.get_mod_keys()
        assert mod == "<Control>"
        assert mod_shift == "<Control><Shift>"
