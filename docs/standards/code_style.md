# Code Style

**Created_at:** 2026-01-16  
**Updated_at:** 2026-03-12  
**Status:** Active  
**Goal:** Define naming conventions and file structure rules for all source code  
**Scope:** All files in `src/`  

---

## One Class Per File

Each class should be in its own standalone file — no nested or multiple classes per file.

## Naming Conventions

- File names use `snake_case`
- Class names use `PascalCase` matching the file name:
  - `git_manager.py` → `GitManager`
  - `git_ignore_utils.py` → `GitIgnoreUtils`
  - `diff_view.py` → `DiffView`
- When renaming a file, rename the class to match (and vice versa)

## Function Locality

Keep related logic local when it is not reused.

- Do not split a function into multiple files or distant helpers if the extracted parts are not shared.
- If a function is still reasonably small and readable, prefer keeping it together in one place.
- Extract helpers only when they improve clarity **and** have clear reuse or a strong separation-of-concerns reason.
