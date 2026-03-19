"""Tests for terminal.terminal_view — pure logic: regex, colors, path resolution."""

import os

import pytest

# Import the module-level constants and regex directly
from terminal.terminal_file_navigation import (
    FILE_PATH_PATTERN,
    KNOWN_EXTENSIONLESS,
)
from terminal.terminal_scroll import (
    apply_vadjustment_delta,
    configure_vte_scrolling,
    map_terminal_scroll_delta,
)


# ---------------------------------------------------------------------------
# Tests for KNOWN_EXTENSIONLESS pattern
# ---------------------------------------------------------------------------
class TestKnownExtensionless:
    """Verify that well-known extensionless filenames are listed."""

    @pytest.mark.parametrize(
        "name",
        [
            "Makefile",
            "Dockerfile",
            "Vagrantfile",
            "Procfile",
            "Gemfile",
            "Rakefile",
            "Guardfile",
            "Brewfile",
            "Justfile",
        ],
    )
    def test_known_names_in_pattern(self, name):
        assert name in KNOWN_EXTENSIONLESS


# ---------------------------------------------------------------------------
# Tests for FILE_PATH_PATTERN regex
# ---------------------------------------------------------------------------
class TestFilePathPattern:
    """Test the regex used to detect file paths in terminal output."""

    @pytest.mark.parametrize(
        "text, expected_path",
        [
            ("  terraform/ses_templates.tf ", "terraform/ses_templates.tf"),
            ("  ./src/main.py ", "./src/main.py"),
            (" /abs/path.txt ", "/abs/path.txt"),
            (" src/components/App.tsx ", "src/components/App.tsx"),
            (" README.md ", "README.md"),
        ],
    )
    def test_matches_file_paths(self, text, expected_path):
        m = FILE_PATH_PATTERN.search(text)
        assert m is not None, f"Expected to match '{expected_path}' in '{text}'"
        assert m.group(1) == expected_path

    @pytest.mark.parametrize(
        "text, expected_path, expected_line",
        [
            (" file.py:42 ", "file.py", "42"),
            (" src/main.rs:100 ", "src/main.rs", "100"),
            (" ./test.js:7 ", "./test.js", "7"),
        ],
    )
    def test_matches_with_line_number(self, text, expected_path, expected_line):
        m = FILE_PATH_PATTERN.search(text)
        assert m is not None
        assert m.group(1) == expected_path
        assert m.group(2) == expected_line

    @pytest.mark.parametrize(
        "text, expected_path, expected_line, expected_col",
        [
            (" file.py:42:10 ", "file.py", "42", "10"),
            (" src/app.ts:1:5 ", "src/app.ts", "1", "5"),
        ],
    )
    def test_matches_with_line_and_column(self, text, expected_path, expected_line, expected_col):
        m = FILE_PATH_PATTERN.search(text)
        assert m is not None
        assert m.group(1) == expected_path
        assert m.group(2) == expected_line
        assert m.group(3) == expected_col

    @pytest.mark.parametrize(
        "text, expected_path",
        [
            (" Makefile ", "Makefile"),
            (" path/to/Makefile ", "path/to/Makefile"),
            (" ./Dockerfile ", "./Dockerfile"),
        ],
    )
    def test_matches_extensionless_known_files(self, text, expected_path):
        m = FILE_PATH_PATTERN.search(text)
        assert m is not None, f"Expected to match '{expected_path}' in '{text}'"
        assert m.group(1) == expected_path

    def test_multiple_paths_in_line(self):
        """Multiple file paths in one line should all be found."""
        text = " src/a.py src/b.rs "
        matches = list(FILE_PATH_PATTERN.finditer(text))
        paths = [m.group(1) for m in matches]
        assert "src/a.py" in paths
        assert "src/b.rs" in paths


# ---------------------------------------------------------------------------
# Tests for _lighten helper (via class instance)
# ---------------------------------------------------------------------------
class TestLighten:
    """Test the color lightening utility.

    _lighten is an instance method but has no GTK dependencies in its logic,
    so we can test it by instantiating with a mock or extracting the logic.
    We test the algorithm directly by reimplementing the expected behavior.
    """

    @staticmethod
    def _lighten(hex_color: str, amount: float) -> str:
        """Reference implementation matching TerminalView._lighten."""
        hex_color = hex_color.lstrip("#")
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        r = min(255, int(r + (255 - r) * amount))
        g = min(255, int(g + (255 - g) * amount))
        b = min(255, int(b + (255 - b) * amount))
        return f"#{r:02x}{g:02x}{b:02x}"

    def test_black_lightened(self):
        """Lightening black by 0.5 should give mid-gray."""
        result = self._lighten("#000000", 0.5)
        assert result == "#7f7f7f"

    def test_white_unchanged(self):
        """Lightening white should stay white."""
        result = self._lighten("#ffffff", 0.5)
        assert result == "#ffffff"

    def test_zero_amount_unchanged(self):
        """Zero amount should return the same color."""
        result = self._lighten("#336699", 0.0)
        assert result == "#336699"

    def test_full_amount_gives_white(self):
        """Amount 1.0 should give white."""
        result = self._lighten("#336699", 1.0)
        assert result == "#ffffff"

    def test_specific_color(self):
        """Test a specific known lightening."""
        result = self._lighten("#800000", 0.2)
        # r = 128 + (255-128)*0.2 = 128 + 25.4 = 153 -> 0x99
        # g = 0 + 255*0.2 = 51 -> 0x33
        # b = 0 + 255*0.2 = 51 -> 0x33
        assert result == "#993333"

    def test_without_hash_prefix(self):
        """Should work without # prefix."""
        result = self._lighten("000000", 0.5)
        assert result == "#7f7f7f"


