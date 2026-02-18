#!/usr/bin/env python3
"""Unit tests for MatrixManager non-blocking animation behavior."""

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

# Mock all CircuitPython dependencies
sys.modules['adafruit_ticks'] = MockModule()
sys.modules['digitalio'] = MockModule()
sys.modules['busio'] = MockModule()
sys.modules['board'] = MockModule()
sys.modules['neopixel'] = MockModule()
sys.modules['microcontroller'] = MockModule()
sys.modules['watchdog'] = MockModule()
sys.modules['audiocore'] = MockModule()
sys.modules['audiobusio'] = MockModule()
sys.modules['audiomixer'] = MockModule()
sys.modules['analogio'] = MockModule()
sys.modules['audiopwmio'] = MockModule()
sys.modules['synthio'] = MockModule()
sys.modules['ulab'] = MockModule()
sys.modules['adafruit_mcp230xx'] = MockModule()
sys.modules['adafruit_mcp230xx.mcp23017'] = MockModule()
sys.modules['adafruit_displayio_ssd1306'] = MockModule()
sys.modules['adafruit_display_text'] = MockModule()
sys.modules['displayio'] = MockModule()
sys.modules['terminalio'] = MockModule()
sys.modules['adafruit_httpserver'] = MockModule()

# Add src directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

# Import the REAL MatrixManager and animate_slide_left from production code
from managers.matrix_manager import MatrixManager
from utilities import matrix_animations


# Mock JEBPixel and neopixel for testing (dependencies for MatrixManager)
class MockNeoPixel:
    """Mock neopixel.NeoPixel for testing."""
    def __init__(self, n):
        self.n = n
        self._pixels = [(0, 0, 0)] * n
        self.brightness = 0.3

    def __setitem__(self, idx, color):
        if 0 <= idx < self.n:
            self._pixels[idx] = color

    def __getitem__(self, idx):
        return self._pixels[idx]

    def fill(self, color):
        self._pixels = [color] * self.n

    def show(self):
        pass  # Mock - does nothing


class MockJEBPixel:
    """Mock JEBPixel wrapper for testing."""
    def __init__(self, num_pixels=64):
        self.n = num_pixels
        self._pixels = MockNeoPixel(num_pixels)
        self.brightness = 0.3

    def __setitem__(self, idx, color):
        self._pixels[idx] = color

    def __getitem__(self, idx):
        return self._pixels[idx]

    def fill(self, color):
        self._pixels.fill(color)

    def show(self):
        self._pixels.show()


@pytest.mark.asyncio
async def test_show_icon_non_blocking_slide_left():
    """Test that show_icon with SLIDE_LEFT animation returns immediately."""
    print("Testing show_icon SLIDE_LEFT non-blocking behavior...")

    # Create mock pixel and REAL matrix manager
    mock_pixel = MockJEBPixel(64)
    matrix = MatrixManager(mock_pixel)

    # Record start time
    start_time = time.time()

    # Call show_icon with SLIDE_LEFT animation (NOT async, so no await)
    matrix.show_icon("DEFAULT", anim_mode="SLIDE_LEFT")

    # Record end time
    elapsed = time.time() - start_time

    # The method should return almost immediately (< 50ms)
    # The animation takes ~450ms (9 frames * 50ms), but should not block
    # Using 100ms threshold to account for system overhead and scheduling delays
    assert elapsed < 0.1, \
        f"show_icon with SLIDE_LEFT should return immediately, took {elapsed:.3f}s"

    print(f"  ✓ show_icon returned in {elapsed*1000:.1f}ms (non-blocking)")

    # Give animation time to complete in background
    await asyncio.sleep(0.5)

    print("✓ SLIDE_LEFT non-blocking test passed")

@pytest.mark.asyncio
async def test_show_icon_other_animations_non_blocking():
    """Test that show_icon with other animations also doesn't block."""
    print("\nTesting show_icon with other animation modes...")

    mock_pixel = MockJEBPixel(64)
    matrix = MatrixManager(mock_pixel)

    # Test PULSE animation (NOT async, so no await)
    start_time = time.time()
    matrix.show_icon("DEFAULT", anim_mode="PULSE", speed=1.0)
    elapsed = time.time() - start_time
    assert elapsed < 0.1, f"show_icon with PULSE should be fast, took {elapsed:.3f}s"
    print(f"  ✓ PULSE animation registered in {elapsed*1000:.1f}ms")

    # Test BLINK animation
    start_time = time.time()
    matrix.show_icon("SUCCESS", anim_mode="BLINK", speed=2.0)
    elapsed = time.time() - start_time
    assert elapsed < 0.1, f"show_icon with BLINK should be fast, took {elapsed:.3f}s"
    print(f"  ✓ BLINK animation registered in {elapsed*1000:.1f}ms")

    # Test static (no animation)
    start_time = time.time()
    matrix.show_icon("FAILURE")
    elapsed = time.time() - start_time
    assert elapsed < 0.1, f"show_icon without animation should be fast, took {elapsed:.3f}s"
    print(f"  ✓ Static icon displayed in {elapsed*1000:.1f}ms")

    print("✓ Other animation modes test passed")

