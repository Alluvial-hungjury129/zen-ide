"""
Diagnostics Manager - runs linters and collects diagnostics per file.

Runs language-specific linters as subprocesses, parses their output, and
provides diagnostics as a list of (line, col, severity, message) tuples.

Linter commands are configurable via settings (diagnostics.{ext}).
Supported output formats:
  - "ruff": ruff JSON output
  - "line": generic file:line:col: message (mypy, flake8, gcc, etc.)

Linting is triggered on file save and runs in a background thread.
Results are delivered to the main thread via main_thread_call().
"""

import os
import shlex
import shutil
import subprocess
import threading
from dataclasses import dataclass, field

from shared.main_thread import main_thread_call

# Severity levels
SEVERITY_ERROR = "error"
SEVERITY_WARNING = "warning"
SEVERITY_INFO = "info"

_SKIP_SEGMENTS = (
    # JS / Node
    "/node_modules/",
    # Python caches & virtual envs
    "/__pycache__/",
    "/.venv/",
    "/venv/",
    "/env/",
    "/.env/",
    "/site-packages/",
    # VCS internals
    "/.git/",
    # Build / dist artifacts
    "/dist/",
    "/build/",
    "/.eggs/",
    "/.tox/",
    "/.nox/",
)

_SYSTEM_PREFIXES = (
    "/usr/lib/",
    "/usr/local/lib/",
    "/usr/local/Cellar/",
    "/opt/homebrew/",
    "/Library/Frameworks/Python.framework/",
)


def _is_ignored_path(path: str) -> bool:
    """Return True if path is inside a library, venv, or system directory."""
    if any(seg in path for seg in _SKIP_SEGMENTS):
        return True
    return any(path.startswith(p) for p in _SYSTEM_PREFIXES)


def _find_venv_binary(binary: str, start_dir: str) -> str | None:
    """Search for a binary in .venv/bin or venv/bin walking up from start_dir."""
    d = os.path.abspath(start_dir)
    for _ in range(20):  # limit depth
        for venv_name in (".venv", "venv"):
            candidate = os.path.join(d, venv_name, "bin", binary)
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                return candidate
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    return None


def _build_batch_args(template: str, file_paths: list[str], cwd: str) -> list[str] | None:
    """Build command args for running a linter on multiple files at once."""
    marker = "\x00BATCH\x00"
    cmd_str = template.replace("{file}", marker)
    try:
        parts = shlex.split(cmd_str)
    except ValueError:
        return None
    binary = _find_venv_binary(parts[0], cwd)
    if not binary:
        binary = shutil.which(parts[0])
    if not binary:
        return None
    parts[0] = binary
    result = []
    for p in parts:
        if marker in p:
            result.extend(file_paths)
        else:
            result.append(p)
    return result


@dataclass
class Diagnostic:
    """A single diagnostic (error/warning) for a file."""

    line: int  # 1-based
    col: int  # 1-based
    severity: str  # "error", "warning", "info"
    message: str
    code: str = ""  # linter rule code (e.g. "E501")
    source: str = ""  # linter name (e.g. "ruff")
    end_line: int = 0  # 1-based, 0 = not specified
    end_col: int = 0  # 1-based, 0 = not specified


@dataclass
class _FileState:
    """Per-file diagnostic state."""

    diagnostics: list[Diagnostic] = field(default_factory=list)
    callbacks: list = field(default_factory=list)


# --- Parsers (moved to shared.linter_parsers) ---
# Re-exported here for backward compatibility.
from shared.linter_parsers import (  # noqa: E402, F401
    _BATCH_PARSERS,
    _CODE_RE,
    _LINE_RE,
    _PARSERS,
    _SEVERITY_RE,
    _line_parse,
    _line_parse_batch,
    _ruff_parse,
    _ruff_parse_batch,
)


def _get_linter_configs() -> dict[str, tuple]:
    """Build linter configs from settings (diagnostics)."""
    from shared.settings import get_setting

    linters = get_setting("diagnostics", {})
    configs = {}

    for ext, cfg in linters.items():
        if isinstance(cfg, str):
            # Shorthand: just a command string, default to "line" format
            command_template = cfg
            fmt = "line"
        elif isinstance(cfg, dict):
            command_template = cfg.get("command", "")
            fmt = cfg.get("format", "line")
        else:
            continue

        if not command_template:
            continue

        parse_fn = _PARSERS.get(fmt, _line_parse)

        def make_args_fn(tmpl=command_template):
            def args_fn(file_path: str) -> list[str] | None:
                cmd_str = tmpl.replace("{file}", file_path)
                try:
                    parts = shlex.split(cmd_str)
                except ValueError:
                    return None
                # Prefer project venv binary over system-wide install
                binary = _find_venv_binary(parts[0], os.path.dirname(file_path))
                if not binary:
                    binary = shutil.which(parts[0])
                if not binary:
                    return None
                parts[0] = binary
                return parts

            return args_fn

        configs[ext] = (make_args_fn(), parse_fn, command_template, fmt)

    return configs


