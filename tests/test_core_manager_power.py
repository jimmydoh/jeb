#!/usr/bin/env python3
"""Test CoreManager POWER command handling with both string and bytes payloads.

This test validates the fix for the "String Boomerang" crash risk where
CoreManager.handle_message would crash when receiving binary payloads.
"""

import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'utilities'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import payload_parser

def test_power_command_with_string_payload():
    """Test that POWER command still works with string payloads (backward compatibility)."""
    print("Testing POWER command with string payload...")
    
    # String payload: "19.2,18.5,5.0"
    string_payload = "19.2,18.5,5.0"
    
    # Parse with helper functions (same as CoreManager does)
    v_data = payload_parser.parse_values(string_payload)
    
    # Extract power values (same as CoreManager does)
    telemetry = {
        "in": payload_parser.get_float(v_data, 0),
        "bus": payload_parser.get_float(v_data, 1),
        "log": payload_parser.get_float(v_data, 2)
    }
    
    # Verify values
    assert abs(telemetry["in"] - 19.2) < 0.01, f"Expected in=19.2, got {telemetry['in']}"
    assert abs(telemetry["bus"] - 18.5) < 0.01, f"Expected bus=18.5, got {telemetry['bus']}"
    assert abs(telemetry["log"] - 5.0) < 0.01, f"Expected log=5.0, got {telemetry['log']}"
    
    print(f"  ✓ Parsed Power: in={telemetry['in']}V, bus={telemetry['bus']}V, logic={telemetry['log']}V")
    print("✓ POWER command with string payload test passed")


def test_power_command_with_bytes_payload():
    """Test that POWER command now works with bytes payloads (the fix)."""
    print("\nTesting POWER command with bytes payload...")
    
    # Binary payload: 3 bytes representing power values
    # For example: [19, 18, 5] as bytes
    binary_payload = bytes([19, 18, 5])
    
    # Parse with helper functions (same as CoreManager does)
    v_data = payload_parser.parse_values(binary_payload)
    
    # Extract power values (same as CoreManager does)
    telemetry = {
        "in": payload_parser.get_float(v_data, 0),
        "bus": payload_parser.get_float(v_data, 1),
        "log": payload_parser.get_float(v_data, 2)
    }
    
    # Verify values
    assert telemetry["in"] == 19.0, f"Expected in=19.0, got {telemetry['in']}"
    assert telemetry["bus"] == 18.0, f"Expected bus=18.0, got {telemetry['bus']}"
    assert telemetry["log"] == 5.0, f"Expected log=5.0, got {telemetry['log']}"
    
    print(f"  ✓ Parsed Power: in={telemetry['in']}V, bus={telemetry['bus']}V, logic={telemetry['log']}V")
    print("✓ POWER command with bytes payload test passed")


def test_power_command_with_empty_payload():
    """Test that POWER command handles empty payloads gracefully."""
    print("\nTesting POWER command with empty payload...")
    
    # Empty payload
    empty_payload = ""
    
    # Parse with helper functions (same as CoreManager does)
    v_data = payload_parser.parse_values(empty_payload)
    
    # Extract power values (same as CoreManager does - no explicit defaults needed)
    # get_float has a default of 0.0 built-in
    telemetry = {
        "in": payload_parser.get_float(v_data, 0),
        "bus": payload_parser.get_float(v_data, 1),
        "log": payload_parser.get_float(v_data, 2)
    }
    
    # Verify defaults are used
    assert telemetry["in"] == 0.0, f"Expected in=0.0, got {telemetry['in']}"
    assert telemetry["bus"] == 0.0, f"Expected bus=0.0, got {telemetry['bus']}"
    assert telemetry["log"] == 0.0, f"Expected log=0.0, got {telemetry['log']}"
    
    print(f"  ✓ Empty payload handled with defaults: {telemetry}")
    print("✓ POWER command with empty payload test passed")


def test_original_string_boomerang_crash():
    """Demonstrate that the old code would have issues with bytes, but the fix handles it."""
    print("\nTesting original String Boomerang crash scenario...")
    
    # Binary payload that would have caused issues with old code
    binary_payload = bytes([19, 18, 5])
    
    # The old code did: payload.split(",")
    # For binary payloads, this would either:
    # 1. In CircuitPython: May not have .split() method or require bytes separator
    # 2. The result would be wrong for numeric binary data
    
    print("  ✓ Old code assumption: payload is always a string with comma-separated values")
    print(f"  ✓ Problem: binary payload {binary_payload} is not a string!")
    
    # The fundamental issue: calling string methods on bytes
    # In some Python versions/CircuitPython, bytes.split(",") would fail
    # Even if it works, the parsing logic would be wrong
    
    # New code uses parse_values which handles both
    v_data = payload_parser.parse_values(binary_payload)
    print(f"  ✓ New code handles bytes gracefully: {v_data}")
    
    # Also test with string to show backward compatibility
    string_payload = "19,18,5"
    v_data_str = payload_parser.parse_values(string_payload)
    print(f"  ✓ New code still handles strings: {v_data_str}")
    
    print("✓ String Boomerang crash scenario test passed")


if __name__ == "__main__":
    print("=" * 60)
    print("CoreManager POWER Command Test Suite")
    print("Testing fix for String Boomerang crash risk")
    print("=" * 60)
    
    test_power_command_with_string_payload()
    test_power_command_with_bytes_payload()
    test_power_command_with_empty_payload()
    test_original_string_boomerang_crash()
    
    print("\n" + "=" * 60)
    print("ALL TESTS PASSED ✓")
    print("=" * 60)
    print()
    print("The fix successfully:")
    print("  • Maintains backward compatibility with string payloads")
    print("  • Handles new binary payloads without crashing")
    print("  • Provides safe defaults for empty payloads")
    print("  • Eliminates the String Boomerang crash risk")
