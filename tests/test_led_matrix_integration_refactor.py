#!/usr/bin/env python3
"""Integration tests for LEDManager and MatrixManager with refactored animation logic."""

import sys
import os
import pytest


# Mock CircuitPython modules BEFORE any imports (same pattern as other tests)
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


# Import managers after mocks are set up
from managers.led_manager import LEDManager
from managers.matrix_manager import MatrixManager
from managers.base_pixel_manager import PixelLayout


def test_led_manager_layout():
    """Test that LEDManager declares LINEAR layout."""
    print("Testing LEDManager layout declaration...")
    
    mock_pixel = MockJEBPixel(10)
    led_manager = LEDManager(mock_pixel)
    
    assert led_manager.get_layout_type() == PixelLayout.LINEAR, \
        "LEDManager should declare LINEAR layout"
    assert led_manager.get_dimensions() == (10,), \
        "LEDManager dimensions should be (num_pixels,)"
    
    print("✓ LEDManager layout test passed")


def test_matrix_manager_layout():
    """Test that MatrixManager declares MATRIX_2D layout."""
    print("\nTesting MatrixManager layout declaration...")
    
    mock_pixel = MockJEBPixel(64)
    matrix_manager = MatrixManager(mock_pixel)
    
    assert matrix_manager.get_layout_type() == PixelLayout.MATRIX_2D, \
        "MatrixManager should declare MATRIX_2D layout"
    assert matrix_manager.get_dimensions() == (8, 8), \
        "MatrixManager dimensions should be (8, 8)"
    
    print("✓ MatrixManager layout test passed")


def test_led_manager_solid_led():
    """Test LEDManager.solid_led() method."""
    print("\nTesting LEDManager.solid_led()...")
    
    mock_pixel = MockJEBPixel(10)
    led_manager = LEDManager(mock_pixel)
    
    led_manager.solid_led(3, (255, 0, 0), brightness=0.5)
    
    slot = led_manager.active_animations[3]
    assert slot.active, "Animation should be active"
    assert slot.type == "SOLID"
    # Color should be brightness-adjusted: (255, 0, 0) * 0.5 = (127, 0, 0)
    assert slot.color == (127, 0, 0)
    
    print("✓ LEDManager.solid_led() test passed")


def test_led_manager_flash_led():
    """Test LEDManager.flash_led() method."""
    print("\nTesting LEDManager.flash_led()...")
    
    mock_pixel = MockJEBPixel(10)
    led_manager = LEDManager(mock_pixel)
    
    led_manager.flash_led(5, (0, 255, 0), brightness=0.8, speed=2.0)
    
    slot = led_manager.active_animations[5]
    assert slot.active
    assert slot.type == "BLINK"
    assert slot.color == (0, 204, 0)  # 255 * 0.8 = 204
    assert slot.speed == 2.0
    
    print("✓ LEDManager.flash_led() test passed")


def test_led_manager_breathe_led():
    """Test LEDManager.breathe_led() method."""
    print("\nTesting LEDManager.breathe_led()...")
    
    mock_pixel = MockJEBPixel(10)
    led_manager = LEDManager(mock_pixel)
    
    led_manager.breathe_led(2, (100, 100, 255), brightness=1.0, speed=3.0)
    
    slot = led_manager.active_animations[2]
    assert slot.active
    assert slot.type == "PULSE"
    assert slot.color == (100, 100, 255)
    assert slot.speed == 3.0
    
    print("✓ LEDManager.breathe_led() test passed")


def test_led_manager_start_cylon():
    """Test LEDManager.start_cylon() method."""
    print("\nTesting LEDManager.start_cylon()...")
    
    mock_pixel = MockJEBPixel(8)
    led_manager = LEDManager(mock_pixel)
    
    led_manager.start_cylon((255, 0, 0), duration=2.0, speed=0.1)
    
    # All pixels should have SCANNER animation
    for i in range(8):
        assert led_manager.active_animations[i].active
        assert led_manager.active_animations[i].type == "SCANNER"
        assert led_manager.active_animations[i].color == (255, 0, 0)
    
    print("✓ LEDManager.start_cylon() test passed")


def test_led_manager_start_centrifuge():
    """Test LEDManager.start_centrifuge() method."""
    print("\nTesting LEDManager.start_centrifuge()...")
    
    mock_pixel = MockJEBPixel(8)
    led_manager = LEDManager(mock_pixel)
    
    led_manager.start_centrifuge((0, 255, 255), speed=0.15)
    
    # All pixels should have CHASER animation
    for i in range(8):
        assert led_manager.active_animations[i].active
        assert led_manager.active_animations[i].type == "CHASER"
    
    print("✓ LEDManager.start_centrifuge() test passed")


