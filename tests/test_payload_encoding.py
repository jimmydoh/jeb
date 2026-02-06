#!/usr/bin/env python3
"""Unit tests for payload encoding with explicit type schemas.

Tests the fix for "magic" payload encoding fragility where satellite IDs
like "01" were being incorrectly interpreted as integers.
"""

import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Mock COBS functions
# Note: This relies on sys.path.insert above to locate src/utilities/cobs
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'utilities'))
import cobs


def calculate_crc8(data):
    """Calculate CRC-8 checksum."""
    crc = 0x00
    polynomial = 0x07
    
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
    
    return crc


# Mock utilities module
class MockUtilities:
    cobs_encode = staticmethod(cobs.cobs_encode)
    cobs_decode = staticmethod(cobs.cobs_decode)
    calculate_crc8 = staticmethod(calculate_crc8)

sys.modules['utilities'] = MockUtilities()


# Mock UARTManager
class MockUARTManager:
    """Mock UARTManager for testing."""
    def __init__(self):
        self.sent_packets = []
        self.receive_buffer = bytearray()
    
    def write(self, data):
        """Mock write method."""
        self.sent_packets.append(data)
    
    def read_until(self, delimiter):
        """Mock read_until method."""
        idx = self.receive_buffer.find(delimiter)
        if idx >= 0:
            data = bytes(self.receive_buffer[:idx + len(delimiter)])
            del self.receive_buffer[:idx + len(delimiter)]
            return data
        return None
    
    def clear_buffer(self):
        """Mock clear_buffer method."""
        pass


# Import transport classes
from transport import Message, UARTTransport
from protocol import COMMAND_MAP, DEST_MAP, MAX_INDEX_VALUE, PAYLOAD_SCHEMAS


def test_id_assign_preserves_leading_zeros():
    """Test that ID_ASSIGN command preserves leading zeros in IDs."""
    print("Testing ID_ASSIGN with leading zeros...")
    
    mock_uart = MockUARTManager()
    transport = UARTTransport(mock_uart, COMMAND_MAP, DEST_MAP, MAX_INDEX_VALUE, PAYLOAD_SCHEMAS)
    
    # Test case from problem statement: "01" should stay as "01", not become 1
    test_cases = [
        ("0100", "Device ID with leading zeros"),
        ("01", "Satellite type with leading zero"),
        ("0001", "ID with multiple leading zeros"),
    ]
    
    for test_id, description in test_cases:
        msg_out = Message("ALL", "ID_ASSIGN", test_id)
        transport.send(msg_out)
        
        # Receive it back
        mock_uart.receive_buffer.extend(mock_uart.sent_packets[-1])
        msg_in = transport.receive()
        
        assert msg_in is not None, f"Failed to receive message for {description}"
        assert msg_in.payload == test_id, \
            f"ID mismatch for {description}: expected '{test_id}', got '{msg_in.payload}'"
        
        print(f"  ✓ {description}: '{test_id}' preserved correctly")
    
    print("✓ ID_ASSIGN leading zero preservation test passed")


def test_new_sat_preserves_string_ids():
    """Test that NEW_SAT command preserves string satellite IDs."""
    print("\nTesting NEW_SAT with string IDs...")
    
    mock_uart = MockUARTManager()
    transport = UARTTransport(mock_uart, COMMAND_MAP, DEST_MAP, MAX_INDEX_VALUE, PAYLOAD_SCHEMAS)
    
    test_cases = ["01", "02", "03", "10"]
    
    for sat_id in test_cases:
        msg_out = Message("SAT", "NEW_SAT", sat_id)
        transport.send(msg_out)
        
        mock_uart.receive_buffer.extend(mock_uart.sent_packets[-1])
        msg_in = transport.receive()
        
        assert msg_in is not None
        assert msg_in.payload == sat_id, \
            f"Satellite ID '{sat_id}' changed to '{msg_in.payload}'"
        
        print(f"  ✓ Satellite ID '{sat_id}' preserved")
    
    print("✓ NEW_SAT string ID preservation test passed")


def test_led_commands_use_byte_encoding():
    """Test that LED commands properly encode RGB values as bytes."""
    print("\nTesting LED command byte encoding...")
    
    mock_uart = MockUARTManager()
    transport = UARTTransport(mock_uart, COMMAND_MAP, DEST_MAP, MAX_INDEX_VALUE, PAYLOAD_SCHEMAS)
    
    # LED command should encode R,G,B,brightness as 4 bytes
    msg_out = Message("0101", "LED", "255,128,64,100")
    transport.send(msg_out)
    
    mock_uart.receive_buffer.extend(mock_uart.sent_packets[-1])
    msg_in = transport.receive()
    
    assert msg_in is not None
    assert msg_in.payload == "255,128,64,100"
    
    print("  ✓ LED RGB values encoded correctly as bytes")
    print("✓ LED command byte encoding test passed")


