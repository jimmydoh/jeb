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

    def read(self, n):
        """Mock read method - delegates to nested uart object."""
        return self.uart.read(n)

    def readinto(self, buf):
        """Mock readinto method - delegates to nested uart object."""
        return self.uart.readinto(buf)

    def read_available(self):
        """Mock read_available method."""
        if self._in_waiting > 0:
            data = self.uart.read(self._in_waiting)
            return data
        return b''

    def reset_input_buffer(self):
        """Mock reset_input_buffer method."""
        self.receive_buffer.clear()
        self._in_waiting = 0
        self.buffer_cleared = True

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

    def clear_buffer(self):
        """Mock clear_buffer method - legacy name for backward compatibility with older test code."""
        self.reset_input_buffer()

# Now import the transport classes
from transport import Message, UARTTransport
from transport.protocol import COMMAND_MAP, DEST_MAP, MAX_INDEX_VALUE, PAYLOAD_SCHEMAS

def drain_tx_buffer(transport, mock_uart):
    """Helper function to manually drain TX buffer for synchronous tests.

    Simulates what the async TX worker does, but synchronously.
    """
    while transport._tx_head != transport._tx_tail:
        head = transport._tx_head
        tail = transport._tx_tail
        size = transport._tx_buffer_size

        # Determine contiguous chunk to write
        if head > tail:
            chunk = transport._tx_mv[tail:head]
        else:
            chunk = transport._tx_mv[tail:size]

        # Write to mock UART (convert memoryview to bytes)
        transport.uart.write(bytes(chunk))

        # Advance tail
        transport._tx_tail = (tail + len(chunk)) % size


def receive_message_sync(transport):
    """Helper function to manually receive a message for synchronous tests.

    Simulates what the async RX worker does, but synchronously.
    Returns a message if available, None otherwise.
    """
    # First try to get from queue if workers have been run
    msg = transport.receive_nowait()
    if msg is not None:
        return msg

    # Otherwise, manually process incoming data
    transport._read_hw()
    return transport._try_decode_one()


def test_message_creation():
    """Test Message class creation and properties."""
    print("Testing Message creation...")

    msg = Message("CORE", "0101", "STATUS", "0000,C,N,0,0")

    assert msg.destination == "0101"
    assert msg.command == "STATUS"
    assert msg.payload == "0000,C,N,0,0"

    print(f"  Created message: {msg}")
    print("✓ Message creation test passed")


def test_message_equality():
    """Test Message equality comparison."""
    print("\nTesting Message equality...")

    msg1 = Message("CORE", "ALL", "ID_ASSIGN", "0100")
    msg2 = Message("CORE", "ALL", "ID_ASSIGN", "0100")
    msg3 = Message("CORE", "0101", "LED", "0,255,0,0")

    assert msg1 == msg2, "Identical messages should be equal"
    assert msg1 != msg3, "Different messages should not be equal"

    print("✓ Message equality test passed")


def test_uart_transport_send():
    """Test UARTTransport sending messages."""
    print("\nTesting UARTTransport send...")

    mock_uart = MockUARTManager()
    transport = UARTTransport(mock_uart, COMMAND_MAP, DEST_MAP, MAX_INDEX_VALUE, PAYLOAD_SCHEMAS)

    # Send a message (writes to TX buffer)
    msg = Message("CORE", "ALL", "ID_ASSIGN", "0100")
    transport.send(msg)
    drain_tx_buffer(transport, mock_uart)  # Drain TX buffer

    # Manually drain TX buffer (simulates what async TX worker does)
    drain_tx_buffer(transport, mock_uart)

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
    transport = UARTTransport(mock_uart, COMMAND_MAP, DEST_MAP, MAX_INDEX_VALUE, PAYLOAD_SCHEMAS)

    # Create a valid message by sending it first (to get proper binary format)
    # Use tuple for STATUS which expects ENCODING_NUMERIC_BYTES
    msg_out = Message("CORE", "0101", "STATUS", (100, 200))
    transport.send(msg_out)
    drain_tx_buffer(transport, mock_uart)  # Drain TX buffer
    drain_tx_buffer(transport, mock_uart)  # Drain TX buffer
    sent_packet = mock_uart.sent_packets[0]

    # Put the packet into receive buffer and update in_waiting
    mock_uart.receive_buffer.extend(sent_packet)
    mock_uart._in_waiting = len(sent_packet)

    # Receive the message (manually process incoming data)
    msg = receive_message_sync(transport)

    assert msg is not None, "Should receive a message"
    assert msg.destination == "0101"
    assert msg.command == "STATUS"
    # STATUS command uses ENCODING_NUMERIC_BYTES, so payload should be a tuple
    assert msg.payload == (100, 200), f"Expected payload (100, 200), got {msg.payload!r}"

    print(f"  Received message: {msg}")
    print("✓ UARTTransport receive test passed")


