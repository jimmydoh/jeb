#!/usr/bin/env python3
"""Unit tests for Payload Parser utilities."""

import sys
import os

# Add src/utilities to path for direct module import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'utilities'))

# Import payload_parser module directly
import payload_parser


def test_parse_values_string_integers():
    """Test parse_values with comma-separated integer strings."""
    print("Testing parse_values with integer strings...")
    
    result = payload_parser.parse_values("100,200,50")
    expected = [100, 200, 50]
    assert result == expected, f"Expected {expected}, got {result}"
    
    # Test with spaces
    result = payload_parser.parse_values("10, 20, 30")
    expected = [10, 20, 30]
    assert result == expected, f"Expected {expected}, got {result}"
    
    # Single value
    result = payload_parser.parse_values("42")
    expected = [42]
    assert result == expected, f"Expected {expected}, got {result}"
    
    print("✓ parse_values string integers test passed")


def test_parse_values_string_floats():
    """Test parse_values with comma-separated float strings."""
    print("\nTesting parse_values with float strings...")
    
    result = payload_parser.parse_values("1.5,2.5,3.5")
    expected = [1.5, 2.5, 3.5]
    assert result == expected, f"Expected {expected}, got {result}"
    
    # Mixed integers and floats
    result = payload_parser.parse_values("100,200.5,50")
    expected = [100, 200.5, 50]
    assert result == expected, f"Expected {expected}, got {result}"
    
    print("✓ parse_values float strings test passed")


def test_parse_values_string_mixed():
    """Test parse_values with mixed numeric and string values."""
    print("\nTesting parse_values with mixed strings...")
    
    result = payload_parser.parse_values("100,hello,50")
    expected = [100, "hello", 50]
    assert result == expected, f"Expected {expected}, got {result}"
    
    # String with spaces is kept as-is
    result = payload_parser.parse_values("test string")
    expected = ["test string"]
    assert result == expected, f"Expected {expected}, got {result}"
    
    print("✓ parse_values mixed strings test passed")


def test_parse_values_bytes():
    """Test parse_values with binary byte payloads."""
    print("\nTesting parse_values with bytes...")
    
    result = payload_parser.parse_values(b'\x64\xc8\x32')
    expected = [100, 200, 50]
    assert result == expected, f"Expected {expected}, got {result}"
    
    # Single byte
    result = payload_parser.parse_values(b'\xff')
    expected = [255]
    assert result == expected, f"Expected {expected}, got {result}"
    
    # Empty bytes
    result = payload_parser.parse_values(b'')
    expected = []
    assert result == expected, f"Expected {expected}, got {result}"
    
    print("✓ parse_values bytes test passed")


def test_parse_values_tuple():
    """Test parse_values with tuple payloads (optimized transport)."""
    print("\nTesting parse_values with tuples...")
    
    result = payload_parser.parse_values((100, 200, 50))
    expected = [100, 200, 50]
    assert result == expected, f"Expected {expected}, got {result}"
    
    # Mixed types in tuple
    result = payload_parser.parse_values((100, 200.5, 50))
    expected = [100, 200.5, 50]
    assert result == expected, f"Expected {expected}, got {result}"
    
    print("✓ parse_values tuple test passed")


def test_parse_values_list():
    """Test parse_values with list payloads."""
    print("\nTesting parse_values with lists...")
    
    result = payload_parser.parse_values([100, 200, 50])
    expected = [100, 200, 50]
    assert result == expected, f"Expected {expected}, got {result}"
    
    print("✓ parse_values list test passed")


def test_parse_values_empty():
    """Test parse_values with empty/None payloads."""
    print("\nTesting parse_values with empty payloads...")
    
    result = payload_parser.parse_values("")
    expected = []
    assert result == expected, f"Expected {expected}, got {result}"
    
    result = payload_parser.parse_values(None)
    expected = []
    assert result == expected, f"Expected {expected}, got {result}"
    
    print("✓ parse_values empty test passed")


def test_unpack_bytes_single():
    """Test unpack_bytes with single byte format."""
    print("\nTesting unpack_bytes single byte...")
    
    result = payload_parser.unpack_bytes(b'\x64', 'B')
    expected = (100,)
    assert result == expected, f"Expected {expected}, got {result}"
    
    # Max byte value
    result = payload_parser.unpack_bytes(b'\xff', 'B')
    expected = (255,)
    assert result == expected, f"Expected {expected}, got {result}"
    
    print("✓ unpack_bytes single byte test passed")


def test_unpack_bytes_multiple():
    """Test unpack_bytes with multiple bytes."""
    print("\nTesting unpack_bytes multiple bytes...")
    
    result = payload_parser.unpack_bytes(b'\x64\xc8', 'BB')
    expected = (100, 200)
    assert result == expected, f"Expected {expected}, got {result}"
    
    # Three bytes
    result = payload_parser.unpack_bytes(b'\x01\x02\x03', 'BBB')
    expected = (1, 2, 3)
    assert result == expected, f"Expected {expected}, got {result}"
    
    print("✓ unpack_bytes multiple bytes test passed")


def test_unpack_bytes_little_endian():
    """Test unpack_bytes with little-endian shorts."""
    print("\nTesting unpack_bytes little-endian shorts...")
    
    # 256 = 0x0100 in little-endian
    result = payload_parser.unpack_bytes(b'\x00\x01', '<H')
    expected = (256,)
    assert result == expected, f"Expected {expected}, got {result}"
    
    # Two shorts: 256 and 512
    result = payload_parser.unpack_bytes(b'\x00\x01\x00\x02', '<HH')
    expected = (256, 512)
    assert result == expected, f"Expected {expected}, got {result}"
    
    print("✓ unpack_bytes little-endian test passed")