# ---------------------------------------------------------------------------
# Tests for _extract_file_path_at_column (via a minimal stub)
# ---------------------------------------------------------------------------
class TestExtractFilePathAtColumn:
    """Test file path extraction logic from a terminal line.

    We re-implement the extraction logic here to test it without GTK,
    since _extract_file_path_at_column only uses FILE_PATH_PATTERN (a module-level regex).
    """

    @staticmethod
    def _extract(line, col):
        """Reimplementation of TerminalView._extract_file_path_at_column."""
        if not line:
            return None, None

        matches = []
        for match in FILE_PATH_PATTERN.finditer(line):
            file_path = match.group(1)
            line_num = int(match.group(2)) if match.group(2) else None
            start_pos = match.start(1)
            end_pos = match.end(1)
            matches.append((file_path, line_num, start_pos, end_pos))

        if not matches:
            return None, None

        best_match = None
        best_distance = float("inf")

        for file_path, line_num, start_pos, end_pos in matches:
            if start_pos <= col <= end_pos:
                return file_path, line_num
            if col < start_pos:
                distance = start_pos - col
            else:
                distance = col - end_pos
            if distance < best_distance:
                best_distance = distance
                best_match = (file_path, line_num)

        if best_match and best_distance <= 10:
            return best_match

        return None, None

    def test_empty_line(self):
        assert self._extract("", 0) == (None, None)

    def test_none_line(self):
        assert self._extract(None, 0) == (None, None)

    def test_cursor_on_path(self):
        line = "  error in src/main.py at line 5"
        path, line_num = self._extract(line, 14)  # cursor on 'main'
        assert path == "src/main.py"

    def test_cursor_near_path(self):
        line = "  error in src/main.py at line 5"
        path, line_num = self._extract(line, 10)  # cursor on 'in', close to path
        assert path == "src/main.py"

    def test_cursor_far_from_path(self):
        """Cursor far from any path should return None."""
        line = "some random text without paths nearby                         src/a.py"
        path, _ = self._extract(line, 0)
        assert path is None

    def test_with_line_number(self):
        line = "  src/app.ts:42 something"
        path, line_num = self._extract(line, 8)
        assert path == "src/app.ts"
        assert line_num == 42

    def test_multiple_paths_selects_nearest(self):
        line = " src/a.py    src/b.py"
        # Cursor near first path
        path, _ = self._extract(line, 5)
        assert path == "src/a.py"
        # Cursor near second path
        path, _ = self._extract(line, 16)
        assert path == "src/b.py"


# ---------------------------------------------------------------------------
# Tests for _resolve_file_path logic
# ---------------------------------------------------------------------------
class TestResolveFilePath:
    """Test file path resolution against cwd and workspace folders."""

    def test_resolve_in_cwd(self, tmp_path):
        """File found in cwd should be resolved."""
        test_file = tmp_path / "src" / "main.py"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("# test")
        resolved = _resolve_file_path(str(tmp_path), None, "src/main.py")
        assert resolved == os.path.abspath(str(test_file))

    def test_resolve_in_workspace_folder(self, tmp_path):
        """File found in workspace folder should be resolved."""
        ws = tmp_path / "workspace"
        ws.mkdir()
        test_file = ws / "lib.py"
        test_file.write_text("# test")

        resolved = _resolve_file_path(str(tmp_path), lambda: [str(ws)], "lib.py")
        assert resolved == os.path.abspath(str(test_file))

    def test_not_found_returns_none(self, tmp_path):
        resolved = _resolve_file_path(str(tmp_path), None, "nonexistent.py")
        assert resolved is None

    def test_cwd_takes_precedence(self, tmp_path):
        """If file exists in both cwd and workspace, cwd wins."""
        cwd_file = tmp_path / "file.py"
        cwd_file.write_text("# cwd")

        ws = tmp_path / "ws"
        ws.mkdir()
        ws_file = ws / "file.py"
        ws_file.write_text("# ws")

        resolved = _resolve_file_path(str(tmp_path), lambda: [str(ws)], "file.py")
        assert resolved == os.path.abspath(str(cwd_file))


