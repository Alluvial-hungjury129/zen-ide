"""Tests for editor.format_manager."""

import json
import os
import tempfile
from unittest.mock import patch

from editor.format_manager import (
    _build_cmd,
    _find_venv_binary,
    _format_json,
    _resolve_binary,
    _run_external,
    format_content,
)


class TestFormatJson:
    def test_formats_valid_json(self):
        raw = '{"b":1,"a":2}'
        result = _format_json(raw)
        assert result is not None
        parsed = json.loads(result)
        assert parsed == {"b": 1, "a": 2}
        assert result.endswith("\n")
        # 2-space indent
        assert "  " in result

    def test_returns_none_for_invalid_json(self):
        assert _format_json("not json") is None

    def test_returns_none_for_empty(self):
        assert _format_json("") is None


class TestFormatContent:
    def test_returns_none_when_format_on_save_disabled(self):
        with patch("shared.settings.get_setting", return_value=False):
            result = format_content("/tmp/test.py", "x = 1")
            assert result is None

    def test_returns_none_for_unknown_extension(self):
        with patch(
            "shared.settings.get_setting",
            side_effect=lambda key, default=None: {
                "editor.format_on_save": True,
                "formatters": {},
            }.get(key, default),
        ):
            result = format_content("/tmp/test.xyz", "content")
            assert result is None

    def test_returns_none_for_no_extension(self):
        with patch(
            "shared.settings.get_setting",
            side_effect=lambda key, default=None: {
                "editor.format_on_save": True,
                "formatters": {},
            }.get(key, default),
        ):
            result = format_content("/tmp/Makefile", "content")
            assert result is None

    def test_builtin_json_formatter(self):
        with patch(
            "shared.settings.get_setting",
            side_effect=lambda key, default=None: {
                "editor.format_on_save": True,
                "formatters": {".json": "builtin"},
            }.get(key, default),
        ):
            raw = '{"key":"value"}'
            result = format_content("/tmp/test.json", raw)
            assert result is not None
            assert json.loads(result) == {"key": "value"}

    def test_external_formatter_success(self):
        with (
            patch(
                "shared.settings.get_setting",
                side_effect=lambda key, default=None: {
                    "editor.format_on_save": True,
                    "formatters": {".py": "cat"},
                }.get(key, default),
            ),
            patch("editor.format_manager._build_cmd", return_value=["/bin/cat"]),
            patch("editor.format_manager.subprocess.run") as mock_run,
        ):
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "formatted"
            result = format_content("/tmp/test.py", "original")
            assert result == "formatted"

    def test_external_formatter_failure_returns_none(self):
        with (
            patch(
                "shared.settings.get_setting",
                side_effect=lambda key, default=None: {
                    "editor.format_on_save": True,
                    "formatters": {".py": "bad-formatter {file}"},
                }.get(key, default),
            ),
            patch("editor.format_manager._build_cmd", return_value=["/bin/false"]),
            patch("editor.format_manager.subprocess.run") as mock_run,
        ):
            mock_run.return_value.returncode = 1
            mock_run.return_value.stdout = ""
            result = format_content("/tmp/test.py", "original")
            assert result is None


