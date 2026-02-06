#!/usr/bin/env python3
"""Unit tests for Transport layer abstraction."""

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


def verify_crc8(packet):
    """Verify CRC-8 checksum of a received packet."""
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
    
    # Compare CRCs (handle type mismatch)
    if isinstance(received_crc, str):
        # Convert integer CRC to hex string for comparison
        calculated_crc_str = f"{calculated_crc:02X}"
        return calculated_crc_str == received_crc, data
    
    return calculated_crc == received_crc, data


# Mock utilities module
class MockUtilities:
    cobs_encode = staticmethod(cobs.cobs_encode)
    cobs_decode = staticmethod(cobs.cobs_decode)
    calculate_crc8 = staticmethod(calculate_crc8)
    verify_crc8 = staticmethod(verify_crc8)

sys.modules['utilities'] = MockUtilities()


# Mock the UARTManager
class MockUARTManager:
    """Mock UARTManager for testing."""
    def __init__(self):
        self.sent_packets = []
        self.receive_buffer = bytearray()
        self.buffer_cleared = False
    
    def write(self, data):
        """Mock write method."""
        self.sent_packets.append(data)
    
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


def test_message_creation():
    """Test Message class creation and properties."""
    print("Testing Message creation...")
    
    msg = Message("0101", "STATUS", "0000,C,N,0,0")
    
    assert msg.destination == "0101"
    assert msg.command == "STATUS"
    assert msg.payload == "0000,C,N,0,0"
    
    print(f"  Created message: {msg}")
    print("✓ Message creation test passed")


def test_message_equality():
    """Test Message equality comparison."""
    print("\nTesting Message equality...")
    
    msg1 = Message("ALL", "ID_ASSIGN", "0100")
    msg2 = Message("ALL", "ID_ASSIGN", "0100")
    msg3 = Message("0101", "LED", "0,255,0,0")
    
    assert msg1 == msg2, "Identical messages should be equal"
    assert msg1 != msg3, "Different messages should not be equal"
    
    print("✓ Message equality test passed")


def test_uart_transport_send():
    """Test UARTTransport sending messages."""
    print("\nTesting UARTTransport send...")
    
    mock_uart = MockUARTManager()
    transport = UARTTransport(mock_uart)
    
    # Send a message
    msg = Message("ALL", "ID_ASSIGN", "0100")
    transport.send(msg)
    
    # Verify packet was sent
    assert len(mock_uart.sent_packets) == 1
    packet = mock_uart.sent_packets[0]
    
    print(f"  Sent packet (hex): {packet.hex()}")
    
    # Verify packet ends with 0x00 terminator (binary protocol with COBS framing)
    assert packet.endswith(b'\x00'), "Packet should end with 0x00 terminator"
    
    # Verify no 0x00 bytes in COBS-encoded portion
    cobs_data = packet[:-1]  # Remove terminator
    assert b'\x00' not in cobs_data, "COBS-encoded data should not contain 0x00"
    
    print("✓ UARTTransport send test passed")


def test_uart_transport_receive():
    """Test UARTTransport receiving messages."""
    print("\nTesting UARTTransport receive...")
    
    mock_uart = MockUARTManager()
    transport = UARTTransport(mock_uart)
    
    # Create a valid message by sending it first (to get proper binary format)
    msg_out = Message("0101", "STATUS", "100,200")
    transport.send(msg_out)
    sent_packet = mock_uart.sent_packets[0]
    
    # Put the packet into receive buffer
    mock_uart.receive_buffer.extend(sent_packet)
    
    # Receive the message
    msg = transport.receive()
    
    assert msg is not None, "Should receive a message"
    assert msg.destination == "0101"
    assert msg.command == "STATUS"
    assert msg.payload == "100,200", f"Expected payload '100,200', got '{msg.payload}'"
    
    print(f"  Received message: {msg}")
    print("✓ UARTTransport receive test passed")


