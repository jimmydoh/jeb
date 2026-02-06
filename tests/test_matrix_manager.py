#!/usr/bin/env python3
"""Unit tests for MatrixManager non-blocking animation behavior."""

import sys
import os
import pytest
import asyncio
import time


# Mock Palette and Icons to avoid CircuitPython dependencies
class MockPalette:
    OFF = (0, 0, 0)
    RED = (255, 0, 0)

class MockIcons:
    DEFAULT = [2] * 64
    SUCCESS = [4] * 64
    FAILURE = [1] * 64
    ICON_LIBRARY = {
        "DEFAULT": DEFAULT,
        "SUCCESS": SUCCESS,
        "FAILURE": FAILURE,
    }


# Mock the animation slot from base_pixel_manager
class AnimationSlot:
    __slots__ = ('active', 'type', 'color', 'speed', 'start', 'duration', 'priority')

    def __init__(self):
        self.active = False
        self.type = None
        self.color = None
        self.speed = 1.0
        self.start = 0.0
        self.duration = None
        self.priority = 0

    def set(self, anim_type, color, speed, start, duration, priority):
        self.active = True
        self.type = anim_type
        self.color = color
        self.speed = speed
        self.start = start
        self.duration = duration
        self.priority = priority

    def clear(self):
        self.active = False


# Mock JEBPixel and neopixel for testing
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


# Simplified MatrixManager for testing (avoiding CircuitPython dependencies)
class TestableMatrixManager:
    """Simplified MatrixManager for testing non-blocking behavior."""

    def __init__(self, jeb_pixel):
        self.pixels = jeb_pixel
        self.num_pixels = self.pixels.n
        self.palette = {1: (255, 0, 0), 2: (0, 0, 255), 4: (0, 255, 0)}
        self.icons = MockIcons()
        self.active_animations = [AnimationSlot() for _ in range(self.num_pixels)]
        self._active_count = 0

    def _get_idx(self, x, y):
        """Maps 2D (0-7) to Serpentine 1D index."""
        if y % 2 == 0:
            return (y * 8) + x
        return (y * 8) + (7 - x)

    def clear(self):
        """Stops all animations and clears LEDs."""
        for slot in self.active_animations:
            slot.clear()
        self._active_count = 0
        self.pixels.fill((0, 0, 0))
        self.pixels.show()

    def draw_pixel(self, x, y, color, show=False, anim_mode=None, speed=1.0, duration=None):
        """Sets a specific pixel on the matrix."""
        if 0 <= x < 8 and 0 <= y < 8:
            idx = self._get_idx(x, y)
            if anim_mode:
                slot = self.active_animations[idx]
                if not slot.active:
                    self._active_count += 1
                slot.set(anim_mode, color, speed, time.time(), duration, 0)
            else:
                self.pixels[idx] = color
        if show:
            self.pixels.show()

    def fill(self, color, show=True, anim_mode=None, speed=1.0, duration=None):
        """Fills the entire matrix with a single color."""
        self.clear()
        self.pixels.fill(color)
        if show:
            self.pixels.show()

    @pytest.mark.asyncio
    async def _animate_slide_left(self, icon_data, color, brightness):
        """
        Internal method to perform SLIDE_LEFT animation.
        Runs as a background task to avoid blocking the caller.
        """
        for offset in range(8, -1, -1):  # Slide from right to left
            self.fill(MockPalette.OFF, show=False)
            for y in range(8):
                for x in range(8):
                    target_x = x - offset
                    if 0 <= target_x < 8:
                        pixel_value = icon_data[y * 8 + x]
                        if pixel_value != 0:
                            base = color if color else self.palette.get(pixel_value, (255, 255, 255))
                            px_color = tuple(int(c * brightness) for c in base)
                            self.draw_pixel(target_x, y, px_color)
            self.pixels.show()
            await asyncio.sleep(0.05)

    @pytest.mark.asyncio
    async def show_icon(
            self,
            icon_name,
            clear=True,
            anim_mode=None,
            speed=1.0,
            color=None,
            brightness=1.0
        ):
        """
        Displays a predefined icon on the matrix with optional animation.
        anim_mode: None, "PULSE", "BLINK" are non-blocking via the animate_loop.
        anim_mode: "SLIDE_LEFT" is non-blocking (spawned as background task).
        """
        if clear:
            self.clear()

        icon_data = self.icons.ICON_LIBRARY.get(icon_name, self.icons.DEFAULT)

        # Handle SLIDE_LEFT Animation - Spawn as background task
        if anim_mode == "SLIDE_LEFT":
            asyncio.create_task(self._animate_slide_left(icon_data, color, brightness))
            return

        for y in range(8):
            for x in range(8):
                idx = self._get_idx(x, y)
                pixel_value = icon_data[y * 8 + x]

                if pixel_value != 0:
                    base = color if color else self.palette.get(pixel_value, (255, 255, 255))
                    px_color = tuple(int(c * brightness) for c in base)

                    if anim_mode:
                        slot = self.active_animations[idx]
                        if not slot.active:
                            self._active_count += 1
                        slot.set(anim_mode, px_color, speed, time.time(), None, 0)
                    else:
                        self.draw_pixel(x, y, px_color)

        self.pixels.show()