class TestFindVenvBinary:
    """Test virtual environment binary discovery."""

    def test_finds_binary_in_venv(self):
        """Finds binary in .venv/bin directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create .venv/bin/ruff
            venv_bin = os.path.join(tmpdir, ".venv", "bin")
            os.makedirs(venv_bin)
            binary_path = os.path.join(venv_bin, "ruff")
            # Create executable file
            with open(binary_path, "w") as f:
                f.write("#!/bin/sh\n")
            os.chmod(binary_path, 0o755)

            result = _find_venv_binary("ruff", tmpdir)
            assert result == binary_path

    def test_finds_binary_in_venv_no_dot(self):
        """Finds binary in venv/bin (without dot)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create venv/bin/black
            venv_bin = os.path.join(tmpdir, "venv", "bin")
            os.makedirs(venv_bin)
            binary_path = os.path.join(venv_bin, "black")
            with open(binary_path, "w") as f:
                f.write("#!/bin/sh\n")
            os.chmod(binary_path, 0o755)

            result = _find_venv_binary("black", tmpdir)
            assert result == binary_path

    def test_returns_none_when_not_found(self):
        """Returns None when binary not found in any venv."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = _find_venv_binary("nonexistent", tmpdir)
            assert result is None

    def test_walks_up_directory_tree(self):
        """Searches parent directories for venv."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create venv at root level
            venv_bin = os.path.join(tmpdir, ".venv", "bin")
            os.makedirs(venv_bin)
            binary_path = os.path.join(venv_bin, "ruff")
            with open(binary_path, "w") as f:
                f.write("#!/bin/sh\n")
            os.chmod(binary_path, 0o755)

            # Start from nested subdirectory
            nested = os.path.join(tmpdir, "src", "app", "utils")
            os.makedirs(nested)

            result = _find_venv_binary("ruff", nested)
            assert result == binary_path

    def test_requires_executable_permission(self):
        """Only returns binary if it's executable."""
        with tempfile.TemporaryDirectory() as tmpdir:
            venv_bin = os.path.join(tmpdir, ".venv", "bin")
            os.makedirs(venv_bin)
            binary_path = os.path.join(venv_bin, "ruff")
            # Create non-executable file
            with open(binary_path, "w") as f:
                f.write("#!/bin/sh\n")
            # Don't set executable permission

            result = _find_venv_binary("ruff", tmpdir)
            assert result is None


class TestResolveBinary:
    """Test binary resolution (venv first, then PATH)."""

    def test_prefers_venv_binary(self):
        """Returns venv binary over PATH binary."""
        with (
            patch("editor.format_manager._find_venv_binary", return_value="/project/.venv/bin/ruff"),
            patch("shutil.which", return_value="/usr/bin/ruff"),
        ):
            result = _resolve_binary("ruff", "/project")
            assert result == "/project/.venv/bin/ruff"

    def test_falls_back_to_path(self):
        """Falls back to PATH when venv binary not found."""
        with (
            patch("editor.format_manager._find_venv_binary", return_value=None),
            patch("shutil.which", return_value="/usr/bin/ruff"),
        ):
            result = _resolve_binary("ruff", "/project")
            assert result == "/usr/bin/ruff"

    def test_returns_none_when_not_found(self):
        """Returns None when binary not found anywhere."""
        with (
            patch("editor.format_manager._find_venv_binary", return_value=None),
            patch("shutil.which", return_value=None),
        ):
            result = _resolve_binary("nonexistent", "/project")
            assert result is None


class TestBuildCmd:
    """Test command building from template."""

    def test_replaces_file_placeholder(self):
        """Replaces {file} with actual path."""
        with patch("editor.format_manager._resolve_binary", return_value="/usr/bin/ruff"):
            result = _build_cmd("ruff format {file}", "/project/main.py", "/project")
            assert result is not None
            assert "/project/main.py" in result

    def test_resolves_binary(self):
        """Resolves binary to absolute path."""
        with patch("editor.format_manager._resolve_binary", return_value="/usr/bin/ruff"):
            result = _build_cmd("ruff format", "/project/main.py", "/project")
            assert result is not None
            assert result[0] == "/usr/bin/ruff"

    def test_returns_none_for_unresolved_binary(self):
        """Returns None when binary cannot be resolved."""
        with patch("editor.format_manager._resolve_binary", return_value=None):
            result = _build_cmd("nonexistent format", "/project/main.py", "/project")
            assert result is None

    def test_returns_none_for_empty_template(self):
        """Returns None for empty command template."""
        result = _build_cmd("", "/project/main.py", "/project")
        assert result is None

    def test_handles_quoted_arguments(self):
        """Handles quoted arguments in template."""
        with patch("editor.format_manager._resolve_binary", return_value="/usr/bin/cmd"):
            result = _build_cmd('cmd --arg "value with spaces"', "/project/file.py", "/project")
            assert result is not None
            assert "value with spaces" in result

    def test_returns_none_for_malformed_quotes(self):
        """Returns None for malformed quote syntax."""
        result = _build_cmd('cmd "unclosed quote', "/project/file.py", "/project")
        assert result is None