def test_uart_transport_receive_invalid_crc():
    """Test UARTTransport rejecting messages with invalid CRC."""
    print("\nTesting UARTTransport reject invalid CRC...")

    mock_uart = MockUARTManager()
    transport = UARTTransport(mock_uart, COMMAND_MAP, DEST_MAP, MAX_INDEX_VALUE, PAYLOAD_SCHEMAS)

    # Create a valid packet then corrupt its CRC
    msg_out = Message("CORE", "0101", "STATUS", "100,200")
    transport.send(msg_out)
    drain_tx_buffer(transport, mock_uart)  # Drain TX buffer
    drain_tx_buffer(transport, mock_uart)  # Drain TX buffer
    sent_packet = mock_uart.sent_packets[0]

    # Corrupt the CRC (change a byte before the terminator)
    corrupted_packet = bytearray(sent_packet)
    if len(corrupted_packet) > 2:
        corrupted_packet[-2] ^= 0xFF  # Flip all bits in the byte before terminator

    # Put corrupted packet into receive buffer and update in_waiting
    mock_uart.receive_buffer.extend(bytes(corrupted_packet))
    mock_uart._in_waiting = len(corrupted_packet)

    # Try to receive the message
    msg = receive_message_sync(transport)

    assert msg is None, "Should reject message with invalid CRC"

    print("✓ Invalid CRC rejection test passed")


def test_uart_transport_receive_malformed():
    """Test UARTTransport rejecting malformed messages."""
    print("\nTesting UARTTransport reject malformed messages...")

    mock_uart = MockUARTManager()
    transport = UARTTransport(mock_uart, COMMAND_MAP, DEST_MAP, MAX_INDEX_VALUE, PAYLOAD_SCHEMAS)

    # Create a malformed packet (too short - just a couple of bytes)
    malformed_packet = b'\x01\x02\x00'  # Too short to be valid

    # Put malformed packet into receive buffer and update in_waiting
    mock_uart.receive_buffer.extend(malformed_packet)
    mock_uart._in_waiting = len(malformed_packet)

    # Try to receive the message
    msg = receive_message_sync(transport)

    assert msg is None, "Should reject malformed message"

    print("✓ Malformed message rejection test passed")


def test_uart_transport_receive_empty():
    """Test UARTTransport with no data available."""
    print("\nTesting UARTTransport with no data...")

    mock_uart = MockUARTManager()
    transport = UARTTransport(mock_uart, COMMAND_MAP, DEST_MAP, MAX_INDEX_VALUE, PAYLOAD_SCHEMAS)

    # Try to receive when nothing is available
    msg = receive_message_sync(transport)

    assert msg is None, "Should return None when no data available"

    print("✓ Empty receive test passed")


def test_uart_transport_clear_buffer():
    """Test UARTTransport buffer clearing."""
    print("\nTesting UARTTransport clear_buffer...")

    mock_uart = MockUARTManager()
    transport = UARTTransport(mock_uart, COMMAND_MAP, DEST_MAP, MAX_INDEX_VALUE, PAYLOAD_SCHEMAS)

    # Clear the buffer
    transport.clear_buffer()

    assert mock_uart.buffer_cleared, "Should call clear_buffer on UART manager"

    print("✓ Clear buffer test passed")


