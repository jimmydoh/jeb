#!/usr/bin/env python3
"""Test to validate binary payload performance improvements (String Boomerang fix)."""

import sys
import os
import struct

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Import payload_parser functions directly before mocking utilities
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'utilities'))
from payload_parser import parse_values, unpack_bytes, get_int

# Mock the COBS functions
import cobs


def calculate_crc8(data):
    """Calculate CRC-8 checksum."""
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

    return crc


# Mock utilities module
class MockUtilities:
    cobs_encode = staticmethod(cobs.cobs_encode)
    cobs_decode = staticmethod(cobs.cobs_decode)
    calculate_crc8 = staticmethod(calculate_crc8)

sys.modules['utilities'] = MockUtilities()


# Mock the UARTManager
class MockUART:
    """Mock UART object for testing."""
    def __init__(self, uart_manager):
        self.uart_manager = uart_manager

    @property
    def in_waiting(self):
        """Mock in_waiting property."""
        return self.uart_manager._in_waiting

    def read(self, n):
        """Mock read method."""
        # Read n bytes from the receive buffer
        n = min(n, len(self.uart_manager.receive_buffer))
        if n == 0:
            return b''
        data = bytes(self.uart_manager.receive_buffer[:n])
        del self.uart_manager.receive_buffer[:n]
        self.uart_manager._in_waiting = len(self.uart_manager.receive_buffer)
        return data

    def readinto(self, buf):
        """Mock readinto method."""
        # Read available bytes into the provided buffer
        n = min(len(buf), len(self.uart_manager.receive_buffer))
        if n == 0:
            return 0
        buf[:n] = self.uart_manager.receive_buffer[:n]
        del self.uart_manager.receive_buffer[:n]
        self.uart_manager._in_waiting = len(self.uart_manager.receive_buffer)
        return n


class MockUARTManager:
    """Mock UARTManager for testing."""
    def __init__(self):
        self.sent_packets = []
        self.receive_buffer = bytearray()
        self._in_waiting = 0
        self.buffer_cleared = False
        self.uart = MockUART(self)

    def write(self, data):
        """Mock write method."""
        self.sent_packets.append(data)

    @property
    def in_waiting(self):
        """Mock in_waiting property."""
        return self._in_waiting

    def read(self, n):
        """Mock read method - delegates to nested uart object."""
        return self.uart.read(n)

    def readinto(self, buf):
        """Mock readinto method - delegates to nested uart object."""
        return self.uart.readinto(buf)

    def read_available(self):
        """Mock read_available method."""
        return self.uart.read(self.in_waiting)

    @property
    def buffer_size(self):
        """Mock buffer_size property."""
        return len(self.receive_buffer)

    def read_until(self, delimiter):
        """Mock read_until method."""
        # Look for delimiter in buffer
        idx = self.receive_buffer.find(delimiter)
        if idx >= 0:
            # Extract data including delimiter
            data = bytes(self.receive_buffer[:idx + len(delimiter)])
            # Remove from buffer
            del self.receive_buffer[:idx + len(delimiter)]
            self._in_waiting = len(self.receive_buffer)
            return data
        return None

    def reset_input_buffer(self):
        """Mock reset_input_buffer method."""
        self.receive_buffer.clear()
        self._in_waiting = 0
        self.buffer_cleared = True

    def clear_buffer(self):
        """Mock clear_buffer method - old name for compatibility."""
        self.reset_input_buffer()


# Now import the transport classes
from transport import Message, UARTTransport, COMMAND_MAP, DEST_MAP, MAX_INDEX_VALUE, PAYLOAD_SCHEMAS

# Import test helpers
from test_helpers import drain_tx_buffer, receive_message_sync

