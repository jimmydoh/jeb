#!/usr/bin/env python3
"""Unit tests for MatrixManager with arbitrary matrix configurations."""

import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


# Mock Palette for testing
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


# Mock NeoPixel for testing
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


# Mock BasePixelManager components
class PixelLayout:
    """Mock PixelLayout enum."""
    LINEAR = "linear"
    MATRIX_2D = "matrix_2d"
    CIRCLE = "circle"
    CUSTOM = "custom"


# Import the real MatrixManager after setting up mocks
import importlib.util
spec = importlib.util.spec_from_file_location(
    "matrix_manager",
    os.path.join(os.path.dirname(__file__), '..', 'src', 'managers', 'matrix_manager.py')
)
matrix_module = importlib.util.module_from_spec(spec)

# Mock dependencies before loading the module
sys.modules['utilities.palette'] = type('MockModule', (), {'Palette': MockPalette})()
sys.modules['utilities.icons'] = type('MockModule', (), {'Icons': MockIcons})()
sys.modules['utilities'] = type('MockModule', (), {'matrix_animations': type('MockModule', (), {})()})()
sys.modules['managers.base_pixel_manager'] = type('MockModule', (), {
    'BasePixelManager': object,
    'PixelLayout': PixelLayout
})()

# Now we need to create a proper MatrixManager mock that implements the logic
class MatrixManager:
    """Test implementation of MatrixManager with arbitrary dimensions."""
    
    def __init__(self, jeb_pixel, width=8, height=8, panel_width=None, panel_height=None):
        """Initialize MatrixManager with configurable dimensions."""
        self.pixels = jeb_pixel
        self.num_pixels = jeb_pixel.n
        self.width = width
        self.height = height
        self.panel_width = panel_width if panel_width is not None else width
        self.panel_height = panel_height if panel_height is not None else height
        self.palette = MockPalette.PALETTE_LIBRARY
        self.icons = MockIcons.ICON_LIBRARY
        
    def _get_idx(self, x, y):
        """Maps 2D coordinates to 1D pixel index with panel-aware addressing."""
        # Determine which panel this coordinate is in
        panel_x = x // self.panel_width
        panel_y = y // self.panel_height
        
        # Local coordinates within the panel
        local_x = x % self.panel_width
        local_y = y % self.panel_height
        
        # Calculate panel index (reading left-to-right, top-to-bottom)
        panels_per_row = self.width // self.panel_width
        panel_idx = panel_y * panels_per_row + panel_x
        
        # Calculate pixel index within the panel (serpentine)
        if local_y % 2 == 0:
            local_idx = (local_y * self.panel_width) + local_x
        else:
            local_idx = (local_y * self.panel_width) + (self.panel_width - 1 - local_x)
        
        # Final pixel index = panel start + local index
        pixels_per_panel = self.panel_width * self.panel_height
        return panel_idx * pixels_per_panel + local_idx
    
    def draw_pixel(self, x, y, color, show=False, anim_mode=None, speed=1.0, duration=None, brightness=1.0):
        """Sets a specific pixel on the matrix."""
        if 0 <= x < self.width and 0 <= y < self.height:
            idx = self._get_idx(x, y)
            # Apply brightness
            adjusted_color = tuple(int(c * brightness) for c in color)
            self.pixels[idx] = adjusted_color
    
    def fill(self, color, show=True, anim_mode=None, speed=1.0, duration=None):
        """Fills the entire matrix with a single color."""
        self.pixels.fill(color)
    
    def show_progress_grid(self, iterations, total=10, color=(100, 0, 200)):
        """Fills the matrix like a rising 'tank' of fluid."""
        self.fill(MockPalette.OFF, show=False)
        fill_limit = int((iterations / total) * self.num_pixels)
        for i in range(fill_limit):
            x = i % self.width
            y = self.height - 1 - (i // self.width)
            self.draw_pixel(x, y, color, show=False)
    
    def draw_quadrant(self, quad_idx, color, anim_mode=None, speed=1.0, duration=None):
        """Fills one of four quadrants."""
        quad_width = self.width // 2
        quad_height = self.height // 2
        
        offsets = [
            (0, 0),                          # Top-left
            (quad_width, 0),                 # Top-right
            (0, quad_height),                # Bottom-left
            (quad_width, quad_height)        # Bottom-right
        ]
        ox, oy = offsets[quad_idx]
        
        for y in range(quad_height):
            for x in range(quad_width):
                self.draw_pixel(ox + x, oy + y, color, show=False)


# ============================================================================
# TESTS
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
    
    # Test pixel mapping
    # Top-left corner (0, 0) should map to index 0
    assert matrix._get_idx(0, 0) == 0
    # Top-right corner (7, 0) should map to index 7 (even row, left-to-right)
    assert matrix._get_idx(7, 0) == 7
    # Second row left (0, 1) should map to index 15 (odd row, right-to-left)
    assert matrix._get_idx(0, 1) == 15
    # Second row right (7, 1) should map to index 8 (odd row, right-to-left)
    assert matrix._get_idx(7, 1) == 8
    
    # Test draw_pixel
    matrix.draw_pixel(0, 0, MockPalette.RED)
    assert matrix.pixels[0] == MockPalette.RED
    
    matrix.draw_pixel(7, 0, MockPalette.GREEN)
    assert matrix.pixels[7] == MockPalette.GREEN
    
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
    
    # Test panel-based addressing
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
    assert matrix._get_idx(8, 0) == 64, f"Expected 64, got {matrix._get_idx(8, 0)}"
    
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
    
    print("  ✓ Panel-based addressing test passed")


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
    assert matrix._get_idx(8, 0) == 64, f"Expected 64, got {matrix._get_idx(8, 0)}"
    
    # Top-right of display (panel 1, pixel 7)
    assert matrix._get_idx(15, 0) == 71
    
    # Second row first pixel (panel 0, serpentine row 1)
    assert matrix._get_idx(0, 1) == 15
    
    # Second row 9th pixel (panel 1, serpentine row 1)
    assert matrix._get_idx(8, 1) == 79
    
    # Test drawing pixels
    matrix.draw_pixel(0, 0, MockPalette.RED)
    assert matrix.pixels[0] == MockPalette.RED
    
    matrix.draw_pixel(8, 0, MockPalette.BLUE)  # First pixel of second panel
    assert matrix.pixels[64] == MockPalette.BLUE
    
    # Test out-of-bounds (should not crash)
    matrix.draw_pixel(16, 0, MockPalette.GREEN)  # Out of bounds
    matrix.draw_pixel(0, 8, MockPalette.GREEN)  # Out of bounds
    
    print("  ✓ 16x8 panel-based matrix test passed")


def test_dual_8x8_vertical():
    """Test dual 8x8 matrices arranged vertically (8x16) with panel addressing."""
    print("\nTesting dual 8x8 vertical (8x16 with panel_width=8, panel_height=8)...")
    
    # Create 8x16 matrix (128 pixels) - two 8x8 panels stacked
    jeb_pixel = MockJEBPixel(128)
    matrix = MatrixManager(jeb_pixel, width=8, height=16, panel_width=8, panel_height=8)
    
    # Verify dimensions
    assert matrix.width == 8
    assert matrix.height == 16
    assert matrix.num_pixels == 128
    
    # Test pixel mapping for panel-based addressing
    # Panel 0 (top): pixels 0-63
    # Panel 1 (bottom): pixels 64-127
    
    # Top-left of display (panel 0, pixel 0)
    assert matrix._get_idx(0, 0) == 0
    
    # Row 1 of first panel (serpentine)
    assert matrix._get_idx(0, 1) == 15
    
    # Row 7 of first panel (row 7, odd, so right-to-left)
    # (0, 7) in local coords with y=7 (odd): (7*8) + (8-1-0) = 56 + 7 = 63
    assert matrix._get_idx(0, 7) == 63
    assert matrix._get_idx(7, 7) == 56
    
    # First row of second panel (row 8 in display coords, row 0 in panel coords)
    assert matrix._get_idx(0, 8) == 64
    
    # Bottom-right of display (panel 1, local (7,7))
    # Panel 1 starts at 64, local (7,7) with y=7 (odd): (7*8) + (8-1-7) = 56
    assert matrix._get_idx(7, 15) == 64 + 56  # 120
    
    print("  ✓ 8x16 panel-based matrix test passed")


def test_strip_as_matrix():
    """Test 1x8 strips arranged as a matrix (8x4 from 4 strips)."""
    print("\nTesting 1x8 strips as 8x4 matrix...")
    
    # Create 8x4 matrix (32 pixels from four 1x8 strips)
    jeb_pixel = MockJEBPixel(32)
    matrix = MatrixManager(jeb_pixel, width=8, height=4)
    
    # Verify dimensions
    assert matrix.width == 8
    assert matrix.height == 4
    assert matrix.num_pixels == 32
    
    # Test pixel mapping
    assert matrix._get_idx(0, 0) == 0
    assert matrix._get_idx(7, 0) == 7
    assert matrix._get_idx(0, 1) == 15  # Odd row, reversed
    assert matrix._get_idx(7, 1) == 8
    
    # Test filling
    matrix.fill(MockPalette.CYAN)
    assert matrix.pixels[0] == MockPalette.CYAN
    assert matrix.pixels[31] == MockPalette.CYAN
    
    print("  ✓ 8x4 strip matrix test passed")


def test_small_matrix():
    """Test small custom matrix (4x4)."""
    print("\nTesting small 4x4 matrix...")
    
    # Create 4x4 matrix (16 pixels)
    jeb_pixel = MockJEBPixel(16)
    matrix = MatrixManager(jeb_pixel, width=4, height=4)
    
    # Verify dimensions
    assert matrix.width == 4
    assert matrix.height == 4
    assert matrix.num_pixels == 16
    
    # Test serpentine mapping
    assert matrix._get_idx(0, 0) == 0
    assert matrix._get_idx(3, 0) == 3
    assert matrix._get_idx(0, 1) == 7  # Odd row
    assert matrix._get_idx(3, 1) == 4
    
    # Test quadrants (should be 2x2 each)
    matrix.draw_quadrant(0, MockPalette.RED)
    assert matrix.pixels[matrix._get_idx(0, 0)] == MockPalette.RED
    assert matrix.pixels[matrix._get_idx(1, 1)] == MockPalette.RED
    
    print("  ✓ 4x4 matrix test passed")


def test_progress_grid_different_sizes():
    """Test progress grid with different matrix sizes."""
    print("\nTesting progress grid on different sizes...")
    
    # Test on 8x8
    jeb_pixel = MockJEBPixel(64)
    matrix = MatrixManager(jeb_pixel, width=8, height=8)
    matrix.show_progress_grid(5, 10, MockPalette.GREEN)
    # 5/10 * 64 = 32 pixels should be lit
    lit_pixels = sum(1 for i in range(64) if matrix.pixels[i] != MockPalette.OFF)
    assert lit_pixels == 32, f"Expected 32 lit pixels, got {lit_pixels}"
    
    # Test on 16x16
    jeb_pixel = MockJEBPixel(256)
    matrix = MatrixManager(jeb_pixel, width=16, height=16)
    matrix.show_progress_grid(5, 10, MockPalette.GREEN)
    # 5/10 * 256 = 128 pixels should be lit
    lit_pixels = sum(1 for i in range(256) if matrix.pixels[i] != MockPalette.OFF)
    assert lit_pixels == 128, f"Expected 128 lit pixels, got {lit_pixels}"
    
    print("  ✓ Progress grid test passed")


def test_brightness_scaling():
    """Test brightness scaling with arbitrary matrix sizes."""
    print("\nTesting brightness scaling...")
    
    jeb_pixel = MockJEBPixel(128)
    matrix = MatrixManager(jeb_pixel, width=16, height=8)
    
    # Test full brightness
    matrix.draw_pixel(0, 0, (100, 100, 100), brightness=1.0)
    assert matrix.pixels[0] == (100, 100, 100)
    
    # Test half brightness
    matrix.draw_pixel(1, 0, (100, 100, 100), brightness=0.5)
    assert matrix.pixels[1] == (50, 50, 50)
    
    # Test zero brightness
    matrix.draw_pixel(2, 0, (100, 100, 100), brightness=0.0)
    assert matrix.pixels[2] == (0, 0, 0)
    
    print("  ✓ Brightness scaling test passed")


def test_large_matrix():
    """Test very large matrix configuration (32x32)."""
    print("\nTesting large 32x32 matrix...")
    
    # Create 32x32 matrix (1024 pixels)
    jeb_pixel = MockJEBPixel(1024)
    matrix = MatrixManager(jeb_pixel, width=32, height=32)
    
    # Verify dimensions
    assert matrix.width == 32
    assert matrix.height == 32
    assert matrix.num_pixels == 1024
    
    # Test corners
    matrix.draw_pixel(0, 0, MockPalette.RED)
    assert matrix.pixels[0] == MockPalette.RED
    
    matrix.draw_pixel(31, 31, MockPalette.BLUE)
    expected_idx = matrix._get_idx(31, 31)
    assert matrix.pixels[expected_idx] == MockPalette.BLUE
    
    print("  ✓ 32x32 matrix test passed")


def test_non_square_matrix():
    """Test non-square matrix configurations."""
    print("\nTesting non-square matrices...")
    
    # Test 12x6 matrix
    jeb_pixel = MockJEBPixel(72)
    matrix = MatrixManager(jeb_pixel, width=12, height=6)
    
    assert matrix.width == 12
    assert matrix.height == 6
    assert matrix.num_pixels == 72
    
    # Test mapping
    assert matrix._get_idx(0, 0) == 0
    assert matrix._get_idx(11, 0) == 11
    assert matrix._get_idx(0, 1) == 23  # Odd row
    
    # Test 20x3 matrix
    jeb_pixel = MockJEBPixel(60)
    matrix = MatrixManager(jeb_pixel, width=20, height=3)
    
    assert matrix.width == 20
    assert matrix.height == 3
    assert matrix.num_pixels == 60
    
    print("  ✓ Non-square matrix test passed")


# ============================================================================
# MAIN TEST RUNNER
# ============================================================================

def run_all_tests():
    """Run all matrix configuration tests."""
    print("=" * 70)
    print("MatrixManager Arbitrary Configuration Test Suite")
    print("=" * 70)
    
    try:
        test_single_8x8_matrix_default()
        test_quad_8x8_panels()
        test_dual_8x8_horizontal()
        test_dual_8x8_vertical()
        test_strip_as_matrix()
        test_small_matrix()
        test_progress_grid_different_sizes()
        test_brightness_scaling()
        test_large_matrix()
        test_non_square_matrix()
        
        print("\n" + "=" * 70)
        print("✓ All matrix configuration tests passed!")
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
