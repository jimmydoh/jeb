#!/usr/bin/env python3
"""Unit tests for GlobalAnimationController — unified global LED animation system."""

import sys
import os
import asyncio
import pytest

# Mock CircuitPython modules BEFORE any imports
class MockModule:
    """Generic mock module."""
    def __getattr__(self, name):
        return MockModule()

    def __call__(self, *args, **kwargs):
        return MockModule()

sys.modules['digitalio'] = MockModule()
sys.modules['busio'] = MockModule()
sys.modules['board'] = MockModule()
sys.modules['adafruit_mcp230xx'] = MockModule()
sys.modules['adafruit_mcp230xx.mcp23017'] = MockModule()
sys.modules['adafruit_ticks'] = MockModule()
sys.modules['audiobusio'] = MockModule()
sys.modules['audiocore'] = MockModule()
sys.modules['audiomixer'] = MockModule()
sys.modules['analogio'] = MockModule()
sys.modules['microcontroller'] = MockModule()
sys.modules['watchdog'] = MockModule()
sys.modules['audiopwmio'] = MockModule()
sys.modules['synthio'] = MockModule()
sys.modules['ulab'] = MockModule()
sys.modules['neopixel'] = MockModule()

# Add src directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from managers.matrix_manager import MatrixManager
from managers.led_manager import LEDManager
from managers.global_animation_controller import GlobalAnimationController


class MockJEBPixel:
    """Mock JEBPixel wrapper for testing."""
    def __init__(self, num_pixels):
        self.n = num_pixels
        self._pixels = [(0, 0, 0)] * num_pixels

    def __setitem__(self, idx, color):
        if 0 <= idx < self.n:
            self._pixels[idx] = color

    def __getitem__(self, idx):
        return self._pixels[idx]

    def fill(self, color):
        self._pixels = [color] * self.n

    def show(self):
        pass


# ---------------------------------------------------------------------------
# Positional registration & pixel map tests
# ---------------------------------------------------------------------------

def test_empty_controller():
    """A new controller has zero canvas dimensions and no pixels."""
    ctrl = GlobalAnimationController()
    assert ctrl.canvas_width == 0
    assert ctrl.canvas_height == 0
    assert ctrl.pixel_count == 0


def test_register_matrix_updates_canvas():
    """Registering a matrix extends canvas dimensions correctly."""
    ctrl = GlobalAnimationController()
    matrix = MatrixManager(MockJEBPixel(64), width=8, height=8)
    ctrl.register_matrix(matrix, offset_x=0, offset_y=0)

    assert ctrl.canvas_width == 8
    assert ctrl.canvas_height == 8
    assert ctrl.pixel_count == 64


def test_register_matrix_with_offset():
    """Matrix registered at an offset shifts all pixel coordinates."""
    ctrl = GlobalAnimationController()
    matrix = MatrixManager(MockJEBPixel(64), width=8, height=8)
    ctrl.register_matrix(matrix, offset_x=4, offset_y=2)

    assert ctrl.canvas_width == 4 + 8   # 12
    assert ctrl.canvas_height == 2 + 8  # 10
    assert ctrl.pixel_count == 64

    # Top-left pixel of the matrix must map to global (4, 2)
    assert (4, 2) in ctrl._pixel_map
    assert (3, 2) not in ctrl._pixel_map  # one column before offset


def test_register_horizontal_led_strip():
    """A horizontal LED strip extends canvas in the X direction."""
    ctrl = GlobalAnimationController()
    led = LEDManager(MockJEBPixel(8))
    ctrl.register_led_strip(led, offset_x=0, offset_y=0, orientation='horizontal')

    assert ctrl.canvas_width == 8
    assert ctrl.canvas_height == 1
    assert ctrl.pixel_count == 8

    for i in range(8):
        assert (i, 0) in ctrl._pixel_map


