#!/usr/bin/env python3
"""Unit tests for MatrixManager with arbitrary matrix configurations.

This test suite now properly tests the REAL MatrixManager implementation
from src/managers/matrix_manager.py by using unittest.mock to isolate
hardware dependencies instead of creating a fake MatrixManager class.
"""

import sys
import os
from unittest import mock

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


# Mock ALL CircuitPython modules before any imports
circuitpython_mocks = [
    'digitalio', 'board', 'busio', 'neopixel', 'microcontroller',
    'analogio', 'audiocore', 'audiobusio', 'audioio', 'audiomixer',
    'adafruit_httpserver', 'adafruit_bus_device', 'adafruit_register',
    'sdcardio', 'storage', 'synthio', 'displayio', 'terminalio',
    'adafruit_framebuf', 'framebufferio', 'rgbmatrix', 'supervisor'
]

for module_name in circuitpython_mocks:
    sys.modules[module_name] = mock.MagicMock()

# Use real asyncio
sys.modules['asyncio'] = __import__('asyncio')


# Mock classes for hardware dependencies
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


# Mock color palette
class MockPalette:
    OFF = (0, 0, 0)
    RED = (255, 0, 0)
    GREEN = (0, 255, 0)
    BLUE = (0, 0, 255)
    YELLOW = (255, 255, 0)
    CYAN = (0, 255, 255)
    MAGENTA = (255, 0, 255)
    WHITE = (255, 255, 255)
    
    PALETTE_LIBRARY = {
        0: OFF,
        1: RED,
        2: GREEN,
        3: BLUE,
        4: YELLOW,
    }


# Mock icons
class MockIcons:
    """Mock Icons for testing."""
    # Simple 8x8 test icon (cross pattern)
    DEFAULT = [
        1, 0, 0, 0, 0, 0, 0, 1,
        0, 1, 0, 0, 0, 0, 1, 0,
        0, 0, 1, 0, 0, 1, 0, 0,
        0, 0, 0, 1, 1, 0, 0, 0,
        0, 0, 0, 1, 1, 0, 0, 0,
        0, 0, 1, 0, 0, 1, 0, 0,
        0, 1, 0, 0, 0, 0, 1, 0,
        1, 0, 0, 0, 0, 0, 0, 1,
    ]
    
    ICON_LIBRARY = {
        "DEFAULT": DEFAULT,
    }


# Mock the utilities modules
mock.patch.dict('sys.modules', {
    'utilities.palette': mock.MagicMock(Palette=MockPalette),
    'utilities.icons': mock.MagicMock(Icons=MockIcons),
    'utilities.matrix_animations': mock.MagicMock(),
}).start()

# Now import the REAL MatrixManager
from managers.matrix_manager import MatrixManager


# ============================================================================
# TESTS - Now testing the REAL MatrixManager from src/managers/matrix_manager.py
# ============================================================================

def test_single_8x8_matrix_default():
    """Test single 8x8 matrix with default parameters (backward compatibility)."""
    print("\nTesting single 8x8 matrix (default)...")
    
    # Create 8x8 matrix (64 pixels)
    jeb_pixel = MockJEBPixel(64)
    matrix = MatrixManager(jeb_pixel)  # Default width=8, height=8
    
    # Verify dimensions
    assert matrix.width == 8, "Default width should be 8"
    assert matrix.height == 8, "Default height should be 8"
    assert matrix.num_pixels == 64, "Should have 64 pixels"
    
    # Test pixel mapping - this is the CORE logic being tested
    # Top-left corner (0, 0) should map to index 0
    assert matrix._get_idx(0, 0) == 0
    # Top-right corner (7, 0) should map to index 7 (even row, left-to-right)
    assert matrix._get_idx(7, 0) == 7
    # Second row left (0, 1) should map to index 15 (odd row, right-to-left)
    assert matrix._get_idx(0, 1) == 15
    # Second row right (7, 1) should map to index 8 (odd row, right-to-left)
    assert matrix._get_idx(7, 1) == 8
    
    print("  ✓ 8x8 matrix default test passed")


