"""AI debug log for Zen IDE.

Append-mode structured logging of all AI HTTP traffic to
~/.zen_ide/ai_debug_log.txt.  Always on (lightweight), with
automatic rotation when the file exceeds _MAX_SIZE_BYTES.

Usage::

    from shared.ai_debug_log import ai_log

    ai_log.request("anthropic", "claude-sonnet-4", msg_count=5)
    ai_log.chunk(234)                     # bytes received
    ai_log.complete(1.8, 4096)            # duration_s, response_len
    ai_log.error("HTTP 500: internal …")
    ai_log.tool_use("read_file", {"file_path": "src/main.py"})
    ai_log.tool_result("read_file", ok=True, chars=1200)
    ai_log.event("stale_watchdog", "cancelled after 90s")
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from pathlib import Path

_LOG_PATH = Path.home() / ".zen_ide" / "ai_debug_log.txt"
_MAX_SIZE_BYTES = 2 * 1024 * 1024  # 2 MB — rotate when exceeded
_LOCK = threading.Lock()


def get_ai_debug_log_path() -> Path:
    """Return the path to the AI debug log file."""
    return _LOG_PATH


class _AIDebugLog:
    """Lightweight structured logger for AI HTTP traffic."""

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _ts() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

    @staticmethod
    def _write(line: str) -> None:
        """Append a single line to the log file (thread-safe)."""
        with _LOCK:
            try:
                _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
                # Rotate if too large
                try:
                    if _LOG_PATH.exists() and _LOG_PATH.stat().st_size > _MAX_SIZE_BYTES:
                        backup = _LOG_PATH.with_suffix(".old.txt")
                        if backup.exists():
                            backup.unlink()
                        _LOG_PATH.rename(backup)
                except Exception:
                    pass
                with open(_LOG_PATH, "a", encoding="utf-8") as f:
                    f.write(line + "\n")
            except Exception:
                pass  # Logging must never raise

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def request(
        self,
        provider: str,
        model: str,
        *,
        msg_count: int = 0,
        has_tools: bool = False,
        max_tokens: int = 0,
    ) -> None:
        """Log the start of an API request."""
        self._write(
            f"[{self._ts()}] REQUEST  provider={provider} model={model} "
            f"messages={msg_count} tools={has_tools} max_tokens={max_tokens}"
        )

    def chunk(self, byte_count: int) -> None:
        """Log a streaming chunk (called sparingly — e.g. every N chunks)."""
        self._write(f"[{self._ts()}] CHUNK    bytes={byte_count}")

    def complete(self, duration_s: float, response_len: int) -> None:
        """Log successful completion of a request."""
        self._write(f"[{self._ts()}] COMPLETE duration={duration_s:.2f}s response_chars={response_len}")

    def error(self, message: str, *, provider: str = "", http_status: int = 0) -> None:
        """Log an error."""
        parts = [f"[{self._ts()}] ERROR   "]
        if provider:
            parts.append(f"provider={provider} ")
        if http_status:
            parts.append(f"http={http_status} ")
        parts.append(message.replace("\n", " | "))
        self._write("".join(parts))

    def tool_use(self, name: str, inp: dict) -> None:
        """Log a tool use request from the AI."""
        # Truncate long input values
        summary = {}
        for k, v in inp.items():
            s = str(v)
            summary[k] = s[:120] + "…" if len(s) > 120 else s
        self._write(f"[{self._ts()}] TOOL_USE {name} {summary}")

    def tool_result(self, name: str, *, ok: bool = True, chars: int = 0) -> None:
        """Log a tool execution result."""
        status = "ok" if ok else "FAIL"
        self._write(f"[{self._ts()}] TOOL_RES {name} status={status} chars={chars}")

    def event(self, tag: str, detail: str = "") -> None:
        """Log a generic debug event."""
        self._write(f"[{self._ts()}] EVENT    {tag} {detail}".rstrip())

    def stream_end(
        self,
        provider: str,
        *,
        stop_reason: str = "",
        response_len: int = 0,
        duration_s: float = 0,
        error_type: str = "",
    ) -> None:
        """Log end of a stream (normal or abnormal)."""
        self._write(
            f"[{self._ts()}] STREAM_END provider={provider} "
            f"stop_reason={stop_reason or 'none'} "
            f"response_chars={response_len} "
            f"duration={duration_s:.2f}s "
            f"error={error_type or 'none'}"
        )


# Singleton instance
ai_log = _AIDebugLog()
