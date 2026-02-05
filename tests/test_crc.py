#!/usr/bin/env python3
"""
Test script for CRC16 implementation in JADNET protocol.
This can be run on a development machine to verify the CRC functions work correctly.
"""

import sys
import os

# Add src/utilities directory to path to import crc module directly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'utilities'))

from crc import calculate_crc16, verify_crc16


def test_crc_calculation():
    """Test CRC16 calculation."""
    print("Testing CRC calculation...")
    
    # Test case 1: Basic packet
    data1 = "ALL|ID_ASSIGN|0100"
    crc1 = calculate_crc16(data1)
    print(f"  Data: '{data1}' -> CRC: {crc1}")
    assert len(crc1) == 4, "CRC should be 4 hex characters"
    assert all(c in "0123456789ABCDEF" for c in crc1), "CRC should be hexadecimal"
    
    # Test case 2: Status packet
    data2 = "01|STATUS|encoder1:0,encoder2:0,toggle1:0"
    crc2 = calculate_crc16(data2)
    print(f"  Data: '{data2}' -> CRC: {crc2}")
    
    # Test case 3: Command packet
    data3 = "01|LED|ALL,255,0,0"
    crc3 = calculate_crc16(data3)
    print(f"  Data: '{data3}' -> CRC: {crc3}")
    
    # Test case 4: Same data should produce same CRC
    crc1_repeat = calculate_crc16(data1)
    assert crc1 == crc1_repeat, "Same data should produce same CRC"
    print(f"  ✓ Same data produces consistent CRC")
    
    # Test case 5: Different data should produce different CRC (high probability)
    data4 = "ALL|ID_ASSIGN|0101"  # Changed last digit
    crc4 = calculate_crc16(data4)
    assert crc1 != crc4, "Different data should produce different CRC"
    print(f"  ✓ Different data produces different CRC")
    
    print("✓ CRC calculation tests passed\n")


def test_crc_verification():
    """Test CRC16 verification."""
    print("Testing CRC verification...")
    
    # Test case 1: Valid packet
    data = "ALL|ID_ASSIGN|0100"
    crc = calculate_crc16(data)
    packet = f"{data}|{crc}"
    is_valid, extracted_data = verify_crc16(packet)
    assert is_valid, "Valid packet should pass verification"
    assert extracted_data == data, "Extracted data should match original"
    print(f"  ✓ Valid packet verified: '{packet}'")
    
    # Test case 2: Corrupted CRC
    corrupted_packet = f"{data}|FFFF"  # Wrong CRC
    is_valid, _ = verify_crc16(corrupted_packet)
    assert not is_valid, "Corrupted CRC should fail verification"
    print(f"  ✓ Corrupted CRC detected")
    
    # Test case 3: Corrupted data
    corrupted_data = "ALL|ID_ASSIGN|0101"  # Changed data
    corrupted_packet2 = f"{corrupted_data}|{crc}"  # But kept old CRC
    is_valid, _ = verify_crc16(corrupted_packet2)
    assert not is_valid, "Corrupted data should fail verification"
    print(f"  ✓ Corrupted data detected")
    
    # Test case 4: Malformed packet (no CRC)
    malformed = "ALL|ID_ASSIGN|0100"
    is_valid, extracted = verify_crc16(malformed)
    assert not is_valid, "Packet without CRC should fail verification"
    print(f"  ✓ Malformed packet (no CRC) detected")
    
    # Test case 5: Multiple pipes in data
    complex_data = "01|STATUS|encoder1:0,encoder2:0,toggle1:0"
    complex_crc = calculate_crc16(complex_data)
    complex_packet = f"{complex_data}|{complex_crc}"
    is_valid, extracted_data = verify_crc16(complex_packet)
    assert is_valid, "Complex packet with multiple pipes should verify"
    assert extracted_data == complex_data, "Complex data should be extracted correctly"
    print(f"  ✓ Complex packet with multiple pipes verified")
    
    print("✓ CRC verification tests passed\n")


def test_noise_simulation():
    """Simulate noise on the line and verify CRC catches it."""
    print("Testing noise detection...")
    
    # Original valid packet
    data = "01|LED|ALL,255,0,0"
    crc = calculate_crc16(data)
    valid_packet = f"{data}|{crc}"
    
    # Simulate single bit flip in data (noise)
    noisy_data = "01|LED|ALL,255,1,0"  # Changed 0 to 1
    noisy_packet = f"{noisy_data}|{crc}"  # Keep old CRC
    
    is_valid_original, _ = verify_crc16(valid_packet)
    is_valid_noisy, _ = verify_crc16(noisy_packet)
    
    assert is_valid_original, "Original packet should be valid"
    assert not is_valid_noisy, "Noisy packet should be detected as invalid"
    print(f"  ✓ Single bit corruption detected")
    
    # Simulate noise in CRC
    noisy_crc = crc[:-1] + ('0' if crc[-1] != '0' else '1')  # Flip last hex digit
    noisy_packet2 = f"{data}|{noisy_crc}"
    is_valid_noisy2, _ = verify_crc16(noisy_packet2)
    assert not is_valid_noisy2, "Noise in CRC should be detected"
    print(f"  ✓ CRC corruption detected")
    
    print("✓ Noise detection tests passed\n")


def test_protocol_examples():
    """Test real protocol examples."""
    print("Testing real protocol examples...")
    
    examples = [
        ("ALL|ID_ASSIGN|0100", "Satellite discovery broadcast"),
        ("01|LED|ALL,255,0,0", "Set all LEDs to red"),
        ("01|STATUS|encoder1:5,encoder2:3", "Status report"),
        ("01|POWER|12.5,12.3,5.0", "Power telemetry"),
        ("01|HELLO|INDUSTRIAL", "Satellite hello"),
        ("01|ERROR|OVERVOLTAGE", "Error report"),
    ]
    
    for data, description in examples:
        crc = calculate_crc16(data)
        packet = f"{data}|{crc}"
        is_valid, extracted = verify_crc16(packet)
        assert is_valid, f"Failed for: {description}"
        assert extracted == data, f"Data mismatch for: {description}"
        print(f"  ✓ {description}: {packet}")
    
    print("✓ Protocol examples passed\n")


def main():
    """Run all tests."""
    print("="*60)
    print("CRC16 JADNET Protocol Test Suite")
    print("="*60 + "\n")
    
    try:
        test_crc_calculation()
        test_crc_verification()
        test_noise_simulation()
        test_protocol_examples()
        
        print("="*60)
        print("ALL TESTS PASSED ✓")
        print("="*60)
        return 0
    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        return 1
    except Exception as e:
        print(f"\n✗ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
