"""
Inline completion provider — calls AI for code completions.

Uses the GitHub Copilot API directly via HTTP for fast completions (~1s).
API-only — no CLI fallback.
"""

import threading
import time
from typing import Callable, Optional

from gi.repository import GLib

from .completion_cache import CompletionCache, CompletionProcessingMixin, _dedupe_suggestions
from .context_gatherer import CompletionContext
from .copilot_api import CopilotAPI

# Cooldown after API failure before retrying (seconds)
_API_RETRY_COOLDOWN_S = 30


class InlineCompletionProvider(CompletionProcessingMixin):
    """Calls AI for inline code completions.

    Uses the Copilot API exclusively (FIM endpoint first, chat fallback).
    No CLI fallback — API-only for speed and quality.
    """

    # Shared across all instances so API status survives tab switches
    _shared_api_available: Optional[bool] = None
    _shared_api_fail_time: float = 0

    def __init__(self):
        self._stop_requested = False
        self._api = CopilotAPI()
        self._cache = CompletionCache()

    @property
    def _api_available(self):
        return InlineCompletionProvider._shared_api_available

    @_api_available.setter
    def _api_available(self, value):
        InlineCompletionProvider._shared_api_available = value

    @property
    def _api_fail_time(self):
        return InlineCompletionProvider._shared_api_fail_time

    @_api_fail_time.setter
    def _api_fail_time(self, value):
        InlineCompletionProvider._shared_api_fail_time = value

    def request_completion(
        self,
        context: CompletionContext,
        on_result: Callable[[str], None],
        on_error: Optional[Callable[[str], None]] = None,
        on_chunk: Optional[Callable[[str], None]] = None,
    ):
        """Request a completion in a background thread.

        Args:
            context: The code context around the cursor.
            on_result: Called on the main thread with the completion text.
            on_error: Called on the main thread if an error occurs.
            on_chunk: Called on the main thread with each streaming token (optional).
        """
        self.cancel()
        self._stop_requested = False

        thread = threading.Thread(
            target=self._run,
            args=(context, on_result, on_error, on_chunk),
            daemon=True,
        )
        thread.start()

    def request_alternatives(
        self,
        context: CompletionContext,
        on_results: Callable[[list[str]], None],
        on_error: Optional[Callable[[str], None]] = None,
        n: int = 3,
    ):
        """Request multiple alternative completions in a background thread.

        Used for suggestion cycling (Alt+]/Alt+[). Requests n completions
        via the multi-completion API endpoints.

        Args:
            context: The code context around the cursor.
            on_results: Called on the main thread with a list of completions.
            on_error: Called on the main thread if an error occurs.
            n: Number of alternatives to request.
        """
        self.cancel()
        self._stop_requested = False

        thread = threading.Thread(
            target=self._run_multi,
            args=(context, on_results, on_error, n),
            daemon=True,
        )
        thread.start()

    def cancel(self):
        """Cancel any in-flight completion request."""
        self._stop_requested = True

    def _run(
        self,
        context: CompletionContext,
        on_result: Callable[[str], None],
        on_error: Optional[Callable[[str], None]],
        on_chunk: Optional[Callable[[str], None]] = None,
    ):
        """Run the completion request in a background thread."""
        t0 = time.monotonic()

        try:
            # Check cache first
            cached = self._cache.get(context)
            if cached:
                if not self._stop_requested and cached:
                    GLib.idle_add(on_result, cached[0])
                return

            from shared.settings import get_setting

            model = get_setting("ai.inline_completion.model", "gpt-4.1-mini")

            # Retry API after cooldown if previously failed
            api_ok = self._api_available is not False or (time.time() - self._api_fail_time > _API_RETRY_COOLDOWN_S)

            if api_ok and self._api.is_available():
                # FIM endpoint only — no chat fallback to avoid doubling
                # API requests (each request costs premium request units).
                completion = self._try_fim(context, t0)
                if completion:
                    self._cache.put(context, [completion])
                    GLib.idle_add(on_result, completion)
                    return
                if self._stop_requested:
                    return
            else:
                pass

        # Boundary catch: completion backends run external/network code paths.
        except Exception as e:
            if on_error and not self._stop_requested:
                GLib.idle_add(on_error, str(e))

    def _run_multi(
        self,
        context: CompletionContext,
        on_results: Callable[[list[str]], None],
        on_error: Optional[Callable[[str], None]],
        n: int = 3,
    ):
        """Request multiple alternative completions in a background thread."""
        t0 = time.monotonic()

        try:
            # Check cache for multiple completions
            cached = self._cache.get(context)
            if cached and len(cached) > 1:
                if not self._stop_requested:
                    GLib.idle_add(on_results, cached)
                return

            from shared.settings import get_setting

            model = get_setting("ai.inline_completion.model", "gpt-4.1-mini")
            api_ok = self._api_available is not False or (time.time() - self._api_fail_time > _API_RETRY_COOLDOWN_S)

            if not (api_ok and self._api.is_available()):
                return

            # 1. Try FIM multi first
            completions = self._try_fim_multi(context, t0, n)
            if completions:
                self._cache.put(context, completions)
                if not self._stop_requested:
                    GLib.idle_add(on_results, completions)
                return
            if self._stop_requested:
                return

            # 2. Fall back to chat multi
            completions = self._try_chat_multi(context, model, t0, n)
            if completions:
                self._cache.put(context, completions)
                if not self._stop_requested:
                    GLib.idle_add(on_results, completions)
                return

        # Boundary catch: completion backends run external/network code paths.
        except Exception as e:
            if on_error and not self._stop_requested:
                GLib.idle_add(on_error, str(e))

    def _try_fim(self, context: CompletionContext, t0: float) -> str | None:
        """Try the FIM completions endpoint (prefix/suffix)."""

        completion = self._api.complete_fim(
            prefix=context.prefix,
            suffix=context.suffix,
            language=context.language,
            file_path=context.file_path,
            max_tokens=500,
            timeout=10,
        )

        if self._stop_requested:
            return None

        if completion:
            self._api_available = True
            completion = completion.rstrip()
            if self._is_prose_response(completion):
                return None
            completion = self._deduplicate(completion, context)
            completion = self._ensure_newline_boundary(completion, context)
            if completion:
                return completion
        else:
            pass

        return None

    def _try_chat(
        self,
        context: CompletionContext,
        model: str,
        t0: float,
        on_chunk: Optional[Callable[[str], None]] = None,
    ) -> str | None:
        """Try the chat completions endpoint with FIM-style prompt."""
        prompt = self._build_prompt(context)

        if on_chunk:
            completion = self._api.complete_stream(
                prompt,
                model=model,
                max_tokens=500,
                timeout=15,
                on_chunk=on_chunk,
            )
        else:
            completion = self._api.complete(prompt, model=model, max_tokens=500, timeout=15)

        if self._stop_requested:
            return None

        if completion:
            self._api_available = True
            completion = self._clean_response(completion)
            completion = self._deduplicate(completion, context)
            completion = self._ensure_newline_boundary(completion, context)
            if completion:
                return completion
        else:
            self._api_available = False
            self._api_fail_time = time.time()

        return None

    def _try_fim_multi(self, context: CompletionContext, t0: float, n: int) -> list[str]:
        """Try FIM endpoint for multiple completions."""

        raw_completions = self._api.complete_fim_multi(
            prefix=context.prefix,
            suffix=context.suffix,
            language=context.language,
            file_path=context.file_path,
            max_tokens=500,
            timeout=15,
            n=n,
        )

        if self._stop_requested:
            return []

        results: list[str] = []
        for comp in raw_completions:
            comp = comp.rstrip()
            if not comp or self._is_prose_response(comp):
                continue
            comp = self._deduplicate(comp, context)
            comp = self._ensure_newline_boundary(comp, context)
            if comp:
                results.append(comp)

        if results:
            self._api_available = True

        return _dedupe_suggestions(results)

    def _try_chat_multi(self, context: CompletionContext, model: str, t0: float, n: int) -> list[str]:
        """Try chat endpoint for multiple completions."""
        prompt = self._build_prompt(context)

        raw_completions = self._api.complete_multi(prompt, model=model, max_tokens=500, timeout=15, n=n)

        if self._stop_requested:
            return []

        results: list[str] = []
        for comp in raw_completions:
            comp = self._clean_response(comp)
            comp = self._deduplicate(comp, context)
            comp = self._ensure_newline_boundary(comp, context)
            if comp:
                results.append(comp)

        if results:
            self._api_available = True
        else:
            self._api_available = False
            self._api_fail_time = time.time()

        return _dedupe_suggestions(results)
