"""Tests for the Spinner class."""

from ai.spinner import Spinner


class TestSpinner:
    """Test cases for Spinner."""

    def test_spin_returns_string(self):
        """spin() returns a single character."""
        s = Spinner()
        char = s.spin()
        assert isinstance(char, str)
        assert len(char) == 1

    def test_spin_cycles_through_characters(self):
        """spin() cycles through all braille characters."""
        s = Spinner()
        chars = [s.spin() for _ in range(10)]
        assert chars == list("⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏")

    def test_spin_wraps_around(self):
        """spin() wraps back to first character after full cycle."""
        s = Spinner()
        for _ in range(10):
            s.spin()
        # 11th call should be same as 1st
        assert s.spin() == "⠋"

    def test_reset(self):
        """reset() returns position to beginning."""
        s = Spinner()
        s.spin()
        s.spin()
        s.reset()
        assert s.spin() == "⠋"

    def test_all_chars_unique(self):
        """All spinner characters are unique."""
        s = Spinner()
        chars = [s.spin() for _ in range(10)]
        assert len(set(chars)) == 10