def test_led_manager_start_rainbow():
    """Test LEDManager.start_rainbow() method."""
    print("\nTesting LEDManager.start_rainbow()...")
    
    mock_pixel = MockJEBPixel(10)
    led_manager = LEDManager(mock_pixel)
    
    led_manager.start_rainbow(duration=5.0, speed=0.02)
    
    # All pixels should have RAINBOW animation
    for i in range(10):
        assert led_manager.active_animations[i].active
        assert led_manager.active_animations[i].type == "RAINBOW"
    
    print("✓ LEDManager.start_rainbow() test passed")


def test_led_manager_start_glitch():
    """Test LEDManager.start_glitch() method."""
    print("\nTesting LEDManager.start_glitch()...")
    
    mock_pixel = MockJEBPixel(6)
    led_manager = LEDManager(mock_pixel)
    
    colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]
    led_manager.start_glitch(colors, duration=1.0)
    
    # All pixels should have GLITCH animation
    for i in range(6):
        assert led_manager.active_animations[i].active
        assert led_manager.active_animations[i].type == "GLITCH"
    
    print("✓ LEDManager.start_glitch() test passed")


def test_led_manager_off_led():
    """Test LEDManager.off_led() method."""
    print("\nTesting LEDManager.off_led()...")
    
    mock_pixel = MockJEBPixel(10)
    led_manager = LEDManager(mock_pixel)
    
    # Set animation first
    led_manager.solid_led(5, (255, 0, 0))
    assert led_manager.active_animations[5].active
    
    # Turn it off
    led_manager.off_led(5)
    assert not led_manager.active_animations[5].active
    
    print("✓ LEDManager.off_led() test passed")


def test_matrix_manager_draw_pixel():
    """Test MatrixManager.draw_pixel() method."""
    print("\nTesting MatrixManager.draw_pixel()...")
    
    mock_pixel = MockJEBPixel(64)
    matrix_manager = MatrixManager(mock_pixel)
    
    matrix_manager.draw_pixel(3, 4, (255, 0, 0))
    
    # Calculate expected index for (3, 4)
    # Row 4 is even, so index = 4 * 8 + 3 = 35
    idx = 35
    slot = matrix_manager.active_animations[idx]
    assert slot.active
    assert slot.type == "SOLID"
    assert slot.color == (255, 0, 0)
    
    print("✓ MatrixManager.draw_pixel() test passed")


def test_matrix_manager_draw_pixel_with_animation():
    """Test MatrixManager.draw_pixel() with animation mode."""
    print("\nTesting MatrixManager.draw_pixel() with animation...")
    
    mock_pixel = MockJEBPixel(64)
    matrix_manager = MatrixManager(mock_pixel)
    
    matrix_manager.draw_pixel(2, 2, (0, 255, 0), anim_mode="PULSE", speed=2.0)
    
    # Row 2 is even, so index = 2 * 8 + 2 = 18
    idx = 18
    slot = matrix_manager.active_animations[idx]
    assert slot.active
    assert slot.type == "PULSE"
    assert slot.color == (0, 255, 0)
    assert slot.speed == 2.0
    
    print("✓ MatrixManager.draw_pixel() with animation test passed")


def test_matrix_manager_fill():
    """Test MatrixManager.fill() method."""
    print("\nTesting MatrixManager.fill()...")
    
    mock_pixel = MockJEBPixel(64)
    matrix_manager = MatrixManager(mock_pixel)
    
    matrix_manager.fill((100, 100, 100), anim_mode="BLINK", speed=1.5)
    
    # All 64 pixels should have BLINK animation
    for i in range(64):
        assert matrix_manager.active_animations[i].active
        assert matrix_manager.active_animations[i].type == "BLINK"
        assert matrix_manager.active_animations[i].color == (100, 100, 100)
        assert matrix_manager.active_animations[i].speed == 1.5
    
    print("✓ MatrixManager.fill() test passed")


def test_matrix_manager_draw_quadrant():
    """Test MatrixManager.draw_quadrant() method."""
    print("\nTesting MatrixManager.draw_quadrant()...")
    
    mock_pixel = MockJEBPixel(64)
    matrix_manager = MatrixManager(mock_pixel)
    
    # Draw top-left quadrant (quad_idx=0)
    matrix_manager.draw_quadrant(0, (255, 0, 0), anim_mode="SOLID")
    
    # Check that 16 pixels (4x4) were set
    active_count = sum(1 for slot in matrix_manager.active_animations if slot.active)
    assert active_count == 16, f"Should have 16 active animations, got {active_count}"
    
    # Verify some specific pixels in the quadrant
    # Top-left quadrant is (0,0) to (3,3)
    # (0,0) -> index 0
    # (1,0) -> index 1
    # (0,1) -> index 8 + 7 = 15 (serpentine, row 1 is odd)
    assert matrix_manager.active_animations[0].active
    assert matrix_manager.active_animations[0].color == (255, 0, 0)
    
    print("✓ MatrixManager.draw_quadrant() test passed")


