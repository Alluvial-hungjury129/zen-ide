"""
AI module for Zen IDE.

Contains both GUI components (GTK4 chat views, popups) and
GUI-independent AI provider implementations.

Providers:
- AnthropicHTTPProvider: Direct HTTP to Anthropic Messages API
- CopilotHTTPProvider: Direct HTTP to GitHub Copilot Chat API

Utilities:
- Spinner: Text-based spinner for loading states
- infer_title: Smart title generation from chat messages
"""

__all__ = [
    "AnthropicHTTPProvider",
    "CopilotHTTPProvider",
    "Spinner",
    "infer_title",
    "MAX_TITLE_LENGTH",
]

# Lazy imports — providers are heavy and not needed at startup
_LAZY_IMPORTS = {
    "AnthropicHTTPProvider": ".anthropic_http_provider",
    "CopilotHTTPProvider": ".copilot_http_provider",
    "Spinner": ".spinner",
    "infer_title": ".tab_title_inferrer",
    "MAX_TITLE_LENGTH": ".tab_title_inferrer",
}


def __getattr__(name):
    if name in _LAZY_IMPORTS:
        import importlib

        module = importlib.import_module(_LAZY_IMPORTS[name], __name__)
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