class DiagnosticsManager:
    """Singleton manager for file diagnostics."""

    _instance = None

    @classmethod
    def get_instance(cls) -> "DiagnosticsManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self._files: dict[str, _FileState] = {}
        self._debounce_timers: dict[str, int] = {}  # repo_root -> GLib timer id
        self._workspace_scanning = False
        self._workspace_folders: list[str] = []  # workspace roots from last scan
        self._global_callback = None  # called per-file on any repo scan

    def set_global_callback(self, callback):
        """Set a callback(file_path, diagnostics) fired for every file on repo scan."""
        self._global_callback = callback

    def _get_repo_root(self, file_path: str) -> str:
        """Get the workspace folder (repo root) containing the file."""
        norm = os.path.normpath(file_path)
        for folder in self._workspace_folders:
            nf = os.path.normpath(folder)
            if norm.startswith(nf + os.sep) or norm == nf:
                return folder
        return os.path.dirname(file_path)

    def run_diagnostics_deferred(self, file_path: str, callback=None, delay_ms: int = 500):
        """Run diagnostics after a delay, debounced per repo root.

        If called again for a file in the same repo before the delay expires,
        the previous timer is cancelled and a new one starts.
        """
        from gi.repository import GLib

        repo_root = self._get_repo_root(file_path)

        # Cancel any pending timer for this repo
        old_timer = self._debounce_timers.pop(repo_root, None)
        if old_timer is not None:
            GLib.source_remove(old_timer)

        def _fire():
            self._debounce_timers.pop(repo_root, None)
            self.run_diagnostics(file_path, callback=callback)
            return False  # Don't repeat

        timer_id = GLib.timeout_add(delay_ms, _fire)
        self._debounce_timers[repo_root] = timer_id

    def _run_repo_lint(
        self, repo_root: str, ext: str, config: tuple, trigger_file: str | None = None, trigger_callback=None
    ):
        """Run linter on entire repo root, update all diagnostics.

        Runs in a background thread. Uses "." as target so the linter
        discovers files itself (respecting .gitignore, configs, etc.).

        Args:
            repo_root: Absolute path to the repo root directory.
            ext: File extension (e.g. ".py") to identify the linter.
            config: Linter config tuple (args_fn, parse_fn, template, fmt).
            trigger_file: If set, the file that triggered the scan.
            trigger_callback: If set, called with (trigger_file, diagnostics) on main thread.
        """
        _, _, template, fmt = config
        batch_parse_fn = _BATCH_PARSERS.get(fmt, _line_parse_batch)
        cmd_args = _build_batch_args(template, ["."], repo_root)
        if not cmd_args:
            return

        def _do_lint():
            try:
                result = subprocess.run(
                    cmd_args,
                    capture_output=True,
                    text=True,
                    timeout=60,
                    cwd=repo_root,
                )
                file_diagnostics = batch_parse_fn(result.stdout, result.stderr)
            except (subprocess.TimeoutExpired, OSError, ValueError):
                return
            except Exception:
                return

            # Convert relative paths to absolute
            abs_diagnostics: dict[str, list[Diagnostic]] = {}
            for fpath, diags in file_diagnostics.items():
                if not os.path.isabs(fpath):
                    fpath = os.path.normpath(os.path.join(repo_root, fpath))
                else:
                    fpath = os.path.normpath(fpath)
                abs_diagnostics[fpath] = diags

            main_thread_call(
                self._on_repo_lint_results,
                repo_root,
                ext,
                abs_diagnostics,
                trigger_file,
                trigger_callback,
            )

        thread = threading.Thread(target=_do_lint, daemon=True)
        thread.start()

    def _on_repo_lint_results(self, repo_root, ext, abs_diagnostics, trigger_file, trigger_callback):
        """Handle repo lint results on main thread."""
        repo_prefix = os.path.normpath(repo_root) + os.sep

        # Clear diagnostics for files in this repo with the same extension
        # that no longer appear in the output
        for cached_path in list(self._files.keys()):
            if cached_path.startswith(repo_prefix) or cached_path == os.path.normpath(repo_root):
                if os.path.splitext(cached_path)[1].lower() == ext:
                    if cached_path not in abs_diagnostics:
                        self._files[cached_path].diagnostics = []
                        if self._global_callback:
                            self._global_callback(cached_path, [])

        # Set new diagnostics
        for fpath, diags in abs_diagnostics.items():
            state = self._files.get(fpath)
            if state is None:
                state = _FileState()
                self._files[fpath] = state
            state.diagnostics = diags
            if self._global_callback:
                self._global_callback(fpath, diags)

        # Fire trigger callback for the specific file that triggered the scan
        if trigger_callback and trigger_file:
            trigger_norm = os.path.normpath(trigger_file)
            trigger_diags = abs_diagnostics.get(trigger_norm, [])
            trigger_callback(trigger_file, trigger_diags)

    def run_workspace_diagnostics(self, folders: list[str], callback=None):
        """Scan workspace folders: run linter once per repo root.

        Runs in a background thread. Each folder is treated as a repo root
        and the linter is invoked with "." as target.

        Args:
            folders: List of workspace root paths.
            callback: Optional callable(file_path, diagnostics) for each file.
        """
        if self._workspace_scanning:
            return
        self._workspace_scanning = True
        self._workspace_folders = list(folders)

        configs = _get_linter_configs()
        if not configs:
            self._workspace_scanning = False
            return

        def _scan():
            for folder in folders:
                for ext, config in configs.items():
                    _, _, template, fmt = config
                    batch_parse_fn = _BATCH_PARSERS.get(fmt, _line_parse_batch)
                    cmd_args = _build_batch_args(template, ["."], folder)
                    if not cmd_args:
                        continue
                    try:
                        result = subprocess.run(
                            cmd_args,
                            capture_output=True,
                            text=True,
                            timeout=60,
                            cwd=folder,
                        )
                        file_diagnostics = batch_parse_fn(result.stdout, result.stderr)
                    except (subprocess.TimeoutExpired, OSError, ValueError):
                        file_diagnostics = {}

                    # Convert relative paths to absolute
                    for fpath, diags in file_diagnostics.items():
                        if not os.path.isabs(fpath):
                            abs_path = os.path.normpath(os.path.join(folder, fpath))
                        else:
                            abs_path = os.path.normpath(fpath)
                        main_thread_call(self._on_workspace_file_result, abs_path, diags, callback)

            main_thread_call(self._on_workspace_scan_done)

        thread = threading.Thread(target=_scan, daemon=True)
        thread.start()

    def _on_workspace_file_result(self, file_path, diagnostics, callback):
        """Handle a single file result from workspace scan (main thread)."""
        norm = os.path.normpath(file_path)
        state = self._files.get(norm)
        if state is None:
            state = _FileState()
            self._files[norm] = state
        state.diagnostics = diagnostics
        if callback:
            callback(file_path, diagnostics)

    def _on_workspace_scan_done(self):
        """Called when workspace scan completes."""
        self._workspace_scanning = False

    def run_diagnostics(self, file_path: str, callback=None):
        """Run linter for the repo containing the given file.

        Scans the entire repo root (not just the single file) so results
        are consistent with workspace scans. Updates diagnostics for all
        files in the repo.

        Args:
            file_path: Absolute path to the file that triggered the scan.
            callback: Optional callable(file_path, diagnostics) called on main thread
                      when results are ready (for the trigger file only).
        """
        if not file_path or not os.path.isfile(file_path):
            return

        if _is_ignored_path(file_path):
            self._files[os.path.normpath(file_path)] = _FileState()
            if callback:
                main_thread_call(callback, file_path, [])
            return

        ext = os.path.splitext(file_path)[1].lower()
        configs = _get_linter_configs()
        config = configs.get(ext)
        if not config:
            self._files[os.path.normpath(file_path)] = _FileState()
            if callback:
                main_thread_call(callback, file_path, [])
            return

        repo_root = self._get_repo_root(file_path)
        self._run_repo_lint(repo_root, ext, config, trigger_file=file_path, trigger_callback=callback)

    def get_diagnostics(self, file_path: str) -> list[Diagnostic]:
        """Get cached diagnostics for a file."""
        norm = os.path.normpath(file_path)
        state = self._files.get(norm)
        return state.diagnostics if state else []

    def has_diagnostics_data(self, file_path: str) -> bool:
        """Return True if diagnostic data exists for this file (even if empty)."""
        return os.path.normpath(file_path) in self._files

    def clear(self, file_path: str):
        """Clear diagnostics for a file."""
        norm = os.path.normpath(file_path)
        if norm in self._files:
            self._files[norm].diagnostics = []

    def get_all_diagnostics(self) -> dict[str, list[Diagnostic]]:
        """Get all cached diagnostics across all files (non-empty only)."""
        return {fp: state.diagnostics for fp, state in self._files.items() if state.diagnostics and not _is_ignored_path(fp)}

    def get_total_counts(self) -> tuple[int, int]:
        """Get (error_count, warning_count) totals across all files."""
        errors = 0
        warnings = 0
        for fp, state in self._files.items():
            if _is_ignored_path(fp):
                continue
            for d in state.diagnostics:
                if d.severity == SEVERITY_ERROR:
                    errors += 1
                elif d.severity == SEVERITY_WARNING:
                    warnings += 1
        return errors, warnings


def get_diagnostics_manager() -> DiagnosticsManager:
    """Get the singleton DiagnosticsManager instance."""
    return DiagnosticsManager.get_instance()
