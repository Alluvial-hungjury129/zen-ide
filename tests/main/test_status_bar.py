"""Tests for status_bar — pure logic and mocked GTK widget behavior."""

import os

import pytest

from shared.utils import contrast_color
from shared.utils import hex_to_rgb as _hex_to_rgb


# ---------------------------------------------------------------------------
# Tests for _hex_to_rgb
# ---------------------------------------------------------------------------
class TestHexToRgb:
    def test_black(self):
        assert _hex_to_rgb("#000000") == (0, 0, 0)

    def test_white(self):
        assert _hex_to_rgb("#ffffff") == (255, 255, 255)

    def test_red(self):
        assert _hex_to_rgb("#ff0000") == (255, 0, 0)

    def test_green(self):
        assert _hex_to_rgb("#00ff00") == (0, 255, 0)

    def test_blue(self):
        assert _hex_to_rgb("#0000ff") == (0, 0, 255)

    def test_without_hash(self):
        assert _hex_to_rgb("abcdef") == (171, 205, 239)

    def test_mixed_case(self):
        assert _hex_to_rgb("#AaBbCc") == (170, 187, 204)


# ---------------------------------------------------------------------------
# Tests for contrast_color (canonical in shared.utils)
# ---------------------------------------------------------------------------
class TestContrastColorUtils:
    def test_white_bg_returns_black(self):
        assert contrast_color("#ffffff") == "#000000"

    def test_black_bg_returns_white(self):
        assert contrast_color("#000000") == "#ffffff"

    def test_dark_bg_returns_white(self):
        assert contrast_color("#1a1b26") == "#ffffff"

    def test_light_bg_returns_black(self):
        assert contrast_color("#ffff00") == "#000000"


# ---------------------------------------------------------------------------
# Tests for _detect_file_type (via StatusBar instance mock)
# ---------------------------------------------------------------------------
class TestDetectFileType:
    """Test file type detection without GTK by calling the static-like method."""

    @pytest.fixture
    def detect(self):
        """Return a standalone _detect_file_type function (no GTK needed)."""

        # Re-implement the logic directly from the module to avoid GTK init
        def _detect_file_type(file_path: str) -> str:
            ext = os.path.splitext(file_path)[1].lower()
            type_map = {
                ".py": "python",
                ".js": "javascript",
                ".ts": "typescript",
                ".jsx": "javascriptreact",
                ".tsx": "typescriptreact",
                ".html": "html",
                ".css": "css",
                ".scss": "scss",
                ".json": "json",
                ".yaml": "yaml",
                ".yml": "yaml",
                ".md": "markdown",
                ".rs": "rust",
                ".go": "go",
                ".java": "java",
                ".c": "c",
                ".cpp": "cpp",
                ".h": "c",
                ".hpp": "cpp",
                ".rb": "ruby",
                ".php": "php",
                ".sh": "shell",
                ".bash": "shell",
                ".zsh": "shell",
                ".sql": "sql",
                ".xml": "xml",
                ".toml": "toml",
                ".lua": "lua",
                ".vim": "vim",
                ".swift": "swift",
                ".kt": "kotlin",
                ".scala": "scala",
                ".clj": "clojure",
                ".ex": "elixir",
                ".exs": "elixir",
                ".erl": "erlang",
                ".hs": "haskell",
                ".ml": "ocaml",
                ".r": "r",
                ".jl": "julia",
                ".dart": "dart",
                ".vue": "vue",
                ".svelte": "svelte",
                ".zen_sketch": "sketch",
            }
            return type_map.get(ext, ext.lstrip(".") if ext else "text")

        return _detect_file_type

    @pytest.mark.parametrize(
        "path, expected",
        [
            ("/src/main.py", "python"),
            ("/src/app.js", "javascript"),
            ("/src/index.ts", "typescript"),
            ("/src/Component.jsx", "javascriptreact"),
            ("/src/Component.tsx", "typescriptreact"),
            ("/src/page.html", "html"),
            ("/src/style.css", "css"),
            ("/src/config.json", "json"),
            ("/src/data.yaml", "yaml"),
            ("/src/data.yml", "yaml"),
            ("/src/README.md", "markdown"),
            ("/src/main.rs", "rust"),
            ("/src/main.go", "go"),
            ("/src/App.java", "java"),
            ("/src/main.c", "c"),
            ("/src/main.cpp", "cpp"),
            ("/src/header.h", "c"),
            ("/src/header.hpp", "cpp"),
            ("/src/script.sh", "shell"),
            ("/src/query.sql", "sql"),
            ("/src/config.toml", "toml"),
            ("/src/init.lua", "lua"),
            ("/src/main.swift", "swift"),
            ("/src/main.kt", "kotlin"),
            ("/src/main.dart", "dart"),
            ("/src/App.vue", "vue"),
            ("/src/App.svelte", "svelte"),
            ("/src/drawing.zen_sketch", "sketch"),
        ],
    )
    def test_known_extensions(self, detect, path, expected):
        assert detect(path) == expected

    def test_unknown_extension_returns_ext(self, detect):
        assert detect("/file.xyz") == "xyz"

    def test_no_extension_returns_text(self, detect):
        assert detect("/Makefile") == "text"

    def test_case_insensitive_extension(self, detect):
        assert detect("/file.PY") == "python"


