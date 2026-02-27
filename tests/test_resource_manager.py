#!/usr/bin/env python3
"""Unit tests for ResourceManager.

Tests validate metric calculations, throttling behaviour, the CPU-load proxy,
and the status-bar text formatter without requiring CircuitPython hardware.
"""

import sys
import os
import gc
import time
import unittest
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Mock CircuitPython modules before importing the module under test
# ---------------------------------------------------------------------------

sys.modules['microcontroller'] = MagicMock()
sys.modules['analogio'] = MagicMock()
sys.modules['busio'] = MagicMock()
sys.modules['digitalio'] = MagicMock()
sys.modules['board'] = MagicMock()
sys.modules['neopixel'] = MagicMock()
sys.modules['storage'] = MagicMock()
sys.modules['supervisor'] = MagicMock()
sys.modules['watchdog'] = MagicMock()

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
# Import the module under test directly (avoids triggering managers/__init__.py
# which pulls in adafruit_ticks via watchdog_manager)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'managers'))

import resource_manager as _rm
ResourceManager = _rm.ResourceManager


class TestResourceManagerInit(unittest.TestCase):
    """Test ResourceManager initialisation."""

    def test_initial_metric_values_are_zero(self):
        """All metrics should default to zero before the first update."""
        rm = ResourceManager()
        self.assertEqual(rm.mem_percent, 0.0)
        self.assertEqual(rm.mem_used_bytes, 0)
        self.assertEqual(rm.cpu_percent, 0.0)
        self.assertEqual(rm.temperature_c, 0.0)

    def test_custom_total_ram_stored(self):
        """Constructor should accept a custom total_ram_bytes parameter."""
        rm = ResourceManager(total_ram_bytes=256 * 1024)
        self.assertEqual(rm._total_ram, 256 * 1024)

    def test_default_total_ram(self):
        """Default total RAM should be 520 KB (RP2350)."""
        rm = ResourceManager()
        self.assertEqual(rm._total_ram, 520 * 1024)


class TestResourceManagerMemory(unittest.TestCase):
    """Test memory metric refresh logic."""

    def test_memory_percent_calculated_from_gc(self):
        """_refresh_memory should compute mem_percent from gc.mem_alloc / total."""
        rm = ResourceManager()
        with patch.object(gc, 'mem_alloc', create=True, return_value=200), \
             patch.object(gc, 'mem_free', create=True, return_value=800):
            rm._refresh_memory()
        # 200 / (200 + 800) * 100 = 20 %
        self.assertAlmostEqual(rm.mem_percent, 20.0, places=1)
        self.assertEqual(rm.mem_used_bytes, 200)

    def test_memory_percent_full(self):
        """100 % usage when free == 0."""
        rm = ResourceManager()
        with patch.object(gc, 'mem_alloc', create=True, return_value=1000), \
             patch.object(gc, 'mem_free', create=True, return_value=0):
            rm._refresh_memory()
        self.assertAlmostEqual(rm.mem_percent, 100.0, places=1)

    def test_memory_percent_zero_total(self):
        """No divide-by-zero when both alloc and free return 0."""
        rm = ResourceManager()
        with patch.object(gc, 'mem_alloc', create=True, return_value=0), \
             patch.object(gc, 'mem_free', create=True, return_value=0):
            rm._refresh_memory()
        self.assertEqual(rm.mem_percent, 0.0)

    def test_memory_exception_handled_gracefully(self):
        """A failing gc call should not raise; metrics remain unchanged."""
        rm = ResourceManager()
        with patch.object(gc, 'mem_alloc', create=True, side_effect=RuntimeError("hw fault")):
            rm._refresh_memory()  # Must not raise
        self.assertEqual(rm.mem_percent, 0.0)


class TestResourceManagerTemperature(unittest.TestCase):
    """Test temperature metric refresh logic."""

    def test_temperature_read_from_microcontroller(self):
        """_refresh_temperature should read microcontroller.cpu.temperature."""
        rm = ResourceManager()
        mock_mc = MagicMock()
        mock_mc.cpu.temperature = 42.5
        with patch.dict('sys.modules', {'microcontroller': mock_mc}):
            rm._refresh_temperature()
        self.assertAlmostEqual(rm.temperature_c, 42.5, places=1)

    def test_temperature_exception_handled_gracefully(self):
        """A failing temperature read should not raise; value remains unchanged."""
        rm = ResourceManager()
        # Simulate ImportError when microcontroller hardware is unavailable
        with patch.dict('sys.modules', {'microcontroller': None}):
            rm._refresh_temperature()  # Must not raise
        self.assertEqual(rm.temperature_c, 0.0)


