#!/usr/bin/env python3
"""
PanedWindow sash drag performance profiler.
"""

import time


def profile_sash_drag(paned_window, num_moves=50):
    """Simulate sash drag and measure performance."""
    times = []

    # Get current sash position
    try:
        current_pos = paned_window.sash_coord(0)[0]
    except Exception:
        print("No sash available")
        return []

    for i in range(num_moves):
        # Oscillate position
        offset = (i % 10) - 5
        new_pos = current_pos + offset * 10

        start = time.perf_counter()
        paned_window.sash_place(0, new_pos, 0)
        paned_window.update_idletasks()
        elapsed = time.perf_counter() - start
        times.append(elapsed * 1000)  # ms

    # Restore position
    paned_window.sash_place(0, current_pos, 0)

    if times:
        avg = sum(times) / len(times)
        max_t = max(times)
        min_t = min(times)

        print(f"Sash drag performance ({num_moves} moves):")
        print(f"  Avg: {avg:.2f}ms")
        print(f"  Min: {min_t:.2f}ms")
        print(f"  Max: {max_t:.2f}ms")

    return times


if __name__ == "__main__":
    print("Run this from within the IDE to profile sash drag")