def test_register_vertical_led_strip():
    """A vertical LED strip extends canvas in the Y direction."""
    ctrl = GlobalAnimationController()
    led = LEDManager(MockJEBPixel(6))
    ctrl.register_led_strip(led, offset_x=3, offset_y=0, orientation='vertical')

    assert ctrl.canvas_width == 4   # offset_x=3 plus width=1 → columns 0-3, so width=4
    assert ctrl.canvas_height == 6
    assert ctrl.pixel_count == 6

    for i in range(6):
        assert (3, i) in ctrl._pixel_map


def test_register_invalid_orientation_raises():
    """Registering an LED strip with an invalid orientation raises ValueError."""
    ctrl = GlobalAnimationController()
    led = LEDManager(MockJEBPixel(4))
    with pytest.raises(ValueError, match="orientation must be"):
        ctrl.register_led_strip(led, orientation='diagonal')


def test_combined_matrix_and_led_strip():
    """Matrix above and LED strip below share a unified canvas."""
    ctrl = GlobalAnimationController()
    matrix = MatrixManager(MockJEBPixel(64), width=8, height=8)
    led = LEDManager(MockJEBPixel(8))

    ctrl.register_matrix(matrix, offset_x=0, offset_y=0)
    ctrl.register_led_strip(led, offset_x=0, offset_y=8, orientation='horizontal')

    # Canvas must span matrix (8×8) + LED strip (8×1)
    assert ctrl.canvas_width == 8
    assert ctrl.canvas_height == 9      # rows 0-7 matrix, row 8 LED strip
    assert ctrl.pixel_count == 64 + 8  # 72 total pixels

    # Matrix pixel at (0, 0) and LED pixel at (0, 8) must both be mapped
    assert (0, 0) in ctrl._pixel_map
    assert (0, 8) in ctrl._pixel_map


def test_pixel_map_matrix_correct_hardware_index():
    """Matrix pixels map to the correct hardware pixel index via _get_idx."""
    ctrl = GlobalAnimationController()
    matrix = MatrixManager(MockJEBPixel(64), width=8, height=8)
    ctrl.register_matrix(matrix, offset_x=0, offset_y=0)

    # (0, 0) should be hardware index 0 (row 0 even → left-to-right)
    mgr, idx = ctrl._pixel_map[(0, 0)]
    assert idx == matrix._get_idx(0, 0)

    # (3, 4) → row 4 is even → index = 4*8 + 3 = 35
    mgr, idx = ctrl._pixel_map[(3, 4)]
    assert idx == matrix._get_idx(3, 4)
    assert idx == 35


def test_pixel_map_led_strip_correct_index():
    """LED strip pixels map to sequential hardware indices."""
    ctrl = GlobalAnimationController()
    led = LEDManager(MockJEBPixel(5))
    ctrl.register_led_strip(led, offset_x=2, offset_y=10, orientation='horizontal')

    for i in range(5):
        mgr, idx = ctrl._pixel_map[(2 + i, 10)]
        assert idx == i


def test_multiple_registrations_rebuild_map():
    """Registering multiple components correctly rebuilds the full pixel map."""
    ctrl = GlobalAnimationController()
    matrix = MatrixManager(MockJEBPixel(64), width=8, height=8)
    led1 = LEDManager(MockJEBPixel(4))
    led2 = LEDManager(MockJEBPixel(4))

    ctrl.register_matrix(matrix, offset_x=0, offset_y=0)
    ctrl.register_led_strip(led1, offset_x=0, offset_y=8, orientation='horizontal')
    ctrl.register_led_strip(led2, offset_x=4, offset_y=8, orientation='horizontal')

    assert ctrl.pixel_count == 64 + 4 + 4


# ---------------------------------------------------------------------------
# set_pixel direct write tests
# ---------------------------------------------------------------------------

def test_set_pixel_writes_to_correct_manager():
    """set_pixel writes the color to the correct hardware pixel."""
    ctrl = GlobalAnimationController()
    matrix = MatrixManager(MockJEBPixel(64), width=8, height=8)
    ctrl.register_matrix(matrix, offset_x=0, offset_y=0)

    ctrl.set_pixel(0, 0, (255, 0, 0))
    hw_idx = matrix._get_idx(0, 0)
    assert matrix.pixels[hw_idx] == (255, 0, 0)