class TestResourceManagerCPUProxy(unittest.TestCase):
    """Test CPU-load proxy metric via record_loop_tick()."""

    def test_cpu_percent_clamped_to_100(self):
        """A delta much larger than the budget should clamp at 100 %."""
        rm = ResourceManager()
        # Simulate a very long loop iteration (1 second vs 50 ms budget)
        rm._last_loop_tick = time.monotonic() - 1.0
        rm.record_loop_tick()
        self.assertEqual(rm.cpu_percent, 100.0)

    def test_cpu_percent_proportional_to_delta(self):
        """A delta equal to the budget should yield ~100 %; half budget -> ~50 %."""
        rm = ResourceManager()
        # Simulate delta == half the budget
        rm._last_loop_tick = time.monotonic() - (rm.LOOP_BUDGET_S / 2)
        rm.record_loop_tick()
        self.assertAlmostEqual(rm.cpu_percent, 50.0, delta=5.0)

    def test_cpu_percent_near_zero_for_fast_loop(self):
        """A very short delta should produce a very low CPU percent."""
        rm = ResourceManager()
        # Simulate a near-instant tick
        rm._last_loop_tick = time.monotonic() - 0.001
        rm.record_loop_tick()
        self.assertLess(rm.cpu_percent, 10.0)

    def test_cpu_percent_never_negative(self):
        """cpu_percent must always be >= 0."""
        rm = ResourceManager()
        rm._last_loop_tick = time.monotonic()
        rm.record_loop_tick()
        self.assertGreaterEqual(rm.cpu_percent, 0.0)


class TestResourceManagerUpdateThrottle(unittest.TestCase):
    """Test that update() throttles based on UPDATE_INTERVAL_S."""

    def test_update_does_not_refresh_before_interval(self):
        """Calling update() twice rapidly should only refresh metrics once."""
        rm = ResourceManager()
        with patch.object(rm, '_refresh_memory') as mock_mem, \
             patch.object(rm, '_refresh_temperature') as mock_temp:
            rm.update()   # First call – should refresh
            rm.update()   # Second call immediately – should be skipped
        mock_mem.assert_called_once()
        mock_temp.assert_called_once()

    def test_update_refreshes_after_interval(self):
        """After UPDATE_INTERVAL_S has elapsed, update() should refresh again."""
        rm = ResourceManager()
        # Force last_update far in the past
        rm._last_update = time.monotonic() - (rm.UPDATE_INTERVAL_S + 1)
        with patch.object(rm, '_refresh_memory') as mock_mem, \
             patch.object(rm, '_refresh_temperature') as mock_temp:
            rm.update()
        mock_mem.assert_called_once()
        mock_temp.assert_called_once()

    def test_first_update_always_runs(self):
        """The very first call to update() should always refresh metrics."""
        rm = ResourceManager()
        # _last_update starts at 0.0, so interval is always exceeded
        with patch.object(rm, '_refresh_memory') as mock_mem, \
             patch.object(rm, '_refresh_temperature') as mock_temp:
            rm.update()
        mock_mem.assert_called_once()
        mock_temp.assert_called_once()


class TestResourceManagerStatusBar(unittest.TestCase):
    """Test the display status-bar text formatter."""

    def test_status_bar_text_format(self):
        """get_status_bar_text() should return the expected compact format."""
        rm = ResourceManager()
        rm._mem_percent = 45.0
        rm._cpu_percent = 30.0
        rm._temperature_c = 35.0
        text = rm.get_status_bar_text()
        self.assertEqual(text, "M:45% C:30% T:35C")

    def test_status_bar_text_rounds_floats(self):
        """Values should be rounded to the nearest integer in the output."""
        rm = ResourceManager()
        rm._mem_percent = 33.7
        rm._cpu_percent = 66.4
        rm._temperature_c = 27.9
        text = rm.get_status_bar_text()
        self.assertEqual(text, "M:34% C:66% T:28C")

    def test_status_bar_text_zero_values(self):
        """All-zero metrics should produce a valid string."""
        rm = ResourceManager()
        text = rm.get_status_bar_text()
        self.assertEqual(text, "M:0% C:0% T:0C")

    def test_status_bar_text_fits_oled_width(self):
        """Status bar text must not exceed 21 characters (OLED width)."""
        rm = ResourceManager()
        rm._mem_percent = 100.0
        rm._cpu_percent = 100.0
        rm._temperature_c = 100.0
        text = rm.get_status_bar_text()
        self.assertLessEqual(len(text), 21, f"Status bar too wide: '{text}' ({len(text)} chars)")


if __name__ == '__main__':
    unittest.main()
