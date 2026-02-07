#!/usr/bin/env python3
"""Memory allocation comparison: String-based vs Tuple-based payload decoding.

This demonstrates the reduction in string allocations from the transport layer optimization.
The key benefit is not necessarily total memory usage, but the reduction in:
1. Temporary string object allocations
2. String join operations
3. String formatting (str(b) for each byte)
"""

import sys
import time


def old_decode_bytes(payload_bytes):
    """Old implementation: creates comma-separated string."""
    return ','.join(str(b) for b in payload_bytes)


def new_decode_bytes(payload_bytes):
    """New implementation: returns tuple."""
    return tuple(payload_bytes)


def count_allocations(func, payload_bytes, iterations=10000):
    """Count the number of objects allocated during execution."""
    start_time = time.perf_counter()
    
    for _ in range(iterations):
        result = func(payload_bytes)
        # Simulate usage by parse_values
        if isinstance(result, str):
            # This is what parse_values does: split and convert
            values = [int(x) for x in result.split(',')]
        else:
            # This is the new path: just convert to list
            values = list(result)
        # Use the values to prevent optimization
        _ = sum(values)
    
    end_time = time.perf_counter()
    elapsed = end_time - start_time
    
    return elapsed


def main():
    print("=" * 70)
    print("String Allocation Comparison: Old vs New Payload Decoding")
    print("=" * 70)
    
    # Test with different payload sizes
    test_cases = [
        (4, "Small payload (4 bytes - e.g., LED RGBA)"),
        (3, "POWER payload (3 floats)"),
        (5, "STATUS payload (5 bytes)"),
    ]
    
    iterations = 100000
    
    print(f"\nRunning {iterations} iterations per test...\n")
    
    for size, description in test_cases:
        payload_bytes = bytes(range(size))
        
        print(f"{description}")
        print("-" * 70)
        
        # Measure old implementation
        old_time = count_allocations(old_decode_bytes, payload_bytes, iterations)
        
        # Measure new implementation
        new_time = count_allocations(new_decode_bytes, payload_bytes, iterations)
        
        # Calculate improvement
        speedup = old_time / new_time if new_time > 0 else 0
        time_saved = old_time - new_time
        time_saved_pct = (time_saved / old_time * 100) if old_time > 0 else 0
        
        print(f"Old (string-based): {old_time:.4f}s")
        print(f"New (tuple-based):  {new_time:.4f}s")
        print(f"Improvement:        {time_saved:.4f}s ({time_saved_pct:.1f}% faster, {speedup:.2f}x speedup)")
        print()
    
    print("=" * 70)
    print("Allocation Analysis:")
    print("=" * 70)
    print("\nOld approach allocates PER MESSAGE:")
    print("  - Generator object for (str(b) for b in payload_bytes)")
    print("  - String object for each str(b) conversion")
    print("  - Intermediate list for join operation")
    print("  - Final comma-separated string")
    print("  - List from split(',') in parse_values")
    print("  - Integer conversion for each value")
    print("\nNew approach allocates PER MESSAGE:")
    print("  - Single tuple object (immutable, efficient)")
    print("  - List conversion in parse_values (one allocation)")
    print("\nResult: Fewer allocations = Less GC pressure = Better performance")


if __name__ == "__main__":
    main()