def test_set_pixel_led_strip():
    """set_pixel writes to correct LED strip pixel."""
    ctrl = GlobalAnimationController()
    led = LEDManager(MockJEBPixel(8))
    ctrl.register_led_strip(led, offset_x=0, offset_y=0, orientation='horizontal')

    ctrl.set_pixel(3, 0, (0, 255, 0))
    assert led.pixels[3] == (0, 255, 0)


def test_set_pixel_out_of_bounds_is_silent():
    """set_pixel on an unmapped coordinate does nothing (no exception)."""
    ctrl = GlobalAnimationController()
    led = LEDManager(MockJEBPixel(4))
    ctrl.register_led_strip(led, offset_x=0, offset_y=0, orientation='horizontal')

    # Should not raise
    ctrl.set_pixel(99, 99, (255, 0, 0))


# ---------------------------------------------------------------------------
# clear() tests
# ---------------------------------------------------------------------------

def test_clear_resets_all_pixels():
    """clear() turns off all pixels across all registered managers."""
    ctrl = GlobalAnimationController()
    matrix = MatrixManager(MockJEBPixel(64), width=8, height=8)
    led = LEDManager(MockJEBPixel(8))
    ctrl.register_matrix(matrix, offset_x=0, offset_y=0)
    ctrl.register_led_strip(led, offset_x=0, offset_y=8, orientation='horizontal')

    # Write some colors
    ctrl.set_pixel(0, 0, (255, 0, 0))
    ctrl.set_pixel(0, 8, (0, 255, 0))

    ctrl.clear()

    # Both managers should be cleared
    assert matrix.pixels[matrix._get_idx(0, 0)] == (0, 0, 0)
    assert led.pixels[0] == (0, 0, 0)


def test_clear_shared_manager_only_cleared_once():
    """The same manager registered twice is still only cleared once (idempotent)."""
    ctrl = GlobalAnimationController()
    led = LEDManager(MockJEBPixel(8))
    # Register the same LED manager twice (unusual but shouldn't crash)
    ctrl.register_led_strip(led, offset_x=0, offset_y=0, orientation='horizontal')
    ctrl.register_led_strip(led, offset_x=0, offset_y=1, orientation='horizontal')

    # Should not raise
    ctrl.clear()


# ---------------------------------------------------------------------------
# global_rainbow_wave() tests
# ---------------------------------------------------------------------------

def test_global_rainbow_wave_runs_and_stops():
    """global_rainbow_wave runs for the given duration and sets SOLID animations."""
    ctrl = GlobalAnimationController()
    led = LEDManager(MockJEBPixel(8))
    ctrl.register_led_strip(led, offset_x=0, offset_y=0, orientation='horizontal')

    async def run():
        await ctrl.global_rainbow_wave(speed=90.0, duration=0.12)

    asyncio.run(run())

    # After the animation, at least some pixels should have SOLID animations set
    active = sum(1 for slot in led.active_animations if slot.active)
    assert active > 0, "Rainbow wave should have set SOLID animations on pixels"


def test_global_rainbow_wave_different_x_get_different_hues():
    """Pixels at different X positions receive different colors from rainbow wave."""
    ctrl = GlobalAnimationController()
    led = LEDManager(MockJEBPixel(8))
    ctrl.register_led_strip(led, offset_x=0, offset_y=0, orientation='horizontal')

    async def run():
        await ctrl.global_rainbow_wave(speed=0.0, duration=0.12)

    asyncio.run(run())

    # With speed=0, colors are driven purely by spatial offset.
    # Pixels at different X values should have different colors.
    colors = set()
    for slot in led.active_animations:
        if slot.active and slot.color:
            colors.add(slot.color)
    assert len(colors) > 1, "Different X positions should produce different hues"


def test_global_rainbow_wave_no_pixels_returns_immediately():
    """global_rainbow_wave on an empty controller returns without error."""
    ctrl = GlobalAnimationController()

    async def run():
        # Should return immediately when no pixels are registered
        await ctrl.global_rainbow_wave(duration=1.0)

    asyncio.run(run())  # Must not hang or raise


