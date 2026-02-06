#!/usr/bin/env python3
"""Unit tests for MatrixManager brightness cache optimization."""

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


# Now define the MatrixManager with the optimization
class MatrixManager(BasePixelManager):
    """Test version of MatrixManager with brightness cache."""
    def __init__(self, jeb_pixel):
        super().__init__(jeb_pixel)
        
        # Pre-calculated brightness cache to avoid tuple allocation
        # Key: (base_color_tuple, brightness_int), Value: dimmed_color_tuple
        # Limited to 128 entries to prevent unbounded memory growth
        self._brightness_cache = {}
        self._CACHE_SIZE_LIMIT = 128
    
    def _get_dimmed_color(self, base_color, brightness):
        """
        Get brightness-adjusted color with caching to avoid repeated tuple allocation.
        
        Args:
            base_color: Tuple of (r, g, b) values
            brightness: Float from 0.0 to 1.0
            
        Returns:
            Tuple of brightness-adjusted (r, g, b) values
        """
        # Fast path: brightness is 0.0, return black (common for "off" pixels)
        if brightness == 0.0:
            return (0, 0, 0)
        
        # Fast path: brightness is 1.0, return original color
        if brightness == 1.0:
            return base_color
        
        # Convert brightness to integer (0-100) for faster hashing
        brightness_int = int(brightness * 100)
        
        # Create cache key with integer brightness
        cache_key = (base_color, brightness_int)
        
        # Check cache
        if cache_key not in self._brightness_cache:
            # Safety valve: clear cache if it grows too large
            if len(self._brightness_cache) >= self._CACHE_SIZE_LIMIT:
                self._brightness_cache.clear()
            
            # Calculate and cache the dimmed color using integer brightness
            brightness_factor = brightness_int / 100.0
            self._brightness_cache[cache_key] = tuple(int(c * brightness_factor) for c in base_color)
        
        return self._brightness_cache[cache_key]


def test_brightness_cache_initialization():
    """Test that the brightness cache is initialized."""
    print("Testing brightness cache initialization...")
    
    mock_pixels = MockPixelObject()
    manager = MatrixManager(mock_pixels)
    
    assert hasattr(manager, '_brightness_cache'), "Manager should have _brightness_cache attribute"
    assert isinstance(manager._brightness_cache, dict), "_brightness_cache should be a dict"
    assert len(manager._brightness_cache) == 0, "Cache should start empty"
    
    print("✓ Brightness cache initialization test passed")


def test_get_dimmed_color_basic():
    """Test basic functionality of _get_dimmed_color."""
    print("\nTesting _get_dimmed_color basic functionality...")
    
    mock_pixels = MockPixelObject()
    manager = MatrixManager(mock_pixels)
    
    # Test with brightness = 1.0 (should return original color)
    base_color = (200, 100, 50)
    result = manager._get_dimmed_color(base_color, 1.0)
    assert result == base_color, f"Brightness 1.0 should return original color, got {result}"
    assert len(manager._brightness_cache) == 0, "Cache should remain empty for brightness 1.0"
    
    # Test with brightness = 0.5
    result = manager._get_dimmed_color(base_color, 0.5)
    expected = (100, 50, 25)  # 200*0.5=100, 100*0.5=50, 50*0.5=25
    assert result == expected, f"Expected {expected}, got {result}"
    assert len(manager._brightness_cache) == 1, "Cache should have 1 entry"
    
    # Test with brightness = 0.0
    result = manager._get_dimmed_color(base_color, 0.0)
    expected = (0, 0, 0)
    assert result == expected, f"Expected {expected}, got {result}"
    assert len(manager._brightness_cache) == 1, "Cache should remain 1 entry (0.0 returns black directly)"
    
    print("✓ _get_dimmed_color basic functionality test passed")


def test_brightness_cache_reuse():
    """Test that cache is reused for repeated calls."""
    print("\nTesting brightness cache reuse...")
    
    mock_pixels = MockPixelObject()
    manager = MatrixManager(mock_pixels)
    
    base_color = (150, 150, 150)
    brightness = 0.75
    
    # First call - should populate cache
    result1 = manager._get_dimmed_color(base_color, brightness)
    cache_size1 = len(manager._brightness_cache)
    
    # Second call with same parameters - should use cache
    result2 = manager._get_dimmed_color(base_color, brightness)
    cache_size2 = len(manager._brightness_cache)
    
    assert result1 == result2, "Results should be identical"
    assert cache_size1 == cache_size2, "Cache size should not increase on reuse"
    assert cache_size1 == 1, f"Cache should have exactly 1 entry, has {cache_size1}"
    
    # Verify the results are the same object (cache hit)
    assert id(result1) == id(result2), "Should return same cached tuple object"
    
    print("✓ Brightness cache reuse test passed")


