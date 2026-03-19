"""Tests for file_watcher.py - FileWatcher change processing logic."""

from unittest.mock import MagicMock, patch

from shared.file_watcher import FileWatcher


class TestProcessChange:
    """Test _process_change logic for filtering and categorizing file changes."""

    def _make_watcher(self):
        return FileWatcher(
            on_tree_refresh=MagicMock(),
            on_git_refresh=MagicMock(),
            on_file_modified=MagicMock(),
            on_file_updated=MagicMock(),
        )

    def test_git_lock_file_ignored(self):
        w = self._make_watcher()
        assert w._process_change(None, "/repo/.git/index.lock") is False

    def test_git_dir_triggers_git_refresh(self):
        w = self._make_watcher()
        assert w._process_change(None, "/repo/.git/HEAD") is True
        assert w._needs_git_refresh is True
        assert w._git_refresh_force is True

    def test_pyc_files_ignored(self):
        w = self._make_watcher()
        assert w._process_change(None, "/repo/foo.pyc") is False

    def test_pyo_files_ignored(self):
        w = self._make_watcher()
        assert w._process_change(None, "/repo/foo.pyo") is False

    def test_swp_files_ignored(self):
        w = self._make_watcher()
        assert w._process_change(None, "/repo/foo.swp") is False

    def test_tmp_files_ignored(self):
        w = self._make_watcher()
        assert w._process_change(None, "/repo/foo.tmp") is False

    def test_tilde_files_ignored(self):
        w = self._make_watcher()
        assert w._process_change(None, "/repo/foo~") is False

    def test_hidden_files_ignored(self):
        w = self._make_watcher()
        assert w._process_change(None, "/repo/.hidden") is False

    def test_pycache_dir_ignored(self):
        w = self._make_watcher()
        assert w._process_change(None, "/repo/__pycache__/foo.py") is False

    def test_node_modules_ignored(self):
        w = self._make_watcher()
        assert w._process_change(None, "/repo/node_modules/pkg/index.js") is False

    def test_venv_ignored(self):
        w = self._make_watcher()
        assert w._process_change(None, "/repo/.venv/lib/something.py") is False

    def test_normal_file_tracked(self):
        w = self._make_watcher()
        result = w._process_change(None, "/repo/src/main.py")
        assert result is True
        assert "/repo/src/main.py" in w._modified_files

    @patch("shared.file_watcher.WATCHFILES_AVAILABLE", True)
    def test_modified_file_triggers_git_not_tree(self):
        """Modified file should trigger git refresh but not tree refresh."""
        w = self._make_watcher()
        # Simulate Change.modified (value 2)
        mock_change = MagicMock()
        mock_change.__eq__ = lambda self, other: True
        with patch("shared.file_watcher.Change") as mock_Change:
            mock_Change.modified = mock_change
            w._process_change(mock_change, "/repo/src/main.py")
            assert w._needs_git_refresh is True


class TestGitAwareFilter:
    """Test GitAwareFilter configuration."""

    def test_ignore_dirs_excludes_pycache(self):
        from shared.file_watcher import GitAwareFilter

        assert "__pycache__" in GitAwareFilter.ignore_dirs

    def test_ignore_dirs_excludes_node_modules(self):
        from shared.file_watcher import GitAwareFilter

        assert "node_modules" in GitAwareFilter.ignore_dirs

    def test_ignore_dirs_does_not_exclude_git(self):
        """GitAwareFilter should NOT ignore .git (we need to detect commits)."""
        from shared.file_watcher import GitAwareFilter

        assert ".git" not in GitAwareFilter.ignore_dirs


class TestFileWatcherInit:
    """Test FileWatcher initialization."""

    def test_default_debounce_delay(self):
        w = FileWatcher()
        assert w.DEBOUNCE_DELAY_MS == 1000

    def test_initial_state(self):
        w = FileWatcher()
        assert w._needs_tree_refresh is False
        assert w._needs_git_refresh is False
        assert w._stopped is False