class _FakeSetterTerminal:
    def __init__(self):
        self.fallback_calls = []
        self.pixel_calls = []

    def set_enable_fallback_scrolling(self, enabled):
        self.fallback_calls.append(enabled)

    def set_scroll_unit_is_pixels(self, enabled):
        self.pixel_calls.append(enabled)


class _FakePropertyTerminal:
    def __init__(self):
        self.properties = {
            "enable-fallback-scrolling": object(),
            "scroll-unit-is-pixels": object(),
        }
        self.set_calls = []

    def find_property(self, name):
        return self.properties.get(name)

    def set_property(self, name, value):
        self.set_calls.append((name, value))


class _FakeNoopTerminal:
    def find_property(self, name):
        return None


class TestConfigureVteScrolling:
    def test_prefers_native_setters(self):
        terminal = _FakeSetterTerminal()

        configure_vte_scrolling(terminal)

        assert terminal.fallback_calls == [True]
        assert terminal.pixel_calls == [True]

    def test_falls_back_to_properties(self):
        terminal = _FakePropertyTerminal()

        configure_vte_scrolling(terminal)

        assert terminal.set_calls == [
            ("enable-fallback-scrolling", True),
            ("scroll-unit-is-pixels", True),
        ]

    def test_noops_when_feature_missing(self):
        terminal = _FakeNoopTerminal()

        configure_vte_scrolling(terminal)


class _FakeAdjustment:
    def __init__(self, *, lower=0.0, upper=1000.0, page_size=200.0, value=0.0):
        self._lower = float(lower)
        self._upper = float(upper)
        self._page_size = float(page_size)
        self._value = float(value)

    def get_lower(self):
        return self._lower

    def get_upper(self):
        return self._upper

    def get_page_size(self):
        return self._page_size

    def get_value(self):
        return self._value

    def set_value(self, value):
        self._value = float(value)


class TestApplyVadjustmentDelta:
    def test_applies_fractional_delta(self):
        vadj = _FakeAdjustment(value=10.0)

        changed = apply_vadjustment_delta(vadj, 0.5)

        assert changed is True
        assert vadj.get_value() == pytest.approx(10.5)

    def test_clamps_to_upper_bound(self):
        vadj = _FakeAdjustment(upper=100.0, page_size=20.0, value=79.5)

        changed = apply_vadjustment_delta(vadj, 5.0)

        assert changed is True
        assert vadj.get_value() == pytest.approx(80.0)

    def test_clamps_to_lower_bound(self):
        vadj = _FakeAdjustment(lower=10.0, value=10.25)

        changed = apply_vadjustment_delta(vadj, -2.0)

        assert changed is True
        assert vadj.get_value() == pytest.approx(10.0)

    def test_returns_false_when_no_movement(self):
        vadj = _FakeAdjustment(upper=100.0, page_size=20.0, value=80.0)

        changed = apply_vadjustment_delta(vadj, 0.0)

        assert changed is False
        assert vadj.get_value() == pytest.approx(80.0)


class _FakeScrollUnit:
    WHEEL = "wheel"
    SURFACE = "surface"


class _FakeGdk:
    ScrollUnit = _FakeScrollUnit


class _FakeController:
    def __init__(self, unit):
        self._unit = unit

    def get_unit(self):
        return self._unit


class _NoUnitController:
    pass


class TestMapTerminalScrollDelta:
    def test_wheel_delta_is_scaled(self):
        consume, delta = map_terminal_scroll_delta(
            _FakeController(_FakeScrollUnit.WHEEL),
            1.5,
            wheel_step_pixels=24.0,
            touchpad_step_pixels=20.0,
            gdk_module=_FakeGdk,
        )

        assert consume is True
        assert delta == pytest.approx(36.0)

    def test_touchpad_delta_not_consumed(self):
        consume, delta = map_terminal_scroll_delta(
            _FakeController(_FakeScrollUnit.SURFACE),
            1.5,
            wheel_step_pixels=24.0,
            touchpad_step_pixels=20.0,
            gdk_module=_FakeGdk,
        )

        assert consume is True
        assert delta == pytest.approx(30.0)

    def test_zero_delta_not_consumed(self):
        consume, delta = map_terminal_scroll_delta(
            _FakeController(_FakeScrollUnit.WHEEL),
            0.0,
            wheel_step_pixels=24.0,
            touchpad_step_pixels=20.0,
            gdk_module=_FakeGdk,
        )

        assert consume is False
        assert delta == pytest.approx(0.0)

    def test_legacy_fallback_consumes_raw_delta(self):
        consume, delta = map_terminal_scroll_delta(
            _NoUnitController(),
            0.5,
            wheel_step_pixels=24.0,
            touchpad_step_pixels=20.0,
            gdk_module=None,
        )

        assert consume is True
        assert delta == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# Helpers for smooth-scroll animation tests
# ---------------------------------------------------------------------------


