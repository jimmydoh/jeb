#!/usr/bin/env python3
"""Unit tests for BasePixelManager common animation methods."""

import sys
import pytest
import time


# Mock JEBPixel for testing
class MockJEBPixel:
    """Mock JEBPixel wrapper for testing."""
    def __init__(self, num_pixels=10):
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
        pass  # Mock - does nothing


# Import after mocks are defined
sys.path.insert(0, '/home/runner/work/jeb/jeb/src')

# Import directly to avoid __init__.py which has CircuitPython dependencies
import importlib.util
spec = importlib.util.spec_from_file_location(
    "base_pixel_manager", 
    "/home/runner/work/jeb/jeb/src/managers/base_pixel_manager.py"
)
base_pixel_manager_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base_pixel_manager_module)

BasePixelManager = base_pixel_manager_module.BasePixelManager
PixelLayout = base_pixel_manager_module.PixelLayout


def test_solid_animation_single_pixel():
    """Test solid() method on a single pixel."""
    print("Testing solid() on single pixel...")
    
    mock_pixel = MockJEBPixel(10)
    manager = BasePixelManager(mock_pixel)
    
    manager.solid(3, (255, 0, 0), brightness=1.0)
    
    # Check that animation was set
    assert manager.active_animations[3].active, "Animation should be active"
    assert manager.active_animations[3].type == "SOLID"
    assert manager.active_animations[3].color == (255, 0, 0)
    assert manager._active_count == 1
    
    print("✓ solid() single pixel test passed")


def test_solid_animation_all_pixels():
    """Test solid() method on all pixels."""
    print("\nTesting solid() on all pixels...")
    
    mock_pixel = MockJEBPixel(5)
    manager = BasePixelManager(mock_pixel)
    
    manager.solid(-1, (0, 255, 0), brightness=0.5)
    
    # Check that all animations were set
    for i in range(5):
        assert manager.active_animations[i].active, f"Animation {i} should be active"
        assert manager.active_animations[i].type == "SOLID"
        # Brightness should be applied: (0, 255, 0) * 0.5 = (0, 127, 0)
        assert manager.active_animations[i].color == (0, 127, 0), \
            f"Color should be brightness-adjusted, got {manager.active_animations[i].color}"
    
    assert manager._active_count == 5
    
    print("✓ solid() all pixels test passed")


def test_flash_animation():
    """Test flash() method."""
    print("\nTesting flash() method...")
    
    mock_pixel = MockJEBPixel(10)
    manager = BasePixelManager(mock_pixel)
    
    manager.flash(2, (100, 100, 255), brightness=0.8, speed=2.0, duration=5.0, priority=3)
    
    slot = manager.active_animations[2]
    assert slot.active
    assert slot.type == "BLINK"
    # Brightness: (100, 100, 255) * 0.8 = (80, 80, 204)
    assert slot.color == (80, 80, 204)
    assert slot.speed == 2.0
    assert slot.priority == 3
    assert slot.duration == 5.0
    
    print("✓ flash() test passed")


def test_breathe_animation():
    """Test breathe() method."""
    print("\nTesting breathe() method...")
    
    mock_pixel = MockJEBPixel(10)
    manager = BasePixelManager(mock_pixel)
    
    manager.breathe(5, (200, 50, 100), brightness=1.0, speed=3.0)
    
    slot = manager.active_animations[5]
    assert slot.active
    assert slot.type == "PULSE"
    assert slot.color == (200, 50, 100)
    assert slot.speed == 3.0
    
    print("✓ breathe() test passed")


def test_cylon_animation():
    """Test cylon() method fills all pixels."""
    print("\nTesting cylon() method...")
    
    mock_pixel = MockJEBPixel(10)
    manager = BasePixelManager(mock_pixel)
    
    manager.cylon((255, 0, 0), duration=2.0, speed=0.1)
    
    # All pixels should have SCANNER animation
    for i in range(10):
        assert manager.active_animations[i].active
        assert manager.active_animations[i].type == "SCANNER"
        assert manager.active_animations[i].color == (255, 0, 0)
        assert manager.active_animations[i].speed == 0.1
        assert manager.active_animations[i].duration == 2.0
    
    assert manager._active_count == 10
    
    print("✓ cylon() test passed")


def test_centrifuge_animation():
    """Test centrifuge() method fills all pixels."""
    print("\nTesting centrifuge() method...")
    
    mock_pixel = MockJEBPixel(8)
    manager = BasePixelManager(mock_pixel)
    
    manager.centrifuge((0, 255, 255), duration=3.0, speed=0.15)
    
    # All pixels should have CHASER animation
    for i in range(8):
        assert manager.active_animations[i].active
        assert manager.active_animations[i].type == "CHASER"
        assert manager.active_animations[i].color == (0, 255, 255)
        assert manager.active_animations[i].speed == 0.15
    
    print("✓ centrifuge() test passed")


