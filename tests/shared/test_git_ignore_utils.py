"""Tests for GitIgnoreUtils pattern parsing and matching."""

import os
import tempfile

from shared.git_ignore_utils import GitIgnoreUtils, find_workspace_root


class TestParseGitignoreFile:
    """Test static _parse_gitignore_file method."""

    def test_empty_file(self):
        """Empty file returns empty list."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".gitignore", delete=False) as f:
            f.write("")
            path = f.name
        try:
            assert GitIgnoreUtils._parse_gitignore_file(path) == []
        finally:
            os.unlink(path)

    def test_comments_ignored(self):
        """Lines starting with # are ignored."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".gitignore", delete=False) as f:
            f.write("# comment\nnode_modules\n")
            path = f.name
        try:
            patterns = GitIgnoreUtils._parse_gitignore_file(path)
            assert len(patterns) == 1
            assert patterns[0][0] == "node_modules"
        finally:
            os.unlink(path)

    def test_negation_pattern(self):
        """Lines starting with ! are marked as negation."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".gitignore", delete=False) as f:
            f.write("*.log\n!important.log\n")
            path = f.name
        try:
            patterns = GitIgnoreUtils._parse_gitignore_file(path)
            assert patterns[0] == ("*.log", False, False)
            assert patterns[1] == ("important.log", True, False)
        finally:
            os.unlink(path)

    def test_dir_only_pattern(self):
        """Lines ending with / are marked as dir-only."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".gitignore", delete=False) as f:
            f.write("build/\n")
            path = f.name
        try:
            patterns = GitIgnoreUtils._parse_gitignore_file(path)
            assert patterns[0] == ("build", False, True)
        finally:
            os.unlink(path)

    def test_leading_slash_stripped(self):
        """Leading / is stripped from patterns."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".gitignore", delete=False) as f:
            f.write("/dist\n")
            path = f.name
        try:
            patterns = GitIgnoreUtils._parse_gitignore_file(path)
            assert patterns[0][0] == "dist"
        finally:
            os.unlink(path)

    def test_nonexistent_file(self):
        """Non-existent file returns empty list."""
        assert GitIgnoreUtils._parse_gitignore_file("/nonexistent/.gitignore") == []


class TestIsIgnored:
    """Test is_ignored pattern matching logic."""

    def test_git_directory_always_ignored(self):
        """The .git directory is always ignored."""
        with tempfile.TemporaryDirectory() as tmpdir:
            matcher = GitIgnoreUtils(tmpdir)
            assert matcher.is_ignored(os.path.join(tmpdir, ".git"), is_dir=True)

    def test_simple_pattern_matches(self):
        """Simple basename pattern matches files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            gitignore = os.path.join(tmpdir, ".gitignore")
            with open(gitignore, "w") as f:
                f.write("*.pyc\n")
            matcher = GitIgnoreUtils(tmpdir)
            assert matcher.is_ignored(os.path.join(tmpdir, "test.pyc"))

    def test_simple_pattern_no_match(self):
        """Non-matching files are not ignored."""
        with tempfile.TemporaryDirectory() as tmpdir:
            gitignore = os.path.join(tmpdir, ".gitignore")
            with open(gitignore, "w") as f:
                f.write("*.pyc\n")
            matcher = GitIgnoreUtils(tmpdir)
            assert not matcher.is_ignored(os.path.join(tmpdir, "test.py"))

    def test_dir_only_pattern_skips_files(self):
        """Dir-only patterns don't match files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            gitignore = os.path.join(tmpdir, ".gitignore")
            with open(gitignore, "w") as f:
                f.write("build/\n")
            matcher = GitIgnoreUtils(tmpdir)
            assert matcher.is_ignored(os.path.join(tmpdir, "build"), is_dir=True)
            assert not matcher.is_ignored(os.path.join(tmpdir, "build"), is_dir=False)

    def test_negation_overrides_ignore(self):
        """Negation pattern un-ignores a file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            gitignore = os.path.join(tmpdir, ".gitignore")
            with open(gitignore, "w") as f:
                f.write("*.log\n!important.log\n")
            matcher = GitIgnoreUtils(tmpdir)
            assert matcher.is_ignored(os.path.join(tmpdir, "debug.log"))
            assert not matcher.is_ignored(os.path.join(tmpdir, "important.log"))

    def test_directory_name_pattern(self):
        """Directory name patterns match at any depth."""
        with tempfile.TemporaryDirectory() as tmpdir:
            gitignore = os.path.join(tmpdir, ".gitignore")
            with open(gitignore, "w") as f:
                f.write("__pycache__\n")
            matcher = GitIgnoreUtils(tmpdir)
            assert matcher.is_ignored(os.path.join(tmpdir, "src", "__pycache__"), is_dir=True)

    def test_path_with_slash_matches_full_path(self):
        """Pattern with / matches against full relative path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            gitignore = os.path.join(tmpdir, ".gitignore")
            with open(gitignore, "w") as f:
                f.write("docs/internal\n")
            matcher = GitIgnoreUtils(tmpdir)
            assert matcher.is_ignored(os.path.join(tmpdir, "docs", "internal"), is_dir=True)


class TestFindWorkspaceRoot:
    """Test find_workspace_root path mapping."""

    def test_exact_match(self):
        assert find_workspace_root("/home/user/project", ["/home/user/project"]) == "/home/user/project"

    def test_child_path(self):
        roots = ["/home/user/project"]
        assert find_workspace_root(f"/home/user/project{os.sep}src{os.sep}main.py", roots) == "/home/user/project"

    def test_no_match(self):
        assert find_workspace_root("/other/path", ["/home/user/project"]) is None

    def test_multiple_roots_picks_correct(self):
        roots = ["/a/b", "/c/d"]
        assert find_workspace_root(f"/c/d{os.sep}file.py", roots) == "/c/d"
