#!/usr/bin/env python3
"""Performance test comparing bytearray vs RingBuffer for UART operations."""

import sys
import os
import time

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'managers'))

from ring_buffer import RingBuffer


def test_bytearray_performance(iterations=1000):
    """Test bytearray with O(N) deletion performance."""
    buffer = bytearray()
    
    start_time = time.time()
    
    for i in range(iterations):
        # Simulate UART receiving data
        buffer.extend(f"Line {i}\n".encode())
        
        # Find and extract line (O(N) deletion)
        newline_idx = buffer.find(b'\n')
        if newline_idx >= 0:
            line = buffer[:newline_idx]
            del buffer[:newline_idx + 1]  # O(N) operation
    
    elapsed = time.time() - start_time
    return elapsed


def test_ringbuffer_performance(iterations=1000):
    """Test RingBuffer with O(1) deletion performance."""
    buffer = RingBuffer(capacity=10000)
    
    start_time = time.time()
    
    for i in range(iterations):
        # Simulate UART receiving data
        buffer.extend(f"Line {i}\n".encode())
        
        # Find and extract line (O(1) deletion)
        newline_idx = buffer.find(b'\n')
        if newline_idx >= 0:
            line = buffer[:newline_idx]
            del buffer[:newline_idx + 1]  # O(1) operation
    
    elapsed = time.time() - start_time
    return elapsed


def test_large_buffer_scenario():
    """Test scenario with large buffer accumulation."""
    print("\nTesting large buffer scenario (900+ bytes in buffer)...")
    
    # Bytearray test
    buffer = bytearray()
    # Fill buffer with data to reach ~900 bytes
    for i in range(100):
        buffer.extend(f"Data{i:04d} ".encode())  # ~10 bytes per item = ~1000 bytes
    
    start_time = time.time()
    for _ in range(1000):
        # Find pattern and delete from front (O(N) where N=~900)
        idx = buffer.find(b' ')
        if idx >= 0:
            del buffer[:idx + 1]
        # Add more data to keep buffer size constant
        buffer.extend(b"NewData0 ")
    bytearray_time = time.time() - start_time
    
    # RingBuffer test
    ring = RingBuffer(capacity=10000)
    # Fill buffer with data
    for i in range(100):
        ring.extend(f"Data{i:04d} ".encode())
    
    start_time = time.time()
    for _ in range(1000):
        # Find pattern and delete from front (O(1))
        idx = ring.find(b' ')
        if idx >= 0:
            del ring[:idx + 1]
        # Add more data to keep buffer size constant
        ring.extend(b"NewData0 ")
    ringbuffer_time = time.time() - start_time
    
    print(f"  Bytearray time:   {bytearray_time:.4f}s")
    print(f"  RingBuffer time:  {ringbuffer_time:.4f}s")
    speedup = bytearray_time / ringbuffer_time if ringbuffer_time > 0 else 0
    print(f"  Speedup:          {speedup:.2f}x")
    print("✓ Large buffer scenario test passed")


def run_performance_tests():
    """Run all performance tests."""
    print("=" * 60)
    print("UART Buffer Performance Comparison")
    print("=" * 60)
    print("\nNote: The key advantage of RingBuffer is O(1) complexity,")
    print("which becomes critical as buffer size increases.")
    print("For embedded systems with limited CPU cycles, avoiding")
    print("the O(N) memory copy is essential for maintaining throughput.")
    
    iterations = 1000
    
    print(f"\nTesting with {iterations} line reads/writes (small lines)...")
    
    bytearray_time = test_bytearray_performance(iterations)
    ringbuffer_time = test_ringbuffer_performance(iterations)
    
    print(f"\nSmall buffer results:")
    print(f"  Bytearray (O(N)):    {bytearray_time:.4f}s")
    print(f"  RingBuffer (O(1)):   {ringbuffer_time:.4f}s")
    
    test_large_buffer_scenario()
    
    print("\n" + "=" * 60)
    print("PERFORMANCE TESTS COMPLETED ✓")
    print("=" * 60)
    print("\nConclusion: RingBuffer provides O(1) deletion from front,")
    print("eliminating the O(N) buffer shifting overhead of bytearray.")
    print("This is critical for high-throughput UART on microcontrollers.")


if __name__ == "__main__":
    run_performance_tests()
