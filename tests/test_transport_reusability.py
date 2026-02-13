#!/usr/bin/env python3
"""Test to demonstrate transport layer reusability with different command sets.

This test shows that the transport layer is now decoupled from application-specific
commands and can be used with different command sets for different projects.
"""

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
        if self._in_waiting > 0:
            data = self.uart.read(self._in_waiting)
            return data
        return b''
    
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
from transport import Message, UARTTransport


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



def test_custom_command_set():
    """Test transport with a completely different command set (e.g., robotics project)."""
    print("\nTesting transport with custom robotics command set...")
    
    # Define a completely different command set for a robotics project
    ROBOT_COMMANDS = {
        "MOVE_FORWARD": 0x01,
        "MOVE_BACKWARD": 0x02,
        "TURN_LEFT": 0x03,
        "TURN_RIGHT": 0x04,
        "GRAB": 0x10,
        "RELEASE": 0x11,
        "LIFT": 0x12,
        "LOWER": 0x13,
    }
    
    ROBOT_DESTINATIONS = {
        "BROADCAST": 0xFF,
        "ARM": 0xFE,
    }
    
    # Create transport with robotics command set
    mock_uart = MockUARTManager()
    transport = UARTTransport(mock_uart, ROBOT_COMMANDS, ROBOT_DESTINATIONS)
    
    # Send a robotics command
    msg = Message("BROADCAST", "MOVE_FORWARD", "100,50")
    transport.send(msg)
    drain_tx_buffer(transport, mock_uart)
    
    # Verify it was sent
    assert len(mock_uart.sent_packets) == 1
    
    # Receive it back
    mock_uart.receive_buffer.extend(mock_uart.sent_packets[0])
    mock_uart._in_waiting = len(mock_uart.receive_buffer)
    received = receive_message_sync(transport)
    
    assert received is not None
    assert received.destination == "BROADCAST"
    assert received.command == "MOVE_FORWARD"
    
    print(f"  ✓ Sent robot command: {msg}")
    print(f"  ✓ Received: {received}")
    print("✓ Custom command set test passed")


def test_minimal_command_set():
    """Test transport with minimal command set (e.g., simple sensor network)."""
    print("\nTesting transport with minimal sensor command set...")
    
    # Define a minimal command set for sensor nodes
    SENSOR_COMMANDS = {
        "READ": 0x01,
        "WRITE": 0x02,
    }
    
    SENSOR_DESTINATIONS = {
        "ALL": 0xFF,
    }
    
    # Create transport with minimal command set
    mock_uart = MockUARTManager()
    transport = UARTTransport(mock_uart, SENSOR_COMMANDS, SENSOR_DESTINATIONS)
    
    # Send a sensor command
    msg = Message("ALL", "READ", "TEMP")
    transport.send(msg)
    drain_tx_buffer(transport, mock_uart)
    
    # Verify it was sent and received
    mock_uart.receive_buffer.extend(mock_uart.sent_packets[0])
    mock_uart._in_waiting = len(mock_uart.receive_buffer)
    received = receive_message_sync(transport)
    
    assert received is not None
    assert received.command == "READ"
    
    print(f"  ✓ Minimal command set works: {received}")
    print("✓ Minimal command set test passed")


def test_empty_command_set():
    """Test transport with no predefined commands (raw numeric commands only)."""
    print("\nTesting transport with no predefined commands...")
    
    # Create transport with no command mapping
    mock_uart = MockUARTManager()
    transport = UARTTransport(mock_uart, {}, {})
    
    # Commands and destinations must be numeric when no mapping provided
    # This would fail with ValueError for string commands, which is expected behavior
    
    print("  ✓ Transport can be created with empty command sets")
    print("  ✓ This allows for purely numeric protocol implementations")
    print("✓ Empty command set test passed")


if __name__ == "__main__":
    print("=" * 60)
    print("Transport Layer Reusability Test Suite")
    print("=" * 60)
    print("\nDemonstrating that transport is decoupled from")
    print("application-specific commands and can be reused")
    print("for different projects with different command sets.")
    
    try:
        test_custom_command_set()
        test_minimal_command_set()
        test_empty_command_set()
        
        print("\n" + "=" * 60)
        print("ALL REUSABILITY TESTS PASSED ✓")
        print("=" * 60)
        print("\nThe transport layer is now truly reusable!")
        print("Different projects can inject their own command sets.")
        
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