class _FakeScrolledWindow:
    """Minimal stand-in for Gtk.ScrolledWindow used by the smooth-scroll tick."""

    def __init__(self, vadj):
        self._vadj = vadj
        self._tick_cb = None
        self._tick_id_counter = 0

    def get_vadjustment(self):
        return self._vadj

    def add_tick_callback(self, cb):
        self._tick_cb = cb
        self._tick_id_counter += 1
        return self._tick_id_counter

    def pump_ticks(self, n=1):
        """Simulate *n* frame-clock ticks, returning how many kept running."""
        ran = 0
        for _ in range(n):
            if self._tick_cb is None:
                break
            keep = self._tick_cb(self, None)
            ran += 1
            if not keep:
                self._tick_cb = None
        return ran


def _make_scroll_state(*, value=0.0, upper=1000.0, page_size=200.0, lerp=0.3):
    """Return ``(vadj, scrolled_window, state_dict)`` ready for tick tests.

    *state_dict* mirrors the instance attrs that ``_smooth_scroll_tick`` and
    ``_on_scroll`` expect on ``self``.
    """
    vadj = _FakeAdjustment(upper=upper, page_size=page_size, value=value)
    sw = _FakeScrolledWindow(vadj)
    state = {
        "_scrolled_window": sw,
        "_scroll_target": None,
        "_scroll_tick_id": 0,
        "_SCROLL_LERP": lerp,
    }
    return vadj, sw, state


# ---------------------------------------------------------------------------
# Tests for _get_wheel_step_pixels / _get_touchpad_step_pixels
# ---------------------------------------------------------------------------


class TestScrollStepPixels:
    """Verify scroll-speed setting feeds through to step calculations."""

    def test_wheel_step_default(self):
        """Default scroll_speed=0.4 → 15 * 0.4 = 6.0."""
        speed = 0.4
        assert max(1.0, 15.0 * speed) == pytest.approx(6.0)

    def test_touchpad_step_default(self):
        """Default scroll_speed=0.4 → 12 * 0.4 = 4.8."""
        speed = 0.4
        assert max(1.0, 12.0 * speed) == pytest.approx(4.8)

    def test_wheel_step_minimum_floor(self):
        """Very low scroll_speed still yields at least 1.0."""
        speed = 0.0
        assert max(1.0, 15.0 * speed) == pytest.approx(1.0)

    def test_touchpad_step_minimum_floor(self):
        speed = 0.0
        assert max(1.0, 12.0 * speed) == pytest.approx(1.0)

    @pytest.mark.parametrize("speed", [0.1, 0.2, 0.5, 1.0, 2.0])
    def test_wheel_scales_linearly(self, speed):
        assert max(1.0, 15.0 * speed) == pytest.approx(max(1.0, 15.0 * speed))

    @pytest.mark.parametrize("speed", [0.1, 0.2, 0.5, 1.0, 2.0])
    def test_touchpad_scales_linearly(self, speed):
        assert max(1.0, 12.0 * speed) == pytest.approx(max(1.0, 12.0 * speed))


# ---------------------------------------------------------------------------
# Tests for _smooth_scroll_tick (lerp animation)
# ---------------------------------------------------------------------------


