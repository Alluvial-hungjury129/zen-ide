"""
AI Tab Title Inferrer - Smart, concise title generation for AI chat tabs.
Generates meaningful titles (max 30 chars) from chat content.

Architecture
------------
Title inference is a pipeline that runs entirely offline (no LLM call).
It is triggered by the VTE commit handler in ``AITerminalView`` and
coordinated by ``AITerminalStack``.

Data flow
~~~~~~~~~
1. **Input capture** (``AITerminalView._on_vte_commit``):
   The VTE ``commit`` signal delivers every byte the user sends to the
   PTY.  An inline state machine filters escape sequences (CSI, OSC,
   DCS) so only real keystrokes reach ``_input_buf``.  On Enter (\\r),
   the buffer is joined, cleaned by ``_strip_escape_fragments``, and
   passed to ``infer_title``.

2. **Title generation** (this module — ``infer_title``):
   Receives the first user message and produces a ≤ 30-char title:

   a. *Semantic patterns* — regex-based intent detection (comparison,
      debugging, explanation, implementation, …).  If a pattern matches,
      a structured title like ``"debug auth"`` is built directly.
   b. *Word-based fallback* — strips filler words (articles, pronouns,
      modal verbs, …), abbreviates common tech terms (``python`` →
      ``py``), keeps action verbs (``fix``, ``refactor``, …), and
      truncates to fit the max length.
   c. The result is returned in Title Case.

3. **Display** (``AITerminalStack._on_title_inferred``):
   Updates the tab button label (horizontal mode) or the per-view
   header (vertical mode), then persists to disk via ``_persist_tabs``.

Retry logic
~~~~~~~~~~~
``_title_inferred`` is only set to ``True`` when ``infer_title`` returns
a non-None value.  If the first message produces no usable title (too
short, all filler words), subsequent messages get another chance.

Startup noise filtering
~~~~~~~~~~~~~~~~~~~~~~~
VTE auto-responds to terminal capability queries (DA, DA2, XTVERSION)
with escape sequences whose payloads can leak printable residue into
``_input_buf``.  Three layers handle this:

- **Escape state machine** in ``_on_vte_commit`` — filters CSI, OSC,
  and DCS sequences byte-by-byte, including across commit boundaries.
- **``_strip_escape_fragments``** — regex cleanup for any residue that
  slips through (partial CSI params, DA2 responses, leading junk).
- **``_enable_commit_tracking``** — fires 1500 ms after spawn, clears
  accumulated startup noise from the buffer while preserving escape
  state.

Persistence
~~~~~~~~~~~
``AITerminalStack.save_state`` serialises tab titles.  On restore,
generic ``"Chat N"`` placeholders are *not* marked as inferred, so the
inferrer will derive a real title from the next user message.
"""

from typing import Optional

# Re-export all pattern data and helpers so existing imports keep working.
from ai.title_patterns import (  # noqa: F401
    ABBREVIATIONS,
    ACTION_VERBS,
    FILLER_WORDS,
    MAX_TITLE_LENGTH,
    QUESTION_PATTERNS,
    SEMANTIC_PATTERNS,
    SEMANTIC_STRUCTURAL_WORDS,
)
from ai.title_patterns import (
    process_message as _process_message,
)


def infer_title(messages: list) -> Optional[str]:
    """
    Infer a smart, meaningful title from chat messages.

    Args:
        messages: List of message dicts with 'role' and 'content' keys

    Returns:
        A title string (max 30 chars, uppercase) or None if no good title found
    """
    if not messages:
        return None

    first_user_msg = None
    for msg in messages:
        if msg.get("role") == "user":
            first_user_msg = msg.get("content", "").strip()
            break

    if not first_user_msg:
        return None

    title = _process_message(first_user_msg)

    if not title or len(title) < 2:
        return None

    return title.title()
