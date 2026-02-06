#!/usr/bin/env python3
"""Unit tests for COBS (Consistent Overhead Byte Stuffing) implementation."""

import sys
import os

# Add src/utilities to path for direct module import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'utilities'))

# Import COBS module directly to avoid __init__ hardware dependencies
import cobs
cobs_encode = cobs.cobs_encode
cobs_decode = cobs.cobs_decode


def test_cobs_encode_empty():
    """Test COBS encoding of empty data."""
    print("Testing COBS encode empty data...")
    
    result = cobs_encode(b'')
    assert result == b'\x01', f"Expected b'\\x01', got {result!r}"
    
    print("✓ COBS encode empty test passed")


def test_cobs_decode_empty():
    """Test COBS decoding of empty data."""
    print("\nTesting COBS decode empty data...")
    
    result = cobs_decode(b'\x01')
    assert result == b'', f"Expected b'', got {result!r}"
    
    print("✓ COBS decode empty test passed")


def test_cobs_encode_single_zero():
    """Test COBS encoding of a single zero byte."""
    print("\nTesting COBS encode single zero...")
    
    result = cobs_encode(b'\x00')
    assert result == b'\x01\x01', f"Expected b'\\x01\\x01', got {result!r}"
    
    print("✓ COBS encode single zero test passed")


def test_cobs_decode_single_zero():
    """Test COBS decoding of a single zero byte."""
    print("\nTesting COBS decode single zero...")
    
    result = cobs_decode(b'\x01\x01')
    assert result == b'\x00', f"Expected b'\\x00', got {result!r}"
    
    print("✓ COBS decode single zero test passed")


def test_cobs_encode_no_zeros():
    """Test COBS encoding data without zeros."""
    print("\nTesting COBS encode without zeros...")
    
    data = b'\x01\x02\x03'
    result = cobs_encode(data)
    expected = b'\x04\x01\x02\x03'
    assert result == expected, f"Expected {expected!r}, got {result!r}"
    
    print("✓ COBS encode without zeros test passed")


def test_cobs_decode_no_zeros():
    """Test COBS decoding data without zeros."""
    print("\nTesting COBS decode without zeros...")
    
    encoded = b'\x04\x01\x02\x03'
    result = cobs_decode(encoded)
    expected = b'\x01\x02\x03'
    assert result == expected, f"Expected {expected!r}, got {result!r}"
    
    print("✓ COBS decode without zeros test passed")


def test_cobs_encode_with_zero():
    """Test COBS encoding data with zero in the middle."""
    print("\nTesting COBS encode with zero in middle...")
    
    data = b'\x01\x00\x02'
    result = cobs_encode(data)
    expected = b'\x02\x01\x02\x02'
    assert result == expected, f"Expected {expected!r}, got {result!r}"
    
    print("✓ COBS encode with zero test passed")


def test_cobs_decode_with_zero():
    """Test COBS decoding data with zero in the middle."""
    print("\nTesting COBS decode with zero in middle...")
    
    encoded = b'\x02\x01\x02\x02'
    result = cobs_decode(encoded)
    expected = b'\x01\x00\x02'
    assert result == expected, f"Expected {expected!r}, got {result!r}"
    
    print("✓ COBS decode with zero test passed")


def test_cobs_roundtrip():
    """Test COBS encode/decode roundtrip."""
    print("\nTesting COBS roundtrip...")
    
    test_cases = [
        b'',
        b'\x00',
        b'\x01\x02\x03',
        b'\x00\x00\x00',
        b'\x01\x00\x02\x00\x03',
        b'Hello World',
        b'\xff\xfe\xfd',
        bytes(range(256)),  # All possible byte values
    ]
    
    for original in test_cases:
        encoded = cobs_encode(original)
        decoded = cobs_decode(encoded)
        assert decoded == original, f"Roundtrip failed for {original!r}"
        # Verify no 0x00 in encoded data
        assert b'\x00' not in encoded, f"Encoded data contains 0x00: {encoded!r}"
    
    print("✓ COBS roundtrip test passed")


def test_cobs_binary_message():
    """Test COBS with realistic binary protocol message."""
    print("\nTesting COBS with binary message...")
    
    # Simulate a binary message: [DEST_ID][CMD][PAYLOAD][CRC]
    # Example: destination=0x01, command=0x10, payload=[100, 200, 0, 50], crc=0xAB
    message = b'\x01\x10\x64\xc8\x00\x32\xab'
    
    # Encode with COBS
    encoded = cobs_encode(message)
    
    # Verify no zeros in encoded data
    assert b'\x00' not in encoded, "Encoded message contains 0x00"
    
    # Decode and verify
    decoded = cobs_decode(encoded)
    assert decoded == message, f"Message mismatch: expected {message!r}, got {decoded!r}"
    
    print(f"  Original: {message.hex()}")
    print(f"  Encoded:  {encoded.hex()}")
    print(f"  Decoded:  {decoded.hex()}")
    print("✓ Binary message test passed")


def test_cobs_invalid_decode():
    """Test COBS decoding with invalid data."""
    print("\nTesting COBS decode with invalid data...")
    
    # Test with data containing 0x00 (invalid in COBS encoding)
    try:
        cobs_decode(b'\x02\x00\x01')
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "0x00" in str(e)
        print(f"  Correctly raised ValueError: {e}")
    
    # Test with empty data
    try:
        cobs_decode(b'')
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "empty" in str(e).lower()
        print(f"  Correctly raised ValueError for empty data: {e}")
    
    print("✓ Invalid decode test passed")


def test_cobs_overhead():
    """Test COBS encoding overhead for various data patterns."""
    print("\nTesting COBS overhead...")
    
    # Best case: no zeros (1 byte overhead for every 254 bytes)
    data_no_zeros = bytes([i for i in range(1, 255)])
    encoded_no_zeros = cobs_encode(data_no_zeros)
    overhead_no_zeros = len(encoded_no_zeros) - len(data_no_zeros)
    print(f"  No zeros: {len(data_no_zeros)} -> {len(encoded_no_zeros)} bytes ({overhead_no_zeros} overhead)")
    
    # Worst case: all zeros (doubles size)
    data_all_zeros = b'\x00' * 10
    encoded_all_zeros = cobs_encode(data_all_zeros)
    overhead_all_zeros = len(encoded_all_zeros) - len(data_all_zeros)
    print(f"  All zeros: {len(data_all_zeros)} -> {len(encoded_all_zeros)} bytes ({overhead_all_zeros} overhead)")
    
    # Average case: random-ish data
    data_mixed = b'Hello\x00World\x00Test\x00Data'
    encoded_mixed = cobs_encode(data_mixed)
    overhead_mixed = len(encoded_mixed) - len(data_mixed)
    print(f"  Mixed data: {len(data_mixed)} -> {len(encoded_mixed)} bytes ({overhead_mixed} overhead)")
    
    print("✓ Overhead analysis test passed")


if __name__ == "__main__":
    print("=" * 60)
    print("COBS Implementation Test Suite")
    print("=" * 60)
    
    try:
        test_cobs_encode_empty()
        test_cobs_decode_empty()
        test_cobs_encode_single_zero()
        test_cobs_decode_single_zero()
        test_cobs_encode_no_zeros()
        test_cobs_decode_no_zeros()
        test_cobs_encode_with_zero()
        test_cobs_decode_with_zero()
        test_cobs_roundtrip()
        test_cobs_binary_message()
        test_cobs_invalid_decode()
        test_cobs_overhead()
        
        print("\n" + "=" * 60)
        print("ALL COBS TESTS PASSED ✓")
        print("=" * 60)
        
    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
