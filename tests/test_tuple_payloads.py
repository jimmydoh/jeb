#!/usr/bin/env python3
"""Test that tuple payloads work correctly with parse_values and get_float."""

import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Direct import to avoid CircuitPython dependencies
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'utilities'))
from payload_parser import parse_values, get_float


def test_parse_values_with_tuple():
    """Test that parse_values handles tuple inputs."""
    print("Testing parse_values with tuple input...")
    
    # Test with integer tuple
    result = parse_values((100, 200, 50))
    assert result == [100, 200, 50], f"Expected [100, 200, 50], got {result}"
    print("  ✓ Integer tuple parsed correctly")
    
    # Test with float tuple
    result = parse_values((19.5, 18.2, 5.0))
    assert result == [19.5, 18.2, 5.0], f"Expected [19.5, 18.2, 5.0], got {result}"
    print("  ✓ Float tuple parsed correctly")
    
    # Test with mixed tuple
    result = parse_values((100, 200.5, 50))
    assert result == [100, 200.5, 50], f"Expected [100, 200.5, 50], got {result}"
    print("  ✓ Mixed tuple parsed correctly")
    
    print("✓ parse_values tuple test passed")


def test_parse_values_with_list():
    """Test that parse_values handles list inputs."""
    print("\nTesting parse_values with list input...")
    
    # Test with integer list
    result = parse_values([100, 200, 50])
    assert result == [100, 200, 50], f"Expected [100, 200, 50], got {result}"
    print("  ✓ Integer list parsed correctly")
    
    # Test with float list
    result = parse_values([19.5, 18.2, 5.0])
    assert result == [19.5, 18.2, 5.0], f"Expected [19.5, 18.2, 5.0], got {result}"
    print("  ✓ Float list parsed correctly")
    
    print("✓ parse_values list test passed")


def test_get_float_with_tuple_payload():
    """Test that get_float works with values parsed from tuples."""
    print("\nTesting get_float with tuple-derived values...")
    
    # Simulate receiving a POWER message with tuple payload
    payload = (19.5, 18.2, 5.0)
    values = parse_values(payload)
    
    # Extract values like SatelliteNetworkManager does
    in_val = get_float(values, 0)
    bus_val = get_float(values, 1)
    log_val = get_float(values, 2)
    
    assert abs(in_val - 19.5) < 0.001, f"Expected 19.5, got {in_val}"
    assert abs(bus_val - 18.2) < 0.001, f"Expected 18.2, got {bus_val}"
    assert abs(log_val - 5.0) < 0.001, f"Expected 5.0, got {log_val}"
    
    print(f"  ✓ Extracted values: in={in_val}, bus={bus_val}, log={log_val}")
    print("✓ get_float with tuple payload test passed")


def test_backward_compatibility():
    """Test that string payloads still work."""
    print("\nTesting backward compatibility with string payloads...")
    
    # Test with comma-separated string (old format)
    payload = "19.5,18.2,5.0"
    values = parse_values(payload)
    
    in_val = get_float(values, 0)
    bus_val = get_float(values, 1)
    log_val = get_float(values, 2)
    
    assert abs(in_val - 19.5) < 0.001, f"Expected 19.5, got {in_val}"
    assert abs(bus_val - 18.2) < 0.001, f"Expected 18.2, got {bus_val}"
    assert abs(log_val - 5.0) < 0.001, f"Expected 5.0, got {log_val}"
    
    print(f"  ✓ String payload still works: in={in_val}, bus={bus_val}, log={log_val}")
    print("✓ Backward compatibility test passed")


def test_bytes_compatibility():
    """Test that bytes payloads still work."""
    print("\nTesting bytes payload handling...")
    
    # Test with bytes (also should work)
    payload = bytes([100, 200, 50])
    values = parse_values(payload)
    
    assert values == [100, 200, 50], f"Expected [100, 200, 50], got {values}"
    
    print(f"  ✓ Bytes payload works: {values}")
    print("✓ Bytes compatibility test passed")


if __name__ == "__main__":
    print("=" * 60)
    print("Tuple Payload Compatibility Test Suite")
    print("=" * 60)
    
    try:
        test_parse_values_with_tuple()
        test_parse_values_with_list()
        test_get_float_with_tuple_payload()
        test_backward_compatibility()
        test_bytes_compatibility()
        
        print("\n" + "=" * 60)
        print("ALL TUPLE PAYLOAD TESTS PASSED ✓")
        print("=" * 60)
        print("\nSatelliteNetworkManager will work correctly with tuple payloads!")
        
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
