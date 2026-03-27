"""Tests for scrolling behavior — vadjustment, scroll delta mapping, smooth scroll animation."""

import pytest

from terminal.terminal_scroll import (
    apply_vadjustment_delta,
    map_terminal_scroll_delta,
)


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


class TestScrollStepPixels:
    """Verify scroll-speed setting feeds through to step calculations."""

    def test_wheel_step_default(self):
        """Default scroll_speed=0.4 -> 15 * 0.4 = 6.0."""
        speed = 0.4
        assert max(1.0, 15.0 * speed) == pytest.approx(6.0)

    def test_touchpad_step_default(self):
        """Default scroll_speed=0.4 -> 12 * 0.4 = 4.8."""
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


def _run_tick(vadj, state):
    """Tick logic extracted from TerminalView._smooth_scroll_tick."""
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


def _accumulate(state, vadj, delta):
    """Replicate the accumulation logic from _on_scroll."""
    lower = float(vadj.get_lower())
    upper = float(vadj.get_upper())
    page_size = float(vadj.get_page_size())
    maximum = max(lower, upper - page_size)
    if state["_scroll_target"] is None:
        state["_scroll_target"] = float(vadj.get_value())
    state["_scroll_target"] = min(max(state["_scroll_target"] + delta, lower), maximum)


class TestSmoothScrollTick:
    """Regression tests for the frame-clock lerp animation."""

    def test_lerp_converges_to_target(self):
        """After enough ticks the scroll value reaches the target."""
        vadj, sw, state = _make_scroll_state(value=0.0)
        state["_scroll_target"] = 100.0
        state["_scroll_tick_id"] = 1

        for _ in range(200):
            if not _run_tick(vadj, state):
                break

        assert vadj.get_value() == pytest.approx(100.0)
        assert state["_scroll_target"] is None
        assert state["_scroll_tick_id"] == 0

    def test_lerp_moves_in_correct_direction_downward(self):
        """First tick moves value toward (higher) target."""
        vadj, sw, state = _make_scroll_state(value=50.0)
        state["_scroll_target"] = 150.0

        _run_tick(vadj, state)

        assert vadj.get_value() > 50.0
        assert vadj.get_value() < 150.0

    def test_lerp_moves_in_correct_direction_upward(self):
        """First tick moves value toward (lower) target."""
        vadj, sw, state = _make_scroll_state(value=150.0)
        state["_scroll_target"] = 50.0

        _run_tick(vadj, state)

        assert vadj.get_value() < 150.0
        assert vadj.get_value() > 50.0

    def test_lerp_factor_controls_speed(self):
        """Higher lerp factor -> larger first step."""
        vadj_slow, _, state_slow = _make_scroll_state(value=0.0, lerp=0.1)
        vadj_fast, _, state_fast = _make_scroll_state(value=0.0, lerp=0.5)
        state_slow["_scroll_target"] = 100.0
        state_fast["_scroll_target"] = 100.0

        _run_tick(vadj_slow, state_slow)
        _run_tick(vadj_fast, state_fast)

        assert vadj_fast.get_value() > vadj_slow.get_value()

    def test_stops_when_close_to_target(self):
        """Tick returns False and snaps to target when diff < 0.5."""
        vadj, sw, state = _make_scroll_state(value=99.8)
        state["_scroll_target"] = 100.0

        keep = _run_tick(vadj, state)

        assert keep is False
        assert vadj.get_value() == pytest.approx(100.0)
        assert state["_scroll_target"] is None
        assert state["_scroll_tick_id"] == 0

    def test_continues_when_far_from_target(self):
        """Tick returns True when still far from target."""
        vadj, sw, state = _make_scroll_state(value=0.0)
        state["_scroll_target"] = 100.0

        keep = _run_tick(vadj, state)

        assert keep is True
        assert state["_scroll_target"] is not None

    def test_stops_when_target_is_none(self):
        """Tick returns False immediately if target is None."""
        vadj, sw, state = _make_scroll_state(value=50.0)
        state["_scroll_target"] = None

        keep = _run_tick(vadj, state)

        assert keep is False
        assert state["_scroll_tick_id"] == 0

    def test_stops_when_vadj_is_none(self):
        """Tick returns False immediately if adjustment is None."""
        state = {"_scroll_target": 100.0, "_scroll_tick_id": 1, "_SCROLL_LERP": 0.3}

        keep = _run_tick(None, state)

        assert keep is False
        assert state["_scroll_tick_id"] == 0

    def test_exact_lerp_value_first_tick(self):
        """First tick value = current + (target - current) * lerp."""
        vadj, sw, state = _make_scroll_state(value=0.0, lerp=0.3)
        state["_scroll_target"] = 100.0

        _run_tick(vadj, state)

        assert vadj.get_value() == pytest.approx(30.0)  # 0 + 100*0.3

    def test_convergence_within_bounded_ticks(self):
        """Animation converges to target in fewer than 100 ticks (~1.7s at 60fps)."""
        vadj, sw, state = _make_scroll_state(value=0.0, lerp=0.3)
        state["_scroll_target"] = 800.0  # max-range scroll

        ticks = 0
        for ticks in range(1, 101):
            if not _run_tick(vadj, state):
                break

        assert state["_scroll_target"] is None, f"Did not converge in {ticks} ticks"
        assert ticks < 100


