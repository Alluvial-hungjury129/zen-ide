# Lazy: don't eagerly import EditorView (it pulls in heavy deps like cmarkgfm/AppKit)
# Use `from editor.editor_view import EditorView` instead of `from editor import EditorView`


def __getattr__(name):
    if name == "EditorView":
        from .editor_view import EditorView

        return EditorView
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["EditorView"]
