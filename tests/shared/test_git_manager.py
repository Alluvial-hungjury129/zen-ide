"""Tests for GitManager parsing and caching logic."""

import subprocess
import time
from unittest.mock import MagicMock, patch

from shared.git_manager import GitManager


class TestGitManagerCache:
    """Test caching behavior."""

    def test_repo_root_cache_hit(self):
        """Cached repo root is returned without subprocess."""
        gm = GitManager()
        now = time.time()
        gm._repo_root_cache["/test/dir"] = ("/test", now)
        with patch.object(gm, "_query_repo_root") as mock:
            result = gm.get_repo_root("/test/dir")
            assert result == "/test"
            mock.assert_not_called()

    def test_repo_root_cache_expired(self):
        """Expired cache triggers a new query."""
        gm = GitManager()
        old_time = time.time() - gm.REPO_ROOT_CACHE_TTL - 1
        gm._repo_root_cache["/test/dir"] = ("/test", old_time)
        with patch.object(gm, "_query_repo_root", return_value="/test/new"):
            result = gm.get_repo_root("/test/dir")
            assert result == "/test/new"

    def test_subdirectory_uses_parent_cache(self):
        """Subdirectory under known repo root reuses cached root."""
        gm = GitManager()
        now = time.time()
        gm._repo_root_cache["/repo"] = ("/repo", now)
        with patch.object(gm, "_query_repo_root") as mock:
            import os

            result = gm.get_repo_root(f"/repo{os.sep}src{os.sep}main.py")
            assert result == "/repo"
            mock.assert_not_called()

    def test_clear_all(self):
        """clear_all empties all caches."""
        gm = GitManager()
        gm._repo_root_cache["a"] = ("b", time.time())
        gm._branch_cache["c"] = ("main", time.time())
        gm._modified_files_cache["d"] = ({}, time.time())
        gm.clear_all()
        assert len(gm._repo_root_cache) == 0
        assert len(gm._branch_cache) == 0
        assert len(gm._modified_files_cache) == 0


class TestGitStatusParsing:
    """Test git status output parsing via get_detailed_status."""

    def _make_gm_with_status(self, porcelain_output):
        """Create GitManager with mocked subprocess for status."""
        gm = GitManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = porcelain_output
        with patch("subprocess.run", return_value=mock_result):
            return gm.get_detailed_status("/repo")

    def test_modified_file(self):
        """Modified file gets 'M' status."""
        status = self._make_gm_with_status(" M src/main.py\0")
        assert status["/repo/src/main.py"] == "M"

    def test_added_file(self):
        """Staged new file gets 'A' status."""
        status = self._make_gm_with_status("A  new_file.py\0")
        assert status["/repo/new_file.py"] == "A"

    def test_deleted_file(self):
        """Deleted file gets 'D' status."""
        status = self._make_gm_with_status(" D old_file.py\0")
        assert status["/repo/old_file.py"] == "D"

    def test_untracked_file(self):
        """Untracked file gets '?' status."""
        status = self._make_gm_with_status("?? new.txt\0")
        assert status["/repo/new.txt"] == "?"

    def test_conflict_file(self):
        """Conflicted file gets 'U' status."""
        status = self._make_gm_with_status("UU conflict.py\0")
        assert status["/repo/conflict.py"] == "U"

    def test_renamed_file(self):
        """Renamed file tracks destination with 'R' status."""
        status = self._make_gm_with_status("R  old.py -> new.py\0")
        assert status["/repo/new.py"] == "R"

    def test_empty_output(self):
        """Empty git status output returns empty dict."""
        status = self._make_gm_with_status("")
        assert status == {}

    def test_multiple_files(self):
        """Multiple files parsed correctly."""
        output = " M a.py\0A  b.py\0?? c.txt\0"
        status = self._make_gm_with_status(output)
        assert len(status) == 3

    def test_untracked_directory_trailing_slash_stripped(self):
        """Untracked directory reported with trailing slash gets normalized path."""
        status = self._make_gm_with_status("?? new_folder/\0")
        assert "/repo/new_folder" in status
        assert status["/repo/new_folder"] == "?"
        # Ensure no trailing-slash key exists
        assert "/repo/new_folder/" not in status