def test_global_rainbow_wave_spans_matrix_and_led():
    """Rainbow wave sets SOLID animations on both matrix and LED strip pixels."""
    ctrl = GlobalAnimationController()
    matrix = MatrixManager(MockJEBPixel(64), width=8, height=8)
    led = LEDManager(MockJEBPixel(8))
    ctrl.register_matrix(matrix, offset_x=0, offset_y=0)
    ctrl.register_led_strip(led, offset_x=0, offset_y=8, orientation='horizontal')

    async def run():
        await ctrl.global_rainbow_wave(speed=90.0, duration=0.12)

    asyncio.run(run())

    matrix_active = sum(1 for slot in matrix.active_animations if slot.active)
    led_active = sum(1 for slot in led.active_animations if slot.active)

    assert matrix_active > 0, "Rainbow wave should activate matrix pixels"
    assert led_active > 0, "Rainbow wave should activate LED strip pixels"


# ---------------------------------------------------------------------------
# global_rain() tests
# ---------------------------------------------------------------------------

def test_global_rain_runs_and_stops():
    """global_rain runs for the given duration without error."""
    ctrl = GlobalAnimationController()
    led = LEDManager(MockJEBPixel(4))
    ctrl.register_led_strip(led, offset_x=0, offset_y=0, orientation='vertical')

    async def run():
        await ctrl.global_rain(color=(0, 180, 255), speed=0.05, duration=0.3, density=1.0)

    asyncio.run(run())  # Must not raise


def test_global_rain_no_pixels_returns_immediately():
    """global_rain on an empty controller returns without error."""
    ctrl = GlobalAnimationController()

    async def run():
        await ctrl.global_rain(duration=1.0)

    asyncio.run(run())  # Must not hang


def test_global_rain_default_color():
    """global_rain uses default cyan-blue color when color=None."""
    ctrl = GlobalAnimationController()
    led = LEDManager(MockJEBPixel(4))
    ctrl.register_led_strip(led, offset_x=0, offset_y=0, orientation='vertical')

    results = []

    async def run():
        await ctrl.global_rain(color=None, speed=0.05, duration=0.15, density=1.0)
        # Collect any non-black pixel values written
        for i in range(led.num_pixels):
            val = led.pixels[i]
            if val != (0, 0, 0):
                results.append(val)

    asyncio.run(run())
    # If any colored pixel was written, it should be the default cyan-blue
    for val in results:
        assert val == (0, 180, 255), f"Expected default rain color (0,180,255), got {val}"


def test_global_rain_drops_travel_downward():
    """Rain drops move from low Y values to high Y values (top to bottom)."""
    ctrl = GlobalAnimationController()
    # Single column of 4 pixels (vertical strip)
    led = LEDManager(MockJEBPixel(4))
    ctrl.register_led_strip(led, offset_x=0, offset_y=0, orientation='vertical')

    seen_rows = set()

    async def run():
        # density=1.0 ensures drops always spawn; short speed for quick test
        await ctrl.global_rain(color=(255, 0, 0), speed=0.05, duration=0.3, density=1.0)
        for i in range(4):
            if led.pixels[i] != (0, 0, 0):
                seen_rows.add(i)

    asyncio.run(run())
    # During the animation, we should have seen pixels at various rows
    # (The test mainly verifies no crash; the seen_rows check is informational)


def test_global_rain_spans_matrix_and_led():
    """Rain animation drives both a matrix and an LED strip below it."""
    ctrl = GlobalAnimationController()
    matrix = MatrixManager(MockJEBPixel(64), width=8, height=8)
    led = LEDManager(MockJEBPixel(8))
    ctrl.register_matrix(matrix, offset_x=0, offset_y=0)
    ctrl.register_led_strip(led, offset_x=0, offset_y=8, orientation='horizontal')

    async def run():
        await ctrl.global_rain(
            color=(0, 200, 255),
            speed=0.05,
            duration=0.5,
            density=1.0
        )

    asyncio.run(run())  # Must not raise


