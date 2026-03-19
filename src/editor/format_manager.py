"""
Format Manager - runs code formatters on file content before saving.

Formatters are configured per file extension via settings (formatters.{ext}).
Each entry maps an extension to a shell command (or a list of commands run as
a pipeline) that reads stdin and writes formatted output to stdout.
The placeholder {file} is replaced with the file path so formatters can
infer language/config.

Special value "builtin" triggers built-in formatters (e.g. JSON pretty-print).
"""

import json
import os
import shlex
import shutil
import subprocess


def _find_venv_binary(binary: str, start_dir: str) -> str | None:
    """Search for a binary in .venv/bin or venv/bin walking up from start_dir."""
    d = os.path.abspath(start_dir)
    for _ in range(20):
        for venv_name in (".venv", "venv"):
            candidate = os.path.join(d, venv_name, "bin", binary)
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                return candidate
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    return None


def _resolve_binary(binary: str, cwd: str) -> str | None:
    """Resolve a binary name to an absolute path (venv first, then PATH)."""
    path = _find_venv_binary(binary, cwd)
    if path:
        return path
    return shutil.which(binary)


def _build_cmd(template: str, file_path: str, cwd: str) -> list[str] | None:
    """Build command args from a template string, resolving the binary."""
    cmd_str = template.replace("{file}", file_path)
    try:
        parts = shlex.split(cmd_str)
    except ValueError:
        return None
    if not parts:
        return None
    binary = _resolve_binary(parts[0], cwd)
    if not binary:
        return None
    parts[0] = binary
    return parts


def _format_json(content: str) -> str | None:
    """Built-in JSON formatter: pretty-print with 2-space indent."""
    try:
        parsed = json.loads(content)
        return json.dumps(parsed, indent=2, ensure_ascii=False) + "\n"
    except (json.JSONDecodeError, ValueError):
        return None


def _run_external(cmd_template: str, file_path: str, content: str) -> str | None:
    """Run an external stdin→stdout command, returning output or None."""
    cwd = os.path.dirname(os.path.abspath(file_path))
    cmd_args = _build_cmd(cmd_template, file_path, cwd)
    if not cmd_args:
        return None
    try:
        result = subprocess.run(
            cmd_args,
            input=content,
            capture_output=True,
            text=True,
            timeout=10,
            cwd=cwd,
        )
        if result.returncode == 0 and result.stdout:
            return result.stdout
    except (subprocess.TimeoutExpired, OSError, ValueError):
        pass
    return None


def format_content(file_path: str, content: str) -> str | None:
    """Format file content using configured formatter pipeline.

    The formatters setting maps extensions to either a single command string,
    a list of commands (run sequentially as a pipeline), or "builtin".

    Returns the processed content, or None if nothing is configured
    or processing failed (caller should use original content).
    """
    from shared.settings import get_setting

    if not get_setting("editor.format_on_save", True):
        return None

    ext = os.path.splitext(file_path)[1].lower()
    if not ext:
        return None

    formatters = get_setting("formatters", {})
    command = formatters.get(ext)
    if not command:
        return None

    if command == "builtin":
        if ext == ".json":
            return _format_json(content)
        return None

    # Normalize to a list of commands
    commands = command if isinstance(command, list) else [command]

    result = content
    changed = False
    for cmd in commands:
        output = _run_external(cmd, file_path, result)
        if output is not None:
            result = output
            changed = True

    return result if changed else None