def test_unpack_bytes_empty():
    """Test unpack_bytes with empty payload."""
    print("\nTesting unpack_bytes empty payload...")
    
    result = payload_parser.unpack_bytes(b'', 'B')
    expected = ()
    assert result == expected, f"Expected {expected}, got {result}"
    
    result = payload_parser.unpack_bytes(None)
    expected = ()
    assert result == expected, f"Expected {expected}, got {result}"
    
    print("✓ unpack_bytes empty test passed")


def test_get_int_valid():
    """Test get_int with valid indices."""
    print("\nTesting get_int with valid indices...")
    
    values = [100, 200, 300]
    
    result = payload_parser.get_int(values, 0)
    assert result == 100, f"Expected 100, got {result}"
    
    result = payload_parser.get_int(values, 2)
    assert result == 300, f"Expected 300, got {result}"
    
    # Float values should be converted to int
    float_values = [1.5, 2.7, 3.9]
    result = payload_parser.get_int(float_values, 1)
    assert result == 2, f"Expected 2, got {result}"
    
    print("✓ get_int valid indices test passed")


def test_get_int_out_of_bounds():
    """Test get_int with out-of-bounds indices."""
    print("\nTesting get_int out of bounds...")
    
    values = [100, 200]
    
    result = payload_parser.get_int(values, 5)
    assert result == 0, f"Expected default 0, got {result}"
    
    result = payload_parser.get_int(values, 5, default=999)
    assert result == 999, f"Expected custom default 999, got {result}"
    
    print("✓ get_int out of bounds test passed")


def test_get_int_non_numeric():
    """Test get_int with non-numeric values."""
    print("\nTesting get_int with non-numeric values...")
    
    values = ["hello", 200]
    
    result = payload_parser.get_int(values, 0)
    assert result == 0, f"Expected default 0 for non-numeric, got {result}"
    
    result = payload_parser.get_int(values, 1)
    assert result == 200, f"Expected 200, got {result}"
    
    print("✓ get_int non-numeric test passed")


def test_get_float_valid():
    """Test get_float with valid indices."""
    print("\nTesting get_float with valid indices...")
    
    values = [1.5, 2.7, 3.9]
    
    result = payload_parser.get_float(values, 0)
    assert result == 1.5, f"Expected 1.5, got {result}"
    
    result = payload_parser.get_float(values, 2)
    assert result == 3.9, f"Expected 3.9, got {result}"
    
    # Int values should be converted to float
    int_values = [100, 200, 300]
    result = payload_parser.get_float(int_values, 1)
    assert result == 200.0, f"Expected 200.0, got {result}"
    
    print("✓ get_float valid indices test passed")


def test_get_float_out_of_bounds():
    """Test get_float with out-of-bounds indices."""
    print("\nTesting get_float out of bounds...")
    
    values = [1.5, 2.5]
    
    result = payload_parser.get_float(values, 5)
    assert result == 0.0, f"Expected default 0.0, got {result}"
    
    result = payload_parser.get_float(values, 5, default=99.9)
    assert result == 99.9, f"Expected custom default 99.9, got {result}"
    
    print("✓ get_float out of bounds test passed")


def test_get_str_valid():
    """Test get_str with valid indices."""
    print("\nTesting get_str with valid indices...")
    
    values = ["hello", "world", "test"]
    
    result = payload_parser.get_str(values, 0)
    assert result == "hello", f"Expected 'hello', got {result}"
    
    result = payload_parser.get_str(values, 2)
    assert result == "test", f"Expected 'test', got {result}"
    
    # Numeric values should be converted to string
    int_values = [100, 200, 300]
    result = payload_parser.get_str(int_values, 1)
    assert result == "200", f"Expected '200', got {result}"
    
    print("✓ get_str valid indices test passed")


def test_get_str_out_of_bounds():
    """Test get_str with out-of-bounds indices."""
    print("\nTesting get_str out of bounds...")
    
    values = ["hello", "world"]
    
    result = payload_parser.get_str(values, 5)
    assert result == "", f"Expected empty string default, got {result}"
    
    result = payload_parser.get_str(values, 5, default="N/A")
    assert result == "N/A", f"Expected custom default 'N/A', got {result}"
    
    print("✓ get_str out of bounds test passed")


def run_all_tests():
    """Run all payload parser tests."""
    print("=" * 60)
    print("Payload Parser Test Suite")
    print("=" * 60)
    
    try:
        test_parse_values_string_integers()
        test_parse_values_string_floats()
        test_parse_values_string_mixed()
        test_parse_values_bytes()
        test_parse_values_tuple()
        test_parse_values_list()
        test_parse_values_empty()
        test_unpack_bytes_single()
        test_unpack_bytes_multiple()
        test_unpack_bytes_little_endian()
        test_unpack_bytes_empty()
        test_get_int_valid()
        test_get_int_out_of_bounds()
        test_get_int_non_numeric()
        test_get_float_valid()
        test_get_float_out_of_bounds()
        test_get_str_valid()
        test_get_str_out_of_bounds()
        
        print("\n" + "=" * 60)
        print("✓ All payload parser tests passed!")
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
