"""Tests for shared.diagnostics_manager — pure parsing logic."""

import json
import os

from shared.diagnostics_manager import (
    SEVERITY_ERROR,
    SEVERITY_INFO,
    SEVERITY_WARNING,
    _is_ignored_path,
    _line_parse,
    _line_parse_batch,
    _ruff_parse,
    _ruff_parse_batch,
)


# ---------------------------------------------------------------------------
# _is_ignored_path
# ---------------------------------------------------------------------------
class TestIsIgnoredPath:
    def test_node_modules(self):
        assert _is_ignored_path("/project/node_modules/pkg/index.js")

    def test_pycache(self):
        assert _is_ignored_path("/project/__pycache__/mod.cpython.pyc")

    def test_venv(self):
        assert _is_ignored_path("/project/.venv/lib/python3.13/site.py")
        assert _is_ignored_path("/project/venv/bin/python")

    def test_normal_path(self):
        assert not _is_ignored_path("/project/src/main.py")

    def test_empty_path(self):
        assert not _is_ignored_path("")


# ---------------------------------------------------------------------------
# _ruff_parse
# ---------------------------------------------------------------------------
class TestRuffParse:
    def test_empty_input(self):
        assert _ruff_parse("", "") == []

    def test_json_diagnostics(self):
        items = [
            {
                "code": "E501",
                "message": "Line too long",
                "location": {"row": 10, "column": 1},
                "end_location": {"row": 10, "column": 120},
            }
        ]
        result = _ruff_parse(json.dumps(items))
        assert len(result) == 1
        d = result[0]
        assert d.line == 10
        assert d.col == 1
        assert d.severity == SEVERITY_ERROR
        assert d.code == "E501"
        assert d.source == "ruff"
        assert d.end_line == 10
        assert d.end_col == 120

    def test_warning_code(self):
        items = [
            {
                "code": "W291",
                "message": "trailing whitespace",
                "location": {"row": 5, "column": 20},
                "end_location": {},
            }
        ]
        result = _ruff_parse(json.dumps(items))
        assert result[0].severity == SEVERITY_WARNING

    def test_f_code_is_error(self):
        items = [
            {
                "code": "F401",
                "message": "unused import",
                "location": {"row": 1, "column": 1},
                "end_location": {},
            }
        ]
        result = _ruff_parse(json.dumps(items))
        assert result[0].severity == SEVERITY_ERROR

    def test_stderr_parse_error(self):
        stderr = "error: Failed to parse test.py:5:10: unexpected token"
        result = _ruff_parse("", stderr)
        assert len(result) == 1
        assert result[0].line == 5
        assert result[0].col == 10
        assert result[0].severity == SEVERITY_ERROR
        assert result[0].code == "E999"

    def test_invalid_json_returns_empty(self):
        assert _ruff_parse("not json") == []

    def test_combined_stdout_and_stderr(self):
        items = [
            {
                "code": "E501",
                "message": "line too long",
                "location": {"row": 1, "column": 1},
                "end_location": {},
            }
        ]
        stderr = "error: Failed to parse bad.py:3:1: bad syntax"
        result = _ruff_parse(json.dumps(items), stderr)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# _ruff_parse_batch
# ---------------------------------------------------------------------------
class TestRuffParseBatch:
    def test_groups_by_filename(self):
        items = [
            {
                "filename": "src/a.py",
                "code": "E501",
                "message": "line too long",
                "location": {"row": 1, "column": 1},
                "end_location": {},
            },
            {
                "filename": "src/b.py",
                "code": "F401",
                "message": "unused import",
                "location": {"row": 2, "column": 1},
                "end_location": {},
            },
        ]
        result = _ruff_parse_batch(json.dumps(items))
        assert os.path.normpath("src/a.py") in result
        assert os.path.normpath("src/b.py") in result

    def test_stderr_grouped_by_filename(self):
        stderr = "error: Failed to parse src/c.py:1:1: bad"
        result = _ruff_parse_batch("", stderr)
        assert os.path.normpath("src/c.py") in result


# ---------------------------------------------------------------------------
# _line_parse
# ---------------------------------------------------------------------------
class TestLineParse:
    def test_empty_input(self):
        assert _line_parse("", "") == []

    def test_basic_line_format(self):
        stdout = "test.py:10:5: something went wrong"
        result = _line_parse(stdout)
        assert len(result) == 1
        d = result[0]
        assert d.line == 10
        assert d.col == 5
        assert d.severity == SEVERITY_WARNING
        assert "something went wrong" in d.message

    def test_error_severity(self):
        stdout = "test.py:1:1: error: undefined name 'foo'"
        result = _line_parse(stdout)
        assert result[0].severity == SEVERITY_ERROR
        assert "undefined name 'foo'" in result[0].message

    def test_info_severity(self):
        stdout = "test.py:1:1: note: see docs"
        result = _line_parse(stdout)
        assert result[0].severity == SEVERITY_INFO

    def test_code_extraction(self):
        stdout = "test.py:1:1: E501 line too long"
        result = _line_parse(stdout)
        assert result[0].code == "E501"
        assert "line too long" in result[0].message

    def test_multiple_lines(self):
        stdout = "a.py:1:1: err1\nb.py:2:2: err2"
        result = _line_parse(stdout)
        assert len(result) == 2

    def test_stderr_parsed_too(self):
        result = _line_parse("", "err.py:5:3: warning: unused var")
        assert len(result) == 1
        assert result[0].severity == SEVERITY_WARNING

    def test_non_matching_lines_skipped(self):
        stdout = "some random output\ntest.py:1:1: real error\nmore junk"
        result = _line_parse(stdout)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# _line_parse_batch
# ---------------------------------------------------------------------------
class TestLineParseBatch:
    def test_groups_by_filename(self):
        stdout = "src/a.py:1:1: err1\nsrc/b.py:2:2: err2\nsrc/a.py:3:3: err3"
        result = _line_parse_batch(stdout)
        a_key = os.path.normpath("src/a.py")
        b_key = os.path.normpath("src/b.py")
        assert len(result[a_key]) == 2
        assert len(result[b_key]) == 1

    def test_empty_returns_empty_dict(self):
        assert _line_parse_batch("") == {}
