"""
Shared module for Zen IDE.

Contains GUI-independent code that can be used by the GTK4 implementation.

Submodules:
- shared.git_manager: Git operations facade
- shared.git_ignore_utils: Gitignore pattern matching
"""

__all__ = [
    "GitManager",
    "get_git_manager",
    "GitIgnoreUtils",
    "get_matcher",
    "should_skip",
    "is_ignored",
]

# Lazy imports — git_manager pulls in subprocess chains
_LAZY_IMPORTS = {
    "GitManager": ".git_manager",
    "get_git_manager": ".git_manager",
    "GitIgnoreUtils": ".git_ignore_utils",
    "get_matcher": ".git_ignore_utils",
    "should_skip": ".git_ignore_utils",
    "is_ignored": ".git_ignore_utils",
}


def __getattr__(name):
    if name in _LAZY_IMPORTS:
        import importlib

        module = importlib.import_module(_LAZY_IMPORTS[name], __name__)
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