def test_quad_8x8_panels():
    """Test four 8x8 panels forming a 16x16 display with panel-based addressing."""
    print("\nTesting quad 8x8 panels (16x16 with panel_width=8, panel_height=8)...")
    
    # Create 16x16 matrix from four 8x8 panels (256 pixels)
    jeb_pixel = MockJEBPixel(256)
    matrix = MatrixManager(jeb_pixel, width=16, height=16, panel_width=8, panel_height=8)
    
    # Verify dimensions
    assert matrix.width == 16
    assert matrix.height == 16
    assert matrix.panel_width == 8
    assert matrix.panel_height == 8
    assert matrix.num_pixels == 256
    
    # Test panel-based addressing - CRITICAL TEST FOR THE ISSUE
    # Panel 0 (top-left): pixels 0-63
    # Panel 1 (top-right): pixels 64-127
    # Panel 2 (bottom-left): pixels 128-191
    # Panel 3 (bottom-right): pixels 192-255
    
    # Top-left corner of display (panel 0, pixel 0)
    assert matrix._get_idx(0, 0) == 0
    
    # Top-right corner of first panel (panel 0, pixel 7)
    assert matrix._get_idx(7, 0) == 7
    
    # Top-left corner of second panel (panel 1, pixel 0)
    # This should be pixel 64, NOT pixel 8!
    actual = matrix._get_idx(8, 0)
    assert actual == 64, f"CRITICAL: Expected 64 for (8,0), got {actual}. Panel addressing is broken!"
    
    # Top-right corner of second panel (panel 1, pixel 7)
    assert matrix._get_idx(15, 0) == 71
    
    # Second row, first pixel (panel 0, row 1, reversed due to serpentine)
    # In an 8x8 panel, row 1 pixel 0 is at index 15 (serpentine)
    assert matrix._get_idx(0, 1) == 15
    
    # Second row, 9th pixel (panel 1, row 1, pixel 0 in panel coordinates)
    # Panel 1 starts at 64, row 1 in serpentine is 15
    assert matrix._get_idx(8, 1) == 64 + 15  # 79
    
    # Bottom-left corner of display (panel 2, pixel 0)
    assert matrix._get_idx(0, 8) == 128
    
    # Bottom-right corner of display (panel 3, local (7,7))
    # Panel 3 starts at 192, local (7,7) with y=7 (odd row, serpentine)
    # local_idx = 7*8 + (8-1-7) = 56 + 0 = 56
    assert matrix._get_idx(15, 15) == 192 + 56  # 248
    
    print("  ✓ Panel-based addressing test passed - tests REAL production code!")


def test_dual_8x8_horizontal():
    """Test dual 8x8 matrices arranged horizontally (16x8) with panel addressing."""
    print("\nTesting dual 8x8 horizontal (16x8 with panel_width=8, panel_height=8)...")
    
    # Create 16x8 matrix (128 pixels) - two 8x8 panels side by side
    jeb_pixel = MockJEBPixel(128)
    matrix = MatrixManager(jeb_pixel, width=16, height=8, panel_width=8, panel_height=8)
    
    # Verify dimensions
    assert matrix.width == 16
    assert matrix.height == 8
    assert matrix.num_pixels == 128
    
    # Test pixel mapping for panel-based addressing
    # Panel 0 (left): pixels 0-63
    # Panel 1 (right): pixels 64-127
    
    # Top-left of display (panel 0, pixel 0)
    assert matrix._get_idx(0, 0) == 0
    
    # Top-right of first panel (panel 0, pixel 7)
    assert matrix._get_idx(7, 0) == 7
    
    # Top-left of second panel (panel 1, pixel 0) - should be 64
    actual = matrix._get_idx(8, 0)
    assert actual == 64, f"Expected 64 for (8,0), got {actual}"
    
    # Top-right of display (panel 1, pixel 7)
    assert matrix._get_idx(15, 0) == 71
    
    # Second row first pixel (panel 0, serpentine row 1)
    assert matrix._get_idx(0, 1) == 15
    
    # Second row 9th pixel (panel 1, serpentine row 1)
    assert matrix._get_idx(8, 1) == 79
    
    print("  ✓ 16x8 panel-based matrix test passed")


def run_all_tests():
    """Run all matrix configuration tests."""
    print("=" * 70)
    print("MatrixManager Arbitrary Configuration Test Suite")
    print("Testing REAL production code from src/managers/matrix_manager.py")
    print("=" * 70)
    
    try:
        test_single_8x8_matrix_default()
        test_quad_8x8_panels()
        test_dual_8x8_horizontal()
        
        print("\n" + "=" * 70)
        print("✓ All core matrix configuration tests passed!")
        print("✓ Tests now validate REAL production code!")
        print("✓ CI will catch any regressions in panel-based addressing!")
        print("=" * 70)
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
    success = run_all_tests()
    sys.exit(0 if success else 1)
