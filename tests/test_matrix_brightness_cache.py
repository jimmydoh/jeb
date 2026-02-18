#!/usr/bin/env python3
"""Unit tests for BasePixelManager stateless brightness calculation."""

import sys
import os

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

# Import the REAL BasePixelManager from production code
from managers.base_pixel_manager import BasePixelManager


# Mock pixel object for testing (dependency for BasePixelManager)
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


def test_stateless_initialization():
    """Test that the manager initializes without a cache."""
    print("Testing stateless initialization...")
    
    mock_pixels = MockPixelObject()
    manager = BasePixelManager(mock_pixels)
    
    assert not hasattr(manager, '_brightness_cache'), "Manager should not have _brightness_cache attribute"
    assert not hasattr(manager, '_CACHE_SIZE_LIMIT'), "Manager should not have _CACHE_SIZE_LIMIT attribute"
    
    print("✓ Stateless initialization test passed")


def test_apply_brightness_basic():
    """Test basic functionality of _apply_brightness."""
    print("\nTesting _apply_brightness basic functionality...")
    
    mock_pixels = MockPixelObject()
    manager = BasePixelManager(mock_pixels)
    
    # Test with brightness = 1.0 (should return original color)
    base_color = (200, 100, 50)
    result = manager._apply_brightness(base_color, 1.0)
    assert result == base_color, f"Brightness 1.0 should return original color, got {result}"
    
    # Test with brightness = 0.5
    result = manager._apply_brightness(base_color, 0.5)
    expected = (100, 50, 25)  # 200*0.5=100, 100*0.5=50, 50*0.5=25
    assert result == expected, f"Expected {expected}, got {result}"
    
    # Test with brightness = 0.0 (should return black)
    result = manager._apply_brightness(base_color, 0.0)
    expected = (0, 0, 0)
    assert result == expected, f"Expected {expected}, got {result}"
    
    print("✓ _apply_brightness basic functionality test passed")


def test_brightness_clamping():
    """Test that brightness is clamped to [0.0, 1.0] range."""
    print("\nTesting brightness clamping...")
    
    mock_pixels = MockPixelObject()
    manager = BasePixelManager(mock_pixels)
    
    base_color = (200, 100, 50)
    
    # Test with brightness > 1.0 (should be clamped to 1.0)
    result = manager._apply_brightness(base_color, 1.5)
    assert result == base_color, f"Brightness > 1.0 should be clamped to 1.0, got {result}"
    
    result = manager._apply_brightness(base_color, 2.0)
    assert result == base_color, f"Brightness > 1.0 should be clamped to 1.0, got {result}"
    
    # Test with brightness < 0.0 (should be clamped to 0.0)
    result = manager._apply_brightness(base_color, -0.5)
    assert result == (0, 0, 0), f"Brightness < 0.0 should be clamped to 0.0, got {result}"
    
    result = manager._apply_brightness(base_color, -1.0)
    assert result == (0, 0, 0), f"Brightness < 0.0 should be clamped to 0.0, got {result}"
    
    print("✓ Brightness clamping test passed")


def test_stateless_calculation():
    """Test that calculations are done without caching."""
    print("\nTesting stateless calculation...")
    
    mock_pixels = MockPixelObject()
    manager = BasePixelManager(mock_pixels)
    
    base_color = (150, 150, 150)
    brightness = 0.75
    
    # First call - should calculate result
    result1 = manager._apply_brightness(base_color, brightness)
    expected = (112, 112, 112)  # 150*0.75 = 112.5, int() = 112
    assert result1 == expected, f"Expected {expected}, got {result1}"
    
    # Second call with same parameters - should calculate again (no cache)
    result2 = manager._apply_brightness(base_color, brightness)
    assert result2 == expected, f"Expected {expected}, got {result2}"
    
    # Results should be identical (even without caching)
    assert result1 == result2, "Stateless calculation should give consistent results"
    
    # Verify no cache attribute exists
    assert not hasattr(manager, '_brightness_cache'), "Manager should not have caching"
    
    print("✓ Stateless calculation test passed")


def test_various_brightness_levels():
    """Test various brightness levels to ensure correctness."""
    print("\nTesting various brightness levels...")
    
    mock_pixels = MockPixelObject()
    manager = BasePixelManager(mock_pixels)
    
    base_color = (200, 100, 50)
    
    # Test multiple brightness levels
    test_cases = [
        (0.0, (0, 0, 0)),
        (0.25, (50, 25, 12)),   # 200*0.25=50, 100*0.25=25, 50*0.25=12.5->12
        (0.5, (100, 50, 25)),
        (0.75, (150, 75, 37)),  # 200*0.75=150, 100*0.75=75, 50*0.75=37.5->37
        (1.0, (200, 100, 50)),
    ]
    
    for brightness, expected in test_cases:
        result = manager._apply_brightness(base_color, brightness)
        assert result == expected, f"Brightness {brightness}: expected {expected}, got {result}"
        print(f"  ✓ Brightness {brightness}: {base_color} → {result}")
    
    print("✓ Various brightness levels test passed")


def test_edge_cases():
    """Test edge cases like black base color, white base color, etc."""
    print("\nTesting edge cases...")
    
    mock_pixels = MockPixelObject()
    manager = BasePixelManager(mock_pixels)
    
    # Test with black base color
    result = manager._apply_brightness((0, 0, 0), 0.5)
    assert result == (0, 0, 0), "Black should stay black at any brightness"
    
    # Test with white base color
    result = manager._apply_brightness((255, 255, 255), 0.5)
    expected = (127, 127, 127)  # 255*0.5 = 127.5 -> 127
    assert result == expected, f"Expected {expected}, got {result}"
    
    # Test with single channel color
    result = manager._apply_brightness((255, 0, 0), 0.5)
    expected = (127, 0, 0)
    assert result == expected, f"Expected {expected}, got {result}"
    
    print("✓ Edge cases test passed")


if __name__ == "__main__":
    print("=" * 60)
    print("BasePixelManager Stateless Brightness Calculation Test Suite")
    print("=" * 60)
    
    try:
        test_stateless_initialization()
        test_apply_brightness_basic()
        test_brightness_clamping()
        test_stateless_calculation()
        test_various_brightness_levels()
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

