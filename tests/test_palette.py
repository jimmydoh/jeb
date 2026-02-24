#!/usr/bin/env python3
"""Unit tests for Palette color utilities."""

import sys
import os

# Add src/utilities to path for direct module import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'utilities'))

# Import Palette module directly
import palette
Palette = palette.Palette
Color = palette.Color


def test_color_class_is_tuple():
    """Test that Color extends tuple and behaves as an RGB tuple."""
    print("Testing Color class tuple behavior...")

    c = Color(11, "RED", 255, 0, 0)
    assert isinstance(c, tuple), "Color should be an instance of tuple"
    assert len(c) == 3, "Color tuple should have exactly 3 elements (R, G, B)"
    assert c == (255, 0, 0), f"Expected (255,0,0), got {c}"
    assert c[0] == 255, "Red channel should be 255"
    assert c[1] == 0, "Green channel should be 0"
    assert c[2] == 0, "Blue channel should be 0"

    print("✓ Color class tuple behavior test passed")


def test_color_class_index():
    """Test that Color objects have an index attribute."""
    print("\nTesting Color.index attribute...")

    assert Palette.OFF.index == 0, f"OFF.index should be 0, got {Palette.OFF.index}"
    assert Palette.WHITE.index == 4, f"WHITE.index should be 4, got {Palette.WHITE.index}"
    assert Palette.RED.index == 11, f"RED.index should be 11, got {Palette.RED.index}"
    assert Palette.GREEN.index == 41, f"GREEN.index should be 41, got {Palette.GREEN.index}"
    assert Palette.BLUE.index == 61, f"BLUE.index should be 61, got {Palette.BLUE.index}"
    assert Palette.CYAN.index == 51, f"CYAN.index should be 51, got {Palette.CYAN.index}"
    assert Palette.MAGENTA.index == 71, f"MAGENTA.index should be 71, got {Palette.MAGENTA.index}"

    print("✓ Color.index attribute test passed")


def test_color_class_name():
    """Test that Color objects have a name attribute."""
    print("\nTesting Color.name attribute...")

    assert Palette.OFF.name == "OFF", f"OFF.name should be 'OFF', got {Palette.OFF.name}"
    assert Palette.WHITE.name == "WHITE", f"WHITE.name should be 'WHITE', got {Palette.WHITE.name}"
    assert Palette.RED.name == "RED", f"RED.name should be 'RED', got {Palette.RED.name}"
    assert Palette.GREEN.name == "GREEN", f"GREEN.name should be 'GREEN', got {Palette.GREEN.name}"
    assert Palette.BLUE.name == "BLUE", f"BLUE.name should be 'BLUE', got {Palette.BLUE.name}"

    print("✓ Color.name attribute test passed")


def test_color_index_matches_library():
    """Test that each Color's index attribute matches its key in LIBRARY."""
    print("\nTesting Color index consistency with LIBRARY...")

    for idx, color in Palette.LIBRARY.items():
        assert color.index == idx, (
            f"Color '{color.name}' has index {color.index} but is stored at key {idx} in LIBRARY"
        )

    print("✓ Color index consistency test passed")


def test_get_color():
    """Test that Palette.get_color() returns the correct color by index."""
    print("\nTesting Palette.get_color()...")

    assert Palette.get_color(0) == Palette.OFF, "Index 0 should return OFF"
    assert Palette.get_color(4) == Palette.WHITE, "Index 4 should return WHITE"
    assert Palette.get_color(11) == Palette.RED, "Index 11 should return RED"
    assert Palette.get_color(41) == Palette.GREEN, "Index 41 should return GREEN"
    assert Palette.get_color(61) == Palette.BLUE, "Index 61 should return BLUE"

    # Test that get_color returns Color objects with correct attributes
    color = Palette.get_color(51)
    assert color == Palette.CYAN, "Index 51 should return CYAN"
    assert color.index == 51, "Returned color should have index 51"
    assert color.name == "CYAN", "Returned color should have name 'CYAN'"

    # Test unknown index falls back to OFF
    unknown = Palette.get_color(999)
    assert unknown == Palette.OFF, "Unknown index should return OFF"

    print("✓ Palette.get_color() test passed")


def test_basic_colors():
    """Test that basic color constants are defined correctly."""
    print("Testing basic color constants...")

    # Test binary colors
    assert Palette.OFF == (0, 0, 0), f"Expected OFF to be (0,0,0), got {Palette.OFF}"
    assert Palette.WHITE == (255, 255, 255), f"Expected WHITE to be (255,255,255), got {Palette.WHITE}"

    # Test primary colors have non-zero values in appropriate channels
    assert Palette.RED[0] > 0, "RED should have non-zero red channel"
    assert Palette.GREEN[1] > 0, "GREEN should have non-zero green channel"
    assert Palette.BLUE[2] > 0, "BLUE should have non-zero blue channel"

    print("✓ Basic color constants test passed")


def test_palette_library():
    """Test that palette library contains expected colors."""
    print("\nTesting palette library...")

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
        test_color_class_is_tuple()
        test_color_class_index()
        test_color_class_name()
        test_color_index_matches_library()
        test_get_color()
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
