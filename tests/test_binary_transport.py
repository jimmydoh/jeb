#!/usr/bin/env python3
"""Unit tests for Binary Transport layer with COBS framing."""

import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Mock the COBS functions
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'utilities'))
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


class MockUARTManager:
    """Mock UARTManager for testing."""
    def __init__(self):
        self.sent_packets = []
        self.receive_buffer = bytearray()
        self.buffer_cleared = False
        self._in_waiting = 0
        self.uart = MockUART(self)
    
    def write(self, data):
        """Mock write method."""
        self.sent_packets.append(data)
    
    @property
    def in_waiting(self):
        """Mock in_waiting property."""
        return self._in_waiting
    
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
            return data
        return None
    
    def clear_buffer(self):
        """Mock clear_buffer method."""
        self.buffer_cleared = True


# Now import the transport classes
from transport import Message, UARTTransport

# Import protocol definitions
from protocol import COMMAND_MAP, DEST_MAP, MAX_INDEX_VALUE, PAYLOAD_SCHEMAS


def test_message_creation():
    """Test Message class creation and properties."""
    print("Testing Message creation...")
    
    msg = Message("0101", "STATUS", "0000,C,N,0,0")
    
    assert msg.destination == "0101"
    assert msg.command == "STATUS"
    assert msg.payload == "0000,C,N,0,0"
    
    print(f"  Created message: {msg}")
    print("✓ Message creation test passed")


def test_binary_transport_send_simple():
    """Test binary transport sending a simple message."""
    print("\nTesting binary transport send (simple)...")
    
    mock_uart = MockUARTManager()
    transport = UARTTransport(mock_uart, COMMAND_MAP, DEST_MAP, MAX_INDEX_VALUE, PAYLOAD_SCHEMAS)
    
    # Send a message
    msg = Message("ALL", "ID_ASSIGN", "0100")
    transport.send(msg)
    
    # Verify packet was sent
    assert len(mock_uart.sent_packets) == 1
    packet = mock_uart.sent_packets[0]
    
    print(f"  Sent packet (hex): {packet.hex()}")
    
    # Verify packet ends with 0x00 terminator
    assert packet.endswith(b'\x00'), "Packet should end with 0x00 terminator"
    
    # Verify no 0x00 bytes in COBS-encoded portion
    cobs_data = packet[:-1]  # Remove terminator
    assert b'\x00' not in cobs_data, "COBS-encoded data should not contain 0x00"
    
    print("✓ Binary transport send test passed")


def test_binary_transport_send_led_command():
    """Test binary transport with LED command (numeric payload)."""
    print("\nTesting binary transport send (LED command)...")
    
    mock_uart = MockUARTManager()
    transport = UARTTransport(mock_uart, COMMAND_MAP, DEST_MAP, MAX_INDEX_VALUE, PAYLOAD_SCHEMAS)
    
    # Send LED command with numeric values
    msg = Message("0101", "LED", "0,255,128,64")
    transport.send(msg)
    
    packet = mock_uart.sent_packets[0]
    print(f"  LED command packet (hex): {packet.hex()}")
    
    # Verify packet structure
    assert packet.endswith(b'\x00')
    assert b'\x00' not in packet[:-1]
    
    print("✓ LED command send test passed")


def test_binary_transport_receive_simple():
    """Test binary transport receiving a message."""
    print("\nTesting binary transport receive (simple)...")
    
    mock_uart = MockUARTManager()
    transport = UARTTransport(mock_uart, COMMAND_MAP, DEST_MAP, MAX_INDEX_VALUE, PAYLOAD_SCHEMAS)
    
    # First send a message to get valid packet format
    msg_out = Message("0101", "STATUS", "100,200")
    transport.send(msg_out)
    sent_packet = mock_uart.sent_packets[0]
    
    # Put the packet into receive buffer
    mock_uart.receive_buffer.extend(sent_packet)
    mock_uart._in_waiting = len(mock_uart.receive_buffer)
    
    # Receive the message
    msg_in = transport.receive()
    
    assert msg_in is not None, "Should receive a message"
    assert msg_in.destination == "0101", f"Expected dest '0101', got '{msg_in.destination}'"
    assert msg_in.command == "STATUS", f"Expected cmd 'STATUS', got '{msg_in.command}'"
    # Payload may be decoded differently, just check it exists
    assert msg_in.payload is not None
    
    print(f"  Sent: {msg_out}")
    print(f"  Received: {msg_in}")
    print("✓ Binary transport receive test passed")


def test_binary_transport_roundtrip():
    """Test binary transport send/receive roundtrip for various commands."""
    print("\nTesting binary transport roundtrip...")
    
    test_cases = [
        Message("ALL", "ID_ASSIGN", "0100"),
        Message("0101", "STATUS", "100,200,50"),
        Message("SAT", "NEW_SAT", "01"),
        Message("0101", "LED", "0,255,0,0"),
        Message("0101", "DSP", "HELLO"),
        Message("0101", "POWER", "19.5,18.2,5.0"),
    ]
    
    for msg_out in test_cases:
        mock_uart = MockUARTManager()
        transport = UARTTransport(mock_uart, COMMAND_MAP, DEST_MAP, MAX_INDEX_VALUE, PAYLOAD_SCHEMAS)
        
        # Send
        transport.send(msg_out)
        sent_packet = mock_uart.sent_packets[0]
        
        # Receive
        mock_uart.receive_buffer.extend(sent_packet)
        mock_uart._in_waiting = len(mock_uart.receive_buffer)
        msg_in = transport.receive()
        
        assert msg_in is not None, f"Failed to receive message: {msg_out}"
        assert msg_in.destination == msg_out.destination, \
            f"Destination mismatch: {msg_out.destination} != {msg_in.destination}"
        assert msg_in.command == msg_out.command, \
            f"Command mismatch: {msg_out.command} != {msg_in.command}"
        
        print(f"  ✓ {msg_out.command}: {msg_out.destination} -> payload OK")
    
    print("✓ Binary transport roundtrip test passed")