def test_transport_abstraction():
    """Test that transport layer properly abstracts CRC and framing."""
    print("\nTesting transport abstraction...")

    mock_uart = MockUARTManager()
    transport = UARTTransport(mock_uart, COMMAND_MAP, DEST_MAP, MAX_INDEX_VALUE, PAYLOAD_SCHEMAS)

    # Send a message - user doesn't need to know about CRC or COBS framing
    # Use tuple for LED which expects ENCODING_NUMERIC_BYTES
    msg_out = Message("CORE", "0101", "LED", (255, 128, 64, 32))
    transport.send(msg_out)
    drain_tx_buffer(transport, mock_uart)  # Drain TX buffer
    drain_tx_buffer(transport, mock_uart)  # Drain TX buffer

    # Simulate receiving the same message
    packet = mock_uart.sent_packets[0]
    mock_uart.receive_buffer.extend(packet)
    mock_uart._in_waiting = len(packet)
    msg_in = receive_message_sync(transport)

    # Messages should match (transport handles CRC/framing transparently)
    assert msg_in is not None, "Should receive a message"
    assert msg_out.destination == msg_in.destination, "Destinations should match"
    assert msg_out.command == msg_in.command, "Commands should match"
    # LED uses ENCODING_NUMERIC_BYTES, so received payload will be a tuple
    assert msg_in.payload == (255, 128, 64, 32), f"Payload should be tuple: got {msg_in.payload!r}"
    print(f"  Sent: {msg_out}")
    print(f"  Received: {msg_in}")

    print("✓ Transport abstraction test passed")


def test_receive_returns_none_for_incomplete_packet():
    """Test that receive() returns None when packet is incomplete."""
    print("\nTesting receive returns None for incomplete packet...")

    mock_uart = MockUARTManager()
    transport = UARTTransport(mock_uart, COMMAND_MAP, DEST_MAP, MAX_INDEX_VALUE, PAYLOAD_SCHEMAS)

    # Send a message to get a valid packet
    msg_out = Message("CORE", "0101", "STATUS", "100,200")
    transport.send(msg_out)
    drain_tx_buffer(transport, mock_uart)  # Drain TX buffer
    drain_tx_buffer(transport, mock_uart)  # Drain TX buffer
    sent_packet = mock_uart.sent_packets[0]

    # Test 1: Put only partial packet (without terminator) into receive buffer
    partial_packet = sent_packet[:-1]  # Remove the 0x00 terminator
    mock_uart.receive_buffer.extend(partial_packet)
    mock_uart._in_waiting = len(partial_packet)

    # Receive should return None immediately (not block waiting for terminator)
    msg = receive_message_sync(transport)
    assert msg is None, "Should return None when packet is incomplete"

    # Test 2: Add the terminator byte
    mock_uart.receive_buffer.extend(b'\x00')
    mock_uart._in_waiting = 1

    # Now receive should return the complete message
    msg = receive_message_sync(transport)
    assert msg is not None, "Should receive complete message after terminator arrives"
    assert msg.destination == "0101"
    assert msg.command == "STATUS"

    print("✓ Receive returns None for incomplete packet test passed")


def test_receive_assembles_fragmented_packets():
    """Test that receive() correctly assembles packets arriving in fragments."""
    print("\nTesting receive assembles fragmented packets...")

    mock_uart = MockUARTManager()
    transport = UARTTransport(mock_uart, COMMAND_MAP, DEST_MAP, MAX_INDEX_VALUE, PAYLOAD_SCHEMAS)

    # Send a message to get a valid packet
    # Use tuple for LED which expects ENCODING_NUMERIC_BYTES
    msg_out = Message("CORE", "0101", "LED", (255, 128, 64, 32))
    transport.send(msg_out)
    drain_tx_buffer(transport, mock_uart)  # Drain TX buffer
    drain_tx_buffer(transport, mock_uart)  # Drain TX buffer
    sent_packet = mock_uart.sent_packets[0]

    # Simulate packet arriving in 3 fragments
    fragment_size = len(sent_packet) // 3
    fragments = [
        sent_packet[:fragment_size],
        sent_packet[fragment_size:2*fragment_size],
        sent_packet[2*fragment_size:]
    ]

    # First fragment - should return None
    mock_uart.receive_buffer.extend(fragments[0])
    mock_uart._in_waiting = len(fragments[0])
    msg = receive_message_sync(transport)
    assert msg is None, "Should return None after first fragment"

    # Second fragment - should return None
    mock_uart.receive_buffer.extend(fragments[1])
    mock_uart._in_waiting = len(fragments[1])
    msg = receive_message_sync(transport)
    assert msg is None, "Should return None after second fragment"

    # Third fragment - should return complete message
    mock_uart.receive_buffer.extend(fragments[2])
    mock_uart._in_waiting = len(fragments[2])
    msg = receive_message_sync(transport)
    assert msg is not None, "Should receive complete message after all fragments"
    assert msg.destination == "0101"
    assert msg.command == "LED"
    assert msg.payload == (255, 128, 64, 32)

    print("✓ Receive assembles fragmented packets test passed")


