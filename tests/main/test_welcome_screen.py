"""Tests for WelcomeScreen (src/welcome_screen.py)."""

import ast
import os

SRC_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "src")


def _read_source() -> str:
    path = os.path.join(SRC_DIR, "main", "welcome_screen.py")
    with open(path) as f:
        return f.read()


def _parse_source() -> ast.Module:
    return ast.parse(_read_source())


def _find_class(tree: ast.Module, name: str) -> ast.ClassDef | None:
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == name:
            return node
    return None


def _find_function(tree: ast.Module, name: str) -> ast.FunctionDef | None:
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def _find_method(cls: ast.ClassDef, name: str) -> ast.FunctionDef | None:
    for node in ast.iter_child_nodes(cls):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


# ── Structure ────────────────────────────────────────────────────────


class TestWelcomeScreenStructure:
    """Verify WelcomeScreen class structure."""

    def test_inherits_gtk_scrolled_window(self):
        tree = _parse_source()
        cls = _find_class(tree, "WelcomeScreen")
        assert cls is not None
        base_names = []
        for base in cls.bases:
            if isinstance(base, ast.Attribute):
                base_names.append(base.attr)
            elif isinstance(base, ast.Name):
                base_names.append(base.id)
        assert "ScrolledWindow" in base_names

    def test_has_init(self):
        tree = _parse_source()
        cls = _find_class(tree, "WelcomeScreen")
        assert _find_method(cls, "__init__") is not None

    def test_has_create_ui(self):
        tree = _parse_source()
        cls = _find_class(tree, "WelcomeScreen")
        assert _find_method(cls, "_create_ui") is not None

    def test_has_apply_font_settings(self):
        tree = _parse_source()
        cls = _find_class(tree, "WelcomeScreen")
        assert _find_method(cls, "apply_font_settings") is not None


# ── Helper functions ─────────────────────────────────────────────────


class TestHelperFunctions:
    """Verify module-level helper functions."""

    def test_get_version_exists(self):
        tree = _parse_source()
        assert _find_function(tree, "_get_version") is not None

    def test_escape_markup_exists(self):
        tree = _parse_source()
        assert _find_function(tree, "_escape_markup") is not None


# ── Content ──────────────────────────────────────────────────────────


class TestWelcomeScreenContent:
    """Verify welcome screen content."""

    def test_has_logo(self):
        source = _read_source()
        assert "LOGO" in source
        assert "███" in source

    def test_shows_version(self):
        source = _read_source()
        assert "version" in source.lower()

    def test_shows_welcome_text(self):
        source = _read_source()
        assert "Welcome to Zen IDE" in source

    def test_shows_made_with_love(self):
        source = _read_source()
        assert "Made with" in source

    def test_uses_keybindings(self):
        source = _read_source()
        assert "KeyBindings" in source
        assert "get_shortcut_categories" in source

    def test_uses_theme(self):
        source = _read_source()
        assert "get_theme" in source
        assert "accent_color" in source

    def test_subscribes_theme_change(self):
        source = _read_source()
        assert "subscribe_theme_change" in source

    def test_applies_css_class(self):
        source = _read_source()
        assert "welcome-screen" in source


# ── _get_version ─────────────────────────────────────────────────────


class TestGetVersion:
    """Verify version reading from pyproject.toml."""

    def test_returns_string(self):
        from main.welcome_screen import _get_version

        result = _get_version()
        assert isinstance(result, str)

    def test_version_not_empty(self):
        from main.welcome_screen import _get_version

        result = _get_version()
        assert len(result) > 0

    def test_version_format(self):
        from main.welcome_screen import _get_version

        result = _get_version()
        # Version should contain at least one dot (e.g., "0.1.0")
        assert "." in result


# ── _escape_markup ───────────────────────────────────────────────────


class TestEscapeMarkup:
    """Verify Pango markup escaping."""

    def test_escapes_ampersand(self):
        from main.welcome_screen import _escape_markup

        assert "&amp;" in _escape_markup("&")

    def test_escapes_less_than(self):
        from main.welcome_screen import _escape_markup

        assert "&lt;" in _escape_markup("<")

    def test_plain_text_unchanged(self):
        from main.welcome_screen import _escape_markup

        assert _escape_markup("hello") == "hello"