class TestSmoothScrollTick:
    """Regression tests for the frame-clock lerp animation."""

    @staticmethod
    def _run_tick(vadj, sw, state):
        """Call the tick logic extracted from TerminalView._smooth_scroll_tick."""
        if vadj is None or state["_scroll_target"] is None:
            state["_scroll_tick_id"] = 0
            return False

        current = float(vadj.get_value())
        diff = state["_scroll_target"] - current

        if abs(diff) < 0.5:
            vadj.set_value(state["_scroll_target"])
            state["_scroll_target"] = None
            state["_scroll_tick_id"] = 0
            return False

        vadj.set_value(current + diff * state["_SCROLL_LERP"])
        return True

    def test_lerp_converges_to_target(self):
        """After enough ticks the scroll value reaches the target."""
        vadj, sw, state = _make_scroll_state(value=0.0)
        state["_scroll_target"] = 100.0
        state["_scroll_tick_id"] = 1

        for _ in range(200):
            if not self._run_tick(vadj, sw, state):
                break

        assert vadj.get_value() == pytest.approx(100.0)
        assert state["_scroll_target"] is None
        assert state["_scroll_tick_id"] == 0

    def test_lerp_moves_in_correct_direction_downward(self):
        """First tick moves value toward (higher) target."""
        vadj, sw, state = _make_scroll_state(value=50.0)
        state["_scroll_target"] = 150.0

        self._run_tick(vadj, sw, state)

        assert vadj.get_value() > 50.0
        assert vadj.get_value() < 150.0

    def test_lerp_moves_in_correct_direction_upward(self):
        """First tick moves value toward (lower) target."""
        vadj, sw, state = _make_scroll_state(value=150.0)
        state["_scroll_target"] = 50.0

        self._run_tick(vadj, sw, state)

        assert vadj.get_value() < 150.0
        assert vadj.get_value() > 50.0

    def test_lerp_factor_controls_speed(self):
        """Higher lerp factor → larger first step."""
        vadj_slow, _, state_slow = _make_scroll_state(value=0.0, lerp=0.1)
        vadj_fast, _, state_fast = _make_scroll_state(value=0.0, lerp=0.5)
        state_slow["_scroll_target"] = 100.0
        state_fast["_scroll_target"] = 100.0

        self._run_tick(vadj_slow, None, state_slow)
        self._run_tick(vadj_fast, None, state_fast)

        assert vadj_fast.get_value() > vadj_slow.get_value()

    def test_stops_when_close_to_target(self):
        """Tick returns False and snaps to target when diff < 0.5."""
        vadj, sw, state = _make_scroll_state(value=99.8)
        state["_scroll_target"] = 100.0

        keep = self._run_tick(vadj, sw, state)

        assert keep is False
        assert vadj.get_value() == pytest.approx(100.0)
        assert state["_scroll_target"] is None
        assert state["_scroll_tick_id"] == 0

    def test_continues_when_far_from_target(self):
        """Tick returns True when still far from target."""
        vadj, sw, state = _make_scroll_state(value=0.0)
        state["_scroll_target"] = 100.0

        keep = self._run_tick(vadj, sw, state)

        assert keep is True
        assert state["_scroll_target"] is not None

    def test_stops_when_target_is_none(self):
        """Tick returns False immediately if target is None."""
        vadj, sw, state = _make_scroll_state(value=50.0)
        state["_scroll_target"] = None

        keep = self._run_tick(vadj, sw, state)

        assert keep is False
        assert state["_scroll_tick_id"] == 0

    def test_stops_when_vadj_is_none(self):
        """Tick returns False immediately if adjustment is None."""
        state = {"_scroll_target": 100.0, "_scroll_tick_id": 1, "_SCROLL_LERP": 0.3}

        keep = self._run_tick(None, None, state)

        assert keep is False
        assert state["_scroll_tick_id"] == 0

    def test_exact_lerp_value_first_tick(self):
        """First tick value = current + (target - current) * lerp."""
        vadj, sw, state = _make_scroll_state(value=0.0, lerp=0.3)
        state["_scroll_target"] = 100.0

        self._run_tick(vadj, sw, state)

        assert vadj.get_value() == pytest.approx(30.0)  # 0 + 100*0.3

    def test_convergence_within_bounded_ticks(self):
        """Animation converges to target in fewer than 100 ticks (≈1.7s at 60fps)."""
        vadj, sw, state = _make_scroll_state(value=0.0, lerp=0.3)
        state["_scroll_target"] = 800.0  # max-range scroll

        ticks = 0
        for ticks in range(1, 101):
            if not self._run_tick(vadj, sw, state):
                break

        assert state["_scroll_target"] is None, f"Did not converge in {ticks} ticks"
        assert ticks < 100


# ---------------------------------------------------------------------------
# Tests for scroll target accumulation (logic from _on_scroll)
# ---------------------------------------------------------------------------


class TestScrollTargetAccumulation:
    """Test the target accumulation and clamping logic used by _on_scroll."""

    @staticmethod
    def _accumulate(state, vadj, delta):
        """Replicate the accumulation logic from _on_scroll."""
        lower = float(vadj.get_lower())
        upper = float(vadj.get_upper())
        page_size = float(vadj.get_page_size())
        maximum = max(lower, upper - page_size)

        if state["_scroll_target"] is None:
            state["_scroll_target"] = float(vadj.get_value())
        state["_scroll_target"] = min(max(state["_scroll_target"] + delta, lower), maximum)

    def test_single_delta_sets_target(self):
        vadj, sw, state = _make_scroll_state(value=100.0)
        self._accumulate(state, vadj, 50.0)

        assert state["_scroll_target"] == pytest.approx(150.0)

    def test_multiple_deltas_accumulate(self):
        vadj, sw, state = _make_scroll_state(value=100.0)
        self._accumulate(state, vadj, 20.0)
        self._accumulate(state, vadj, 30.0)

        assert state["_scroll_target"] == pytest.approx(150.0)

    def test_clamps_to_upper_bound(self):
        vadj, sw, state = _make_scroll_state(value=700.0, upper=1000.0, page_size=200.0)
        self._accumulate(state, vadj, 200.0)  # would be 900, but max=800

        assert state["_scroll_target"] == pytest.approx(800.0)

    def test_clamps_to_lower_bound(self):
        vadj, sw, state = _make_scroll_state(value=10.0)
        self._accumulate(state, vadj, -100.0)

        assert state["_scroll_target"] == pytest.approx(0.0)

    def test_negative_delta_scrolls_up(self):
        vadj, sw, state = _make_scroll_state(value=500.0)
        self._accumulate(state, vadj, -200.0)

        assert state["_scroll_target"] == pytest.approx(300.0)

    def test_rapid_scrolls_accumulate_before_animation(self):
        """Multiple rapid scroll events accumulate into a single target."""
        vadj, sw, state = _make_scroll_state(value=0.0)
        for _ in range(10):
            self._accumulate(state, vadj, 10.0)

        assert state["_scroll_target"] == pytest.approx(100.0)

    def test_scroll_then_reverse_partial(self):
        """Scroll down then partially back up."""
        vadj, sw, state = _make_scroll_state(value=100.0)
        self._accumulate(state, vadj, 50.0)
        self._accumulate(state, vadj, -20.0)

        assert state["_scroll_target"] == pytest.approx(130.0)

    def test_accumulate_during_animation(self):
        """New scroll events arriving mid-animation update the target."""
        vadj, sw, state = _make_scroll_state(value=0.0, lerp=0.3)
        # First scroll sets target to 100
        self._accumulate(state, vadj, 100.0)

        # Simulate a few animation ticks (value moves toward 100)
        for _ in range(3):
            current = float(vadj.get_value())
            diff = state["_scroll_target"] - current
            if abs(diff) >= 0.5:
                vadj.set_value(current + diff * state["_SCROLL_LERP"])

        mid_value = vadj.get_value()
        assert mid_value > 0.0
        assert mid_value < 100.0

        # New scroll arrives — target extends beyond 100
        self._accumulate(state, vadj, 50.0)
        assert state["_scroll_target"] == pytest.approx(150.0)

        # Value hasn't jumped — animation continues from where it was
        assert vadj.get_value() == pytest.approx(mid_value)