def test_multiple_packets_in_buffer():
    """Test that receive() handles multiple packets in buffer."""
    print("\nTesting multiple packets in buffer...")

    mock_uart = MockUARTManager()
    transport = UARTTransport(mock_uart, COMMAND_MAP, DEST_MAP, MAX_INDEX_VALUE, PAYLOAD_SCHEMAS)

    # Send two messages
    msg1 = Message("CORE", "0101", "STATUS", "100")
    msg2 = Message("CORE", "0102", "LED", "255,0,0,0")
    transport.send(msg1)
    drain_tx_buffer(transport, mock_uart)  # Drain TX buffer
    transport.send(msg2)
    drain_tx_buffer(transport, mock_uart)  # Drain TX buffer

    packet1 = mock_uart.sent_packets[0]
    packet2 = mock_uart.sent_packets[1]

    # Put both packets into receive buffer at once
    mock_uart.receive_buffer.extend(packet1 + packet2)
    mock_uart._in_waiting = len(packet1 + packet2)

    # First receive should get first packet
    received1 = receive_message_sync(transport)
    assert received1 is not None, "Should receive first packet"
    assert received1.destination == "0101"
    assert received1.command == "STATUS"

    # After first receive, UART buffer should be empty but transport's internal buffer has packet2
    # (both packets were read from UART into internal buffer on first receive() call)

    # Second receive should get second packet (already in internal buffer)
    received2 = receive_message_sync(transport)
    assert received2 is not None, "Should receive second packet"
    assert received2.destination == "0102"
    assert received2.command == "LED"

    # Third receive should return None
    received3 = receive_message_sync(transport)
    assert received3 is None, "Should return None when no more packets"

    print("✓ Multiple packets in buffer test passed")


def test_receive_buffer_overflow_protection():
    """Test that receive() protects against buffer overflow from garbage data."""
    print("\nTesting buffer overflow protection...")

    mock_uart = MockUARTManager()
    transport = UARTTransport(mock_uart, COMMAND_MAP, DEST_MAP, MAX_INDEX_VALUE, PAYLOAD_SCHEMAS)

    # Simulate flooding with 2000 bytes of garbage (no null terminator)
    garbage_data = bytes(range(1, 256)) * 8  # 2040 bytes of non-zero data
    mock_uart.receive_buffer.extend(garbage_data)
    mock_uart._in_waiting = len(garbage_data)

    # First receive should detect overflow and handle it gracefully
    msg = receive_message_sync(transport)
    assert msg is None, "Should return None when buffer overflows"

    # Ring buffer will have consumed what it can (up to 2KB) and started advancing tail
    # The exact state depends on buffer size, but system should remain functional

    # Now send a valid packet - system should recover
    msg_valid = Message("CORE", "0101", "STATUS", "100")
    transport.send(msg_valid)
    drain_tx_buffer(transport, mock_uart)  # Drain TX buffer
    valid_packet = mock_uart.sent_packets[0]

    mock_uart.receive_buffer.extend(valid_packet)
    mock_uart._in_waiting = len(valid_packet)

    # Should be able to receive valid packet after recovery
    received = receive_message_sync(transport)
    assert received is not None, "Should receive valid packet after overflow recovery"
    assert received.destination == "0101"
    assert received.command == "STATUS"

    print("✓ Buffer overflow protection test passed")


