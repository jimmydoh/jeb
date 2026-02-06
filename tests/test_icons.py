#!/usr/bin/env python3
"""Unit tests for Icons library."""

import sys
import os

# Add src/utilities to path for direct module import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'utilities'))

# Import Icons module directly
import icons
Icons = icons.Icons


def test_icon_dimensions():
    """Test that all icons are 8x8 (64 pixels)."""
    print("Testing icon dimensions...")
    
    # Test individual icons
    icons_to_test = ['DEFAULT', 'JEBRIS', 'SIMON', 'SAFE', 'IND', 
                     'SUCCESS', 'FAILURE']
    
    for icon_name in icons_to_test:
        icon_data = getattr(Icons, icon_name)
        assert len(icon_data) == 64, \
            f"Icon {icon_name} should have 64 pixels (8x8), got {len(icon_data)}"
    
    print("✓ Icon dimensions test passed")


def test_number_icons():
    """Test that all number icons (0-9) are present and valid."""
    print("\nTesting number icons...")
    
    number_names = ['ZERO', 'ONE', 'TWO', 'THREE', 'FOUR', 
                    'FIVE', 'SIX', 'SEVEN', 'EIGHT', 'NINE']
    
    for num_name in number_names:
        icon_data = getattr(Icons, num_name)
        assert len(icon_data) == 64, \
            f"Number icon {num_name} should have 64 pixels, got {len(icon_data)}"
        # Each pixel should be a valid color index (0-13)
        assert all(0 <= px <= 13 for px in icon_data), \
            f"Icon {num_name} has invalid color indices"
    
    print("✓ Number icons test passed")


def test_icon_library():
    """Test that icon library contains expected entries."""
    print("\nTesting icon library...")
    
    expected_icons = {
        "DEFAULT": Icons.DEFAULT,
        "SIMON": Icons.SIMON,
        "SAFE": Icons.SAFE,
        "IND": Icons.IND,
        "SUCCESS": Icons.SUCCESS,
        "FAILURE": Icons.FAILURE,
        "0": Icons.ZERO,
        "1": Icons.ONE,
        "2": Icons.TWO,
        "3": Icons.THREE,
        "4": Icons.FOUR,
        "5": Icons.FIVE,
        "6": Icons.SIX,
        "7": Icons.SEVEN,
        "8": Icons.EIGHT,
        "9": Icons.NINE
    }
    
    # Verify all expected icons are in the library
    for key, value in expected_icons.items():
        assert key in Icons.ICON_LIBRARY, f"Icon '{key}' not found in ICON_LIBRARY"
        assert Icons.ICON_LIBRARY[key] == value, \
            f"Icon '{key}' in library doesn't match class constant"
    
    print("✓ Icon library test passed")


def test_icon_color_indices():
    """Test that all icons use valid color indices (0-13)."""
    print("\nTesting icon color indices...")
    
    # Test all icons in the library
    for icon_name, icon_data in Icons.ICON_LIBRARY.items():
        for i, pixel in enumerate(icon_data):
            assert 0 <= pixel <= 13, \
                f"Icon '{icon_name}' has invalid color index {pixel} at position {i}"
    
    print("✓ Icon color indices test passed")


def test_specific_icon_patterns():
    """Test specific patterns in some icons."""
    print("\nTesting specific icon patterns...")
    
    # Test DEFAULT icon has expected colors in corners
    default = Icons.DEFAULT
    assert default[0] == 2, "DEFAULT icon should have blue in top-left corner"
    assert default[7] == 2, "DEFAULT icon should have blue in top-right corner"
    
    # Test SUCCESS icon has green pixels (color 4)
    success = Icons.SUCCESS
    assert 4 in success, "SUCCESS icon should contain green pixels (color 4)"
    
    # Test FAILURE icon has red pixels (color 1) and orange (color 9)
    failure = Icons.FAILURE
    assert 1 in failure, "FAILURE icon should contain red pixels (color 1)"
    assert 9 in failure, "FAILURE icon should contain orange pixels (color 9)"
    
    # Test JEBRIS has magenta (12) and cyan (11)
    jebris = Icons.JEBRIS
    assert 12 in jebris, "JEBRIS icon should contain magenta pixels (color 12)"
    assert 11 in jebris, "JEBRIS icon should contain cyan pixels (color 11)"
    
    print("✓ Specific icon patterns test passed")


def test_icon_not_all_zeros():
    """Test that icons are not all zeros (blank)."""
    print("\nTesting icons are not blank...")
    
    for icon_name, icon_data in Icons.ICON_LIBRARY.items():
        non_zero_pixels = sum(1 for px in icon_data if px != 0)
        assert non_zero_pixels > 0, \
            f"Icon '{icon_name}' is completely blank (all zeros)"
        # Most icons should have at least a few colored pixels
        if icon_name != "DEFAULT":  # DEFAULT might be mostly empty
            assert non_zero_pixels >= 4, \
                f"Icon '{icon_name}' has too few colored pixels ({non_zero_pixels})"
    
    print("✓ Icons not blank test passed")


def test_number_icon_lookup():
    """Test that number icons can be accessed by string keys."""
    print("\nTesting number icon lookup by string...")
    
    for i in range(10):
        key = str(i)
        assert key in Icons.ICON_LIBRARY, f"Number '{key}' not accessible in library"
        icon_data = Icons.ICON_LIBRARY[key]
        assert len(icon_data) == 64, f"Number icon '{key}' has wrong size"
    
    print("✓ Number icon lookup test passed")


def run_all_tests():
    """Run all icon tests."""
    print("=" * 60)
    print("Icons Library Test Suite")
    print("=" * 60)
    
    try:
        test_icon_dimensions()
        test_number_icons()
        test_icon_library()
        test_icon_color_indices()
        test_specific_icon_patterns()
        test_icon_not_all_zeros()
        test_number_icon_lookup()
        
        print("\n" + "=" * 60)
        print("✓ All icon tests passed!")
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
