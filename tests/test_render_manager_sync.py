#!/usr/bin/env python3
"""Unit tests for RenderManager sync drift hysteresis."""

import sys
import os

# Mock CircuitPython modules BEFORE any imports
class MockModule:
    """Generic mock module."""
    def __getattr__(self, name):
        return MockModule()
    
    def __call__(self, *args, **kwargs):
        return MockModule()

# Mock all CircuitPython-specific modules
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
sys.modules['adafruit_displayio_ssd1306'] = MockModule()
sys.modules['adafruit_display_text'] = MockModule()
sys.modules['adafruit_display_text.label'] = MockModule()
sys.modules['adafruit_ht16k33'] = MockModule()
sys.modules['adafruit_ht16k33.segments'] = MockModule()

# Add src directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

# Import production RenderManager
from managers.render_manager import RenderManager


# Mock pixel object
class MockPixelObject:
    def __init__(self):
        self.show_called = 0

    def show(self):
        self.show_called += 1


def test_sync_large_drift_snaps():
    """Test that large drift (>2 frames) causes immediate snap."""
    print("Testing large drift snap behavior...")

    pixels = MockPixelObject()
    renderer = RenderManager(pixels, sync_role="SLAVE")

    # Simulate satellite being 5 frames ahead
    renderer.frame_counter = 105
    core_frame = 100  # Core is at frame 100

    renderer.apply_sync(core_frame)

    # Should snap to estimated_core (100 + 1 = 101)
    assert renderer.frame_counter == 101, f"Expected frame_counter to snap to 101, got {renderer.frame_counter}"
    assert renderer.sleep_adjustment == 0.0, "Sleep adjustment should not be set for large drift"

    print("✓ Large drift snap test passed")


def test_sync_small_drift_nudge_ahead():
    """Test that small drift (1 frame ahead) causes gradual nudge."""
    print("Testing small drift nudge behavior (ahead)...")

    pixels = MockPixelObject()
    renderer = RenderManager(pixels, sync_role="SLAVE")

    # Simulate satellite being 1 frame ahead
    renderer.frame_counter = 102
    core_frame = 100  # Core is at frame 100, estimated_core = 101

    renderer.apply_sync(core_frame)

    # Should NOT snap
    assert renderer.frame_counter == 102, f"Expected frame_counter to remain 102, got {renderer.frame_counter}"

    # Should set positive adjustment (slow down by sleeping more)
    frame_time = 1.0 / renderer.target_frame_rate
    expected_adjustment = renderer.DRIFT_ADJUSTMENT_FACTOR * frame_time
    assert abs(renderer.sleep_adjustment - expected_adjustment) < 1e-9, \
        f"Expected sleep_adjustment to be {expected_adjustment}, got {renderer.sleep_adjustment}"

    print(f"✓ Small drift ahead test passed (adjustment: {renderer.sleep_adjustment:.6f}s)")


def test_sync_small_drift_nudge_behind():
    """Test that small drift (1 frame behind) causes gradual nudge."""
    print("Testing small drift nudge behavior (behind)...")

    pixels = MockPixelObject()
    renderer = RenderManager(pixels, sync_role="SLAVE")

    # Simulate satellite being 1 frame behind
    renderer.frame_counter = 100
    core_frame = 100  # Core is at frame 100, estimated_core = 101

    renderer.apply_sync(core_frame)

    # Should NOT snap
    assert renderer.frame_counter == 100, f"Expected frame_counter to remain 100, got {renderer.frame_counter}"

    # Should set negative adjustment (speed up by sleeping less)
    frame_time = 1.0 / renderer.target_frame_rate
    expected_adjustment = -renderer.DRIFT_ADJUSTMENT_FACTOR * frame_time
    assert abs(renderer.sleep_adjustment - expected_adjustment) < 1e-9, \
        f"Expected sleep_adjustment to be {expected_adjustment}, got {renderer.sleep_adjustment}"

    print(f"✓ Small drift behind test passed (adjustment: {renderer.sleep_adjustment:.6f}s)")


