#!/usr/bin/env python3
"""Unit tests for CRC-8 implementation."""

import sys


def calculate_crc8(data):
    """Calculate CRC-8 checksum for a given string or bytes.

    Uses CRC-8-CCITT polynomial (0x07) for error detection in UART packets.

    Parameters:
        data (str or bytes): The data to calculate CRC for (e.g., "ID|CMD|VAL" or b"ID|CMD|VAL").

    Returns:
        str: Two-character hexadecimal CRC value (e.g., "A3").
    """
    crc = 0x00
    polynomial = 0x07

    # Handle both str and bytes input
    if isinstance(data, str):
        data = data.encode('utf-8')

    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x80:
                crc = (crc << 1) ^ polynomial
            else:
                crc <<= 1
            crc &= 0xFF

    return f"{crc:02X}"


def verify_crc8(packet):
    """Verify CRC-8 checksum of a received packet.

    Parameters:
        packet (str or bytes): Complete packet with CRC (e.g., "ID|CMD|VAL|A3" or b"ID|CMD|VAL|A3").

    Returns:
        tuple: (is_valid: bool, data: str or bytes) where data is the packet without CRC.
    """
    # Handle both str and bytes input
    if isinstance(packet, str):
        separator = "|"
    else:
        separator = b"|"
    
    parts = packet.rsplit(separator, 1)
    if len(parts) != 2:
        return False, None

    data, received_crc = parts
    calculated_crc = calculate_crc8(data)
    
    # Handle type mismatch for comparison
    if isinstance(received_crc, bytes):
        calculated_crc = calculated_crc.encode('ascii')

    return calculated_crc == received_crc, data


def test_calculate_crc8():
    """Test CRC-8 calculation."""
    print("Testing CRC-8 calculation...")

    # Test case 1: Simple packet
    data1 = "ALL|ID_ASSIGN|0100"
    crc1 = calculate_crc8(data1)
    print(f"  Data: '{data1}' -> CRC: {crc1}")
    assert len(crc1) == 2, "CRC should be 2 characters"
    assert all(c in '0123456789ABCDEF' for c in crc1), "CRC should be hex"

    # Test case 2: Different data should produce different CRC
    data2 = "0101|STATUS|0000,C,N,0,0"
    crc2 = calculate_crc8(data2)
    print(f"  Data: '{data2}' -> CRC: {crc2}")
    assert crc1 != crc2, "Different data should produce different CRC"

    # Test case 3: Same data should produce same CRC
    crc3 = calculate_crc8(data1)
    assert crc1 == crc3, "Same data should produce same CRC"
    print(f"  Same data produces same CRC: {crc1} == {crc3}")

    print("✓ CRC-8 calculation tests passed")


def test_verify_crc8():
    """Test CRC-8 verification."""
    print("\nTesting CRC-8 verification...")

    # Test case 1: Valid packet
    data = "ALL|ID_ASSIGN|0100"
    crc = calculate_crc8(data)
    packet = f"{data}|{crc}"
    is_valid, extracted_data = verify_crc8(packet)
    print(f"  Valid packet: '{packet}'")
    assert is_valid, "Valid packet should pass verification"
    assert extracted_data == data, "Extracted data should match original"
    print(f"  ✓ Valid packet verified, data extracted: '{extracted_data}'")

    # Test case 2: Corrupted packet (wrong CRC)
    bad_packet = f"{data}|FF"
    is_valid, extracted_data = verify_crc8(bad_packet)
    print(f"  Corrupted packet: '{bad_packet}'")
    assert not is_valid, "Corrupted packet should fail verification"
    print(f"  ✓ Corrupted packet rejected")

    # Test case 3: Corrupted data (bit flip in data)
    corrupted_data = "ALL|ID_ASSIGN|0101"  # Changed 0100 to 0101
    bad_packet2 = f"{corrupted_data}|{crc}"  # Using old CRC
    is_valid, extracted_data = verify_crc8(bad_packet2)
    print(f"  Corrupted data packet: '{bad_packet2}'")
    assert not is_valid, "Packet with corrupted data should fail verification"
    print(f"  ✓ Corrupted data packet rejected")

    # Test case 4: Malformed packet (no CRC)
    malformed = "ALL|ID_ASSIGN|0100"
    is_valid, extracted_data = verify_crc8(malformed)
    print(f"  Malformed packet (no CRC): '{malformed}'")
    assert not is_valid, "Malformed packet should fail verification"
    print(f"  ✓ Malformed packet rejected")

    print("✓ CRC-8 verification tests passed")