class TestGitLogParsing:
    """Test git log output parsing."""

    def test_parse_commit_log(self):
        """Parses pipe-delimited git log output."""
        gm = GitManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "abc123|Fix bug|Alice|2024-01-15\ndef456|Add feature|Bob|2024-01-14"

        with (
            patch.object(gm, "get_repo_root", return_value="/repo"),
            patch("subprocess.run", return_value=mock_result),
        ):
            commits = gm.get_file_commits("/repo/main.py")

        assert len(commits) == 2
        assert commits[0]["sha"] == "abc123"
        assert commits[0]["message"] == "Fix bug"
        assert commits[0]["author"] == "Alice"
        assert commits[0]["date"] == "2024-01-15"

    def test_no_repo_returns_empty(self):
        """Returns empty list when not in a repo."""
        gm = GitManager()
        with patch.object(gm, "get_repo_root", return_value=None):
            assert gm.get_file_commits("/not/a/repo/file.py") == []


class TestBranchCache:
    """Test branch caching logic."""

    def test_branch_cache_hit(self):
        """Cached branch is returned without subprocess."""
        gm = GitManager()
        gm._branch_cache["/repo"] = ("feature-x", time.time())
        with patch("subprocess.run") as mock:
            result = gm.get_current_branch("/repo")
            assert result == "feature-x"
            mock.assert_not_called()


class TestGetFileAtRef:
    """Test file content retrieval at specific git refs."""

    def test_get_file_at_ref_success(self):
        """Returns file content at specified ref."""
        gm = GitManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "file content at ref"

        with patch("subprocess.run", return_value=mock_result):
            result = gm.get_file_at_ref("/repo", "src/main.py", "abc123")
            assert result == "file content at ref"

    def test_get_file_at_ref_not_found(self):
        """Returns None when file not in ref."""
        gm = GitManager()
        mock_result = MagicMock()
        mock_result.returncode = 1

        with patch("subprocess.run", return_value=mock_result):
            result = gm.get_file_at_ref("/repo", "nonexistent.py", "main")
            assert result is None

    def test_get_file_at_ref_timeout(self):
        """Returns None on timeout."""
        gm = GitManager()
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("git", 10)):
            result = gm.get_file_at_ref("/repo", "file.py", "main")
            assert result is None

    def test_get_file_at_main_branch_tries_multiple(self):
        """Tries main, master, develop in order."""
        gm = GitManager()
        call_count = [0]

        def mock_get_file(repo, path, ref):
            call_count[0] += 1
            if ref == "develop":
                return "content from develop"
            return None

        with patch.object(gm, "get_file_at_ref", side_effect=mock_get_file):
            result = gm.get_file_at_main_branch("/repo", "file.py")
            assert result == "content from develop"
            assert call_count[0] == 3  # Tried main, master, then develop


class TestIsFileTracked:
    """Test file tracking status."""

    def test_tracked_file(self):
        """Returns True for tracked files."""
        gm = GitManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "src/main.py"

        with patch("subprocess.run", return_value=mock_result):
            result = gm.is_file_tracked("/repo", "src/main.py")
            assert result is True

    def test_untracked_file(self):
        """Returns False for untracked files."""
        gm = GitManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""

        with patch("subprocess.run", return_value=mock_result):
            result = gm.is_file_tracked("/repo", "new_file.py")
            assert result is False

    def test_git_error(self):
        """Returns False on git error."""
        gm = GitManager()
        mock_result = MagicMock()
        mock_result.returncode = 128

        with patch("subprocess.run", return_value=mock_result):
            result = gm.is_file_tracked("/repo", "file.py")
            assert result is False


