#!/usr/bin/env python3
"""Unit tests for JEBPixel wrapper class."""

import sys
import os

# Add src/utilities to path for direct module import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'utilities'))

# Import JEBPixel module
import jeb_pixel
JEBPixel = jeb_pixel.JEBPixel


class MockNeoPixel:
    """Mock NeoPixel strip for testing."""
    
    def __init__(self, size):
        self.pixels = [(0, 0, 0)] * size
        self.show_called = False
    
    def __setitem__(self, index, value):
        if 0 <= index < len(self.pixels):
            self.pixels[index] = value
    
    def __getitem__(self, index):
        if 0 <= index < len(self.pixels):
            return self.pixels[index]
        return (0, 0, 0)
    
    def show(self):
        self.show_called = True


def test_jeb_pixel_initialization():
    """Test JEBPixel initialization."""
    print("Testing JEBPixel initialization...")
    
    parent = MockNeoPixel(68)
    jeb = JEBPixel(parent, start_idx=64, num_pixels=4)
    
    assert jeb.parent == parent, "Parent should be stored"
    assert jeb.start == 64, "Start index should be 64"
    assert jeb.n == 4, "Number of pixels should be 4"
    
    print("✓ JEBPixel initialization test passed")


def test_jeb_pixel_setitem():
    """Test setting individual pixels."""
    print("\nTesting JEBPixel __setitem__...")
    
    parent = MockNeoPixel(68)
    jeb = JEBPixel(parent, start_idx=10, num_pixels=4)
    
    # Set pixel at index 0 (should map to parent[10])
    jeb[0] = (255, 0, 0)
    assert parent[10] == (255, 0, 0), "Pixel 0 should map to parent[10]"
    
    # Set pixel at index 2 (should map to parent[12])
    jeb[2] = (0, 255, 0)
    assert parent[12] == (0, 255, 0), "Pixel 2 should map to parent[12]"
    
    # Other pixels should be unchanged
    assert parent[9] == (0, 0, 0), "Pixels before segment should be unchanged"
    assert parent[14] == (0, 0, 0), "Pixels after segment should be unchanged"
    
    print("✓ JEBPixel __setitem__ test passed")


def test_jeb_pixel_getitem():
    """Test getting individual pixels."""
    print("\nTesting JEBPixel __getitem__...")
    
    parent = MockNeoPixel(68)
    jeb = JEBPixel(parent, start_idx=20, num_pixels=3)
    
    # Set some parent pixels
    parent[20] = (100, 0, 0)
    parent[21] = (0, 100, 0)
    parent[22] = (0, 0, 100)
    
    # Get through JEBPixel wrapper
    assert jeb[0] == (100, 0, 0), "Should get parent[20]"
    assert jeb[1] == (0, 100, 0), "Should get parent[21]"
    assert jeb[2] == (0, 0, 100), "Should get parent[22]"
    
    print("✓ JEBPixel __getitem__ test passed")


def test_jeb_pixel_bounds_checking_set():
    """Test bounds checking when setting pixels."""
    print("\nTesting JEBPixel bounds checking (set)...")
    
    parent = MockNeoPixel(68)
    jeb = JEBPixel(parent, start_idx=10, num_pixels=4)
    
    # Set valid indices
    jeb[0] = (255, 0, 0)
    jeb[3] = (0, 255, 0)
    
    # Try to set out of bounds (should be ignored)
    jeb[-1] = (100, 100, 100)  # Negative index
    jeb[4] = (100, 100, 100)   # Beyond segment
    jeb[10] = (100, 100, 100)  # Way beyond
    
    # Check that only valid indices were set
    assert parent[10] == (255, 0, 0), "Index 0 should be set"
    assert parent[13] == (0, 255, 0), "Index 3 should be set"
    assert parent[9] == (0, 0, 0), "Before segment should be unchanged"
    assert parent[14] == (0, 0, 0), "After segment should be unchanged"
    
    print("✓ JEBPixel bounds checking (set) test passed")


def test_jeb_pixel_bounds_checking_get():
    """Test bounds checking when getting pixels."""
    print("\nTesting JEBPixel bounds checking (get)...")
    
    parent = MockNeoPixel(68)
    jeb = JEBPixel(parent, start_idx=10, num_pixels=4)
    
    parent[10] = (255, 0, 0)
    
    # Get valid index
    assert jeb[0] == (255, 0, 0), "Valid index should return correct value"
    
    # Get out of bounds (should return black)
    assert jeb[-1] == (0, 0, 0), "Negative index should return black"
    assert jeb[4] == (0, 0, 0), "Beyond segment should return black"
    assert jeb[10] == (0, 0, 0), "Way beyond should return black"
    
    print("✓ JEBPixel bounds checking (get) test passed")


