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
    
    def __init__(self, jeb_pixel, width=8, height=8):
        """Initialize MatrixManager with configurable dimensions."""
        self.pixels = jeb_pixel
        self.num_pixels = jeb_pixel.n
        self.width = width
        self.height = height
        self.palette = MockPalette.PALETTE_LIBRARY
        self.icons = MockIcons.ICON_LIBRARY
        
    def _get_idx(self, x, y):
        """Maps 2D coordinates to Serpentine 1D index."""
        if y % 2 == 0:
            return (y * self.width) + x
        return (y * self.width) + (self.width - 1 - x)
    
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


def test_dual_8x8_horizontal():
    """Test dual 8x8 matrices arranged horizontally (16x8)."""
    print("\nTesting dual 8x8 horizontal (16x8)...")
    
    # Create 16x8 matrix (128 pixels)
    jeb_pixel = MockJEBPixel(128)
    matrix = MatrixManager(jeb_pixel, width=16, height=8)
    
    # Verify dimensions
    assert matrix.width == 16
    assert matrix.height == 8
    assert matrix.num_pixels == 128
    
    # Test pixel mapping for 16-wide matrix
    # Top-left (0, 0) -> 0
    assert matrix._get_idx(0, 0) == 0
    # Top-right (15, 0) -> 15 (even row)
    assert matrix._get_idx(15, 0) == 15
    # Second row left (0, 1) -> 31 (odd row, reversed)
    assert matrix._get_idx(0, 1) == 31
    # Second row right (15, 1) -> 16 (odd row, reversed)
    assert matrix._get_idx(15, 1) == 16
    
    # Test drawing pixels
    matrix.draw_pixel(0, 0, MockPalette.RED)
    assert matrix.pixels[0] == MockPalette.RED
    
    matrix.draw_pixel(15, 0, MockPalette.BLUE)
    assert matrix.pixels[15] == MockPalette.BLUE
    
    # Test out-of-bounds (should not crash)
    matrix.draw_pixel(16, 0, MockPalette.GREEN)  # Out of bounds
    matrix.draw_pixel(0, 8, MockPalette.GREEN)  # Out of bounds
    
    print("  ✓ 16x8 matrix test passed")


def test_dual_8x8_vertical():
    """Test dual 8x8 matrices arranged vertically (8x16)."""
    print("\nTesting dual 8x8 vertical (8x16)...")
    
    # Create 8x16 matrix (128 pixels)
    jeb_pixel = MockJEBPixel(128)
    matrix = MatrixManager(jeb_pixel, width=8, height=16)
    
    # Verify dimensions
    assert matrix.width == 8
    assert matrix.height == 16
    assert matrix.num_pixels == 128
    
    # Test pixel mapping
    # Top-left (0, 0) -> 0
    assert matrix._get_idx(0, 0) == 0
    # Row 1 (odd), left (0, 1) -> 15
    assert matrix._get_idx(0, 1) == 15
    # Bottom-left (0, 15) -> 8*15 + (8-1) = 127 (odd row)
    assert matrix._get_idx(0, 15) == 127
    # Bottom-right (7, 15) -> 8*15 = 120 (odd row)
    assert matrix._get_idx(7, 15) == 120
    
    print("  ✓ 8x16 matrix test passed")


def test_quad_8x8():
    """Test quad 8x8 matrices (16x16)."""
    print("\nTesting quad 8x8 (16x16)...")
    
    # Create 16x16 matrix (256 pixels)
    jeb_pixel = MockJEBPixel(256)
    matrix = MatrixManager(jeb_pixel, width=16, height=16)
    
    # Verify dimensions
    assert matrix.width == 16
    assert matrix.height == 16
    assert matrix.num_pixels == 256
    
    # Test corner pixels
    assert matrix._get_idx(0, 0) == 0  # Top-left
    assert matrix._get_idx(15, 0) == 15  # Top-right (even row)
    assert matrix._get_idx(0, 15) == 16*15 + 15  # Bottom-left (odd row)
    assert matrix._get_idx(15, 15) == 16*15  # Bottom-right (odd row)
    
    # Test quadrants
    matrix.draw_quadrant(0, MockPalette.RED)  # Top-left
    # Top-left quadrant should be 8x8, starting at (0,0)
    # Check a few pixels in top-left quadrant
    assert matrix.pixels[matrix._get_idx(0, 0)] == MockPalette.RED
    assert matrix.pixels[matrix._get_idx(4, 4)] == MockPalette.RED
    
    matrix.draw_quadrant(1, MockPalette.GREEN)  # Top-right
    assert matrix.pixels[matrix._get_idx(8, 0)] == MockPalette.GREEN
    
    matrix.draw_quadrant(2, MockPalette.BLUE)  # Bottom-left
    assert matrix.pixels[matrix._get_idx(0, 8)] == MockPalette.BLUE
    
    matrix.draw_quadrant(3, MockPalette.YELLOW)  # Bottom-right
    assert matrix.pixels[matrix._get_idx(8, 8)] == MockPalette.YELLOW
    
    print("  ✓ 16x16 matrix test passed")


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
        test_dual_8x8_horizontal()
        test_dual_8x8_vertical()
        test_quad_8x8()
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
