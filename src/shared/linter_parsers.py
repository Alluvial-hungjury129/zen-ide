"""
Linter output parsing logic.

Parsers for different linter output formats (ruff JSON, generic line format).
Used by DiagnosticsManager to convert raw linter output into Diagnostic objects.
"""

import json
import os
import re

from shared.diagnostics_manager import SEVERITY_ERROR, SEVERITY_INFO, SEVERITY_WARNING, Diagnostic

# --- Built-in parsers ---


def _ruff_parse(stdout: str, stderr: str = "") -> list[Diagnostic]:
    """Parse ruff JSON output into diagnostics."""
    results = []

    # Parse stderr for syntax/parse errors (ruff reports these to stderr)
    if stderr:
        for line in stderr.splitlines():
            m = re.match(r"error: Failed to parse .+?:(\d+):(\d+): (.+)", line)
            if m:
                results.append(
                    Diagnostic(
                        line=int(m.group(1)),
                        col=int(m.group(2)),
                        severity=SEVERITY_ERROR,
                        message=m.group(3),
                        code="E999",
                        source="ruff",
                    )
                )

    # Parse stdout JSON for lint diagnostics
    if stdout.strip():
        try:
            items = json.loads(stdout)
        except (json.JSONDecodeError, ValueError):
            items = []

        for item in items:
            severity = SEVERITY_WARNING
            code = item.get("code", "")
            if code.startswith(("E", "F")):
                severity = SEVERITY_ERROR
            elif code.startswith("W"):
                severity = SEVERITY_WARNING

            end_loc = item.get("end_location", {})
            results.append(
                Diagnostic(
                    line=item.get("location", {}).get("row", 1),
                    col=item.get("location", {}).get("column", 1),
                    severity=severity,
                    message=item.get("message", ""),
                    code=code,
                    source="ruff",
                    end_line=end_loc.get("row", 0),
                    end_col=end_loc.get("column", 0),
                )
            )

    return results


def _ruff_parse_batch(stdout: str, stderr: str = "") -> dict[str, list[Diagnostic]]:
    """Parse ruff JSON output for multiple files, grouped by filename."""
    results: dict[str, list[Diagnostic]] = {}
    if stderr:
        for line in stderr.splitlines():
            m = re.match(r"error: Failed to parse (.+?):(\d+):(\d+): (.+)", line)
            if m:
                fname = os.path.normpath(m.group(1))
                results.setdefault(fname, []).append(
                    Diagnostic(
                        line=int(m.group(2)),
                        col=int(m.group(3)),
                        severity=SEVERITY_ERROR,
                        message=m.group(4),
                        code="E999",
                        source="ruff",
                    )
                )
    if stdout.strip():
        try:
            items = json.loads(stdout)
        except (json.JSONDecodeError, ValueError):
            items = []
        for item in items:
            severity = SEVERITY_WARNING
            code = item.get("code") or ""
            if code.startswith(("E", "F")):
                severity = SEVERITY_ERROR
            elif code.startswith("W"):
                severity = SEVERITY_WARNING
            fname = os.path.normpath(item.get("filename") or "")
            end_loc = item.get("end_location", {})
            results.setdefault(fname, []).append(
                Diagnostic(
                    line=item.get("location", {}).get("row", 1),
                    col=item.get("location", {}).get("column", 1),
                    severity=severity,
                    message=item.get("message", ""),
                    code=code,
                    source="ruff",
                    end_line=end_loc.get("row", 0),
                    end_col=end_loc.get("column", 0),
                )
            )
    return results


# Regex for generic line format: file:line:col: message
_LINE_RE = re.compile(r"^.+?:(\d+):(\d+):\s*(.+)$")
# Optional severity prefix in the message
_SEVERITY_RE = re.compile(r"^(error|warning|info|note):\s*(.+)$", re.IGNORECASE)
# Optional code prefix like [E501] or (E501)
_CODE_RE = re.compile(r"^\[?([A-Z]\w*)\]?\s+(.+)$")


def _line_parse(stdout: str, stderr: str = "") -> list[Diagnostic]:
    """Parse generic line format: file:line:col: message.

    Works with mypy, flake8, pylint, gcc, rustc, and similar tools.
    """
    results = []
    for text in (stdout, stderr):
        if not text:
            continue
        for raw_line in text.splitlines():
            m = _LINE_RE.match(raw_line)
            if not m:
                continue
            line_num = int(m.group(1))
            col_num = int(m.group(2))
            msg = m.group(3).strip()

            # Extract severity from message prefix
            severity = SEVERITY_WARNING
            sm = _SEVERITY_RE.match(msg)
            if sm:
                sev_str = sm.group(1).lower()
                if sev_str == "error":
                    severity = SEVERITY_ERROR
                elif sev_str in ("info", "note"):
                    severity = SEVERITY_INFO
                msg = sm.group(2).strip()

            # Extract code from message
            code = ""
            cm = _CODE_RE.match(msg)
            if cm:
                code = cm.group(1)
                msg = cm.group(2).strip()

            results.append(
                Diagnostic(
                    line=line_num,
                    col=col_num,
                    severity=severity,
                    message=msg,
                    code=code,
                    source="linter",
                )
            )
    return results


_BATCH_LINE_RE = re.compile(r"^(.+?):(\d+):(\d+):\s*(.+)$")


def _line_parse_batch(stdout: str, stderr: str = "") -> dict[str, list[Diagnostic]]:
    """Parse generic line format for multiple files, grouped by filename."""
    results: dict[str, list[Diagnostic]] = {}
    for text in (stdout, stderr):
        if not text:
            continue
        for raw_line in text.splitlines():
            m = _BATCH_LINE_RE.match(raw_line)
            if not m:
                continue
            fname = os.path.normpath(m.group(1))
            line_num = int(m.group(2))
            col_num = int(m.group(3))
            msg = m.group(4).strip()
            severity = SEVERITY_WARNING
            sm = _SEVERITY_RE.match(msg)
            if sm:
                sev_str = sm.group(1).lower()
                if sev_str == "error":
                    severity = SEVERITY_ERROR
                elif sev_str in ("info", "note"):
                    severity = SEVERITY_INFO
                msg = sm.group(2).strip()
            code = ""
            cm = _CODE_RE.match(msg)
            if cm:
                code = cm.group(1)
                msg = cm.group(2).strip()
            results.setdefault(fname, []).append(
                Diagnostic(
                    line=line_num,
                    col=col_num,
                    severity=severity,
                    message=msg,
                    code=code,
                    source="linter",
                )
            )
    return results


_PARSERS = {
    "ruff": _ruff_parse,
    "line": _line_parse,
}

_BATCH_PARSERS = {
    "ruff": _ruff_parse_batch,
    "line": _line_parse_batch,
}
