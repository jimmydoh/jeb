#!/usr/bin/env python3
"""Test UART TX Chunking to Prevent Event Loop Blocking.

This test validates that the _tx_worker in UARTTransport limits the chunk size
sent to uart.write() to prevent blocking the asyncio event loop.

The issue: In CircuitPython, busio.UART.write() is a blocking operation.
Transmitting large packets (e.g., 256 bytes) at 115200 baud blocks the
event loop for >20ms, causing jitter in LED matrix rendering or synthio
background updates.

The fix: Limit the maximum number of bytes written per loop iteration
(MAX_TX_CHUNK = 32 bytes) to ensure the event loop yields frequently.
"""

import sys
import os
import asyncio

# Add paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from transport.uart_transport import UARTTransport


class MockUART:
    """Mock UART hardware for testing."""
    
    def __init__(self):
        self.written_chunks = []
        self.in_waiting = 0
        self.read_buffer = bytearray()
        
    def write(self, data):
        """Record the size of each write call."""
        chunk_size = len(data)
        self.written_chunks.append(chunk_size)
        return chunk_size
    
    def readinto(self, buf):
        """Mock readinto - returns 0 (no data)."""
        return 0
    
    def read(self, n):
        """Mock read - returns empty bytes."""
        return b''
    
    def reset_input_buffer(self):
        """Mock buffer reset."""
        self.read_buffer = bytearray()


async def test_tx_chunk_size_limit():
    """Test that TX chunks are limited to MAX_TX_CHUNK size."""
    print("\nTesting TX chunk size limiting...")
    
    # Create transport with mock UART
    mock_uart = MockUART()
    transport = UARTTransport(
        uart_hw=mock_uart,
        command_map={'TEST': 0x01},
        dest_map={'ALL': 0xFF}
    )
    
    # Start the transport (this starts the _tx_worker task)
    transport.start()
    
    # Create a large message that will generate >256 bytes when encoded
    # This simulates a large packet that would block the event loop
    large_payload = bytes(range(256))  # 256 bytes of data
    
    from transport.message import Message
    msg = Message(
        source='0101',
        destination='ALL',
        command='TEST',
        payload=large_payload
    )
    
    # Send the message
    transport.send(msg)
    
    # Give the TX worker time to process
    await asyncio.sleep(0.1)
    
    # Check that chunks were written
    assert len(mock_uart.written_chunks) > 0, "Should have written some chunks"
    
    # Check that no individual chunk exceeds MAX_TX_CHUNK
    max_chunk = max(mock_uart.written_chunks)
    assert max_chunk <= transport.MAX_TX_CHUNK, \
        f"Chunk size {max_chunk} exceeds MAX_TX_CHUNK ({transport.MAX_TX_CHUNK})"
    
    print(f"  ✓ Written chunks: {mock_uart.written_chunks}")
    print(f"  ✓ Max chunk size: {max_chunk} bytes (limit: {transport.MAX_TX_CHUNK})")
    print(f"  ✓ All chunks respect MAX_TX_CHUNK limit")
    
    # Clean up
    if transport._tx_task:
        transport._tx_task.cancel()
        try:
            await transport._tx_task
        except asyncio.CancelledError:
            pass
    if transport._rx_task:
        transport._rx_task.cancel()
        try:
            await transport._rx_task
        except asyncio.CancelledError:
            pass
    
    print("✓ TX chunk size limit test passed")


async def test_max_tx_chunk_constant_exists():
    """Test that MAX_TX_CHUNK constant is defined."""
    print("\nTesting MAX_TX_CHUNK constant...")
    
    # Create transport
    mock_uart = MockUART()
    transport = UARTTransport(uart_hw=mock_uart)
    
    # Check that MAX_TX_CHUNK exists
    assert hasattr(transport, 'MAX_TX_CHUNK'), \
        "UARTTransport should have MAX_TX_CHUNK constant"
    
    # Check that it's a reasonable value (not too small, not too large)
    assert 8 <= transport.MAX_TX_CHUNK <= 128, \
        f"MAX_TX_CHUNK ({transport.MAX_TX_CHUNK}) should be between 8 and 128 bytes"
    
    print(f"  ✓ MAX_TX_CHUNK is defined: {transport.MAX_TX_CHUNK} bytes")
    print("✓ MAX_TX_CHUNK constant test passed")


async def test_multiple_small_messages():
    """Test that small messages still work correctly."""
    print("\nTesting multiple small messages...")
    
    # Create transport with mock UART
    mock_uart = MockUART()
    transport = UARTTransport(
        uart_hw=mock_uart,
        command_map={'TEST': 0x01},
        dest_map={'ALL': 0xFF}
    )
    
    # Start the transport
    transport.start()
    
    from transport.message import Message
    
    # Send multiple small messages
    for i in range(5):
        msg = Message(
            source='0101',
            destination='ALL',
            command='TEST',
            payload=bytes([i, i+1, i+2])
        )
        transport.send(msg)
    
    # Give the TX worker time to process
    await asyncio.sleep(0.1)
    
    # Check that chunks were written
    assert len(mock_uart.written_chunks) > 0, "Should have written some chunks"
    
    # All chunks should be small (well below MAX_TX_CHUNK)
    for chunk_size in mock_uart.written_chunks:
        assert chunk_size <= transport.MAX_TX_CHUNK, \
            f"Chunk size {chunk_size} exceeds MAX_TX_CHUNK ({transport.MAX_TX_CHUNK})"
    
    print(f"  ✓ Written {len(mock_uart.written_chunks)} chunks")
    print(f"  ✓ All chunks within limit")
    
    # Clean up
    if transport._tx_task:
        transport._tx_task.cancel()
        try:
            await transport._tx_task
        except asyncio.CancelledError:
            pass
    if transport._rx_task:
        transport._rx_task.cancel()
        try:
            await transport._rx_task
        except asyncio.CancelledError:
            pass
    
    print("✓ Multiple small messages test passed")


async def run_all_tests():
    """Run all async tests."""
    print("=" * 70)
    print("UART TX Chunking Test Suite")
    print("=" * 70)
    
    try:
        await test_max_tx_chunk_constant_exists()
        await test_tx_chunk_size_limit()
        await test_multiple_small_messages()
        
        print("\n" + "=" * 70)
        print("ALL TX CHUNKING TESTS PASSED ✓")
        print("=" * 70)
        print("\nThe TX chunking implementation successfully:")
        print(f"  • Defines MAX_TX_CHUNK constant ({UARTTransport.MAX_TX_CHUNK} bytes)")
        print("  • Limits chunk size in _tx_worker to prevent event loop blocking")
        print("  • Handles large packets by splitting them into smaller chunks")
        print("  • Maintains correct behavior for small messages")
        print("  • Prevents >20ms blocking at 115200 baud (256 bytes)")
        
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


if __name__ == "__main__":
    # Run the async tests
    asyncio.run(run_all_tests())
