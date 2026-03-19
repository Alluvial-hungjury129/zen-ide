"""Helpers for VTE scrolling configuration."""


def configure_vte_scrolling(terminal) -> None:
    """Opt into the best GtkScrolledWindow/VTE scrolling path available.

    ``scroll-unit-is-pixels`` only changes the GtkAdjustment units exposed by
    VTE. It helps GtkScrolledWindow keep high-resolution deltas in pixel space,
    but it does not guarantee visually sub-row scrolling.

    ``enable-fallback-scrolling`` keeps unconsumed scroll events flowing to the
    parent GtkScrolledWindow, which is how kinetic scrolling works while VTE
    does not implement it on its own.
    """

    if hasattr(terminal, "set_enable_fallback_scrolling"):
        terminal.set_enable_fallback_scrolling(True)
    elif terminal.find_property("enable-fallback-scrolling") is not None:
        terminal.set_property("enable-fallback-scrolling", True)

    if hasattr(terminal, "set_scroll_unit_is_pixels"):
        terminal.set_scroll_unit_is_pixels(True)
    elif terminal.find_property("scroll-unit-is-pixels") is not None:
        terminal.set_property("scroll-unit-is-pixels", True)


def apply_vadjustment_delta(vadjustment, delta: float) -> bool:
    """Apply a pixel delta to a vertical adjustment and clamp to valid range."""
    lower = float(vadjustment.get_lower())
    upper = float(vadjustment.get_upper())
    page_size = float(vadjustment.get_page_size())
    current = float(vadjustment.get_value())
    maximum = max(lower, upper - page_size)
    target = min(max(current + float(delta), lower), maximum)
    if abs(target - current) < 1e-6:
        return False
    vadjustment.set_value(target)
    return True


def map_terminal_scroll_delta(
    controller,
    dy: float,
    *,
    wheel_step_pixels: float,
    touchpad_step_pixels: float,
    gdk_module,
) -> tuple[bool, float]:
    """Map GTK scroll events to terminal adjustment deltas.

    Returns ``(consume, delta)``:
    - Discrete wheel ticks return ``(True, dy * wheel_step_pixels)``.
    - Touchpad/smooth events return ``(True, dy * touchpad_step_pixels)`` so the
      adjustment always moves in pixel deltas through a single path.
    - On very old GTK bindings without ``ScrollUnit``, we consume the event and
      preserve legacy behavior by forwarding raw ``dy``.
    """
    dy = float(dy)
    if dy == 0.0:
        return False, 0.0

    get_unit = getattr(controller, "get_unit", None)
    scroll_unit = getattr(gdk_module, "ScrollUnit", None) if gdk_module is not None else None
    if callable(get_unit) and scroll_unit is not None:
        if get_unit() == scroll_unit.WHEEL:
            return True, dy * float(wheel_step_pixels)
        return True, dy * float(touchpad_step_pixels)

    return True, dy