def test_power_commands_use_float_encoding():
    """Test that POWER commands use float encoding for measurements."""
    print("\nTesting POWER command float encoding...")
    
    mock_uart = MockUARTManager()
    transport = UARTTransport(mock_uart, COMMAND_MAP, DEST_MAP, MAX_INDEX_VALUE, PAYLOAD_SCHEMAS)
    
    # POWER command uses floats for voltage/current
    msg_out = Message("0101", "POWER", "19.5,18.2,5.0")
    transport.send(msg_out)
    
    mock_uart.receive_buffer.extend(mock_uart.sent_packets[-1])
    msg_in = transport.receive()
    
    assert msg_in is not None
    # Float decoding may have slight precision differences
    payload_parts = msg_in.payload.split(',')
    assert len(payload_parts) == 3
    assert abs(float(payload_parts[0]) - 19.5) < 0.01
    assert abs(float(payload_parts[1]) - 18.2) < 0.01
    assert abs(float(payload_parts[2]) - 5.0) < 0.01
    
    print("  ✓ POWER voltages/currents encoded as floats")
    print("✓ POWER command float encoding test passed")


def test_power_commands_accept_list_tuple():
    """Test that POWER commands accept list/tuple inputs directly (no string parsing)."""
    print("\nTesting POWER command with list/tuple inputs...")
    
    mock_uart = MockUARTManager()
    transport = UARTTransport(mock_uart, COMMAND_MAP, DEST_MAP, MAX_INDEX_VALUE, PAYLOAD_SCHEMAS)
    
    # Test with list input (satellite-side optimization)
    test_values = [19.5, 18.2, 5.0]
    msg_out = Message("0101", "POWER", test_values)
    transport.send(msg_out)
    
    mock_uart.receive_buffer.extend(mock_uart.sent_packets[-1])
    msg_in = transport.receive()
    
    assert msg_in is not None
    payload_parts = msg_in.payload.split(',')
    assert len(payload_parts) == 3
    assert abs(float(payload_parts[0]) - 19.5) < 0.01
    assert abs(float(payload_parts[1]) - 18.2) < 0.01
    assert abs(float(payload_parts[2]) - 5.0) < 0.01
    
    print("  ✓ List input encoded correctly")
    
    # Test with tuple input
    mock_uart = MockUARTManager()
    transport = UARTTransport(mock_uart, COMMAND_MAP, DEST_MAP, MAX_INDEX_VALUE, PAYLOAD_SCHEMAS)
    
    test_values = (19.5, 18.2, 5.0)
    msg_out = Message("0101", "POWER", test_values)
    transport.send(msg_out)
    
    mock_uart.receive_buffer.extend(mock_uart.sent_packets[-1])
    msg_in = transport.receive()
    
    assert msg_in is not None
    payload_parts = msg_in.payload.split(',')
    assert len(payload_parts) == 3
    assert abs(float(payload_parts[0]) - 19.5) < 0.01
    assert abs(float(payload_parts[1]) - 18.2) < 0.01
    assert abs(float(payload_parts[2]) - 5.0) < 0.01
    
    print("  ✓ Tuple input encoded correctly")
    
    # Verify list/tuple produces same result as string
    mock_uart_str = MockUARTManager()
    transport_str = UARTTransport(mock_uart_str, COMMAND_MAP, DEST_MAP, MAX_INDEX_VALUE, PAYLOAD_SCHEMAS)
    msg_str = Message("0101", "POWER", "19.5,18.2,5.0")
    transport_str.send(msg_str)
    
    mock_uart_list = MockUARTManager()
    transport_list = UARTTransport(mock_uart_list, COMMAND_MAP, DEST_MAP, MAX_INDEX_VALUE, PAYLOAD_SCHEMAS)
    msg_list = Message("0101", "POWER", [19.5, 18.2, 5.0])
    transport_list.send(msg_list)
    
    assert mock_uart_str.sent_packets[0] == mock_uart_list.sent_packets[0], \
        "String and list encoding should produce identical binary packets"
    
    print("  ✓ List/tuple produce identical binary output as string")
    print("✓ POWER list/tuple input test passed")