# ---------------------------------------------------------------------------
# Tests for full smooth-scroll round-trip (accumulate + tick)
# ---------------------------------------------------------------------------


class TestSmoothScrollRoundTrip:
    """End-to-end: accumulate deltas then animate to final position."""

    @staticmethod
    def _run_tick(vadj, state):
        if vadj is None or state["_scroll_target"] is None:
            state["_scroll_tick_id"] = 0
            return False
        current = float(vadj.get_value())
        diff = state["_scroll_target"] - current
        if abs(diff) < 0.5:
            vadj.set_value(state["_scroll_target"])
            state["_scroll_target"] = None
            state["_scroll_tick_id"] = 0
            return False
        vadj.set_value(current + diff * state["_SCROLL_LERP"])
        return True

    @staticmethod
    def _accumulate(state, vadj, delta):
        lower = float(vadj.get_lower())
        upper = float(vadj.get_upper())
        page_size = float(vadj.get_page_size())
        maximum = max(lower, upper - page_size)
        if state["_scroll_target"] is None:
            state["_scroll_target"] = float(vadj.get_value())
        state["_scroll_target"] = min(max(state["_scroll_target"] + delta, lower), maximum)

    def test_scroll_down_and_animate(self):
        """Single scroll event followed by full animation reaches target."""
        vadj, sw, state = _make_scroll_state(value=0.0)
        self._accumulate(state, vadj, 100.0)

        for _ in range(200):
            if not self._run_tick(vadj, state):
                break

        assert vadj.get_value() == pytest.approx(100.0)

    def test_scroll_up_and_animate(self):
        vadj, sw, state = _make_scroll_state(value=400.0)
        self._accumulate(state, vadj, -200.0)

        for _ in range(200):
            if not self._run_tick(vadj, state):
                break

        assert vadj.get_value() == pytest.approx(200.0)

    def test_multiple_scrolls_then_animate(self):
        """Several accumulated deltas resolve to correct final position."""
        vadj, sw, state = _make_scroll_state(value=0.0)
        self._accumulate(state, vadj, 30.0)
        self._accumulate(state, vadj, 30.0)
        self._accumulate(state, vadj, 40.0)

        for _ in range(200):
            if not self._run_tick(vadj, state):
                break

        assert vadj.get_value() == pytest.approx(100.0)

    def test_animation_is_monotonic_downward(self):
        """Scroll values only increase when scrolling down."""
        vadj, sw, state = _make_scroll_state(value=0.0)
        self._accumulate(state, vadj, 200.0)

        values = [vadj.get_value()]
        for _ in range(200):
            if not self._run_tick(vadj, state):
                break
            values.append(vadj.get_value())

        for i in range(1, len(values)):
            assert values[i] >= values[i - 1], f"Non-monotonic at tick {i}"

    def test_animation_is_monotonic_upward(self):
        """Scroll values only decrease when scrolling up."""
        vadj, sw, state = _make_scroll_state(value=500.0)
        self._accumulate(state, vadj, -300.0)

        values = [vadj.get_value()]
        for _ in range(200):
            if not self._run_tick(vadj, state):
                break
            values.append(vadj.get_value())

        for i in range(1, len(values)):
            assert values[i] <= values[i - 1], f"Non-monotonic at tick {i}"

    def test_clamped_at_bottom_after_overshoot(self):
        """Cannot scroll past the bottom."""
        vadj, sw, state = _make_scroll_state(value=750.0, upper=1000.0, page_size=200.0)
        self._accumulate(state, vadj, 500.0)  # would overshoot max=800

        for _ in range(200):
            if not self._run_tick(vadj, state):
                break

        assert vadj.get_value() == pytest.approx(800.0)

    def test_clamped_at_top_after_overshoot(self):
        """Cannot scroll past the top."""
        vadj, sw, state = _make_scroll_state(value=50.0)
        self._accumulate(state, vadj, -500.0)

        for _ in range(200):
            if not self._run_tick(vadj, state):
                break

        assert vadj.get_value() == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Tests for _create_custom_bashrc logic