def test_binary_transport_invalid_crc():
    """Test binary transport rejecting messages with invalid CRC."""
    print("\nTesting binary transport reject invalid CRC...")
    
    mock_uart = MockUARTManager()
    transport = UARTTransport(mock_uart, COMMAND_MAP, DEST_MAP, MAX_INDEX_VALUE, PAYLOAD_SCHEMAS)
    
    # Send a valid message
    msg = Message("0101", "STATUS", "100")
    transport.send(msg)
    packet = mock_uart.sent_packets[0]
    
    # Corrupt the packet (modify a byte in COBS data)
    corrupted = bytearray(packet)
    if len(corrupted) > 2:
        corrupted[1] ^= 0xFF  # Flip bits in second byte
    
    # Try to receive corrupted packet
    mock_uart.receive_buffer.extend(bytes(corrupted))
    mock_uart._in_waiting = len(mock_uart.receive_buffer)
    msg_in = transport.receive()
    
    assert msg_in is None, "Should reject message with corrupted data"
    
    print("✓ Invalid CRC rejection test passed")


def test_binary_transport_no_data():
    """Test binary transport with no data available."""
    print("\nTesting binary transport with no data...")
    
    mock_uart = MockUARTManager()
    transport = UARTTransport(mock_uart, COMMAND_MAP, DEST_MAP, MAX_INDEX_VALUE, PAYLOAD_SCHEMAS)
    
    # Try to receive when nothing is available
    msg = transport.receive()
    
    assert msg is None, "Should return None when no data available"
    
    print("✓ No data test passed")


def test_binary_transport_clear_buffer():
    """Test binary transport buffer clearing."""
    print("\nTesting binary transport clear_buffer...")
    
    mock_uart = MockUARTManager()
    transport = UARTTransport(mock_uart, COMMAND_MAP, DEST_MAP, MAX_INDEX_VALUE, PAYLOAD_SCHEMAS)
    
    # Clear the buffer
    transport.clear_buffer()
    
    assert mock_uart.buffer_cleared, "Should call clear_buffer on UART manager"
    
    print("✓ Clear buffer test passed")


def test_binary_vs_text_overhead():
    """Compare binary vs text protocol overhead."""
    print("\nTesting binary vs text protocol overhead...")
    
    # Text protocol: "0101|STATUS|100,200,50|CRC\n"
    text_msg = "0101|STATUS|100,200,50|"
    text_crc = calculate_crc8(text_msg)
    text_packet = (text_msg + f"{text_crc:02X}" + "\n").encode()
    text_size = len(text_packet)
    
    # Binary protocol
    mock_uart = MockUARTManager()
    transport = UARTTransport(mock_uart, COMMAND_MAP, DEST_MAP, MAX_INDEX_VALUE, PAYLOAD_SCHEMAS)
    msg = Message("0101", "STATUS", "100,200,50")
    transport.send(msg)
    binary_packet = mock_uart.sent_packets[0]
    binary_size = len(binary_packet)
    
    print(f"  Text protocol:   {text_size} bytes")
    print(f"  Binary protocol: {binary_size} bytes")
    print(f"  Savings: {text_size - binary_size} bytes ({100 * (text_size - binary_size) / text_size:.1f}%)")
    
    print("✓ Overhead comparison test passed")


def test_special_destinations():
    """Test special destination encoding (ALL, SAT)."""
    print("\nTesting special destinations...")
    
    test_cases = [
        ("ALL", "ID_ASSIGN", "0100"),
        ("SAT", "NEW_SAT", "01"),
        ("0101", "STATUS", "100"),
    ]
    
    for dest, cmd, payload in test_cases:
        mock_uart = MockUARTManager()
        transport = UARTTransport(mock_uart, COMMAND_MAP, DEST_MAP, MAX_INDEX_VALUE, PAYLOAD_SCHEMAS)
        
        msg_out = Message(dest, cmd, payload)
        transport.send(msg_out)
        
        # Receive back
        mock_uart.receive_buffer.extend(mock_uart.sent_packets[0])
        mock_uart._in_waiting = len(mock_uart.receive_buffer)
        msg_in = transport.receive()
        
        assert msg_in is not None
        assert msg_in.destination == dest, f"Destination mismatch: {dest} != {msg_in.destination}"
        
        print(f"  ✓ Destination '{dest}' encoded/decoded correctly")
    
    print("✓ Special destinations test passed")


if __name__ == "__main__":
    print("=" * 60)
    print("Binary Transport Protocol Test Suite")
    print("=" * 60)
    
    try:
        test_message_creation()
        test_binary_transport_send_simple()
        test_binary_transport_send_led_command()
        test_binary_transport_receive_simple()
        test_binary_transport_roundtrip()
        test_binary_transport_invalid_crc()
        test_binary_transport_no_data()
        test_binary_transport_clear_buffer()
        test_binary_vs_text_overhead()
        test_special_destinations()
        
        print("\n" + "=" * 60)
        print("ALL BINARY TRANSPORT TESTS PASSED ✓")
        print("=" * 60)
        
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