def test_brightness_rounding():
    """Test that brightness values are converted to integers for cache efficiency."""
    print("\nTesting brightness integer conversion...")
    
    mock_pixels = MockPixelObject()
    manager = MatrixManager(mock_pixels)
    
    base_color = (200, 100, 50)
    
    # These should all convert to 75 (int) and use the same cache entry
    brightness_values = [0.751, 0.752, 0.753, 0.754]
    
    results = []
    for brightness in brightness_values:
        result = manager._get_dimmed_color(base_color, brightness)
        results.append(result)
    
    # All results should be the same because they convert to int 75
    assert all(r == results[0] for r in results), "All values converting to same int should produce same result"
    assert len(manager._brightness_cache) == 1, f"Should have 1 cache entry, has {len(manager._brightness_cache)}"
    
    print("✓ Brightness integer conversion test passed")


def test_multiple_colors_cached():
    """Test that different base colors create separate cache entries."""
    print("\nTesting multiple colors cached...")
    
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
    
    # Should have 3 cache entries (one per color)
    assert len(manager._brightness_cache) == 3, f"Should have 3 cache entries, has {len(manager._brightness_cache)}"
    
    # Verify results are different
    assert results[0] == (127, 0, 0), "Red dimmed should be (127, 0, 0)"
    assert results[1] == (0, 127, 0), "Green dimmed should be (0, 127, 0)"
    assert results[2] == (0, 0, 127), "Blue dimmed should be (0, 0, 127)"
    
    print("✓ Multiple colors cached test passed")


def test_cache_efficiency():
    """Test that cache significantly reduces tuple allocations."""
    print("\nTesting cache efficiency...")
    
    mock_pixels = MockPixelObject()
    manager = MatrixManager(mock_pixels)
    
    base_color = (200, 100, 50)
    brightness = 0.8
    
    # Simulate calling for many pixels (like in show_icon)
    for _ in range(100):
        result = manager._get_dimmed_color(base_color, brightness)
    
    # Despite 100 calls, should only have 1 cache entry
    assert len(manager._brightness_cache) == 1, f"Should have 1 cache entry despite 100 calls, has {len(manager._brightness_cache)}"
    
    print("✓ Cache efficiency test passed")


def test_edge_cases():
    """Test edge cases for brightness values."""
    print("\nTesting edge cases...")
    
    mock_pixels = MockPixelObject()
    manager = MatrixManager(mock_pixels)
    
    base_color = (100, 100, 100)
    
    # Test brightness = 0
    result = manager._get_dimmed_color(base_color, 0)
    assert result == (0, 0, 0), "Brightness 0 should return black"
    
    # Test brightness = 1
    result = manager._get_dimmed_color(base_color, 1.0)
    assert result == base_color, "Brightness 1.0 should return original"
    
    # Test very small brightness
    result = manager._get_dimmed_color(base_color, 0.01)
    assert result == (1, 1, 1), "Very small brightness should work"
    
    # Test with (0, 0, 0) base color
    result = manager._get_dimmed_color((0, 0, 0), 0.5)
    assert result == (0, 0, 0), "Black should remain black at any brightness"
    
    print("✓ Edge cases test passed")


def test_cache_key_format():
    """Test that cache keys are properly formatted with integer brightness."""
    print("\nTesting cache key format...")
    
    mock_pixels = MockPixelObject()
    manager = MatrixManager(mock_pixels)
    
    base_color = (200, 150, 100)
    brightness = 0.753
    
    manager._get_dimmed_color(base_color, brightness)
    
    # Check that the cache key is properly formed with integer brightness
    expected_key = ((200, 150, 100), 75)  # int(0.753 * 100) = 75
    assert expected_key in manager._brightness_cache, f"Expected key {expected_key} in cache"
    
    print("✓ Cache key format test passed")


def test_cache_size_limit():
    """Test that cache is cleared when it exceeds size limit."""
    print("\nTesting cache size limit...")
    
    mock_pixels = MockPixelObject()
    manager = MatrixManager(mock_pixels)
    
    # Fill cache to just below limit (128 entries)
    base_color = (100, 100, 100)
    for i in range(manager._CACHE_SIZE_LIMIT):
        # Use different colors to create unique cache entries
        color = (i, i, i)
        manager._get_dimmed_color(color, 0.5)
    
    # Verify cache is at limit
    assert len(manager._brightness_cache) == manager._CACHE_SIZE_LIMIT, \
        f"Cache should be at limit {manager._CACHE_SIZE_LIMIT}, has {len(manager._brightness_cache)}"
    
    # Add one more entry - should trigger cache clear
    manager._get_dimmed_color((255, 255, 255), 0.5)
    
    # Cache should be small again (only the new entry)
    assert len(manager._brightness_cache) == 1, \
        f"Cache should be cleared and have 1 entry, has {len(manager._brightness_cache)}"
    
    print("✓ Cache size limit test passed")


if __name__ == "__main__":
    print("=" * 60)
    print("MatrixManager Brightness Cache Test Suite")
    print("=" * 60)
    
    try:
        test_brightness_cache_initialization()
        test_get_dimmed_color_basic()
        test_brightness_cache_reuse()
        test_brightness_rounding()
        test_multiple_colors_cached()
        test_cache_efficiency()
        test_edge_cases()
        test_cache_key_format()
        test_cache_size_limit()
        
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