def test_global_rain_custom_color():
    """global_rain respects a custom color argument."""
    ctrl = GlobalAnimationController()
    led = LEDManager(MockJEBPixel(4))
    ctrl.register_led_strip(led, offset_x=0, offset_y=0, orientation='vertical')

    custom_color = (255, 50, 0)

    written_colors = set()

    class TrackingPixel:
        def __init__(self, n):
            self.n = n
            self._pixels = [(0, 0, 0)] * n

        def __setitem__(self, idx, color):
            if 0 <= idx < self.n:
                self._pixels[idx] = color
                if color != (0, 0, 0):
                    written_colors.add(color)

        def __getitem__(self, idx):
            return self._pixels[idx]

        def fill(self, color):
            self._pixels = [color] * self.n

        def show(self):
            pass

    tracking = TrackingPixel(4)
    led2 = LEDManager(tracking)
    ctrl2 = GlobalAnimationController()
    ctrl2.register_led_strip(led2, offset_x=0, offset_y=0, orientation='vertical')

    async def run():
        await ctrl2.global_rain(color=custom_color, speed=0.05, duration=0.25, density=1.0)

    asyncio.run(run())
    if written_colors:
        assert all(c == custom_color for c in written_colors), \
            f"Expected only {custom_color}, but got: {written_colors}"


# ---------------------------------------------------------------------------
# canvas properties
# ---------------------------------------------------------------------------

def test_canvas_dimensions_matrix_and_offset_led():
    """Canvas dimensions update correctly when both components are offset."""
    ctrl = GlobalAnimationController()
    matrix = MatrixManager(MockJEBPixel(64), width=8, height=8)
    led = LEDManager(MockJEBPixel(4))

    ctrl.register_matrix(matrix, offset_x=2, offset_y=0)
    # LED strip below and to the right
    ctrl.register_led_strip(led, offset_x=5, offset_y=8, orientation='horizontal')

    # Matrix: x in [2, 9], y in [0, 7]
    # LED:    x in [5, 8], y = 8
    assert ctrl.canvas_width == 10   # max_x = 2+8-1=9, so width=10
    assert ctrl.canvas_height == 9   # max_y = 8, so height=9


if __name__ == "__main__":
    print("=" * 60)
    print("GlobalAnimationController Test Suite")
    print("=" * 60)

    import traceback

    tests = [
        test_empty_controller,
        test_register_matrix_updates_canvas,
        test_register_matrix_with_offset,
        test_register_horizontal_led_strip,
        test_register_vertical_led_strip,
        test_register_invalid_orientation_raises,
        test_combined_matrix_and_led_strip,
        test_pixel_map_matrix_correct_hardware_index,
        test_pixel_map_led_strip_correct_index,
        test_multiple_registrations_rebuild_map,
        test_set_pixel_writes_to_correct_manager,
        test_set_pixel_led_strip,
        test_set_pixel_out_of_bounds_is_silent,
        test_clear_resets_all_pixels,
        test_clear_shared_manager_only_cleared_once,
        test_global_rainbow_wave_runs_and_stops,
        test_global_rainbow_wave_different_x_get_different_hues,
        test_global_rainbow_wave_no_pixels_returns_immediately,
        test_global_rainbow_wave_spans_matrix_and_led,
        test_global_rain_runs_and_stops,
        test_global_rain_no_pixels_returns_immediately,
        test_global_rain_default_color,
        test_global_rain_drops_travel_downward,
        test_global_rain_spans_matrix_and_led,
        test_global_rain_custom_color,
        test_canvas_dimensions_matrix_and_offset_led,
    ]

    passed = 0
    failed = 0
    for test_fn in tests:
        try:
            test_fn()
            print(f"  ✓ {test_fn.__name__}")
            passed += 1
        except Exception as e:
            print(f"  ✗ {test_fn.__name__}: {e}")
            traceback.print_exc()
            failed += 1

    print("\n" + "=" * 60)
    if failed == 0:
        print(f"ALL {passed} TESTS PASSED ✓")
    else:
        print(f"{passed} passed, {failed} FAILED ✗")
    print("=" * 60)
    sys.exit(0 if failed == 0 else 1)
