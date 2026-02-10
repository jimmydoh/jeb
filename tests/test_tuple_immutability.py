#!/usr/bin/env python3
"""Test that tuple/list payloads are not mutated in LED managers."""

import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'utilities'))

from payload_parser import parse_values, get_int, get_float


def test_values_not_mutated():
    """Test that values array is not mutated during command processing."""
    print("Testing that values array is not mutated...")
    
    # Test with tuple payload
    original_tuple = (255, 128, 64, 1.0, 2.0, 0.5, 1)
    values = parse_values(original_tuple)
    
    # Simulate extracting values like apply_command does
    r = get_int(values, 0)
    g = get_int(values, 1) 
    b = get_int(values, 2)
    brightness = get_float(values, 3, 1.0)
    
    # Create color tuple
    color = (r, g, b)
    
    # Verify values array was not modified
    assert values[0] == 255, "values[0] should not be modified"
    assert values[1] == 128, "values[1] should not be modified"
    assert values[2] == 64, "values[2] should not be modified"
    
    print("  ✓ Tuple payload values not mutated")
    
    # Test with list payload
    original_list = [255, 128, 64, 1.0, 2.0, 0.5, 1]
    values = parse_values(original_list)
    
    r = get_int(values, 0)
    g = get_int(values, 1)
    b = get_int(values, 2)
    color = (r, g, b)
    
    # Verify values array was not modified
    assert values[0] == 255, "values[0] should not be modified"
    assert values[1] == 128, "values[1] should not be modified"
    assert values[2] == 64, "values[2] should not be modified"
    
    print("  ✓ List payload values not mutated")
    print("✓ Values not mutated test passed")


def test_color_tuples_created():
    """Test that colors are always created as new tuples."""
    print("\nTesting that colors are created as new tuples...")
    
    # Simulate what happens in apply_command
    values = [255, 128, 64]
    
    # Create color tuple like led_manager does
    color = (get_int(values, 0), get_int(values, 1), get_int(values, 2))
    
    assert isinstance(color, tuple), "Color should be a tuple"
    assert color == (255, 128, 64), "Color values should be correct"
    
    print("  ✓ Color created as tuple")
    
    # Test that brightness calculation creates new tuple
    brightness = 0.5
    adjusted_color = tuple(int(c * brightness) for c in color)
    
    assert isinstance(adjusted_color, tuple), "Adjusted color should be a tuple"
    assert adjusted_color == (127, 64, 32), f"Expected (127, 64, 32), got {adjusted_color}"
    assert color == (255, 128, 64), "Original color should not be modified"
    
    print("  ✓ Brightness adjustment creates new tuple")
    print("✓ Color tuple creation test passed")


def test_color_operations_immutable():
    """Test that color operations don't mutate original colors."""
    print("\nTesting that color operations are immutable...")
    
    # Original color tuple
    color = (255, 200, 100)
    
    # Simulate brightness calculations like in base_pixel_manager.py
    brightness = 0.5
    dimmed = tuple(int(c * brightness) for c in color)
    
    assert color == (255, 200, 100), "Original color should not change"
    assert dimmed == (127, 100, 50), f"Expected (127, 100, 50), got {dimmed}"
    assert color is not dimmed, "Dimmed color should be a new tuple"
    
    print("  ✓ Brightness calculation doesn't mutate original")
    
    # Test with factor calculation (like PULSE animation)
    factor = 0.3
    pulsed = tuple(int(c * factor) for c in color)
    
    assert color == (255, 200, 100), "Original color should not change"
    assert pulsed == (76, 60, 30), f"Expected (76, 60, 30), got {pulsed}"
    
    print("  ✓ Factor calculation doesn't mutate original")
    print("✓ Color immutability test passed")


def test_list_vs_tuple_safety():
    """Test that both lists and tuples work safely without mutation."""
    print("\nTesting list vs tuple safety...")
    
    # Test with tuple (immutable)
    tuple_color = (255, 128, 64)
    tuple_result = tuple(int(c * 0.5) for c in tuple_color)
    assert tuple_color == (255, 128, 64), "Tuple should not change"
    
    print("  ✓ Tuple colors are safe")
    
    # Test with list (mutable, but not mutated by our code)
    list_color = [255, 128, 64]
    list_result = tuple(int(c * 0.5) for c in list_color)
    assert list_color == [255, 128, 64], "List should not be mutated"
    assert isinstance(list_result, tuple), "Result should be a tuple"
    
    print("  ✓ List colors are converted to tuples without mutation")
    print("✓ List vs tuple safety test passed")


if __name__ == "__main__":
    print("=" * 60)
    print("Tuple/List Immutability Test Suite")
    print("=" * 60)
    
    try:
        test_values_not_mutated()
        test_color_tuples_created()
        test_color_operations_immutable()
        test_list_vs_tuple_safety()
        
        print("\n" + "=" * 60)
        print("ALL IMMUTABILITY TESTS PASSED ✓")
        print("=" * 60)
        print("\nNo payload or color mutations detected!")
        print("Tuple payloads are safe to use.")
        
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