@pytest.mark.asyncio
async def test_show_icon_non_blocking_slide_left():
    """Test that show_icon with SLIDE_LEFT animation returns immediately."""
    print("Testing show_icon SLIDE_LEFT non-blocking behavior...")

    # Create mock pixel and matrix manager
    mock_pixel = MockJEBPixel(64)
    matrix = TestableMatrixManager(mock_pixel)

    # Record start time
    start_time = time.time()

    # Call show_icon with SLIDE_LEFT animation
    await matrix.show_icon("DEFAULT", anim_mode="SLIDE_LEFT")

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
    matrix = TestableMatrixManager(mock_pixel)

    # Test PULSE animation
    start_time = time.time()
    await matrix.show_icon("DEFAULT", anim_mode="PULSE", speed=1.0)
    elapsed = time.time() - start_time
    assert elapsed < 0.1, f"show_icon with PULSE should be fast, took {elapsed:.3f}s"
    print(f"  ✓ PULSE animation registered in {elapsed*1000:.1f}ms")

    # Test BLINK animation
    start_time = time.time()
    await matrix.show_icon("SUCCESS", anim_mode="BLINK", speed=2.0)
    elapsed = time.time() - start_time
    assert elapsed < 0.1, f"show_icon with BLINK should be fast, took {elapsed:.3f}s"
    print(f"  ✓ BLINK animation registered in {elapsed*1000:.1f}ms")

    # Test static (no animation)
    start_time = time.time()
    await matrix.show_icon("FAILURE")
    elapsed = time.time() - start_time
    assert elapsed < 0.1, f"show_icon without animation should be fast, took {elapsed:.3f}s"
    print(f"  ✓ Static icon displayed in {elapsed*1000:.1f}ms")

    print("✓ Other animation modes test passed")

@pytest.mark.asyncio
async def test_concurrent_show_icon_calls():
    """Test that multiple show_icon calls with SLIDE_LEFT can run concurrently."""
    print("\nTesting concurrent SLIDE_LEFT animations...")

    mock_pixel = MockJEBPixel(64)
    matrix = TestableMatrixManager(mock_pixel)

    # Start multiple SLIDE_LEFT animations concurrently
    start_time = time.time()

    # These should all return immediately and run in background
    await matrix.show_icon("DEFAULT", anim_mode="SLIDE_LEFT")
    await asyncio.sleep(0.1)  # Small delay to avoid race
    await matrix.show_icon("SUCCESS", anim_mode="SLIDE_LEFT")
    await asyncio.sleep(0.1)
    await matrix.show_icon("FAILURE", anim_mode="SLIDE_LEFT")

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
    """Test that SLIDE_LEFT animation actually runs in the background."""
    print("\nTesting SLIDE_LEFT animation completion...")

    mock_pixel = MockJEBPixel(64)
    matrix = TestableMatrixManager(mock_pixel)

    # Track if pixels are being updated
    initial_state = [mock_pixel[i] for i in range(64)]

    # Start animation
    await matrix.show_icon("DEFAULT", anim_mode="SLIDE_LEFT")

    # Animation should still be running, so wait a bit
    await asyncio.sleep(0.1)

    # Check that some pixels have changed (animation is running)
    mid_state = [mock_pixel[i] for i in range(64)]
    pixels_changed = sum(1 for i in range(64) if initial_state[i] != mid_state[i])

    # At least some pixels should have changed during animation
    assert pixels_changed > 0, "Animation should have started updating pixels"
    print(f"  ✓ Animation started, {pixels_changed} pixels changed")

    # Wait for animation to complete
    await asyncio.sleep(0.5)

    print("✓ SLIDE_LEFT animation completion test passed")

@pytest.mark.asyncio
async def test_blocking_vs_non_blocking_comparison():
    """Compare timing of blocking vs non-blocking approach."""
    print("\nTesting performance comparison...")

    mock_pixel = MockJEBPixel(64)
    matrix = TestableMatrixManager(mock_pixel)

    # Test non-blocking (current implementation)
    start_time = time.time()
    await matrix.show_icon("DEFAULT", anim_mode="SLIDE_LEFT")
    await matrix.show_icon("SUCCESS", anim_mode="SLIDE_LEFT")
    await matrix.show_icon("FAILURE", anim_mode="SLIDE_LEFT")
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
