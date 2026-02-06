#!/usr/bin/env python3
"""Unit tests for RingBuffer implementation."""

import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'managers'))

from ring_buffer import RingBuffer


def test_basic_operations():
    """Test basic ring buffer operations."""
    print("Testing basic operations...")
    
    rb = RingBuffer(capacity=10)
    
    # Test initial state
    assert len(rb) == 0, "Initial buffer should be empty"
    assert rb.capacity == 10, "Capacity should be 10"
    
    # Test extend
    rb.extend(b"Hello")
    assert len(rb) == 5, "Buffer should have 5 bytes"
    
    # Test slicing
    data = rb[0:5]
    assert data == b"Hello", f"Expected b'Hello', got {data}"
    
    print("✓ Basic operations test passed")


def test_find():
    """Test finding patterns in the buffer."""
    print("\nTesting find operation...")
    
    rb = RingBuffer(capacity=20)
    rb.extend(b"Hello\nWorld\n")
    
    # Find newline
    idx = rb.find(b'\n')
    assert idx == 5, f"Expected newline at index 5, got {idx}"
    
    # Find substring
    idx = rb.find(b"World")
    assert idx == 6, f"Expected 'World' at index 6, got {idx}"
    
    # Find non-existent pattern
    idx = rb.find(b"Test")
    assert idx == -1, f"Expected -1 for non-existent pattern, got {idx}"
    
    print("✓ Find operation test passed")


def test_deletion():
    """Test deletion from the front of the buffer."""
    print("\nTesting deletion...")
    
    rb = RingBuffer(capacity=20)
    rb.extend(b"Hello\nWorld\n")
    
    # Delete from front
    del rb[:6]  # Delete "Hello\n"
    assert len(rb) == 6, f"Expected 6 bytes remaining, got {len(rb)}"
    
    data = rb[0:6]
    assert data == b"World\n", f"Expected b'World\\n', got {data}"
    
    print("✓ Deletion test passed")


def test_wrap_around():
    """Test ring buffer wrap-around behavior."""
    print("\nTesting wrap-around...")
    
    rb = RingBuffer(capacity=10)
    
    # Fill buffer
    rb.extend(b"12345678")
    assert len(rb) == 8
    
    # Delete some data
    del rb[:5]
    assert len(rb) == 3
    
    # Add more data (should wrap around)
    rb.extend(b"ABCDEFG")
    assert len(rb) == 10
    
    # Verify data
    data = rb[0:10]
    assert data == b"678ABCDEFG", f"Expected b'678ABCDEFG', got {data}"
    
    print("✓ Wrap-around test passed")


def test_buffer_overflow():
    """Test buffer overflow protection."""
    print("\nTesting buffer overflow protection...")
    
    rb = RingBuffer(capacity=10)
    rb.extend(b"12345")
    
    try:
        # Try to add more than capacity
        rb.extend(b"67890ABCDE")
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "Buffer overflow" in str(e)
    
    print("✓ Buffer overflow protection test passed")


def test_clear():
    """Test clearing the buffer."""
    print("\nTesting clear operation...")
    
    rb = RingBuffer(capacity=10)
    rb.extend(b"Hello")
    
    rb.clear()
    assert len(rb) == 0, "Buffer should be empty after clear"
    
    # Should be able to add data again
    rb.extend(b"World")
    assert len(rb) == 5
    
    print("✓ Clear operation test passed")


def test_uart_use_case():
    """Test typical UART use case: read_line pattern."""
    print("\nTesting UART use case (read_line pattern)...")
    
    rb = RingBuffer(capacity=100)
    
    # Simulate receiving fragmented data
    rb.extend(b"First ")
    rb.extend(b"line\n")
    rb.extend(b"Second")
    
    # Find and extract first line
    newline_idx = rb.find(b'\n')
    assert newline_idx == 10, f"Expected newline at 10, got {newline_idx}"
    
    line = rb[:newline_idx + 1]
    assert line == b"First line\n", f"Expected b'First line\\n', got {line}"
    
    # Remove extracted line
    del rb[:newline_idx + 1]
    assert len(rb) == 6, f"Expected 6 bytes remaining, got {len(rb)}"
    
    # Verify remaining data
    remaining = rb[0:len(rb)]
    assert remaining == b"Second", f"Expected b'Second', got {remaining}"
    
    print("✓ UART use case test passed")


def test_read_until_pattern():
    """Test read_until pattern with delimiter."""
    print("\nTesting read_until pattern...")
    
    rb = RingBuffer(capacity=100)
    
    # Simulate binary protocol with 0x00 delimiter
    rb.extend(b"Data\x00More")
    
    # Find delimiter
    delim_idx = rb.find(b'\x00')
    assert delim_idx == 4, f"Expected delimiter at 4, got {delim_idx}"
    
    # Extract data including delimiter
    data = rb[:delim_idx + 1]
    assert data == b"Data\x00", f"Expected b'Data\\x00', got {data}"
    
    # Remove extracted data
    del rb[:delim_idx + 1]
    
    # Verify remaining data
    remaining = rb[0:len(rb)]
    assert remaining == b"More", f"Expected b'More', got {remaining}"
    
    print("✓ Read until pattern test passed")


def test_multiple_lines():
    """Test handling multiple complete lines."""
    print("\nTesting multiple lines...")
    
    rb = RingBuffer(capacity=100)
    rb.extend(b"Line1\nLine2\nLine3\n")
    
    lines = []
    while True:
        newline_idx = rb.find(b'\n')
        if newline_idx < 0:
            break
        
        line = rb[:newline_idx]
        lines.append(bytes(line))
        del rb[:newline_idx + 1]
    
    assert lines == [b"Line1", b"Line2", b"Line3"], f"Expected 3 lines, got {lines}"
    assert len(rb) == 0, "Buffer should be empty"
    
    print("✓ Multiple lines test passed")


def test_large_buffer_wrapping():
    """Test buffer with many wrap-arounds."""
    print("\nTesting large buffer with wrapping...")
    
    rb = RingBuffer(capacity=20)
    
    # Simulate continuous UART traffic
    for i in range(10):
        rb.extend(f"L{i}\n".encode())
        
        # Extract the line
        newline_idx = rb.find(b'\n')
        if newline_idx >= 0:
            line = rb[:newline_idx]
            del rb[:newline_idx + 1]
            assert line == f"L{i}".encode(), f"Line mismatch at iteration {i}"
    
    assert len(rb) == 0, "Buffer should be empty after processing all lines"
    
    print("✓ Large buffer wrapping test passed")


def run_all_tests():
    """Run all ring buffer tests."""
    print("=" * 60)
    print("Ring Buffer Test Suite")
    print("=" * 60)
    
    test_basic_operations()
    test_find()
    test_deletion()
    test_wrap_around()
    test_buffer_overflow()
    test_clear()
    test_uart_use_case()
    test_read_until_pattern()
    test_multiple_lines()
    test_large_buffer_wrapping()
    
    print("\n" + "=" * 60)
    print("ALL TESTS PASSED ✓")
    print("=" * 60)


if __name__ == "__main__":
    run_all_tests()