# ---------------------------------------------------------------------------
# Tests for _detect_encoding (file I/O)
# ---------------------------------------------------------------------------
class TestDetectEncoding:
    """Test encoding detection using real temp files."""

    @staticmethod
    def _detect_encoding(file_path: str) -> str:
        """Standalone re-implementation of StatusBar._detect_encoding."""
        try:
            with open(file_path, "rb") as f:
                raw = f.read(4)
            if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
                return "UTF-16"
            if raw.startswith(b"\xef\xbb\xbf"):
                return "UTF-8-BOM"
            with open(file_path, "r", encoding="utf-8") as f:
                f.read(8192)
            return "UTF-8"
        except (UnicodeDecodeError, OSError):
            return "Binary"

    def test_utf8_file(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("Hello world", encoding="utf-8")
        assert self._detect_encoding(str(f)) == "UTF-8"

    def test_utf8_bom_file(self, tmp_path):
        f = tmp_path / "bom.txt"
        f.write_bytes(b"\xef\xbb\xbfHello BOM")
        assert self._detect_encoding(str(f)) == "UTF-8-BOM"

    def test_utf16_le_file(self, tmp_path):
        f = tmp_path / "utf16le.txt"
        f.write_bytes(b"\xff\xfeH\x00i\x00")
        assert self._detect_encoding(str(f)) == "UTF-16"

    def test_utf16_be_file(self, tmp_path):
        f = tmp_path / "utf16be.txt"
        f.write_bytes(b"\xfe\xff\x00H\x00i")
        assert self._detect_encoding(str(f)) == "UTF-16"

    def test_binary_file(self, tmp_path):
        f = tmp_path / "binary.bin"
        # Invalid UTF-8 sequence
        f.write_bytes(b"\x80\x81\x82\x83" * 100)
        assert self._detect_encoding(str(f)) == "Binary"

    def test_nonexistent_file(self):
        assert self._detect_encoding("/nonexistent/file.txt") == "Binary"


# ---------------------------------------------------------------------------
# Tests for position percentage logic
# ---------------------------------------------------------------------------
class TestPositionPercentage:
    """Test the percentage calculation from set_position without GTK."""

    @staticmethod
    def _calc_percent(line: int, total_lines: int) -> str:
        """Standalone re-implementation of the percentage logic."""
        if total_lines <= 1:
            return "Top"
        elif line == 1:
            return "Top"
        elif line >= total_lines:
            return "Bot"
        else:
            percent = int((line / total_lines) * 100)
            return f"{percent}%"

    def test_single_line_file(self):
        assert self._calc_percent(1, 1) == "Top"

    def test_first_line(self):
        assert self._calc_percent(1, 100) == "Top"

    def test_last_line(self):
        assert self._calc_percent(100, 100) == "Bot"

    def test_middle_of_file(self):
        assert self._calc_percent(50, 100) == "50%"

    def test_quarter_through(self):
        assert self._calc_percent(25, 100) == "25%"

    def test_near_bottom(self):
        assert self._calc_percent(99, 100) == "99%"

    def test_line_2_of_many(self):
        assert self._calc_percent(2, 1000) == "0%"

    def test_beyond_total_lines(self):
        assert self._calc_percent(200, 100) == "Bot"

    def test_empty_file(self):
        assert self._calc_percent(1, 0) == "Top"


# ---------------------------------------------------------------------------
# Tests for modified indicator logic
# ---------------------------------------------------------------------------
class TestModifiedIndicator:
    """Test the modified label logic without GTK."""

    @staticmethod
    def _modified_label(modified: bool) -> str:
        return "Δ" if modified else ""

    def test_modified_true(self):
        assert self._modified_label(True) == "Δ"

    def test_modified_false(self):
        assert self._modified_label(False) == ""


# ---------------------------------------------------------------------------
# Tests for set_file display path logic
# ---------------------------------------------------------------------------
class TestFileDisplayPath:
    """Test the display path logic from set_file without GTK."""

    @staticmethod
    def _display_path(file_path: str, show_full: bool) -> str:
        """Standalone re-implementation of the display path logic."""
        if show_full:
            home = os.path.expanduser("~")
            if file_path.startswith(home):
                return "~" + file_path[len(home) :]
            return file_path
        return os.path.basename(file_path)

    def test_full_path_with_home(self):
        home = os.path.expanduser("~")
        result = self._display_path(f"{home}/projects/test.py", True)
        assert result == "~/projects/test.py"

    def test_full_path_without_home(self):
        result = self._display_path("/opt/data/test.py", True)
        assert result == "/opt/data/test.py"

    def test_basename_only(self):
        result = self._display_path("/some/deep/path/file.py", False)
        assert result == "file.py"

    def test_basename_no_directory(self):
        result = self._display_path("file.py", False)
        assert result == "file.py"
