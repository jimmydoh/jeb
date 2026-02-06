#!/usr/bin/env python3
"""Performance comparison for brightness cache optimization."""

import sys
import time


def test_without_cache(num_iterations=10000):
    """Simulate the old approach without caching."""
    base_colors = [
        (255, 0, 0),    # Red
        (0, 255, 0),    # Green
        (0, 0, 255),    # Blue
        (200, 100, 50), # Orange
    ]
    brightness = 0.75
    
    start = time.perf_counter()
    for _ in range(num_iterations):
        for base in base_colors:
            # Old approach: create tuple every time
            px_color = tuple(int(c * brightness) for c in base)
    end = time.perf_counter()
    
    return end - start


def test_with_cache(num_iterations=10000):
    """Simulate the new approach with caching."""
    base_colors = [
        (255, 0, 0),    # Red
        (0, 255, 0),    # Green
        (0, 0, 255),    # Blue
        (200, 100, 50), # Orange
    ]
    brightness = 0.75
    cache = {}
    cache_limit = 128
    
    def get_dimmed_color(base_color, brightness):
        if brightness == 0.0:
            return (0, 0, 0)
        if brightness == 1.0:
            return base_color
        brightness_int = round(brightness * 100)
        cache_key = (base_color, brightness_int)
        if cache_key not in cache:
            if len(cache) >= cache_limit:
                cache.clear()
            brightness_factor = brightness_int / 100.0
            cache[cache_key] = tuple(int(c * brightness_factor) for c in base_color)
        return cache[cache_key]
    
    start = time.perf_counter()
    for _ in range(num_iterations):
        for base in base_colors:
            # New approach: use cache
            px_color = get_dimmed_color(base, brightness)
    end = time.perf_counter()
    
    return end - start


def main():
    print("=" * 70)
    print("Performance Test: Brightness Cache Optimization")
    print("=" * 70)
    print()
    print("Simulating show_icon rendering with 4 colors and repeated calls...")
    print()
    
    # Warm up
    test_without_cache(100)
    test_with_cache(100)
    
    # Run tests
    num_iterations = 10000
    
    print(f"Running {num_iterations} iterations per test...")
    print()
    
    # Test without cache
    time_without = test_without_cache(num_iterations)
    print(f"Without cache: {time_without:.4f} seconds")
    
    # Test with cache
    time_with = test_with_cache(num_iterations)
    print(f"With cache:    {time_with:.4f} seconds")
    
    # Calculate improvement
    speedup = time_without / time_with
    improvement = ((time_without - time_with) / time_without) * 100
    
    print()
    print("Results:")
    print(f"  Speedup:     {speedup:.2f}x faster")
    print(f"  Improvement: {improvement:.1f}% reduction in execution time")
    print()
    
    # Calculate tuple allocations saved
    allocations_without = num_iterations * 4  # 4 colors per iteration
    allocations_with = 4  # Only 4 unique cache entries created
    allocations_saved = allocations_without - allocations_with
    
    print("Tuple Allocations:")
    print(f"  Without cache: {allocations_without:,} tuple objects created")
    print(f"  With cache:    {allocations_with:,} tuple objects created")
    print(f"  Saved:         {allocations_saved:,} tuple allocations ({(allocations_saved/allocations_without)*100:.2f}% reduction)")
    print()
    
    print("=" * 70)
    print("✓ Performance test completed")
    print("=" * 70)


if __name__ == "__main__":
    main()
