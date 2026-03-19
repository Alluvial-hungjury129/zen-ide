# Inline Completion Architecture Analysis

**Created_at:** 2026-03-08  
**Updated_at:** 2026-03-18  
**Status:** Active  
**Goal:** Document Zen IDE's inline completion architecture and compare with typical cloud-hosted completion systems  
**Scope:** Architecture, rendering, context gathering, providers, caching, UX

---

## Overview

Zen IDE provides AI-powered inline code completions displayed as "ghost text" at the cursor. This document analyses Zen's architecture and compares it with the typical cloud-hosted extension model used by most mainstream editors.

---

## Architecture

### Cloud-Hosted Extension Model (typical)

```
Extension → Cloud Proxy → LLM → ghost text via native InlineCompletionProvider API
```

- **Closed-source extension** running inside the host editor's extension process
- **Single cloud provider**: All requests go through a proprietary proxy
- **Native API**: Uses a built-in `InlineCompletionProvider` — a first-class editor concept with native ghost text rendering, partial accept, and suggestion cycling
- **LSP integration**: Can leverage Language Server Protocol for richer context

### Zen IDE

```
EditorTab → InlineCompletionManager → ContextGatherer + Provider (multi-stage) → GhostTextRenderer → GTK4 Snapshot
```

- **Open architecture** — all components are local Python modules
- **Multi-stage provider chain**: Direct Copilot HTTP API (~1s) → Copilot CLI fallback (~6s) → Claude CLI fallback (~6s)
- **Custom rendering**: Ghost text rendered via GTK4 `GtkSnapshot.append_layout()` — no framework-level "inline completion" concept exists in GTK
- **No LSP dependency**: Context is gathered directly from the GtkSourceView buffer

---

## Key Differences

### 1. Provider Strategy

| Aspect | Cloud-Hosted Extensions | Zen IDE |
|--------|------------------------|---------|
| **Provider** | Single cloud service | Multi-stage fallback chain: Copilot API → Copilot CLI → Claude CLI |
| **Model** | Server-selected (opaque) | Configurable: `gpt-4.1` default, supports Claude models |
| **Auth** | OAuth via extension login flow | Reads OAuth token from `~/.config/github-copilot/apps.json`, caches session tokens |
| **Fallback** | None — if cloud is down, no completions | Graceful degradation through 3 providers |
| **Vendor lock-in** | Tied to one provider | Provider-agnostic (Copilot + Claude + extensible) |

**Zen advantage**: Provider resilience and model choice. If the Copilot API is down, Zen falls back to CLI tools. Users can also prefer Claude models.

**Trade-off**: Optimised single-provider pipelines have no fallback latency and use purpose-built protocols.

### 2. Ghost Text Rendering

| Aspect | Native API Editors | Zen IDE |
|--------|-------------------|---------|
| **Mechanism** | Framework-native `InlineCompletionProvider` API | Custom `GhostTextRenderer` using GTK4 `snapshot.append_layout()` |
| **Buffer impact** | Ghost text is NOT in the document model | Ghost text is NOT in the buffer (purely visual overlay) |
| **Styling** | Grey/dimmed text, editor theme-aware | 55% alpha, italic, theme's `fg_dim` color |
| **Multi-line** | Native support | Custom positioning: first line at cursor, subsequent lines at left margin |

**Both** correctly avoid inserting ghost text into the document buffer, preserving undo history.

**Zen approach**: More control but more maintenance burden. Must manually calculate positions via `get_iter_location()` and `buffer_to_window_coords()`.

### 3. Context Gathering

| Aspect | Cloud-Hosted | Zen IDE |
|--------|-------------|---------|
| **Scope** | Current file + recently opened files + project context | Current file only (prefix 1200 chars + suffix 400 chars) |
| **Language detection** | Extension API + LSP | GtkSourceView language ID |
| **Cross-file context** | Yes — analyses imports, related files | No — single-file context only |
| **Prompt construction** | Proprietary (server-side optimisation) | Simple template: `{prefix}<CURSOR>{suffix}` with rules |
| **Context window** | Large (server manages truncation) | Conservative: 1600 chars total |

**Industry advantage**: Cross-file context leads to significantly better suggestions for codebases with many interdependent files. Server-side prompt engineering is highly optimised.

