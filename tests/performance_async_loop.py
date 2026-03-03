#!/usr/bin/env python3
"""Performance benchmarks for async event loop optimisations.

Covers:
  1. PowerBus ADC polling throttle - confirms that rapid successive calls to
     ``is_healthy()``, ``get_telemetry()``, and ``__str__()`` share a single
     hardware read instead of each triggering a new I2C/ADC transaction.
     This happens via ``_update_if_stale()`` which throttles reads to at most
     one per ``POLL_INTERVAL_MS`` milliseconds.
"""

import sys
import os
import time

src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src'))
if src_path not in sys.path:
    sys.path.insert(0, src_path)

# -------------------------------------------------------------------------
# PowerBus polling throttle benchmark
# -------------------------------------------------------------------------

def _make_counting_bus():
    """Build a PowerBus backed by a sensor that counts hardware reads."""
    from utilities.power_bus import PowerBus, ADCSensorWrapper

    read_count = [0]

    class CountingADC:
        channels = {}
        def read(self, name):
            read_count[0] += 1
            return 19.5

    bus = PowerBus(
        "input_20v",
        ADCSensorWrapper(CountingADC(), "input_20v"),
        min_threshold=1.0,
    )
    return bus, read_count


def test_convenience_methods_share_one_read_per_tick():
    """is_healthy(), get_telemetry(), and __str__() must share one hardware read."""
    bus, read_count = _make_counting_bus()

    # Simulate multiple convenience-method callers within the same event-loop tick.
    # All three would previously each trigger a separate ADC read.
    bus.is_healthy()    # first call triggers a read
    bus.get_telemetry() # called within POLL_INTERVAL_MS -> uses cached result
    str(bus)            # called within POLL_INTERVAL_MS -> uses cached result

    assert read_count[0] == 1, (
        f"is_healthy(), get_telemetry(), and str() in the same tick should "
        f"share one hardware read (got {read_count[0]})"
    )

    print(f"  ok {read_count[0]} hardware read shared across is_healthy(), "
          f"get_telemetry(), str()")
    print("ok Convenience-method shared-read test passed")


def test_direct_update_always_reads():
    """update() must always read hardware (no throttle on the explicit path)."""
    bus, read_count = _make_counting_bus()

    bus.update()
    assert read_count[0] == 1, "First update() must read hardware"

    bus.update()
    assert read_count[0] == 2, "Successive direct update() calls must each read hardware"

    print(f"  ok {read_count[0]} hardware reads from 2 direct update() calls")
    print("ok Direct update() always-reads test passed")


def test_stale_cache_triggers_new_read():
    """is_healthy() must read hardware again once POLL_INTERVAL_MS has elapsed."""
    from utilities.power_bus import PowerBus

    bus, read_count = _make_counting_bus()

    bus.is_healthy()   # first read
    assert read_count[0] == 1

    # Sleep for POLL_INTERVAL_MS plus a 5 ms buffer to ensure the ticks_diff
    # comparison reliably exceeds the throttle window on all platforms.
    time.sleep(PowerBus.POLL_INTERVAL_MS / 1000.0 + 0.005)

    bus.is_healthy()   # cache is stale -> new read
    assert read_count[0] == 2, (
        f"is_healthy() must re-read hardware after {PowerBus.POLL_INTERVAL_MS} ms "
        f"(expected 2 reads, got {read_count[0]})"
    )

    print(f"  ok Hardware re-read after {PowerBus.POLL_INTERVAL_MS} ms stale interval")
    print("ok Stale-cache re-read test passed")


def benchmark_powerbus_convenience_throttle(iterations=10_000):
    """Measure how many hardware reads are triggered by rapid convenience calls."""
    from utilities.power_bus import PowerBus, ADCSensorWrapper

    reads = [0]

    class CountingADC:
        channels = {}
        def read(self, name):
            reads[0] += 1
            return 19.5

    bus = PowerBus("input_20v", ADCSensorWrapper(CountingADC(), "input_20v"), min_threshold=1.0)

    start = time.perf_counter()
    for _ in range(iterations):
        bus.is_healthy()
        bus.get_telemetry()
    elapsed = time.perf_counter() - start

    throttle_pct = reads[0] / (iterations * 2) * 100
    print(f"\n  Throttled convenience-method benchmark ({iterations * 2:,} calls):")
    print(f"    Hardware reads triggered : {reads[0]:,} ({throttle_pct:.1f}%)")
    print(f"    Total time               : {elapsed * 1000:.1f} ms")
    print(f"    Calls/s                  : {iterations * 2 / elapsed:,.0f}")
    print("  ok Benchmark complete")


# -------------------------------------------------------------------------
# Main
# -------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("Async Event Loop Performance Benchmarks")
    print("=" * 60)

    print("\n--- PowerBus ADC Polling Throttle ---")
    test_convenience_methods_share_one_read_per_tick()
    test_direct_update_always_reads()
    test_stale_cache_triggers_new_read()
    benchmark_powerbus_convenience_throttle()

    print("\n" + "=" * 60)
    print("ALL BENCHMARKS PASSED")
    print("=" * 60)
    print()
    print("Summary of optimisations validated:")
    print("  * PowerBus._update_if_stale(): max 1 hardware read per 10 ms")
    print("    via is_healthy() / get_telemetry() / __str__()")
    print("  * update() path unchanged - always reads hardware for explicit callers")