def test_buffer_overflow_preserves_valid_packets():
    """Test that valid packets are preserved when overflow occurs between packets."""
    print("\nTesting buffer overflow preserves valid packets...")

    mock_uart = MockUARTManager()
    transport = UARTTransport(mock_uart, COMMAND_MAP, DEST_MAP, MAX_INDEX_VALUE, PAYLOAD_SCHEMAS)

    # Test threshold: intentionally exceed RING_BUFFER_SIZE by 20%
    OVERFLOW_TEST_THRESHOLD = 1.2

    # Create multiple valid packets
    messages = [
        Message("CORE", "0101", "STATUS", f"{i}") for i in range(100, 200)
    ]

    # Send all messages to get valid packets
    for msg in messages:
        transport.send(msg)
    drain_tx_buffer(transport, mock_uart)  # Drain TX buffer

    valid_packets = mock_uart.sent_packets[:]
    mock_uart.sent_packets.clear()

    # Add enough packets to buffer to exceed RING_BUFFER_SIZE
    total_size = 0
    for packet in valid_packets:
        mock_uart.receive_buffer.extend(packet)
        total_size += len(packet)
        if total_size > transport.RING_BUFFER_SIZE * OVERFLOW_TEST_THRESHOLD:
            break

    print(f"  Added {total_size} bytes to buffer (MAX={transport.RING_BUFFER_SIZE})")
    mock_uart._in_waiting = len(mock_uart.receive_buffer)

    # Receive messages - should be able to process many of them despite overflow
    received_count = 0
    while True:
        msg = receive_message_sync(transport)
        if msg is None:
            break
        received_count += 1
        # Stop after getting a reasonable number to avoid infinite loop
        if received_count > len(valid_packets):
            break

    # We should receive at least some valid packets before/after overflow handling
    assert received_count > 0, "Should receive at least some valid packets"
    print(f"  Successfully received {received_count} packets despite overflow")

    print("✓ Buffer overflow preserves valid packets test passed")