class TestDiscardChanges:
    """Test discard changes functionality."""

    def test_discard_changes_success(self):
        """Successfully discards changes to tracked file."""
        gm = GitManager()
        mock_result = MagicMock()
        mock_result.returncode = 0

        with (
            patch.object(gm, "get_repo_root", return_value="/repo"),
            patch.object(gm, "get_detailed_status", return_value={"/repo/file.py": "M"}),
            patch("subprocess.run", return_value=mock_result),
            patch.object(gm, "invalidate_modified_files"),
        ):
            success, msg = gm.discard_changes("/repo/file.py")
            assert success is True
            assert "discarded" in msg.lower()

    def test_discard_untracked_file_fails(self):
        """Cannot discard untracked files."""
        gm = GitManager()
        with (
            patch.object(gm, "get_repo_root", return_value="/repo"),
            patch.object(gm, "get_detailed_status", return_value={"/repo/new.py": "?"}),
        ):
            success, msg = gm.discard_changes("/repo/new.py")
            assert success is False
            assert "untracked" in msg.lower()

    def test_discard_not_in_repo(self):
        """Fails for files not in a git repo."""
        gm = GitManager()
        with patch.object(gm, "get_repo_root", return_value=None):
            success, msg = gm.discard_changes("/not/a/repo/file.py")
            assert success is False
            assert "repository" in msg.lower()

    def test_discard_falls_back_to_checkout(self):
        """Falls back to git checkout if git restore fails."""
        gm = GitManager()
        restore_result = MagicMock()
        restore_result.returncode = 1
        checkout_result = MagicMock()
        checkout_result.returncode = 0

        with (
            patch.object(gm, "get_repo_root", return_value="/repo"),
            patch.object(gm, "get_detailed_status", return_value={"/repo/file.py": "M"}),
            patch("subprocess.run", side_effect=[restore_result, checkout_result]),
            patch.object(gm, "invalidate_modified_files"),
        ):
            success, msg = gm.discard_changes("/repo/file.py")
            assert success is True


class TestGetAllDetailedStatus:
    """Test multi-workspace status retrieval."""

    def test_batches_by_repo_root(self):
        """Queries each repo root only once."""
        gm = GitManager()
        query_count = [0]

        def mock_get_status(repo_root):
            query_count[0] += 1
            return {f"{repo_root}/file.py": "M"}

        with (
            patch.object(gm, "get_repo_root", side_effect=lambda p: "/repo" if "repo" in p else None),
            patch.object(gm, "get_detailed_status", side_effect=mock_get_status),
            patch("os.path.isdir", return_value=True),
        ):
            # Two folders: /repo in git, /other not in git
            result = gm.get_all_detailed_status(["/repo", "/other"])

            # Only one repo query (for /repo)
            assert query_count[0] == 1
            assert "/repo/file.py" in result

    def test_handles_non_repo_folders(self):
        """Skips folders not in any repo."""
        gm = GitManager()
        with (
            patch.object(gm, "get_repo_root", return_value=None),
            patch("os.path.isdir", return_value=True),
        ):
            result = gm.get_all_detailed_status(["/not/a/repo"])
            assert result == {}

    def test_handles_nonexistent_folders(self):
        """Skips non-existent folders."""
        gm = GitManager()
        with patch("os.path.isdir", return_value=False):
            result = gm.get_all_detailed_status(["/nonexistent"])
            assert result == {}


class TestModifiedFilesCache:
    """Test modified files cache behavior."""

    def test_cache_invalidation_single_repo(self):
        """Can invalidate cache for single repo."""
        gm = GitManager()
        gm._modified_files_cache["/repo1"] = ({}, time.time())
        gm._modified_files_cache["/repo2"] = ({}, time.time())

        gm.invalidate_modified_files("/repo1")

        assert "/repo1" not in gm._modified_files_cache
        assert "/repo2" in gm._modified_files_cache

    def test_cache_invalidation_all(self):
        """Can invalidate cache for all repos."""
        gm = GitManager()
        gm._modified_files_cache["/repo1"] = ({}, time.time())
        gm._modified_files_cache["/repo2"] = ({}, time.time())

        gm.invalidate_modified_files()

        assert len(gm._modified_files_cache) == 0