**Zen trade-off**: Simpler, faster context gathering. No network overhead for context assembly. But suggestions lack awareness of types, imports, and related files.

### 4. Debouncing & Cancellation

| Aspect | Cloud-Hosted | Zen IDE |
|--------|-------------|---------|
| **Debounce delay** | Dynamic (adapts to typing speed) | Fixed 500ms (configurable via `trigger_delay_ms`) |
| **Cancellation** | CancellationToken API — precise request cancellation | Cancels in-flight requests on new keystroke |
| **Skip conditions** | Proprietary heuristics | Skips on: empty lines, trailing whitespace, autocomplete visible |

**Zen advantage**: Explicit skip heuristics (trailing whitespace detection) prevent low-quality suggestions proactively.

### 5. Acceptance UX

| Action | Typical | Zen IDE |
|--------|---------|---------|
| **Accept all** | `Tab` | `Tab` |
| **Accept word** | `Ctrl+Right` | `Cmd+Right` (macOS) / `Ctrl+Right` |
| **Accept line** | `Ctrl+→` (line mode) | `Cmd+Down` (macOS) / `Ctrl+Down` |
| **Dismiss** | `Escape` | `Escape` or any keystroke |
| **Cycle suggestions** | `Alt+]` / `Alt+[` | Planned, not yet implemented |
| **Manual trigger** | `Alt+\` | `Alt+\` |

**Zen gap**: No suggestion cycling yet. Only one suggestion displayed at a time.

### 6. Caching

| Aspect | Cloud-Hosted | Zen IDE |
|--------|-------------|---------|
| **Response caching** | Local + server-side caching for similar contexts | No response caching |
| **Token caching** | Managed by extension | Copilot session token cached with 60s refresh margin |
| **Path caching** | N/A | CLI paths cached at class level (one-time lookup) |

**Zen opportunity**: Response caching could significantly reduce API calls and latency.

### 7. Streaming

| Aspect | Cloud-Hosted | Zen IDE |
|--------|-------------|---------|
| **Streaming** | Yes — ghost text appears progressively | No — waits for full response before displaying |

Streaming gives perceived speed — users see partial suggestions appearing while the model generates. Zen waits for the complete response, adding perceived latency even when the API responds quickly.

---

## Summary: Strengths & Gaps

### Where Zen IDE Excels

1. **Provider resilience** — 3-stage fallback chain vs single point of failure
2. **Model choice** — Users can select Copilot or Claude models
3. **Transparency** — Open architecture, full trace logging (`[IC]` prefix), all code visible
4. **No vendor lock-in** — Provider-agnostic design
5. **Buffer safety** — Ghost text never touches the buffer, implemented from scratch
6. **Smart filtering** — Trailing whitespace heuristic prevents hallucinated completions

### Industry-Standard Features to Adopt

1. **Cross-file context** — Analyse imports, open files, project structure
2. **Streaming display** — Progressive ghost text rendering
3. **Multi-suggestion cycling** — Browse alternative completions
4. **Response caching** — Reuse suggestions for similar contexts
5. **Adaptive debouncing** — Learn typing patterns
6. **Framework-native rendering** — Reduce custom coordinate calculations

### Zen IDE Roadmap Opportunities

| Feature | Impact | Complexity |
|---------|--------|------------|
| Cross-file context (imports, open tabs) | High — dramatically better suggestions | Medium |
| Response caching | Medium — reduces latency and API calls | Low |
| Streaming display | Medium — perceived speed improvement | Medium |
| Multi-suggestion cycling | Low — nice to have | Low |
| Adaptive debouncing | Low — minor UX improvement | Low |

---

## Architectural Insight

The fundamental difference is **where intelligence lives**:

- **Cloud-hosted extensions**: Intelligence is server-side. The extension is a thin client that sends context and renders results. The cloud provider controls prompt engineering, model selection, caching, and optimisation.
- **Zen IDE**: Intelligence is client-side. The IDE controls the full pipeline — context gathering, prompt construction, provider selection, post-processing, and rendering. This gives full control but requires implementing optimisations that a cloud service provides automatically.

This mirrors a broader trade-off: **platform integration vs independence**. Cloud-hosted completions are deeply coupled to vendor infrastructure. Zen IDE's approach is portable and provider-agnostic, at the cost of reimplementing optimisations that a cloud service provides automatically.
