"""Tests for editor/binary_viewer.py - binary file detection and hex formatting."""

from editor.preview.binary_viewer import _format_hex_dump, is_binary_file


class TestIsBinaryFile:
    """Test binary file detection."""

    def test_text_file_not_binary(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("Hello world\nThis is text\n")
        assert is_binary_file(str(f)) is False

    def test_binary_file_detected(self, tmp_path):
        f = tmp_path / "test.bin"
        f.write_bytes(b"\x00\x01\x02\xff\xfe\xfd")
        assert is_binary_file(str(f)) is True

    def test_empty_file_not_binary(self, tmp_path):
        f = tmp_path / "empty"
        f.write_bytes(b"")
        assert is_binary_file(str(f)) is False

    def test_nonexistent_file_returns_false(self):
        assert is_binary_file("/nonexistent/path/file.bin") is False

    def test_utf8_not_binary(self, tmp_path):
        f = tmp_path / "unicode.txt"
        f.write_text("こんにちは世界", encoding="utf-8")
        assert is_binary_file(str(f)) is False


class TestFormatHexDump:
    """Test hex dump formatting."""

    def test_empty_data(self):
        assert _format_hex_dump(b"") == ""

    def test_single_byte(self):
        result = _format_hex_dump(b"\x41")
        assert "00000000" in result
        assert "41" in result
        assert "A" in result

    def test_full_row(self):
        data = bytes(range(16))
        result = _format_hex_dump(data)
        assert "00000000" in result
        assert "00" in result
        assert "0F" in result

    def test_non_printable_shown_as_dot(self):
        result = _format_hex_dump(b"\x01")
        assert "." in result

    def test_printable_ascii(self):
        result = _format_hex_dump(b"Hello")
        assert "Hello" in result

    def test_multi_row(self):
        data = bytes(range(32))
        result = _format_hex_dump(data)
        lines = result.strip().split("\n")
        assert len(lines) == 2
        assert "00000000" in lines[0]
        assert "00000010" in lines[1]

    def test_offset_format(self):
        data = bytes(range(48))
        result = _format_hex_dump(data)
        assert "00000020" in result