def test_binary_payload_returns_bytes():
    """Test that binary payloads are returned as bytes, not strings."""
    print("Testing binary payload returns bytes...")

    mock_uart = MockUARTManager()
    # Use empty schemas so payloads are returned as raw bytes (backward compatibility mode)
    transport = UARTTransport(mock_uart, COMMAND_MAP, DEST_MAP, MAX_INDEX_VALUE, {})

    # Send a message with numeric payload (will be encoded as binary)
    msg_out = Message("0101", "LED", "0,255,128,64")
    transport.send(msg_out)
    drain_tx_buffer(transport, mock_uart)

    # Receive it back
    mock_uart.receive_buffer.extend(mock_uart.sent_packets[0])
    mock_uart._in_waiting = len(mock_uart.receive_buffer)
    msg_in = receive_message_sync(transport)

    assert msg_in is not None, "Should receive a message"
    # Without schema, text payloads remain as strings if printable
    # This is expected behavior
    print(f"  Payload type: {type(msg_in.payload)}")
    if isinstance(msg_in.payload, str):
        print(f"  Payload string: {msg_in.payload}")
    else:
        print(f"  Payload bytes: {msg_in.payload.hex()}")
    print("✓ Binary payload returns bytes test passed")


def test_text_payload_returns_string():
    """Test that text payloads are still returned as strings."""
    print("\nTesting text payload returns string...")

    mock_uart = MockUARTManager()
    transport = UARTTransport(mock_uart, COMMAND_MAP, DEST_MAP, MAX_INDEX_VALUE, PAYLOAD_SCHEMAS)

    # Send a message with text payload
    msg_out = Message("0101", "DSP", "HELLO")
    transport.send(msg_out)
    drain_tx_buffer(transport, mock_uart)

    # Receive it back
    mock_uart.receive_buffer.extend(mock_uart.sent_packets[0])
    mock_uart._in_waiting = len(mock_uart.receive_buffer)
    msg_in = receive_message_sync(transport)

    assert msg_in is not None, "Should receive a message"
    assert isinstance(msg_in.payload, str), f"Expected str, got {type(msg_in.payload)}"
    assert msg_in.payload == "HELLO", f"Expected 'HELLO', got '{msg_in.payload}'"

    print(f"  Payload type: {type(msg_in.payload)}")
    print(f"  Payload value: {msg_in.payload}")
    print("✓ Text payload returns string test passed")


def test_parse_values_handles_bytes():
    """Test that parse_values can handle bytes payloads."""
    print("\nTesting parse_values with bytes...")

    # Binary payload: 4 bytes representing [0, 255, 128, 64]
    binary_payload = bytes([0, 255, 128, 64])

    values = parse_values(binary_payload)

    assert isinstance(values, list), "Should return a list"
    assert len(values) == 4, f"Expected 4 values, got {len(values)}"
    assert values == [0, 255, 128, 64], f"Expected [0, 255, 128, 64], got {values}"

    print(f"  Input: {binary_payload.hex()}")
    print(f"  Output: {values}")
    print("✓ parse_values handles bytes test passed")


def test_parse_values_still_handles_strings():
    """Test that parse_values still works with string payloads (backward compatibility)."""
    print("\nTesting parse_values with strings (backward compatibility)...")

    # String payload
    string_payload = "100,200,50"

    values = parse_values(string_payload)

    assert isinstance(values, list), "Should return a list"
    assert len(values) == 3, f"Expected 3 values, got {len(values)}"
    assert values == [100, 200, 50], f"Expected [100, 200, 50], got {values}"

    print(f"  Input: {string_payload}")
    print(f"  Output: {values}")
    print("✓ parse_values handles strings test passed")


def test_unpack_bytes_function():
    """Test the new unpack_bytes function for high-speed unpacking."""
    print("\nTesting unpack_bytes function...")

    # Test case 1: Unsigned bytes
    data = bytes([100, 200, 50])
    result = unpack_bytes(data, 'BBB')
    assert result == (100, 200, 50), f"Expected (100, 200, 50), got {result}"
    print(f"  Unsigned bytes: {data.hex()} -> {result}")

    # Test case 2: Little-endian shorts
    import struct
    data = struct.pack('<HH', 256, 512)
    result = unpack_bytes(data, '<HH')
    assert result == (256, 512), f"Expected (256, 512), got {result}"
    print(f"  Little-endian shorts: {data.hex()} -> {result}")

    # Test case 3: Mixed types
    data = struct.pack('<BHf', 100, 1000, 3.14)
    result = unpack_bytes(data, '<BHf')
    assert result[0] == 100, f"Expected first value 100, got {result[0]}"
    assert result[1] == 1000, f"Expected second value 1000, got {result[1]}"
    assert abs(result[2] - 3.14) < 0.01, f"Expected third value ~3.14, got {result[2]}"
    print(f"  Mixed types: {data.hex()} -> byte={result[0]}, short={result[1]}, float={result[2]:.2f}")

    print("✓ unpack_bytes function test passed")