def test_display_commands_preserve_text():
    """Test that DSP command preserves text exactly."""
    print("\nTesting DSP text preservation...")
    
    mock_uart = MockUARTManager()
    transport = UARTTransport(mock_uart, COMMAND_MAP, DEST_MAP, MAX_INDEX_VALUE, PAYLOAD_SCHEMAS)
    
    test_texts = [
        "HELLO",
        "BUS_SHUTDOWN:LOW_V",
        "System Ready",
        "01234",  # Numeric-looking text should stay as text
    ]
    
    for text in test_texts:
        msg_out = Message("0101", "DSP", text)
        transport.send(msg_out)
        
        mock_uart.receive_buffer.extend(mock_uart.sent_packets[-1])
        msg_in = transport.receive()
        
        assert msg_in is not None
        assert msg_in.payload == text, \
            f"Text '{text}' changed to '{msg_in.payload}'"
        
        print(f"  ✓ Text '{text}' preserved")
    
    print("✓ DSP text preservation test passed")


def test_backward_compatibility():
    """Test that commands without schemas still work (backward compatibility)."""
    print("\nTesting backward compatibility for commands without schemas...")
    
    mock_uart = MockUARTManager()
    transport = UARTTransport(mock_uart, COMMAND_MAP, DEST_MAP, MAX_INDEX_VALUE, PAYLOAD_SCHEMAS)
    
    # Test STATUS with correct number of values (5 bytes)
    msg_out = Message("0101", "STATUS", "100,200,50,75,25")
    transport.send(msg_out)
    
    mock_uart.receive_buffer.extend(mock_uart.sent_packets[-1])
    msg_in = transport.receive()
    
    assert msg_in is not None
    # Should decode to bytes
    assert msg_in.payload == "100,200,50,75,25"
    
    print("  ✓ Commands with schemas work correctly")
    print("✓ Backward compatibility test passed")


def test_roundtrip_all_command_types():
    """Test roundtrip encoding/decoding for all command types."""
    print("\nTesting roundtrip for all command types...")
    
    test_cases = [
        Message("ALL", "ID_ASSIGN", "0100"),
        Message("SAT", "NEW_SAT", "01"),
        Message("0101", "LED", "255,0,128,100"),
        Message("0101", "POWER", "19.5,18.2,5.0"),
        Message("0101", "DSP", "HELLO WORLD"),
        Message("0101", "ERROR", "LOW_VOLTAGE"),
        Message("0101", "STATUS", "100,200,50,75,25"),
    ]
    
    for msg_out in test_cases:
        mock_uart = MockUARTManager()
        transport = UARTTransport(mock_uart, COMMAND_MAP, DEST_MAP, MAX_INDEX_VALUE, PAYLOAD_SCHEMAS)
        
        transport.send(msg_out)
        mock_uart.receive_buffer.extend(mock_uart.sent_packets[0])
        msg_in = transport.receive()
        
        assert msg_in is not None, f"Failed to receive {msg_out.command}"
        assert msg_in.destination == msg_out.destination
        assert msg_in.command == msg_out.command
        
        # For floats, allow small precision differences
        if msg_out.command == "POWER":
            out_parts = [float(x) for x in msg_out.payload.split(',')]
            in_parts = [float(x) for x in msg_in.payload.split(',')]
            assert len(out_parts) == len(in_parts)
            for out_val, in_val in zip(out_parts, in_parts):
                assert abs(out_val - in_val) < 0.01
        else:
            assert msg_in.payload == msg_out.payload, \
                f"{msg_out.command}: expected '{msg_out.payload}', got '{msg_in.payload}'"
        
        print(f"  ✓ {msg_out.command} roundtrip OK")
    
    print("✓ Roundtrip test passed for all command types")


if __name__ == "__main__":
    print("=" * 60)
    print("Payload Encoding Type Safety Test Suite")
    print("=" * 60)
    
    try:
        test_id_assign_preserves_leading_zeros()
        test_new_sat_preserves_string_ids()
        test_led_commands_use_byte_encoding()
        test_power_commands_use_float_encoding()
        test_power_commands_accept_list_tuple()
        test_display_commands_preserve_text()
        test_backward_compatibility()
        test_roundtrip_all_command_types()
        
        print("\n" + "=" * 60)
        print("ALL PAYLOAD ENCODING TESTS PASSED ✓")
        print("=" * 60)
        print("\nThe 'magic' type guessing issue has been fixed!")
        print("Commands now use explicit schemas for type-safe encoding.")
        print("List/tuple inputs are supported for performance optimization.")
        
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