def test_jeb_pixel_fill():
    """Test filling segment with a color."""
    print("\nTesting JEBPixel fill()...")
    
    parent = MockNeoPixel(68)
    jeb = JEBPixel(parent, start_idx=30, num_pixels=5)
    
    # Fill segment with color
    jeb.fill((200, 100, 50))
    
    # Check that segment is filled
    for i in range(5):
        assert parent[30 + i] == (200, 100, 50), \
            f"Pixel at parent[{30+i}] should be filled"
    
    # Check that pixels outside segment are not affected
    assert parent[29] == (0, 0, 0), "Before segment should be unchanged"
    assert parent[35] == (0, 0, 0), "After segment should be unchanged"
    
    print("✓ JEBPixel fill() test passed")


def test_jeb_pixel_show():
    """Test that show() no longer calls parent's show()."""
    print("\nTesting JEBPixel show()...")
    
    parent = MockNeoPixel(68)
    jeb = JEBPixel(parent, start_idx=0, num_pixels=8)
    
    assert parent.show_called == False, "Show should not be called initially"
    
    # Call show on JEBPixel - should NOT trigger hardware write
    jeb.show()
    
    # The new behavior: show() no longer calls parent.show()
    # Hardware writes are centralized in CoreManager.render_loop()
    assert parent.show_called == False, "Show should NOT be called on parent (hardware writes centralized)"
    
    print("✓ JEBPixel show() test passed")


def test_jeb_pixel_multiple_segments():
    """Test multiple JEBPixel segments on same parent."""
    print("\nTesting multiple JEBPixel segments...")
    
    parent = MockNeoPixel(68)
    
    # Create two non-overlapping segments
    segment1 = JEBPixel(parent, start_idx=0, num_pixels=8)
    segment2 = JEBPixel(parent, start_idx=64, num_pixels=4)
    
    # Set colors in each segment
    segment1.fill((255, 0, 0))
    segment2.fill((0, 0, 255))
    
    # Check segment1
    for i in range(8):
        assert parent[i] == (255, 0, 0), f"Segment1 pixel {i} should be red"
    
    # Check segment2
    for i in range(4):
        assert parent[64 + i] == (0, 0, 255), f"Segment2 pixel {i} should be blue"
    
    # Check pixels between segments are unchanged
    assert parent[32] == (0, 0, 0), "Pixels between segments should be unchanged"
    
    print("✓ Multiple JEBPixel segments test passed")


def test_jeb_pixel_use_case_matrix_buttons():
    """Test realistic use case: 8x8 matrix + 4 buttons."""
    print("\nTesting realistic use case (matrix + buttons)...")
    
    # Total strip: 64 matrix pixels + 4 button pixels = 68
    parent = MockNeoPixel(68)
    
    # Create segments
    matrix = JEBPixel(parent, start_idx=0, num_pixels=64)
    buttons = JEBPixel(parent, start_idx=64, num_pixels=4)
    
    # Set matrix pattern
    matrix[0] = (255, 0, 0)  # Top-left red
    matrix[63] = (0, 255, 0)  # Bottom-right green
    
    # Set button colors
    buttons[0] = (100, 100, 0)  # Button 1 yellow
    buttons[3] = (0, 100, 100)  # Button 4 cyan
    
    # Verify mapping
    assert parent[0] == (255, 0, 0), "Matrix top-left correct"
    assert parent[63] == (0, 255, 0), "Matrix bottom-right correct"
    assert parent[64] == (100, 100, 0), "Button 1 correct"
    assert parent[67] == (0, 100, 100), "Button 4 correct"
    
    # Show all - new behavior: does not trigger hardware write
    # Hardware writes are now centralized in CoreManager.render_loop()
    matrix.show()  # This updates memory buffer only
    assert parent.show_called == False, "Hardware write is centralized, not called from JEBPixel"
    
    print("✓ Realistic use case test passed")


def run_all_tests():
    """Run all JEBPixel tests."""
    print("=" * 60)
    print("JEBPixel Wrapper Test Suite")
    print("=" * 60)
    
    try:
        test_jeb_pixel_initialization()
        test_jeb_pixel_setitem()
        test_jeb_pixel_getitem()
        test_jeb_pixel_bounds_checking_set()
        test_jeb_pixel_bounds_checking_get()
        test_jeb_pixel_fill()
        test_jeb_pixel_show()
        test_jeb_pixel_multiple_segments()
        test_jeb_pixel_use_case_matrix_buttons()
        
        print("\n" + "=" * 60)
        print("✓ All JEBPixel tests passed!")
        print("=" * 60)
        return True
        
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        return False
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
