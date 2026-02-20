#!/usr/bin/env python3
"""Integration test to verify the animation fix works in realistic scenarios."""

import sys
import os
import pytest
import asyncio
import time

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

# Import production MatrixManager
from managers.matrix_manager import MatrixManager


class MockCriticalMonitor:
    """Simulates a critical monitoring task like E-Stop."""
    def __init__(self):
        self.checks_performed = 0
        self.max_delay = 0.0
        self.last_check = time.time()

    async def monitor_loop(self):
        """Simulates E-Stop monitoring that should run every 10ms."""
        while True:
            now = time.time()
            delay = now - self.last_check
            self.max_delay = max(self.max_delay, delay)
            self.last_check = now
            self.checks_performed += 1
            await asyncio.sleep(0.01)  # Check every 10ms


class MockJEBPixel:
    def __init__(self, num_pixels=64):
        self.n = num_pixels
        self._pixels = [(0, 0, 0)] * num_pixels
        self.brightness = 0.3
    def __setitem__(self, idx, color):
        if 0 <= idx < self.n:
            self._pixels[idx] = color
    def __getitem__(self, idx):
        return self._pixels[idx]
    def fill(self, color):
        self._pixels = [color] * self.n
    def show(self):
        pass


@pytest.mark.asyncio
async def test_critical_monitoring_not_blocked():
    """
    Integration test: Verify that critical monitoring (like E-Stop)
    is not delayed by SLIDE_LEFT animations.
    """
    print("Testing integration: Animation + Critical Monitoring")
    print("=" * 60)

    # Setup
    mock_pixel = MockJEBPixel(64)
    matrix = MatrixManager(mock_pixel)
    monitor = MockCriticalMonitor()

    # Start critical monitor
    monitor_task = asyncio.create_task(monitor.monitor_loop())

    # Give monitor time to establish baseline
    await asyncio.sleep(0.1)

    print(f"\nBaseline: {monitor.checks_performed} checks in 100ms")
    baseline_checks = monitor.checks_performed

    # Reset counters
    monitor.checks_performed = 0
    monitor.max_delay = 0.0

    # Trigger multiple SLIDE_LEFT animations (simulating menu navigation)
    print("\nTriggering 5 SLIDE_LEFT animations...")
    for i in range(5):
        matrix.show_icon("DEFAULT", anim_mode="SLIDE_LEFT")
        await asyncio.sleep(0.05)  # Small delay between animations

    # Let animations complete while monitor runs
    await asyncio.sleep(0.6)

    animation_period_checks = monitor.checks_performed
    max_delay_ms = monitor.max_delay * 1000

    print(f"During animations: {animation_period_checks} checks in 600ms")
    print(f"Max delay between checks: {max_delay_ms:.1f}ms")

    # Cleanup
    monitor_task.cancel()
    try:
        await monitor_task
    except asyncio.CancelledError:
        pass

    # Verify results
    print("\n" + "=" * 60)
    print("Results:")
    print("=" * 60)

    # Expected: ~60 checks in 600ms (one every 10ms)
    # Allow variance due to task scheduling overhead and asyncio.sleep() imprecision
    expected_checks = 50  # tolerance for system variations
    assert animation_period_checks >= expected_checks, \
        f"Monitor should run ~60 times in 600ms, got {animation_period_checks}"
    print(f"✓ Monitor ran {animation_period_checks} times (>= {expected_checks} expected)")

    # Max delay should be reasonable (< 50ms)
    # With blocking animation, this would be ~450ms (full animation duration)
    assert max_delay_ms < 50, \
        f"Max delay should be < 50ms, got {max_delay_ms:.1f}ms (blocking would be ~450ms)"
    print(f"✓ Max delay: {max_delay_ms:.1f}ms (< 50ms threshold)")

    print("\n" + "=" * 60)
    print("✓ INTEGRATION TEST PASSED")
    print("=" * 60)
    print("\nConclusion: SLIDE_LEFT animations do NOT block critical monitoring!")
    print("E-Stop and other safety features will remain responsive.")

@pytest.mark.asyncio
async def test_mode_transition_responsiveness():
    """
    Test that mode transitions remain responsive when using animations.
    """
    print("\n\nTesting mode transition responsiveness")
    print("=" * 60)

    mock_pixel = MockJEBPixel(64)
    matrix = MatrixManager(mock_pixel)

    # Simulate rapid mode transitions (like menu navigation)
    start_time = time.time()

    for i in range(10):
        # Simulate mode change with animation
        matrix.show_icon("DEFAULT", anim_mode="SLIDE_LEFT")
        # Simulate other mode transition work
        await asyncio.sleep(0.01)

    elapsed = time.time() - start_time
    elapsed_ms = elapsed * 1000

    print(f"10 mode transitions completed in: {elapsed_ms:.1f}ms")

    # Should complete quickly (< 200ms)
    # With blocking animations, this would take > 4500ms (10 * 450ms)
    assert elapsed < 0.2, \
        f"Transitions should be fast, took {elapsed:.3f}s (blocking would be ~4.5s)"

    print(f"✓ Mode transitions are responsive (< 200ms)")
    print("✓ Each transition returned immediately, animations run in background")

    # Wait for background animations to complete
    await asyncio.sleep(0.6)

    print("\n✓ MODE TRANSITION TEST PASSED")


async def run_integration_tests():
    """Run all integration tests."""
    print("\n" + "=" * 60)
    print("INTEGRATION TEST SUITE: Animation Fix Verification")
    print("=" * 60)

    try:
        await test_critical_monitoring_not_blocked()
        await test_mode_transition_responsiveness()

        print("\n" + "=" * 60)
        print("✓✓✓ ALL INTEGRATION TESTS PASSED ✓✓✓")
        print("=" * 60)
        print("\nThe animation fix successfully prevents blocking of:")
        print("  • E-Stop monitoring")
        print("  • Mode transitions")
        print("  • Other critical event handlers")
        return True

    except AssertionError as e:
        print(f"\n✗ Integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    import sys
    success = asyncio.run(run_integration_tests())
    sys.exit(0 if success else 1)