def test_led_manager_set_led_with_animations():
    """Test LEDManager.set_led() with different animation modes."""
    print("\nTesting LEDManager.set_led() with animations...")
    
    mock_pixel = MockJEBPixel(10)
    led_manager = LEDManager(mock_pixel)
    
    # Test SOLID (no animation)
    led_manager.set_led(0, (255, 0, 0), brightness=1.0, anim=None)
    assert led_manager.active_animations[0].type == "SOLID"
    
    # Test FLASH animation
    led_manager.set_led(1, (0, 255, 0), brightness=1.0, anim="FLASH", speed=2.0)
    assert led_manager.active_animations[1].type == "BLINK"
    
    # Test BREATH animation
    led_manager.set_led(2, (0, 0, 255), brightness=1.0, anim="BREATH", speed=3.0)
    assert led_manager.active_animations[2].type == "PULSE"
    
    # Test unknown animation (should default to SOLID)
    led_manager.set_led(3, (255, 255, 0), brightness=1.0, anim="UNKNOWN")
    assert led_manager.active_animations[3].type == "SOLID"
    
    print("✓ LEDManager.set_led() with animations test passed")


def test_backward_compatibility():
    """Test that existing code patterns still work."""
    print("\nTesting backward compatibility...")
    
    # LEDManager patterns
    mock_pixel_led = MockJEBPixel(10)
    led_manager = LEDManager(mock_pixel_led)
    
    # Old-style calls should still work
    led_manager.solid_led(0, (255, 0, 0), brightness=0.5, duration=2.0, priority=3)
    led_manager.flash_led(1, (0, 255, 0), speed=1.0)
    led_manager.breathe_led(2, (0, 0, 255), speed=2.0)
    led_manager.start_cylon((255, 255, 0))
    led_manager.start_rainbow()
    
    assert led_manager._active_count > 0, "Animations should be active"
    
    # MatrixManager patterns
    mock_pixel_matrix = MockJEBPixel(64)
    matrix_manager = MatrixManager(mock_pixel_matrix)
    
    # Old-style calls should still work
    matrix_manager.draw_pixel(0, 0, (255, 0, 0))
    matrix_manager.fill((0, 255, 0), anim_mode="PULSE")
    matrix_manager.draw_quadrant(0, (0, 0, 255))
    
    # New brightness parameter should work
    matrix_manager.draw_pixel(1, 1, (255, 128, 64), brightness=0.5)
    
    assert matrix_manager._active_count > 0, "Animations should be active"
    
    print("✓ Backward compatibility test passed")


def test_matrix_manager_brightness_parameter():
    """Test MatrixManager draw_pixel with brightness parameter."""
    print("\nTesting MatrixManager brightness parameter...")
    
    mock_pixel = MockJEBPixel(64)
    matrix_manager = MatrixManager(mock_pixel)
    
    # Test draw_pixel with brightness
    matrix_manager.draw_pixel(0, 0, (200, 100, 50), brightness=0.5)
    
    # Row 0 is even, so index = 0 * 8 + 0 = 0
    slot = matrix_manager.active_animations[0]
    assert slot.active
    assert slot.color == (100, 50, 25), \
        f"Expected (100, 50, 25), got {slot.color}"
    
    # Test with brightness > 1.0 (should clamp)
    matrix_manager.draw_pixel(1, 0, (255, 128, 64), brightness=2.0)
    slot = matrix_manager.active_animations[1]
    assert slot.color == (255, 128, 64), \
        f"Brightness > 1.0 should clamp, got {slot.color}"
    
    # Test with brightness = 0.0
    matrix_manager.draw_pixel(2, 0, (180, 90, 45), brightness=0.0)
    slot = matrix_manager.active_animations[2]
    assert slot.color == (0, 0, 0), \
        f"Brightness 0.0 should give black, got {slot.color}"
    
    print("✓ MatrixManager brightness parameter test passed")


if __name__ == "__main__":
    print("=" * 60)
    print("LEDManager & MatrixManager Integration Test Suite")
    print("=" * 60)
    
    try:
        test_led_manager_layout()
        test_matrix_manager_layout()
        test_led_manager_solid_led()
        test_led_manager_flash_led()
        test_led_manager_breathe_led()
        test_led_manager_start_cylon()
        test_led_manager_start_centrifuge()
        test_led_manager_start_rainbow()
        test_led_manager_start_glitch()
        test_led_manager_off_led()
        test_matrix_manager_draw_pixel()
        test_matrix_manager_draw_pixel_with_animation()
        test_matrix_manager_fill()
        test_matrix_manager_draw_quadrant()
        test_led_manager_set_led_with_animations()
        test_backward_compatibility()
        test_matrix_manager_brightness_parameter()
        
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