def test_rainbow_animation():
    """Test rainbow() method."""
    print("\nTesting rainbow() method...")
    
    mock_pixel = MockJEBPixel(12)
    manager = BasePixelManager(mock_pixel)
    
    manager.rainbow(duration=5.0, speed=0.02)
    
    # All pixels should have RAINBOW animation
    for i in range(12):
        assert manager.active_animations[i].active
        assert manager.active_animations[i].type == "RAINBOW"
        assert manager.active_animations[i].color is None  # Rainbow doesn't use color
        assert manager.active_animations[i].speed == 0.02
    
    print("✓ rainbow() test passed")


def test_glitch_animation():
    """Test glitch() method."""
    print("\nTesting glitch() method...")
    
    mock_pixel = MockJEBPixel(6)
    manager = BasePixelManager(mock_pixel)
    
    colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]
    manager.glitch(colors, duration=1.0, speed=0.1)
    
    # All pixels should have GLITCH animation
    for i in range(6):
        assert manager.active_animations[i].active
        assert manager.active_animations[i].type == "GLITCH"
        # Colors should be stored as tuple
        assert manager.active_animations[i].color == tuple(colors)
        assert manager.active_animations[i].speed == 0.1
    
    print("✓ glitch() test passed")


def test_brightness_calculation():
    """Test that brightness is correctly applied to colors."""
    print("\nTesting brightness calculation...")
    
    mock_pixel = MockJEBPixel(5)
    manager = BasePixelManager(mock_pixel)
    
    # Test various brightness values
    test_cases = [
        ((255, 255, 255), 1.0, (255, 255, 255)),
        ((255, 255, 255), 0.5, (127, 127, 127)),
        ((200, 100, 50), 0.5, (100, 50, 25)),
        ((100, 200, 150), 0.2, (20, 40, 30)),
        ((255, 128, 64), 0.0, (0, 0, 0)),
    ]
    
    for idx, (color, brightness, expected) in enumerate(test_cases):
        manager.solid(idx, color, brightness=brightness)
        result = manager.active_animations[idx].color
        assert result == expected, \
            f"Brightness {brightness} on {color} should give {expected}, got {result}"
    
    print("✓ Brightness calculation test passed")


def test_priority_handling():
    """Test that priority is properly passed to animations."""
    print("\nTesting priority handling...")
    
    mock_pixel = MockJEBPixel(10)
    manager = BasePixelManager(mock_pixel)
    
    # Set animation with priority 5
    manager.solid(0, (255, 0, 0), priority=5)
    assert manager.active_animations[0].priority == 5
    
    # Set animation with priority 10
    manager.flash(1, (0, 255, 0), priority=10)
    assert manager.active_animations[1].priority == 10
    
    # Set animation with default priority
    manager.breathe(2, (0, 0, 255))
    assert manager.active_animations[2].priority == 2  # default
    
    print("✓ Priority handling test passed")


def test_duration_handling():
    """Test that duration is properly passed to animations."""
    print("\nTesting duration handling...")
    
    mock_pixel = MockJEBPixel(10)
    manager = BasePixelManager(mock_pixel)
    
    # Set animation with duration
    manager.solid(0, (255, 0, 0), duration=3.5)
    assert manager.active_animations[0].duration == 3.5
    
    # Set animation without duration (None)
    manager.flash(1, (0, 255, 0))
    assert manager.active_animations[1].duration is None
    
    print("✓ Duration handling test passed")


def test_animation_methods_work_with_different_layouts():
    """Test that animation methods work with different layout types."""
    print("\nTesting animation methods with different layouts...")
    
    # Test with LINEAR layout
    mock_pixel_linear = MockJEBPixel(10)
    manager_linear = BasePixelManager(mock_pixel_linear, layout_type=PixelLayout.LINEAR)
    manager_linear.solid(0, (255, 0, 0))
    assert manager_linear.active_animations[0].active
    
    # Test with MATRIX_2D layout
    mock_pixel_matrix = MockJEBPixel(64)
    manager_matrix = BasePixelManager(mock_pixel_matrix, 
                                      layout_type=PixelLayout.MATRIX_2D, 
                                      dimensions=(8, 8))
    manager_matrix.flash(10, (0, 255, 0))
    assert manager_matrix.active_animations[10].active
    
    # Test with CIRCLE layout
    mock_pixel_circle = MockJEBPixel(24)
    manager_circle = BasePixelManager(mock_pixel_circle, layout_type=PixelLayout.CIRCLE)
    manager_circle.breathe(5, (0, 0, 255))
    assert manager_circle.active_animations[5].active
    
    print("✓ Different layouts test passed")


if __name__ == "__main__":
    print("=" * 60)
    print("BasePixelManager Common Animation Methods Test Suite")
    print("=" * 60)
    
    try:
        test_solid_animation_single_pixel()
        test_solid_animation_all_pixels()
        test_flash_animation()
        test_breathe_animation()
        test_cylon_animation()
        test_centrifuge_animation()
        test_rainbow_animation()
        test_glitch_animation()
        test_brightness_calculation()
        test_priority_handling()
        test_duration_handling()
        test_animation_methods_work_with_different_layouts()
        
        print("\n" + "=" * 60)
        print("ALL TESTS PASSED ✓")
        print("=" * 60)
        sys.exit(0)
        
    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