def test_protocol_examples():
    """Test CRC with real protocol examples."""
    print("\nTesting real protocol examples...")

    examples = [
        "ALL|ID_ASSIGN|0100",
        "SAT|NEW_SAT|01",
        "0101|STATUS|0000,C,N,0,0",
        "0101|POWER|24.2,23.8,5.0",
        "0101|ERROR|LOGIC_BROWNOUT:4.5V",
        "0101|LED|0,255,0,0,2.0,0.5,2",
        "0101|DSP|HELLO,1,0.2,L",
    ]

    for data in examples:
        crc = calculate_crc8(data)
        packet = f"{data}|{crc}"
        is_valid, extracted = verify_crc8(packet)
        status = "✓" if is_valid else "✗"
        print(f"  {status} '{data}' -> CRC: {crc}")
        assert is_valid, f"Failed to verify packet: {packet}"
        assert extracted == data, f"Data mismatch: {extracted} != {data}"

    print("✓ Protocol examples tests passed")


def test_error_detection():
    """Test that CRC can detect single-bit errors."""
    print("\nTesting single-bit error detection...")

    data = "0101|STATUS|0000,C,N,0,0"
    crc = calculate_crc8(data)
    packet = f"{data}|{crc}"

    # Introduce single-bit errors at different positions
    error_count = 0
    for i in range(len(data)):
        # Flip a character
        corrupted = list(data)
        if corrupted[i] == '0':
            corrupted[i] = '1'
        elif corrupted[i] == '1':
            corrupted[i] = '0'
        else:
            # Change other characters to 'X'
            corrupted[i] = 'X'

        corrupted_data = ''.join(corrupted)
        corrupted_packet = f"{corrupted_data}|{crc}"
        is_valid, _ = verify_crc8(corrupted_packet)

        if not is_valid:
            error_count += 1

    # CRC-8 should detect most single-bit errors
    detection_rate = error_count / len(data) * 100
    print(f"  Single-bit error detection rate: {detection_rate:.1f}% ({error_count}/{len(data)})")
    assert detection_rate > 95, "CRC should detect most single-bit errors"
    print("✓ Error detection tests passed")


def test_bytes_input():
    """Test that CRC functions handle bytes input correctly."""
    print("\nTesting bytes input handling...")
    
    # Test calculate_crc8 with bytes
    data_bytes = b"ALL|ID_ASSIGN|0100"
    crc_from_bytes = calculate_crc8(data_bytes)
    print(f"  CRC from bytes: {crc_from_bytes}")
    assert isinstance(crc_from_bytes, str), "CRC should be string in test implementation"
    
    # Test calculate_crc8 with string (should give same result)
    data_str = "ALL|ID_ASSIGN|0100"
    crc_from_str = calculate_crc8(data_str)
    print(f"  CRC from string: {crc_from_str}")
    assert crc_from_bytes == crc_from_str, "CRC from bytes and string should match"
    
    # Test verify_crc8 with bytes packet
    packet_bytes = b"ALL|ID_ASSIGN|0100|BC"
    is_valid, data = verify_crc8(packet_bytes)
    print(f"  Bytes packet verified: {is_valid}, data type: {type(data)}")
    assert is_valid, "Bytes packet should be valid"
    assert isinstance(data, bytes), "Data should be bytes when input is bytes"
    assert data == b"ALL|ID_ASSIGN|0100", "Extracted data should match"
    
    # Test verify_crc8 with string packet
    packet_str = "ALL|ID_ASSIGN|0100|BC"
    is_valid, data = verify_crc8(packet_str)
    print(f"  String packet verified: {is_valid}, data type: {type(data)}")
    assert is_valid, "String packet should be valid"
    assert isinstance(data, str), "Data should be string when input is string"
    assert data == "ALL|ID_ASSIGN|0100", "Extracted data should match"
    
    print("✓ Bytes input handling tests passed")


if __name__ == "__main__":
    print("=" * 60)
    print("CRC-8 UART Integrity Test Suite")
    print("=" * 60)

    try:
        test_calculate_crc8()
        test_verify_crc8()
        test_protocol_examples()
        test_error_detection()
        test_bytes_input()

        print("\n" + "=" * 60)
        print("ALL TESTS PASSED ✓")
        print("=" * 60)

    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