def test_uart_transport_receive_invalid_crc():
    """Test UARTTransport rejecting messages with invalid CRC."""
    print("\nTesting UARTTransport reject invalid CRC...")
    
    mock_uart = MockUARTManager()
    transport = UARTTransport(mock_uart)
    
    # Create a valid packet then corrupt its CRC
    msg_out = Message("0101", "STATUS", "100,200")
    transport.send(msg_out)
    sent_packet = mock_uart.sent_packets[0]
    
    # Corrupt the CRC (change a byte before the terminator)
    corrupted_packet = bytearray(sent_packet)
    if len(corrupted_packet) > 2:
        corrupted_packet[-2] ^= 0xFF  # Flip all bits in the byte before terminator
    
    # Put corrupted packet into receive buffer
    mock_uart.receive_buffer.extend(bytes(corrupted_packet))
    
    # Try to receive the message
    msg = transport.receive()
    
    assert msg is None, "Should reject message with invalid CRC"
    
    print("✓ Invalid CRC rejection test passed")


def test_uart_transport_receive_malformed():
    """Test UARTTransport rejecting malformed messages."""
    print("\nTesting UARTTransport reject malformed messages...")
    
    mock_uart = MockUARTManager()
    transport = UARTTransport(mock_uart)
    
    # Create a malformed packet (too short - just a couple of bytes)
    malformed_packet = b'\x01\x02\x00'  # Too short to be valid
    
    # Put malformed packet into receive buffer
    mock_uart.receive_buffer.extend(malformed_packet)
    
    # Try to receive the message
    msg = transport.receive()
    
    assert msg is None, "Should reject malformed message"
    
    print("✓ Malformed message rejection test passed")


def test_uart_transport_receive_empty():
    """Test UARTTransport with no data available."""
    print("\nTesting UARTTransport with no data...")
    
    mock_uart = MockUARTManager()
    transport = UARTTransport(mock_uart)
    
    # Try to receive when nothing is available
    msg = transport.receive()
    
    assert msg is None, "Should return None when no data available"
    
    print("✓ Empty receive test passed")


def test_uart_transport_clear_buffer():
    """Test UARTTransport buffer clearing."""
    print("\nTesting UARTTransport clear_buffer...")
    
    mock_uart = MockUARTManager()
    transport = UARTTransport(mock_uart)
    
    # Clear the buffer
    transport.clear_buffer()
    
    assert mock_uart.buffer_cleared, "Should call clear_buffer on UART manager"
    
    print("✓ Clear buffer test passed")


def test_transport_abstraction():
    """Test that transport layer properly abstracts CRC and framing."""
    print("\nTesting transport abstraction...")
    
    mock_uart = MockUARTManager()
    transport = UARTTransport(mock_uart)
    
    # Send a message - user doesn't need to know about CRC or COBS framing
    msg_out = Message("0101", "LED", "255,128,64,32")
    transport.send(msg_out)
    
    # Simulate receiving the same message
    packet = mock_uart.sent_packets[0]
    mock_uart.receive_buffer.extend(packet)
    msg_in = transport.receive()
    
    # Messages should match (transport handles CRC/framing transparently)
    assert msg_in is not None, "Should receive a message"
    assert msg_out.destination == msg_in.destination, "Destinations should match"
    assert msg_out.command == msg_in.command, "Commands should match"
    assert msg_out.payload == msg_in.payload, f"Payloads should match: '{msg_out.payload}' != '{msg_in.payload}'"
    print(f"  Sent: {msg_out}")
    print(f"  Received: {msg_in}")
    
    print("✓ Transport abstraction test passed")


if __name__ == "__main__":
    print("=" * 60)
    print("Transport Layer Test Suite")
    print("=" * 60)
    
    try:
        test_message_creation()
        test_message_equality()
        test_uart_transport_send()
        test_uart_transport_receive()
        test_uart_transport_receive_invalid_crc()
        test_uart_transport_receive_malformed()
        test_uart_transport_receive_empty()
        test_uart_transport_clear_buffer()
        test_transport_abstraction()
        
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