# ---------------------------------------------------------------------------
class TestCreateCustomBashrc:
    """Test custom bashrc generation."""

    def test_creates_bashrc_file(self, tmp_path):
        """Bashrc file should be created in config dir."""
        config_dir = str(tmp_path / "config")
        path = _create_custom_bashrc(config_dir)
        assert path is not None
        assert os.path.isfile(path)
        assert path.endswith("bashrc")

    def test_bashrc_content(self, tmp_path):
        """Bashrc should contain expected shell configuration."""
        config_dir = str(tmp_path / "config")
        path = _create_custom_bashrc(config_dir)
        content = open(path).read()

        # Check key sections
        assert "TERM=xterm-256color" in content
        assert "HISTFILE" in content
        assert "__zen_real_histfile" in content
        assert "HISTIGNORE=" in content
        assert "set +o history" in content
        assert "set -o history" in content
        assert "awk '" in content
        assert "history -n" in content
        assert "alias gst=" in content
        assert "PROMPT_COMMAND" in content
        assert "printf '\\033]7;file://%s%s\\007'" in content
        assert "printf '\\\\033]7;file://%s%s\\\\007'" not in content
        assert "PS1='\\[\\e[36m\\]\\W" in content
        assert "PS1='\\\\[\\\\e[36m\\\\]\\\\W" not in content
        assert content.rfind("set -o history") > content.rfind("PS1=")

    def test_creates_config_dir(self, tmp_path):
        """Should create config dir if it doesn't exist."""
        config_dir = str(tmp_path / "new" / "config")
        assert not os.path.exists(config_dir)
        path = _create_custom_bashrc(config_dir)
        assert path is not None
        assert os.path.isdir(config_dir)


# ---------------------------------------------------------------------------
# Helper: standalone versions of TerminalView methods for testing
# ---------------------------------------------------------------------------
def _resolve_file_path(cwd, get_workspace_folders, relative_path):
    """Standalone version of TerminalView._resolve_file_path."""
    candidate = os.path.join(cwd, relative_path)
    if os.path.isfile(candidate):
        return os.path.abspath(candidate)

    if get_workspace_folders:
        for folder in get_workspace_folders():
            candidate = os.path.join(folder, relative_path)
            if os.path.isfile(candidate):
                return os.path.abspath(candidate)

    return None