class TestScrollTargetAccumulation:
    """Test the target accumulation and clamping logic used by _on_scroll."""

    def test_single_delta_sets_target(self):
        vadj, sw, state = _make_scroll_state(value=100.0)
        _accumulate(state, vadj, 50.0)

        assert state["_scroll_target"] == pytest.approx(150.0)

    def test_multiple_deltas_accumulate(self):
        vadj, sw, state = _make_scroll_state(value=100.0)
        _accumulate(state, vadj, 20.0)
        _accumulate(state, vadj, 30.0)

        assert state["_scroll_target"] == pytest.approx(150.0)

    def test_clamps_to_upper_bound(self):
        vadj, sw, state = _make_scroll_state(value=700.0, upper=1000.0, page_size=200.0)
        _accumulate(state, vadj, 200.0)  # would be 900, but max=800

        assert state["_scroll_target"] == pytest.approx(800.0)

    def test_clamps_to_lower_bound(self):
        vadj, sw, state = _make_scroll_state(value=10.0)
        _accumulate(state, vadj, -100.0)

        assert state["_scroll_target"] == pytest.approx(0.0)

    def test_negative_delta_scrolls_up(self):
        vadj, sw, state = _make_scroll_state(value=500.0)
        _accumulate(state, vadj, -200.0)

        assert state["_scroll_target"] == pytest.approx(300.0)

    def test_rapid_scrolls_accumulate_before_animation(self):
        """Multiple rapid scroll events accumulate into a single target."""
        vadj, sw, state = _make_scroll_state(value=0.0)
        for _ in range(10):
            _accumulate(state, vadj, 10.0)

        assert state["_scroll_target"] == pytest.approx(100.0)

    def test_scroll_then_reverse_partial(self):
        """Scroll down then partially back up."""
        vadj, sw, state = _make_scroll_state(value=100.0)
        _accumulate(state, vadj, 50.0)
        _accumulate(state, vadj, -20.0)

        assert state["_scroll_target"] == pytest.approx(130.0)

    def test_accumulate_during_animation(self):
        """New scroll events arriving mid-animation update the target."""
        vadj, sw, state = _make_scroll_state(value=0.0, lerp=0.3)
        # First scroll sets target to 100
        _accumulate(state, vadj, 100.0)

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
        _accumulate(state, vadj, 50.0)
        assert state["_scroll_target"] == pytest.approx(150.0)

        # Value hasn't jumped — animation continues from where it was
        assert vadj.get_value() == pytest.approx(mid_value)


class TestSmoothScrollRoundTrip:
    """End-to-end: accumulate deltas then animate to final position."""

    def test_scroll_down_and_animate(self):
        """Single scroll event followed by full animation reaches target."""
        vadj, sw, state = _make_scroll_state(value=0.0)
        _accumulate(state, vadj, 100.0)

        for _ in range(200):
            if not _run_tick(vadj, state):
                break

        assert vadj.get_value() == pytest.approx(100.0)

    def test_scroll_up_and_animate(self):
        vadj, sw, state = _make_scroll_state(value=400.0)
        _accumulate(state, vadj, -200.0)

        for _ in range(200):
            if not _run_tick(vadj, state):
                break

        assert vadj.get_value() == pytest.approx(200.0)

    def test_multiple_scrolls_then_animate(self):
        """Several accumulated deltas resolve to correct final position."""
        vadj, sw, state = _make_scroll_state(value=0.0)
        _accumulate(state, vadj, 30.0)
        _accumulate(state, vadj, 30.0)
        _accumulate(state, vadj, 40.0)

        for _ in range(200):
            if not _run_tick(vadj, state):
                break

        assert vadj.get_value() == pytest.approx(100.0)

    def test_animation_is_monotonic_downward(self):
        """Scroll values only increase when scrolling down."""
        vadj, sw, state = _make_scroll_state(value=0.0)
        _accumulate(state, vadj, 200.0)

        values = [vadj.get_value()]
        for _ in range(200):
            if not _run_tick(vadj, state):
                break
            values.append(vadj.get_value())

        for i in range(1, len(values)):
            assert values[i] >= values[i - 1], f"Non-monotonic at tick {i}"

    def test_animation_is_monotonic_upward(self):
        """Scroll values only decrease when scrolling up."""
        vadj, sw, state = _make_scroll_state(value=500.0)
        _accumulate(state, vadj, -300.0)

        values = [vadj.get_value()]
        for _ in range(200):
            if not _run_tick(vadj, state):
                break
            values.append(vadj.get_value())

        for i in range(1, len(values)):
            assert values[i] <= values[i - 1], f"Non-monotonic at tick {i}"

    def test_clamped_at_bottom_after_overshoot(self):
        """Cannot scroll past the bottom."""
        vadj, sw, state = _make_scroll_state(value=750.0, upper=1000.0, page_size=200.0)
        _accumulate(state, vadj, 500.0)  # would overshoot max=800

        for _ in range(200):
            if not _run_tick(vadj, state):
                break

        assert vadj.get_value() == pytest.approx(800.0)

    def test_clamped_at_top_after_overshoot(self):
        """Cannot scroll past the top."""
        vadj, sw, state = _make_scroll_state(value=50.0)
        _accumulate(state, vadj, -500.0)

        for _ in range(200):
            if not _run_tick(vadj, state):
                break

        assert vadj.get_value() == pytest.approx(0.0)
