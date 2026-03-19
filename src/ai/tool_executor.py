"""
Tool executor for AI agentic coding in Zen IDE.

Executes tools requested by AI models: file operations (read, write, edit),
file discovery (list, search), and shell commands. All paths are resolved
relative to the workspace root.
"""

import glob as glob_module
import os
import re
import subprocess
from pathlib import Path
from typing import Optional

_COMMAND_TIMEOUT_S = 30
_MAX_FILE_SIZE = 512 * 1024  # 512 KB read limit
_MAX_OUTPUT_CHARS = 64_000  # Truncate long outputs
_MAX_RESULTS = 200  # Max glob/grep results


class ToolExecutor:
    """Executes AI tool calls within a workspace."""

    def __init__(self, workspace_root: str):
        self._root = Path(workspace_root).resolve()

    def execute(self, tool_name: str, tool_input: dict) -> str:
        """Execute a tool call and return the result as text.

        Returns a human-readable result string (file content, success
        message, error message, command output, etc.).
        """
        handlers = {
            "read_file": self._read_file,
            "write_file": self._write_file,
            "edit_file": self._edit_file,
            "list_files": self._list_files,
            "search_files": self._search_files,
            "run_command": self._run_command,
        }
        handler = handlers.get(tool_name)
        if not handler:
            return f"Unknown tool: {tool_name}"
        try:
            return handler(tool_input)
        except Exception as e:
            return f"Error executing {tool_name}: {e}"

    def _resolve_path(self, file_path: str) -> Path:
        """Resolve a path relative to the workspace root.

        Raises ValueError if the resolved path escapes the workspace.
        """
        p = Path(file_path)
        if p.is_absolute():
            resolved = p.resolve()
        else:
            resolved = (self._root / p).resolve()
        # Security: prevent path traversal outside workspace
        try:
            resolved.relative_to(self._root)
        except ValueError:
            raise ValueError(f"Path {file_path} is outside the workspace")
        return resolved

    def _read_file(self, inp: dict) -> str:
        file_path = inp.get("file_path", "")
        if not file_path:
            return "Error: file_path is required"
        path = self._resolve_path(file_path)
        if not path.is_file():
            return f"Error: File not found: {file_path}"
        size = path.stat().st_size
        if size > _MAX_FILE_SIZE:
            return f"Error: File too large ({size} bytes, limit {_MAX_FILE_SIZE})"
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            return f"Error reading file: {e}"
        return _truncate(content, _MAX_OUTPUT_CHARS)

    def _write_file(self, inp: dict) -> str:
        file_path = inp.get("file_path", "")
        content = inp.get("content", "")
        if not file_path:
            return "Error: file_path is required"
        if content is None:
            return "Error: content is required"
        path = self._resolve_path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            path.write_text(content, encoding="utf-8")
        except Exception as e:
            return f"Error writing file: {e}"
        return f"Successfully wrote {len(content)} characters to {file_path}"

    def _edit_file(self, inp: dict) -> str:
        file_path = inp.get("file_path", "")
        old_text = inp.get("old_text", "")
        new_text = inp.get("new_text", "")
        if not file_path:
            return "Error: file_path is required"
        if not old_text:
            return "Error: old_text is required"
        path = self._resolve_path(file_path)
        if not path.is_file():
            return f"Error: File not found: {file_path}"
        try:
            content = path.read_text(encoding="utf-8")
        except Exception as e:
            return f"Error reading file: {e}"
        count = content.count(old_text)
        if count == 0:
            return f"Error: old_text not found in {file_path}"
        if count > 1:
            return f"Error: old_text matches {count} locations in {file_path} (must be unique)"
        new_content = content.replace(old_text, new_text, 1)
        try:
            path.write_text(new_content, encoding="utf-8")
        except Exception as e:
            return f"Error writing file: {e}"
        return f"Successfully edited {file_path}"

    def _list_files(self, inp: dict) -> str:
        pattern = inp.get("pattern", "")
        search_path = inp.get("path", "")
        if not pattern:
            return "Error: pattern is required"
        base = self._resolve_path(search_path) if search_path else self._root
        if not base.is_dir():
            return f"Error: Directory not found: {search_path}"
        matches = sorted(glob_module.glob(str(base / pattern), recursive=True))
        # Convert to relative paths
        results = []
        for m in matches[:_MAX_RESULTS]:
            try:
                results.append(str(Path(m).relative_to(self._root)))
            except ValueError:
                results.append(m)
        if not results:
            return f"No files matching '{pattern}'"
        text = "\n".join(results)
        if len(matches) > _MAX_RESULTS:
            text += f"\n... and {len(matches) - _MAX_RESULTS} more"
        return text

    def _search_files(self, inp: dict) -> str:
        pattern = inp.get("pattern", "")
        search_path = inp.get("path", "")
        include = inp.get("include", "")
        if not pattern:
            return "Error: pattern is required"
        base = self._resolve_path(search_path) if search_path else self._root
        if not base.is_dir():
            return f"Error: Directory not found: {search_path}"
        # Use grep if available, otherwise fall back to Python
        return self._grep(pattern, base, include)

    def _grep(self, pattern: str, base: Path, include: Optional[str]) -> str:
        """Run grep (or ripgrep) to search file contents."""
        cmd: list[str] = []
        # Prefer ripgrep, fall back to grep
        for exe in ("rg", "grep"):
            if _which(exe):
                cmd.append(exe)
                break
        if not cmd:
            return self._python_grep(pattern, base, include)

        if cmd[0] == "rg":
            cmd.extend(["-n", "--no-heading", "--max-count", "5", "--max-filesize", "1M"])
            if include:
                cmd.extend(["-g", include])
            cmd.extend([pattern, str(base)])
        else:
            cmd.extend(["-rn", "--max-count=5"])
            if include:
                cmd.extend(["--include", include])
            cmd.extend([pattern, str(base)])

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=_COMMAND_TIMEOUT_S, cwd=str(self._root))
            output = result.stdout.strip()
        except subprocess.TimeoutExpired:
            return "Error: Search timed out"
        except Exception as e:
            return f"Error running search: {e}"
        if not output:
            return f"No matches found for '{pattern}'"
        # Make paths relative
        lines = []
        for line in output.split("\n")[:_MAX_RESULTS]:
            line = line.replace(str(self._root) + "/", "")
            lines.append(line)
        return _truncate("\n".join(lines), _MAX_OUTPUT_CHARS)

    def _python_grep(self, pattern: str, base: Path, include: Optional[str]) -> str:
        """Pure-Python fallback for grep."""
        try:
            regex = re.compile(pattern)
        except re.error as e:
            return f"Error: Invalid regex pattern: {e}"
        results = []
        for root, _, files in os.walk(base):
            for fname in files:
                if include and not glob_module.fnmatch.fnmatch(fname, include):
                    continue
                fpath = Path(root) / fname
                try:
                    text = fpath.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue
                for i, line in enumerate(text.split("\n"), 1):
                    if regex.search(line):
                        rel = str(fpath.relative_to(self._root))
                        results.append(f"{rel}:{i}:{line.rstrip()}")
                        if len(results) >= _MAX_RESULTS:
                            break
                if len(results) >= _MAX_RESULTS:
                    break
            if len(results) >= _MAX_RESULTS:
                break
        if not results:
            return f"No matches found for '{pattern}'"
        return _truncate("\n".join(results), _MAX_OUTPUT_CHARS)

    def _run_command(self, inp: dict) -> str:
        command = inp.get("command", "")
        if not command:
            return "Error: command is required"
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=_COMMAND_TIMEOUT_S,
                cwd=str(self._root),
                env={**os.environ, "TERM": "dumb"},
            )
            parts = []
            if result.stdout.strip():
                parts.append(result.stdout.strip())
            if result.stderr.strip():
                parts.append(f"stderr:\n{result.stderr.strip()}")
            if result.returncode != 0:
                parts.append(f"Exit code: {result.returncode}")
            output = "\n".join(parts) if parts else "(no output)"
            return _truncate(output, _MAX_OUTPUT_CHARS)
        except subprocess.TimeoutExpired:
            return f"Error: Command timed out after {_COMMAND_TIMEOUT_S}s"
        except Exception as e:
            return f"Error running command: {e}"


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + f"\n... (truncated, {len(text)} total characters)"


def _which(name: str) -> Optional[str]:
    """Check if an executable is available."""
    try:
        result = subprocess.run(["which", name], capture_output=True, text=True, timeout=2)
        return result.stdout.strip() if result.returncode == 0 else None
    except Exception:
        return None