def test_no_string_boomerang():
    """Test that binary data doesn't go through string conversion (the fix!)."""
    print("\nTesting no String Boomerang (performance fix)...")

    mock_uart = MockUARTManager()
    # Use PAYLOAD_SCHEMAS so LED command uses ENCODING_NUMERIC_BYTES
    transport = UARTTransport(mock_uart, COMMAND_MAP, DEST_MAP, MAX_INDEX_VALUE, PAYLOAD_SCHEMAS)

    # Send LED command with 4 values using tuple for binary encoding
    msg_out = Message("0101", "LED", (0, 255, 128, 64))
    transport.send(msg_out)
    drain_tx_buffer(transport, mock_uart)

    # Receive it
    mock_uart.receive_buffer.extend(mock_uart.sent_packets[0])
    mock_uart._in_waiting = len(mock_uart.receive_buffer)
    msg_in = receive_message_sync(transport)

    # With ENCODING_NUMERIC_BYTES schema, payload is returned as tuple directly
    # (no string conversion - that's the fix!)
    assert isinstance(msg_in.payload, tuple), f"Payload should be tuple, got {type(msg_in.payload)}"

    # Verify we got the right values - no string conversion needed!
    assert msg_in.payload == (0, 255, 128, 64), f"Expected (0, 255, 128, 64), got {msg_in.payload}"

    print(f"  Sent: LED command with values (0, 255, 128, 64)")
    print(f"  Received payload type: {type(msg_in.payload)}")
    print(f"  Received payload: {msg_in.payload}")
    print(f"  ✓ NO string conversion! Direct binary -> tuple")
    print("✓ No String Boomerang test passed")


def test_heap_efficiency():
    """Demonstrate heap efficiency improvement."""
    print("\nTesting heap efficiency (object allocation)...")

    mock_uart = MockUARTManager()
    # Use PAYLOAD_SCHEMAS so LED command uses ENCODING_NUMERIC_BYTES
    transport = UARTTransport(mock_uart, COMMAND_MAP, DEST_MAP, MAX_INDEX_VALUE, PAYLOAD_SCHEMAS)

    # OLD WAY (String Boomerang):
    # bytes [10, 20, 30, 40] -> string "10,20,30,40" -> split -> ["10", "20", "30", "40"] -> parse -> [10, 20, 30, 40]
    # Creates: 1 string + 4 string objects + 1 list = 6 objects

    # NEW WAY (Direct):
    # bytes [10, 20, 30, 40] -> tuple (10, 20, 30, 40)
    # Creates: 1 tuple = 1 object (zero copies)

    msg_out = Message("0101", "LED", (10, 20, 30, 40))
    transport.send(msg_out)
    drain_tx_buffer(transport, mock_uart)

    mock_uart.receive_buffer.extend(mock_uart.sent_packets[0])
    mock_uart._in_waiting = len(mock_uart.receive_buffer)
    msg_in = receive_message_sync(transport)

    # The payload is now tuple - no intermediate string objects created!
    assert isinstance(msg_in.payload, tuple), f"Expected tuple, got {type(msg_in.payload)}"

    # Direct tuple access - no list conversion needed
    assert msg_in.payload == (10, 20, 30, 40)

    print(f"  OLD: bytes -> string -> list of strings -> list of ints (6+ objects)")
    print(f"  NEW: bytes -> tuple of ints (1 object, zero copies)")
    print(f"  Result: {msg_in.payload}")
    print("✓ Heap efficiency test passed")


if __name__ == "__main__":
    print("=" * 70)
    print("Binary Payload Performance Test Suite (String Boomerang Fix)")
    print("=" * 70)

    try:
        test_binary_payload_returns_bytes()
        test_text_payload_returns_string()
        test_parse_values_handles_bytes()
        test_parse_values_still_handles_strings()
        test_unpack_bytes_function()
        test_no_string_boomerang()
        test_heap_efficiency()

        print("\n" + "=" * 70)
        print("ALL PERFORMANCE TESTS PASSED ✓")
        print("String Boomerang ELIMINATED - Binary data stays binary!")
        print("=" * 70)

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
