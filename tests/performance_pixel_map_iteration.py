#!/usr/bin/env python3
"""
Performance comparison: dict iteration vs. flat-list iteration for pixel maps.

GlobalAnimationController._pixel_map is a dict keyed by (x, y) tuples. When
animations iterate over all pixels every frame, Python must materialize a new
(key, value) tuple on each step (dict items view), generating GC pressure.

The optimized approach pre-builds _pixel_list — a flat list of
(gx, gy, manager, idx) tuples allocated once at registration time. Animation
loops iterate the list directly, reusing already-allocated tuple objects and
avoiding per-frame allocations.

This file benchmarks the allocation difference at representative canvas sizes.
"""

import sys
import time


# ---------------------------------------------------------------------------
# Simulate the two iteration styles at a fixed canvas size
# ---------------------------------------------------------------------------

class _FakeManager:
    """Minimal stand-in that mirrors the real manager interface."""
    pass


def _make_pixel_map(width, height):
    """Build a dict like GlobalAnimationController._pixel_map."""
    mgr = _FakeManager()
    return {(x, y): (mgr, y * width + x) for y in range(height) for x in range(width)}


def _make_pixel_list(pixel_map):
    """Build a flat list like GlobalAnimationController._pixel_list."""
    return [(gx, gy, mgr, idx) for (gx, gy), (mgr, idx) in pixel_map.items()]


def bench_dict_iteration(pixel_map, frames=500):
    """Iterate pixel_map.items() once per frame — old approach."""
    start = time.perf_counter()
    for _ in range(frames):
        for (gx, gy), (manager, idx) in pixel_map.items():
            # Simulate cheapest possible per-pixel work (hue calc placeholder)
            _ = gx + gy + idx
    return time.perf_counter() - start


def bench_list_iteration(pixel_list, frames=500):
    """Iterate _pixel_list once per frame — optimized approach."""
    start = time.perf_counter()
    for _ in range(frames):
        for gx, gy, manager, idx in pixel_list:
            _ = gx + gy + idx
    return time.perf_counter() - start


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_benchmark(label, width, height, frames=500):
    pixel_map = _make_pixel_map(width, height)
    pixel_list = _make_pixel_list(pixel_map)
    pixel_count = width * height

    t_dict = bench_dict_iteration(pixel_map, frames)
    t_list = bench_list_iteration(pixel_list, frames)

    improvement = ((t_dict - t_list) / t_dict * 100) if t_dict > 0 else 0.0
    faster = "faster" if t_list < t_dict else "slower"

    print(f"\n{label} ({pixel_count} pixels, {frames} frames)")
    print(f"  dict iteration : {t_dict * 1000:.2f} ms  ({t_dict / frames * 1e6:.1f} µs/frame)")
    print(f"  list iteration : {t_list * 1000:.2f} ms  ({t_list / frames * 1e6:.1f} µs/frame)")
    print(f"  list is {abs(improvement):.1f}% {faster} than dict")

    return t_dict, t_list


if __name__ == "__main__":
    print("=" * 60)
    print("Pixel map iteration benchmark")
    print("(dict.items() vs pre-built flat list)")
    print("=" * 60)

    # Small canvas: single 8×8 matrix
    run_benchmark("8×8 matrix (64 pixels)", 8, 8)

    # Medium canvas: 8×8 matrix + 8-pixel LED strip = ~72 pixels
    run_benchmark("8×9 canvas (72 pixels)", 8, 9)

    # Larger canvas: 16×16 matrix
    run_benchmark("16×16 matrix (256 pixels)", 16, 16)

    print()
    print("=" * 60)
    print("Benchmark complete")
    print("=" * 60)
    sys.exit(0)
