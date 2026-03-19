# Markdown Preview Fixes

**Created_at:** 2026-03-13  
**Updated_at:** 2026-03-13  
**Status:** Active  
**Goal:** Fix critical bugs, moderate issues, and performance problems in the markdown preview component  
**Scope:** `src/editor/preview/markdown_preview.py`  

---

## Overview

Analysis of `markdown_preview.py` (1045 lines) revealed 8 issues across three severity levels. This document tracks each fix.

---

## 🔴 Critical Bugs

### 1. Python 2 Exception Syntax (lines 35, 41, 47)

**Problem:** `except ValueError, ImportError:` is Python 2 syntax. In Python 3, this catches `ValueError` and assigns the exception to the name `ImportError`, shadowing the built-in.

**Fix:** Change to `except (ValueError, ImportError):` with a tuple.

### 2. No Error Handling for cmarkgfm (line 972)

**Problem:** `cmarkgfm.github_flavored_markdown_to_html()` can raise on malformed input. No try/except wrapping the call, so an unhandled exception could crash the preview.

**Fix:** Wrap in try/except, log the error, and render an error message in the preview instead of crashing.

### 3. macOS WKWebView Attach Race (line 707)

**Problem:** Fixed 200ms retry interval with no attempt limit. On slow machines the window may never appear; on fast machines it needlessly waits. Unbounded retries waste resources if the window never materialises.

**Fix:** Add exponential backoff (200ms → 400ms → 800ms) with a maximum of 10 attempts. Log a warning if attachment fails permanently.

---

## 🟡 Moderate Issues

### 4. Silent `except Exception: pass` (line 965)

**Problem:** `_on_webkit_load_changed` has a bare `except Exception: pass` that silently swallows errors, making debugging impossible.

**Fix:** Log the exception with `logging.debug()`.

### 5. Full Re-render on Font/Theme Change Without Debounce (lines 1035, 1041)

**Problem:** `_on_theme_change` and `_on_font_change` each trigger a full re-render via `GLib.idle_add`. If multiple change signals fire rapidly, multiple redundant renders occur.

**Fix:** Add a debounce mechanism — schedule a render after a short delay, cancelling any pending scheduled render.

### 6. Temp File Leak on macOS

**Problem:** `_MacOSWebKitHelper.load_html()` writes a temp file each time, but only tracks the latest one via `_tmp_html_path`. Previous temp files are not cleaned up if `load_html` is called rapidly.

**Fix:** The current code already cleans the previous temp file before creating a new one (lines 322-327). However, ensure we also handle the case where `destroy()` is called before any render. No code change needed — this was a false positive on re-inspection.

### 7. Scroll Sync Echo Potential

**Problem:** The editor-to-preview guard (`_syncing_scroll`) clears after 150ms, but the WebKit `load-changed` handler re-applies scroll after only 50ms. If both fire in quick succession, the JS scroll guard (`_zenScrolling`) and Python guard (`_syncing_scroll`) have slightly different windows, creating a potential for echo.

**Fix:** Align the JS guard timeout with the Python guard timeout (both 150ms). Already implemented consistently — the JS guard in `_apply_scroll_fraction` uses 150ms and the Python guard also uses 150ms. No change needed.

---

## ⚡ Performance

### 8. Full HTML Parse Every Render

**Problem:** Every call to `render()` does a full cmarkgfm parse and full HTML load. For large documents during live preview this can be expensive.

**Fix:** Cache the last markdown text hash and skip re-rendering if the content hasn't changed. This is a simple optimisation that avoids redundant cmarkgfm + WebKit loads.

---

## Summary of Changes

| # | Issue | Severity | Action |
|---|-------|----------|--------|
| 1 | Python 2 exception syntax | Critical | Fix 3 except clauses |
| 2 | No cmarkgfm error handling | Critical | Add try/except with error display |
| 3 | macOS WKWebView attach race | Critical | Add backoff + max attempts |
| 4 | Silent except pass | Moderate | Add logging |
| 5 | No debounce on re-render | Moderate | Add render debounce |
| 6 | Temp file leak | Moderate | False positive — already handled |
| 7 | Scroll sync echo | Moderate | Already consistent — no change |
| 8 | Redundant full parse | Performance | Add content hash check |