def test_sync_no_drift():
    """Test that no drift results in no adjustment."""
    print("Testing no drift behavior...")

    pixels = MockPixelObject()
    renderer = RenderManager(pixels, sync_role="SLAVE")

    # Simulate satellite being in sync
    renderer.frame_counter = 101
    core_frame = 100  # Core is at frame 100, estimated_core = 101

    renderer.apply_sync(core_frame)

    # Should NOT snap or adjust
    assert renderer.frame_counter == 101, f"Expected frame_counter to remain 101, got {renderer.frame_counter}"
    assert renderer.sleep_adjustment == 0.0, "Sleep adjustment should not be set when in sync"

    print("✓ No drift test passed")


def test_sync_two_frame_drift_no_action():
    """Test that 2 frame drift does nothing (dead zone boundary)."""
    print("Testing 2-frame drift dead zone...")

    pixels = MockPixelObject()
    renderer = RenderManager(pixels, sync_role="SLAVE")

    # Simulate satellite being 2 frames ahead
    renderer.frame_counter = 103
    core_frame = 100  # Core is at frame 100, estimated_core = 101, drift = 2

    renderer.apply_sync(core_frame)

    # Should NOT snap or adjust (drift == 2, not > 2)
    assert renderer.frame_counter == 103, f"Expected frame_counter to remain 103, got {renderer.frame_counter}"
    assert renderer.sleep_adjustment == 0.0, "Sleep adjustment should not be set for 2-frame drift"

    print("✓ Two-frame drift dead zone test passed")


def test_sync_master_ignores():
    """Test that MASTER role ignores sync commands."""
    print("Testing MASTER role ignores sync...")

    pixels = MockPixelObject()
    renderer = RenderManager(pixels, sync_role="MASTER")

    renderer.frame_counter = 105
    core_frame = 100

    renderer.apply_sync(core_frame)

    # Should not change anything
    assert renderer.frame_counter == 105, "MASTER should ignore sync"
    assert renderer.sleep_adjustment == 0.0, "MASTER should not adjust sleep"

    print("✓ MASTER ignores sync test passed")


def test_sync_none_ignores():
    """Test that NONE role ignores sync commands."""
    print("Testing NONE role ignores sync...")

    pixels = MockPixelObject()
    renderer = RenderManager(pixels, sync_role="NONE")

    renderer.frame_counter = 105
    core_frame = 100

    renderer.apply_sync(core_frame)

    # Should not change anything
    assert renderer.frame_counter == 105, "NONE should ignore sync"
    assert renderer.sleep_adjustment == 0.0, "NONE should not adjust sleep"

    print("✓ NONE ignores sync test passed")


def test_adjustment_values():
    """Test that adjustment values are correct (10% of frame time)."""
    print("Testing adjustment value calculations...")

    pixels = MockPixelObject()
    renderer = RenderManager(pixels, sync_role="SLAVE")

    frame_time = 1.0 / renderer.target_frame_rate
    expected_magnitude = renderer.DRIFT_ADJUSTMENT_FACTOR * frame_time

    # Test ahead (positive adjustment to slow down by sleeping more)
    renderer.frame_counter = 102
    renderer.apply_sync(100)
    assert renderer.sleep_adjustment == expected_magnitude, \
        f"Expected adjustment magnitude {expected_magnitude}, got {renderer.sleep_adjustment}"

    # Reset and test behind (negative adjustment to speed up by sleeping less)
    renderer.sleep_adjustment = 0.0
    renderer.frame_counter = 100
    renderer.apply_sync(100)
    assert renderer.sleep_adjustment == -expected_magnitude, \
        f"Expected adjustment magnitude {-expected_magnitude}, got {renderer.sleep_adjustment}"

    print(f"✓ Adjustment value test passed ({int(renderer.DRIFT_ADJUSTMENT_FACTOR * 100)}% of {frame_time:.6f}s = ±{expected_magnitude:.6f}s)")


def run_all_tests():
    """Run all tests."""
    print("=" * 60)
    print("Running RenderManager Sync Drift Hysteresis Tests")
    print("=" * 60)
    print()

    try:
        test_sync_large_drift_snaps()
        test_sync_small_drift_nudge_ahead()
        test_sync_small_drift_nudge_behind()
        test_sync_no_drift()
        test_sync_two_frame_drift_no_action()
        test_sync_master_ignores()
        test_sync_none_ignores()
        test_adjustment_values()

        print()
        print("=" * 60)
        print("✓ ALL TESTS PASSED")
        print("=" * 60)
        return True

    except AssertionError as e:
        print()
        print("=" * 60)
        print(f"✗ TEST FAILED: {e}")
        print("=" * 60)
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