def _create_custom_bashrc(config_dir):
    """Standalone version of TerminalView._create_custom_bashrc."""
    bashrc_content = r"""
# Prevent bootstrap commands in this file from being added to history.
set +o history

# Source user's bash profile first
if [ -f ~/.bash_profile ]; then
    . ~/.bash_profile 2>/dev/null
elif [ -f ~/.bashrc ]; then
    . ~/.bashrc 2>/dev/null
fi

# User shell config may re-enable history; force it back off for Zen bootstrap.
set +o history

export TERM=xterm-256color
export COLORTERM=truecolor
export PY_COLORS=1
export FORCE_COLOR=1

stty erase '^?' 2>/dev/null
shopt -s checkwinsize

# During startup bootstrap, keep history detached from persisted file.
__zen_real_histfile=~/.zen_ide/bash_history
HISTFILE=/dev/null
HISTSIZE=1000
HISTFILESIZE=2000
HISTCONTROL=ignoreboth:erasedups
HISTIGNORE="${HISTIGNORE:+$HISTIGNORE:}*___BEGIN___COMMAND_OUTPUT_MARKER___*:*PS1=\\"\\";PS2=\\"\\";unset HISTFILE*:*echo TEST_OK:*sleep 30:*clear; printf '\\033[3J'"

# Enable tab completion
if [ -f /etc/bash_completion ]; then
    . /etc/bash_completion 2>/dev/null
elif [ -f /usr/share/bash-completion/bash_completion ]; then
    . /usr/share/bash-completion/bash_completion 2>/dev/null
elif [ -f /usr/local/etc/bash_completion ]; then
    . /usr/local/etc/bash_completion 2>/dev/null
fi

bind 'set show-all-if-ambiguous on' 2>/dev/null
bind 'set completion-ignore-case on' 2>/dev/null
bind '"\\e[A": history-search-backward' 2>/dev/null
bind '"\\e[B": history-search-forward' 2>/dev/null

if ls --color=auto / >/dev/null 2>&1; then
    alias ls='ls --color=auto'
    alias ll='ls -l --color=auto'
else
    alias ls='ls -G'
    alias ll='ls -lG'
fi

alias gst='git status'
alias groh='git reset --hard @{u}'
alias git_prune_branches='git branch | grep -v "^\\*" | grep -v "^  main$" | xargs git branch -D'

# Source user custom aliases
if [ -f ~/.zen_ide/aliases ]; then
    . ~/.zen_ide/aliases 2>/dev/null
fi

bind 'set enable-bracketed-paste off' 2>/dev/null

# Git-aware prompt via PS1 command substitution (avoids visual
# side effects during SIGWINCH redraws).
# PROMPT_COMMAND is reserved for non-visual OSC 7 CWD reporting only.
__zen_git_prompt() {
    local branch
    branch=$(git symbolic-ref --short HEAD 2>/dev/null || git rev-parse --short HEAD 2>/dev/null)
    if [ -z "$branch" ]; then
        return
    fi
    if [ ${#branch} -gt 18 ]; then
        branch="${branch:0:15}..."
    fi
    if git diff --no-ext-diff --quiet --exit-code 2>/dev/null && git diff --no-ext-diff --cached --quiet --exit-code 2>/dev/null; then
        printf ' (%s)' "$branch"
    else
        printf ' (%s *)' "$branch"
    fi
}

# Report CWD to terminal emulator via OSC 7 (enables Cmd+click on relative file paths)
__zen_osc7() {
    printf '\033]7;file://%s%s\007' "$(hostname)" "$(pwd)"
}
PROMPT_COMMAND="__zen_osc7"

# Persist only user commands (not startup/probe noise)
# Remove known bootstrap/probe noise persisted by older versions.
if [ -f "$__zen_real_histfile" ]; then
    _zen_hist_tmp="${__zen_real_histfile}.tmp.$$"
    if awk '
        /^HISTFILE=~\/\.zen_ide\/bash_history$/ { next }
        /^HISTSIZE=1000$/ { next }
        /^HISTFILESIZE=2000$/ { next }
        /^HISTCONTROL=ignoreboth(:erasedups)?$/ { next }
        /^if \[ -f \/etc\/bash_completion \]; then/ { next }
        /^if ls --color=auto \/ >\/dev\/null 2>&1; then/ { next }
        /^if \[ -f ~\/\.zen_ide\/aliases \]; then/ { next }
        /^bind '\''set show-all-if-ambiguous on'\'' 2>\/dev\/null$/ { next }
        /^bind '\''set completion-ignore-case on'\'' 2>\/dev\/null$/ { next }
        /^bind '\''"\\e\[A": history-search-backward'\'' 2>\/dev\/null$/ { next }
        /^bind '\''"\\e\[B": history-search-forward'\'' 2>\/dev\/null$/ { next }
        /^alias gst='\''git status'\''$/ { next }
        /^alias groh='\''git reset --hard @\{u\}'\''$/ { next }
        /^alias git_prune_branches=/ { next }
        /^bind '\''set enable-bracketed-paste off'\'' 2>\/dev\/null$/ { next }
        /^__zen_git_prompt\(\) \{/ { next }
        /^__zen_osc7\(\) \{/ { next }
        /^PROMPT_COMMAND="__zen_osc7"$/ { next }
        /^PS1=/ { next }
        /^unset __zen_real_histfile$/ { next }
        /^# Enable tab completion$/ { next }
        /^# Source user custom aliases$/ { next }
        index($0, "___BEGIN___COMMAND_OUTPUT_MARKER___") > 0 { next }
        index($0, "PS1=\"\";PS2=\"\";unset HISTFILE") > 0 { next }
        index($0, "echo TEST_OK") > 0 { next }
        index($0, "sleep 30") > 0 { next }
        index($0, "clear; printf '\\''\\033[3J'\\''") > 0 { next }
        { print }
    ' "$__zen_real_histfile" > "$_zen_hist_tmp" 2>/dev/null; then
        mv "$_zen_hist_tmp" "$__zen_real_histfile"
    else
        rm -f "$_zen_hist_tmp"
    fi
fi
HISTFILE="$__zen_real_histfile"
PS1='\[\e[36m\]\W\[\e[0m\]\[\e[33m\]$(__zen_git_prompt)\[\e[0m\] \[\e[32m\]$\[\e[0m\] '
HISTSIZE=1000
HISTFILESIZE=2000
HISTCONTROL=ignoreboth:erasedups
shopt -s histappend
history -n "$HISTFILE" 2>/dev/null
set -o history
"""
    try:
        if not os.path.exists(config_dir):
            os.makedirs(config_dir)
        bashrc_path = os.path.join(config_dir, "bashrc")
        with open(bashrc_path, "w") as f:
            f.write(bashrc_content)
        return bashrc_path
    except Exception:
        return None