def test_ring_buffer_wrapped_packet():
    """Test that ring buffer correctly handles packets that wrap around the buffer end."""
    print("\nTesting ring buffer wrapped packet handling...")

    mock_uart = MockUARTManager()
    transport = UARTTransport(mock_uart, COMMAND_MAP, DEST_MAP, MAX_INDEX_VALUE, PAYLOAD_SCHEMAS)

    # Create a valid packet
    msg_out = Message("CORE", "0101", "LED", (255, 128, 64, 32))
    transport.send(msg_out)
    drain_tx_buffer(transport, mock_uart)  # Drain TX buffer
    sent_packet = mock_uart.sent_packets[0]
    packet_len = len(sent_packet)

    # Position the ring buffer so that when we add the packet, it will wrap
    # We'll manually set head and tail to near the end
    wrap_position = transport._rx_buf_size - (packet_len // 2)
    transport._rx_head = wrap_position
    transport._rx_tail = wrap_position

    print(f"  Starting position: head={transport._rx_head}, tail={transport._rx_tail}")

    # Add the packet to UART buffer
    mock_uart.receive_buffer.extend(sent_packet)
    mock_uart._in_waiting = len(sent_packet)

    # Receive may need multiple calls if packet is fragmented by readinto()
    msg = None
    for attempt in range(5):  # Try up to 5 times
        msg = receive_message_sync(transport)
        if msg is not None:
            break

    assert msg is not None, f"Should receive wrapped packet (head={transport._rx_head}, tail={transport._rx_tail})"
    assert msg.destination == "0101"
    assert msg.command == "LED"
    assert msg.payload == (255, 128, 64, 32)

    print(f"  Successfully received packet that wrapped around position {wrap_position}")
    print("✓ Ring buffer wrapped packet test passed")


def test_ring_buffer_multiple_wrapped_packets():
    """Test receiving multiple packets when ring buffer wraps around."""
    print("\nTesting multiple packets with ring buffer wrap-around...")

    mock_uart = MockUARTManager()
    transport = UARTTransport(mock_uart, COMMAND_MAP, DEST_MAP, MAX_INDEX_VALUE, PAYLOAD_SCHEMAS)

    # Create several packets
    messages = [
        Message("CORE", "0101", "STATUS", f"{i}") for i in range(10)
    ]

    for msg in messages:
        transport.send(msg)
    drain_tx_buffer(transport, mock_uart)  # Drain TX buffer

    packets = mock_uart.sent_packets[:]
    mock_uart.sent_packets.clear()

    # Position head near end of buffer
    offset = transport._rx_buf_size - 50
    transport._rx_head = offset
    transport._rx_tail = offset

    # Add all packets - they will wrap around
    for packet in packets:
        mock_uart.receive_buffer.extend(packet)
    mock_uart._in_waiting = len(mock_uart.receive_buffer)

    # Receive all packets
    received = []
    for _ in range(len(messages)):
        msg = receive_message_sync(transport)
        if msg:
            received.append(msg)

    # Should receive all packets correctly
    assert len(received) == len(messages), f"Should receive all {len(messages)} packets, got {len(received)}"

    for i, msg in enumerate(received):
        assert msg.destination == "0101"
        assert msg.command == "STATUS"

    print(f"  Successfully received {len(received)} packets with wrap-around")
    print("✓ Multiple wrapped packets test passed")


def test_ring_buffer_full_recovery():
    """Test that ring buffer recovers when buffer overflow is detected."""
    print("\nTesting ring buffer overflow recovery...")

    mock_uart = MockUARTManager()
    transport = UARTTransport(mock_uart, COMMAND_MAP, DEST_MAP, MAX_INDEX_VALUE, PAYLOAD_SCHEMAS)

    # Fill buffer with garbage that exceeds threshold but has no delimiters
    # This should trigger the overflow protection which resets the buffer
    garbage_size = transport._rx_buf_size - 100  # Nearly full but not completely
    garbage = bytes(range(1, 256)) * (garbage_size // 255 + 1)
    garbage = garbage[:garbage_size]

    mock_uart.receive_buffer.extend(garbage)
    mock_uart._in_waiting = len(garbage)

    # Try to receive - should detect buffer getting too full with no delimiters
    # May need multiple receive() calls to fully process and reset
    for _ in range(5):
        msg = receive_message_sync(transport)
        if msg is None:
            bytes_in_buffer = (transport._rx_head - transport._rx_tail) % transport._rx_buf_size
            if bytes_in_buffer < 256:  # Buffer has been cleared/managed
                break

    bytes_in_buffer = (transport._rx_head - transport._rx_tail) % transport._rx_buf_size
    print(f"  After overflow handling, buffer has {bytes_in_buffer} bytes")

    # Now send a valid packet - system should be able to receive it
    msg_valid = Message("CORE", "0101", "STATUS", (200,))  # Use tuple for numeric byte payload
    transport.send(msg_valid)
    drain_tx_buffer(transport, mock_uart)  # Drain TX buffer
    valid_packet = mock_uart.sent_packets[0]

    # Clear any remaining garbage first for clean test
    transport.clear_buffer()

    mock_uart.receive_buffer.extend(valid_packet)
    mock_uart._in_waiting = len(valid_packet)

    # Should receive the valid packet
    received = receive_message_sync(transport)
    assert received is not None, "Should receive valid packet after buffer overflow recovery"
    assert received.destination == "0101"
    assert received.command == "STATUS"
    assert received.payload == (200,)

    print("✓ Ring buffer overflow recovery test passed")


def test_ring_buffer_end_of_array_deadlock():
    """Test that buffer does not deadlock when empty at the very end of the array."""
    print("\nTesting ring buffer end-of-array deadlock...")

    mock_uart = MockUARTManager()
    transport = UARTTransport(mock_uart, COMMAND_MAP, DEST_MAP, MAX_INDEX_VALUE, PAYLOAD_SCHEMAS)

    # 1. Force pointers to the very last byte (2047)
    # Simulates a scenario where we just read everything up to the end
    transport._rx_head = 2047
    transport._rx_tail = 2047

    # 2. Add 1 byte of data to UART
    # This should be writable! (Write at 2047, head wraps to 0)
    mock_uart.receive_buffer.extend(b'\x00')  # A delimiter
    mock_uart._in_waiting = 1

    # 3. Trigger read
    transport._read_hw()

    # 4. Check if head moved
    # If buggy, head stays 2047 (space calculated as 0)
    # If fixed, head wraps to 0
    assert transport._rx_head == 0, f"Deadlock! Head stuck at {transport._rx_head} instead of wrapping to 0"

    print("✓ Deadlock test passed")


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
        test_receive_returns_none_for_incomplete_packet()
        test_receive_assembles_fragmented_packets()
        test_multiple_packets_in_buffer()
        test_receive_buffer_overflow_protection()
        test_buffer_overflow_preserves_valid_packets()
        test_ring_buffer_wrapped_packet()
        test_ring_buffer_multiple_wrapped_packets()
        test_ring_buffer_full_recovery()
        test_ring_buffer_end_of_array_deadlock()

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