class TestRunExternal:
    """Test external formatter execution."""

    def test_returns_output_on_success(self):
        """Returns stdout on successful execution."""
        with (
            patch("editor.format_manager._build_cmd", return_value=["/usr/bin/cat"]),
            patch("editor.format_manager.subprocess.run") as mock_run,
        ):
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "formatted content"

            result = _run_external("cat", "/tmp/test.py", "input")
            assert result == "formatted content"

    def test_returns_none_on_failure(self):
        """Returns None when formatter exits with error."""
        with (
            patch("editor.format_manager._build_cmd", return_value=["/usr/bin/false"]),
            patch("editor.format_manager.subprocess.run") as mock_run,
        ):
            mock_run.return_value.returncode = 1
            mock_run.return_value.stdout = ""

            result = _run_external("false", "/tmp/test.py", "input")
            assert result is None

    def test_returns_none_on_timeout(self):
        """Returns None when formatter times out."""
        import subprocess

        with (
            patch("editor.format_manager._build_cmd", return_value=["/usr/bin/sleep"]),
            patch(
                "editor.format_manager.subprocess.run",
                side_effect=subprocess.TimeoutExpired("sleep", 10),
            ),
        ):
            result = _run_external("sleep 100", "/tmp/test.py", "input")
            assert result is None

    def test_returns_none_when_build_cmd_fails(self):
        """Returns None when command cannot be built."""
        with patch("editor.format_manager._build_cmd", return_value=None):
            result = _run_external("nonexistent", "/tmp/test.py", "input")
            assert result is None

    def test_returns_none_on_empty_output(self):
        """Returns None when formatter produces no output."""
        with (
            patch("editor.format_manager._build_cmd", return_value=["/usr/bin/echo"]),
            patch("editor.format_manager.subprocess.run") as mock_run,
        ):
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = ""

            result = _run_external("echo", "/tmp/test.py", "input")
            assert result is None


class TestFormatContentPipeline:
    """Test formatter pipeline execution."""

    def test_runs_multiple_formatters_in_sequence(self):
        """Runs list of formatters as pipeline."""
        with (
            patch(
                "shared.settings.get_setting",
                side_effect=lambda key, default=None: {
                    "editor.format_on_save": True,
                    "formatters": {".py": ["isort", "black"]},
                }.get(key, default),
            ),
            patch("editor.format_manager._run_external") as mock_run,
        ):
            # Each formatter transforms the content
            mock_run.side_effect = ["isort output", "black output"]

            result = format_content("/tmp/test.py", "original")

            assert result == "black output"
            assert mock_run.call_count == 2

    def test_pipeline_passes_intermediate_results(self):
        """Each formatter receives output from previous."""
        call_inputs = []

        def capture_input(cmd, path, content):
            call_inputs.append(content)
            return f"output from {cmd}"

        with (
            patch(
                "shared.settings.get_setting",
                side_effect=lambda key, default=None: {
                    "editor.format_on_save": True,
                    "formatters": {".py": ["first", "second"]},
                }.get(key, default),
            ),
            patch("editor.format_manager._run_external", side_effect=capture_input),
        ):
            format_content("/tmp/test.py", "original")

            # First formatter gets original content
            assert call_inputs[0] == "original"
            # Second formatter gets first formatter's output
            assert call_inputs[1] == "output from first"

    def test_pipeline_continues_on_formatter_failure(self):
        """Pipeline continues if one formatter fails."""
        with (
            patch(
                "shared.settings.get_setting",
                side_effect=lambda key, default=None: {
                    "editor.format_on_save": True,
                    "formatters": {".py": ["failing", "working"]},
                }.get(key, default),
            ),
            patch("editor.format_manager._run_external") as mock_run,
        ):
            # First formatter fails, second succeeds
            mock_run.side_effect = [None, "formatted"]

            result = format_content("/tmp/test.py", "original")

            # Second formatter still runs and its output is used
            assert result == "formatted"

    def test_returns_none_if_all_formatters_fail(self):
        """Returns None if no formatter produces output."""
        with (
            patch(
                "shared.settings.get_setting",
                side_effect=lambda key, default=None: {
                    "editor.format_on_save": True,
                    "formatters": {".py": ["bad1", "bad2"]},
                }.get(key, default),
            ),
            patch("editor.format_manager._run_external", return_value=None),
        ):
            result = format_content("/tmp/test.py", "original")
            assert result is None
