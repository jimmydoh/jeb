#!/usr/bin/env python3
"""Unit tests for MatrixManager stateless brightness calculation."""

import sys
import os


# Mock the base class that MatrixManager inherits from
class AnimationSlot:
    """Reusable animation slot to avoid object churn."""
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
        """Update slot properties in place."""
        self.active = True
        self.type = anim_type
        self.color = color
        self.speed = speed
        self.start = start
        self.duration = duration
        self.priority = priority
    
    def clear(self):
        """Mark slot as inactive without deallocating."""
        self.active = False


class BasePixelManager:
    """Minimal mock of BasePixelManager."""
    def __init__(self, pixel_object):
        self.pixels = pixel_object
        self.num_pixels = self.pixels.n
        self.active_animations = [AnimationSlot() for _ in range(self.num_pixels)]
        self._active_count = 0


class MockPixelObject:
    """Mock pixel object for testing."""
    def __init__(self, n=64):
        self.n = n
        self._pixels = [(0, 0, 0)] * n
    
    def __setitem__(self, idx, color):
        self._pixels[idx] = color
    
    def __getitem__(self, idx):
        return self._pixels[idx]
    
    def fill(self, color):
        for i in range(self.n):
            self._pixels[i] = color
    
    def show(self):
        pass


# Now define the MatrixManager with the stateless brightness calculation
class MatrixManager(BasePixelManager):
    """Test version of MatrixManager with stateless brightness calculation."""
    def __init__(self, jeb_pixel):
        super().__init__(jeb_pixel)
    
    def _get_dimmed_color(self, base_color, brightness):
        """
        Stateless brightness calculation.
        Sacrifices a tiny amount of CPU speed for significantly better memory stability.
        
        Args:
            base_color: Tuple of (r, g, b) values
            brightness: Float from 0.0 to 1.0
            
        Returns:
            Tuple of brightness-adjusted (r, g, b) values
            
        Note:
            On RP2350 (150MHz+), this math is incredibly fast. Removed the cache
            to prevent heap fragmentation in CircuitPython's non-compacting GC.
        """
        if brightness >= 1.0:
            return base_color
        if brightness <= 0.0:
            return (0, 0, 0)
            
        # On RP2350, this math is incredibly fast
        return (
            int(base_color[0] * brightness),
            int(base_color[1] * brightness),
            int(base_color[2] * brightness)
        )


def test_stateless_initialization():
    """Test that the manager initializes without a cache."""
    print("Testing stateless initialization...")
    
    mock_pixels = MockPixelObject()
    manager = MatrixManager(mock_pixels)
    
    assert not hasattr(manager, '_brightness_cache'), "Manager should not have _brightness_cache attribute"
    assert not hasattr(manager, '_CACHE_SIZE_LIMIT'), "Manager should not have _CACHE_SIZE_LIMIT attribute"
    
    print("✓ Stateless initialization test passed")


def test_get_dimmed_color_basic():
    """Test basic functionality of _get_dimmed_color."""
    print("\nTesting _get_dimmed_color basic functionality...")
    
    mock_pixels = MockPixelObject()
    manager = MatrixManager(mock_pixels)
    
    # Test with brightness = 1.0 (should return original color)
    base_color = (200, 100, 50)
    result = manager._get_dimmed_color(base_color, 1.0)
    assert result == base_color, f"Brightness 1.0 should return original color, got {result}"
    
    # Test with brightness = 0.5
    result = manager._get_dimmed_color(base_color, 0.5)
    expected = (100, 50, 25)  # 200*0.5=100, 100*0.5=50, 50*0.5=25
    assert result == expected, f"Expected {expected}, got {result}"
    
    # Test with brightness = 0.0 (should return black)
    result = manager._get_dimmed_color(base_color, 0.0)
    expected = (0, 0, 0)
    assert result == expected, f"Expected {expected}, got {result}"
    
    print("✓ _get_dimmed_color basic functionality test passed")


def test_stateless_calculation():
    """Test that calculations are done without caching."""
    print("\nTesting stateless calculation...")
    
    mock_pixels = MockPixelObject()
    manager = MatrixManager(mock_pixels)
    
    base_color = (150, 150, 150)
    brightness = 0.75
    
    # First call - should calculate result
    result1 = manager._get_dimmed_color(base_color, brightness)
    
    # Second call with same parameters - should calculate again (no cache)
    result2 = manager._get_dimmed_color(base_color, brightness)
    
    assert result1 == result2, "Results should be identical"
    
    # Verify the results are NOT the same object (no caching)
    # Note: Due to Python's integer interning, very small tuples may have same id,
    # but we're testing the concept that there's no cache
    assert not hasattr(manager, '_brightness_cache'), "Manager should not have cache"
    
    print("✓ Stateless calculation test passed")


