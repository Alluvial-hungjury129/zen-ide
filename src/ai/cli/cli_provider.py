"""CLIProvider — abstract interface for AI CLI providers.

Each provider (Claude, Copilot, …) subclasses ``CLIProvider`` to expose
binary discovery, model listing, argv building, and session management.
"""

from __future__ import annotations

import pathlib
from abc import ABC, abstractmethod
from typing import Optional

# Per-binary model cache: binary path → list of model strings.
# Only non-empty results are cached; empty results are retried on next call.
_model_cache: dict[str, list[str]] = {}


class CLIProvider(ABC):
    """Abstract interface that every AI CLI backend must implement."""

    # --- identity ---

    @property
    @abstractmethod
    def id(self) -> str:
        """Unique key, e.g. ``"claude_cli"``."""

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Human-readable name shown in UI, e.g. ``"Claude"``."""

    # --- binary discovery ---

    @abstractmethod
    def find_binary(self) -> Optional[str]:
        """Return the absolute path to the CLI binary, or ``None``."""

    # --- models ---

    def fetch_models(self, binary: str) -> list[str]:
        """Return available model names/aliases.  Results are cached."""
        if binary in _model_cache:
            return _model_cache[binary]
        models = self._fetch_models_impl(binary)
        if models:
            _model_cache[binary] = models
        return models

    @abstractmethod
    def _fetch_models_impl(self, binary: str) -> list[str]:
        """Provider-specific model discovery (no caching)."""

    # --- argv building ---

    @abstractmethod
    def build_argv(
        self,
        binary: str,
        *,
        resume_session: str | None = None,
        continue_last: bool = False,
        yolo: bool = False,
        model: str = "",
        extra_dirs: list[str] | None = None,
    ) -> list[str]:
        """Build the full argv list for spawning the CLI process."""

    @abstractmethod
    def append_ide_context(self, argv: list[str], editor_ctx: dict) -> None:
        """Append IDE context (system prompt, instructions file, etc.) to *argv*."""

    # --- session management ---

    @abstractmethod
    def sessions_dir(self, cwd: str | None = None) -> pathlib.Path | None:
        """Return the on-disk directory where sessions are stored, or ``None``."""

    @abstractmethod
    def list_sessions(self, cwd: str | None = None) -> set[str]:
        """Return the set of session IDs currently on disk."""

    @abstractmethod
    def session_exists(self, session_id: str, cwd: str | None = None) -> bool:
        """Return True if *session_id* can be found on disk."""

    # --- install instructions ---

    @abstractmethod
    def install_lines(self) -> list[str]:
        """Return ANSI-formatted lines with install instructions."""
