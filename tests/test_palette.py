#!/usr/bin/env python3
"""Unit tests for Palette color utilities."""

import sys
import os

# Add src/utilities to path for direct module import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'utilities'))

# Import Palette module directly
import palette
Palette = palette.Palette


def test_basic_colors():
    """Test that basic color constants are defined correctly."""
    print("Testing basic color constants...")

    # Test binary colors
    assert Palette.OFF == (0, 0, 0), f"Expected OFF to be (0,0,0), got {Palette.OFF}"
    assert Palette.WHITE == (150, 150, 150), f"Expected WHITE to be (150,150,150), got {Palette.WHITE}"

    # Test primary colors have non-zero values in appropriate channels
    assert Palette.RED[0] > 0, "RED should have non-zero red channel"
    assert Palette.GREEN[1] > 0, "GREEN should have non-zero green channel"
    assert Palette.BLUE[2] > 0, "BLUE should have non-zero blue channel"

    print("✓ Basic color constants test passed")


def test_palette_library():
    """Test that palette library contains expected colors."""
    print("\nTesting palette library...")

    # The palette library now uses numeric indices 0-39
    # Test that library contains all expected indices
    expected_indices = list(range(40))  # 0-39

    for index in expected_indices:
        assert index in Palette.LIBRARY, f"Index {index} not found in library"
        assert len(Palette.LIBRARY[index]) == 3, \
            f"Color at index {index} should be RGB tuple with 3 values"

    # Test that specific colors are mapped correctly
    assert Palette.LIBRARY[0] == Palette.OFF, "Index 0 should be OFF"
    assert Palette.LIBRARY[1] == Palette.CHARCOAL, "Index 1 should be CHARCOAL"
    assert Palette.LIBRARY[22] == Palette.GOLD, "Index 22 should be GOLD"
    assert Palette.LIBRARY[51] == Palette.CYAN, "Index 51 should be CYAN"

    print("✓ Palette library test passed")


def test_hsv_to_rgb_grayscale():
    """Test HSV to RGB conversion for grayscale (saturation = 0)."""
    print("\nTesting HSV to RGB grayscale conversion...")

    # When saturation is 0, output should be grayscale
    result = Palette.hsv_to_rgb(0, 0.0, 0.5)
    expected = (127, 127, 127)
    assert result == expected, f"Expected {expected}, got {result}"

    # Pure black
    result = Palette.hsv_to_rgb(0, 0.0, 0.0)
    assert result == (0, 0, 0), f"Expected (0,0,0), got {result}"

    # Pure white
    result = Palette.hsv_to_rgb(0, 0.0, 1.0)
    assert result == (255, 255, 255), f"Expected (255,255,255), got {result}"

    print("✓ HSV to RGB grayscale test passed")


def test_hsv_to_rgb_primary_colors():
    """Test HSV to RGB conversion for primary colors."""
    print("\nTesting HSV to RGB primary colors...")

    # Red (H=0)
    result = Palette.hsv_to_rgb(0, 1.0, 1.0)
    assert result == (255, 0, 0), f"Expected pure red (255,0,0), got {result}"

    # Green (H=120)
    result = Palette.hsv_to_rgb(120, 1.0, 1.0)
    assert result == (0, 255, 0), f"Expected pure green (0,255,0), got {result}"

    # Blue (H=240)
    result = Palette.hsv_to_rgb(240, 1.0, 1.0)
    assert result == (0, 0, 255), f"Expected pure blue (0,0,255), got {result}"

    print("✓ HSV to RGB primary colors test passed")


def test_hsv_to_rgb_hue_ranges():
    """Test HSV to RGB conversion across different hue ranges."""
    print("\nTesting HSV to RGB hue ranges...")

    # Test each hue sector (0-60, 60-120, 120-180, 180-240, 240-300, 300-360)
    test_hues = [30, 90, 150, 210, 270, 330]

    for hue in test_hues:
        result = Palette.hsv_to_rgb(hue, 1.0, 1.0)
        # Result should be a valid RGB tuple
        assert len(result) == 3, f"HSV result should be RGB tuple, got {result}"
        assert all(0 <= c <= 255 for c in result), \
            f"All RGB values should be in range [0,255], got {result}"
        # At least one channel should be at max
        assert max(result) == 255, f"At full saturation and value, max channel should be 255, got {result}"
        # At least one channel should be at min
        assert min(result) == 0, f"At full saturation, min channel should be 0, got {result}"

    print("✓ HSV to RGB hue ranges test passed")


def test_hsv_to_rgb_saturation():
    """Test HSV to RGB conversion with varying saturation."""
    print("\nTesting HSV to RGB saturation variation...")

    # Test red with different saturations
    # Full saturation
    result = Palette.hsv_to_rgb(0, 1.0, 1.0)
    assert result == (255, 0, 0), f"Expected (255,0,0), got {result}"

    # Half saturation
    result = Palette.hsv_to_rgb(0, 0.5, 1.0)
    assert result[0] == 255, "Red channel should be 255"
    assert result[1] == result[2], "Green and blue channels should be equal"
    assert 100 < result[1] < 150, f"Half saturation should give mid-range other channels, got {result}"

    print("✓ HSV to RGB saturation test passed")


def test_hsv_to_rgb_value():
    """Test HSV to RGB conversion with varying value (brightness)."""
    print("\nTesting HSV to RGB value variation...")

    # Full value
    result = Palette.hsv_to_rgb(0, 1.0, 1.0)
    assert result == (255, 0, 0), f"Expected (255,0,0), got {result}"

    # Half value (brightness)
    result = Palette.hsv_to_rgb(0, 1.0, 0.5)
    assert result == (127, 0, 0), f"Expected (127,0,0), got {result}"

    # Quarter value
    result = Palette.hsv_to_rgb(0, 1.0, 0.25)
    assert result == (63, 0, 0), f"Expected (63,0,0), got {result}"

    print("✓ HSV to RGB value test passed")


def run_all_tests():
    """Run all palette tests."""
    print("=" * 60)
    print("Palette Utility Test Suite")
    print("=" * 60)

    try:
        test_basic_colors()
        test_palette_library()
        test_hsv_to_rgb_grayscale()
        test_hsv_to_rgb_primary_colors()
        test_hsv_to_rgb_hue_ranges()
        test_hsv_to_rgb_saturation()
        test_hsv_to_rgb_value()

        print("\n" + "=" * 60)
        print("✓ All palette tests passed!")
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