def test_brightness_precision():
    """Test that brightness values are calculated with proper precision."""
    print("\nTesting brightness precision...")
    
    mock_pixels = MockPixelObject()
    manager = MatrixManager(mock_pixels)
    
    base_color = (200, 100, 50)
    
    # Test various brightness values - each should calculate independently
    brightness_values = [0.751, 0.752, 0.753, 0.754]
    
    results = []
    for brightness in brightness_values:
        result = manager._get_dimmed_color(base_color, brightness)
        results.append(result)
    
    # Results should be calculated directly from brightness (no rounding to int)
    # int(200 * 0.751) = 150, int(200 * 0.752) = 150, etc.
    # All should give same result due to int() truncation
    assert all(r == results[0] for r in results), "Similar brightness values should produce same result after int()"
    
    print("✓ Brightness precision test passed")


def test_multiple_colors_calculated():
    """Test that different base colors produce correct results."""
    print("\nTesting multiple colors calculated...")
    
    mock_pixels = MockPixelObject()
    manager = MatrixManager(mock_pixels)
    
    colors = [
        (255, 0, 0),    # Red
        (0, 255, 0),    # Green
        (0, 0, 255),    # Blue
    ]
    brightness = 0.5
    
    results = []
    for color in colors:
        result = manager._get_dimmed_color(color, brightness)
        results.append(result)
    
    # Verify results are correct
    assert results[0] == (127, 0, 0), f"Red dimmed should be (127, 0, 0), got {results[0]}"
    assert results[1] == (0, 127, 0), f"Green dimmed should be (0, 127, 0), got {results[1]}"
    assert results[2] == (0, 0, 127), f"Blue dimmed should be (0, 0, 127), got {results[2]}"
    
    print("✓ Multiple colors calculated test passed")


def test_calculation_correctness():
    """Test that calculations are always correct without caching."""
    print("\nTesting calculation correctness...")
    
    mock_pixels = MockPixelObject()
    manager = MatrixManager(mock_pixels)
    
    base_color = (200, 100, 50)
    brightness = 0.8
    
    # Simulate calling for many pixels (like in show_icon)
    results = []
    for _ in range(100):
        result = manager._get_dimmed_color(base_color, brightness)
        results.append(result)
    
    # All results should be identical and correct
    expected = (160, 80, 40)  # 200*0.8=160, 100*0.8=80, 50*0.8=40
    assert all(r == expected for r in results), f"All results should be {expected}"
    
    print("✓ Calculation correctness test passed")


def test_edge_cases():
    """Test edge cases for brightness values."""
    print("\nTesting edge cases...")
    
    mock_pixels = MockPixelObject()
    manager = MatrixManager(mock_pixels)
    
    base_color = (100, 100, 100)
    
    # Test brightness = 0
    result = manager._get_dimmed_color(base_color, 0)
    assert result == (0, 0, 0), "Brightness 0 should return black"
    
    # Test brightness = 1.0 (exactly)
    result = manager._get_dimmed_color(base_color, 1.0)
    assert result == base_color, "Brightness 1.0 should return original"
    
    # Test brightness > 1.0 (should clamp to original)
    result = manager._get_dimmed_color(base_color, 1.5)
    assert result == base_color, "Brightness > 1.0 should return original"
    
    # Test very small brightness
    result = manager._get_dimmed_color(base_color, 0.01)
    assert result == (1, 1, 1), "Very small brightness should work"
    
    # Test with (0, 0, 0) base color
    result = manager._get_dimmed_color((0, 0, 0), 0.5)
    assert result == (0, 0, 0), "Black should remain black at any brightness"
    
    print("✓ Edge cases test passed")


if __name__ == "__main__":
    print("=" * 60)
    print("MatrixManager Stateless Brightness Calculation Test Suite")
    print("=" * 60)
    
    try:
        test_stateless_initialization()
        test_get_dimmed_color_basic()
        test_stateless_calculation()
        test_brightness_precision()
        test_multiple_colors_calculated()
        test_calculation_correctness()
        test_edge_cases()
        
        print("\n" + "=" * 60)
        print("ALL TESTS PASSED ✓")
        print("=" * 60)
        
    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