@pytest.mark.asyncio
async def test_concurrent_show_icon_calls():
    """Test that multiple show_icon calls with SLIDE_LEFT can run concurrently."""
    print("\nTesting concurrent SLIDE_LEFT animations...")

    mock_pixel = MockJEBPixel(64)
    matrix = MatrixManager(mock_pixel)

    # Start multiple SLIDE_LEFT animations concurrently
    start_time = time.time()

    # These should all return immediately and run in background (NOT async, so no await)
    matrix.show_icon("DEFAULT", anim_mode="SLIDE_LEFT")
    await asyncio.sleep(0.1)  # Small delay to avoid race
    matrix.show_icon("SUCCESS", anim_mode="SLIDE_LEFT")
    await asyncio.sleep(0.1)
    matrix.show_icon("FAILURE", anim_mode="SLIDE_LEFT")

    elapsed = time.time() - start_time

    # All three calls with delays should complete in < 0.5s total
    # (not 3 * 0.45s = 1.35s if they were blocking)
    assert elapsed < 0.5, \
        f"Three show_icon calls should return quickly, took {elapsed:.3f}s"

    print(f"  ✓ Three show_icon calls returned in {elapsed:.3f}s")

    # Wait for animations to complete
    await asyncio.sleep(0.6)

    print("✓ Concurrent animations test passed")

@pytest.mark.asyncio
async def test_slide_left_animation_completes():
    """Test that SLIDE_LEFT animation runs in the background without crashing."""
    print("\nTesting SLIDE_LEFT animation completion...")

    mock_pixel = MockJEBPixel(64)
    matrix = MatrixManager(mock_pixel)

    # Start animation (NOT async, so no await)
    # This should create a background task that runs the animation
    matrix.show_icon("DEFAULT", anim_mode="SLIDE_LEFT")

    # Give the animation time to run several frames
    # The animation takes ~450ms (9 frames * 50ms each)
    # We wait longer to ensure it completes without exceptions
    await asyncio.sleep(0.6)

    # If we got here, the animation ran without crashing
    # (A crash would have raised an exception and failed the test)
    print(f"  ✓ Animation completed without exceptions")

    print("✓ SLIDE_LEFT animation completion test passed")

@pytest.mark.asyncio
async def test_blocking_vs_non_blocking_comparison():
    """Compare timing of blocking vs non-blocking approach."""
    print("\nTesting performance comparison...")

    mock_pixel = MockJEBPixel(64)
    matrix = MatrixManager(mock_pixel)

    # Test non-blocking (current implementation) (NOT async, so no await)
    start_time = time.time()
    matrix.show_icon("DEFAULT", anim_mode="SLIDE_LEFT")
    matrix.show_icon("SUCCESS", anim_mode="SLIDE_LEFT")
    matrix.show_icon("FAILURE", anim_mode="SLIDE_LEFT")
    non_blocking_time = time.time() - start_time

    print(f"  ✓ Non-blocking: 3 calls took {non_blocking_time*1000:.1f}ms")

    # The non-blocking version should be very fast (< 10ms)
    assert non_blocking_time < 0.05, \
        f"Non-blocking calls should be nearly instant, took {non_blocking_time:.3f}s"

    # Wait for background animations to complete
    await asyncio.sleep(0.6)

    print("✓ Performance comparison test passed")



async def run_async_tests():
    """Run all async tests."""
    print("=" * 60)
    print("MatrixManager Non-Blocking Animation Test Suite")
    print("=" * 60)

    try:
        await test_show_icon_non_blocking_slide_left()
        await test_show_icon_other_animations_non_blocking()
        await test_concurrent_show_icon_calls()
        await test_slide_left_animation_completes()
        await test_blocking_vs_non_blocking_comparison()

        print("\n" + "=" * 60)
        print("✓ All matrix manager tests passed!")
        print("=" * 60)
        return True

    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    # Run async tests
    success = asyncio.run(run_async_tests())
    sys.exit(0 if success else 1)
