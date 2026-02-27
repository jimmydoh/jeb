"""Monitors system resources: memory usage, CPU load proxy, and temperature."""

import gc
import time

from utilities.logger import JEBLogger

# Default total RAM for RP2350 (Raspberry Pi Pico 2): 520 KB
_DEFAULT_TOTAL_RAM_BYTES = 520 * 1024


class ResourceManager:
    """Monitors system resource metrics: memory, CPU load proxy, and temperature.

    Memory stats are gathered via the ``gc`` module (``gc.mem_alloc`` /
    ``gc.mem_free``).  Temperature is read from
    ``microcontroller.cpu.temperature``.  CPU load is approximated by
    comparing the measured main-loop tick delta against the expected loop
    budget; a long delta indicates the loop was stalled, suggesting higher
    load.

    ``update()`` is throttled by ``UPDATE_INTERVAL_S`` so that expensive
    operations (gc.collect, temperature read) do not cause display lag when
    called on every iteration.  ``record_loop_tick()`` should be called
    once per main-loop iteration for an accurate CPU proxy.

    Usage::

        resources = ResourceManager()

        # Inside main loop:
        resources.record_loop_tick()

        # Periodically (update() self-throttles):
        resources.update()
        display.update_footer(resources.get_status_bar_text())
    """

    #: Seconds between full metric refreshes
    UPDATE_INTERVAL_S = 4.0

    #: Ideal loop period (seconds) used as the CPU-load baseline (20 Hz)
    LOOP_BUDGET_S = 0.05

    def __init__(self, total_ram_bytes=_DEFAULT_TOTAL_RAM_BYTES):
        """Initialise the ResourceManager.

        Args:
            total_ram_bytes: Total RAM available on the platform in bytes.
                Defaults to 520 KB (RP2350).
        """
        JEBLogger.info("RSRC", "[INIT] ResourceManager")

        self._total_ram = total_ram_bytes

        # Cached metric values (updated lazily by update())
        self._mem_percent = 0.0
        self._mem_used_bytes = 0
        self._cpu_percent = 0.0
        self._temperature_c = 0.0

        # CPU-proxy state: track the monotonic time of the last recorded tick
        self._last_loop_tick = time.monotonic()

        # Timestamp of the last full update (0.0 forces an immediate first run)
        self._last_update = 0.0

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def update(self):
        """Refresh all metrics (throttled by ``UPDATE_INTERVAL_S``)."""
        now = time.monotonic()
        if now - self._last_update < self.UPDATE_INTERVAL_S:
            return
        self._last_update = now

        self._refresh_memory()
        self._refresh_temperature()

    def record_loop_tick(self):
        """Record one main-loop iteration for the CPU-load proxy metric.

        Call this once per iteration of the top-level ``asyncio`` run loop
        (e.g. inside the outermost ``while True`` of ``CoreManager.start``).
        The elapsed delta is compared against ``LOOP_BUDGET_S``; a ratio > 1
        means the loop was slower than expected, which is treated as 100 %
        load.
        """
        now = time.monotonic()
        delta = now - self._last_loop_tick
        self._last_loop_tick = now

        if self.LOOP_BUDGET_S > 0:
            ratio = delta / self.LOOP_BUDGET_S
            self._cpu_percent = min(ratio * 100.0, 100.0)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def mem_percent(self):
        """Memory used as a percentage of total heap (float 0–100)."""
        return self._mem_percent

    @property
    def mem_used_bytes(self):
        """Memory allocated by the interpreter in bytes (int)."""
        return self._mem_used_bytes

    @property
    def cpu_percent(self):
        """Approximate CPU load percentage derived from loop timing (float 0–100)."""
        return self._cpu_percent

    @property
    def temperature_c(self):
        """CPU die temperature in degrees Celsius (float)."""
        return self._temperature_c

    # ------------------------------------------------------------------
    # Display helpers
    # ------------------------------------------------------------------

    def get_status_bar_text(self):
        """Return a compact status-bar string for the OLED footer.

        The string fits within the 21-character width of the SSD1306 display::

            "M:45% C:30% T:35C"

        Returns:
            str: Formatted resource metrics string.
        """
        return (
            f"M:{self._mem_percent:.0f}%"
            f" C:{self._cpu_percent:.0f}%"
            f" T:{self._temperature_c:.0f}C"
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _refresh_memory(self):
        """Update memory metrics using the gc module."""
        try:
            gc.collect()
            free = gc.mem_free()
            used = gc.mem_alloc()
            total = free + used
            self._mem_used_bytes = used
            self._mem_percent = (used / total * 100.0) if total > 0 else 0.0
        except Exception as exc:  # pragma: no cover
            JEBLogger.warning("RSRC", f"Memory read failed: {exc}")

    def _refresh_temperature(self):
        """Update temperature from the microcontroller module."""
        try:
            import microcontroller  # noqa: PLC0415 - hardware-only import
            self._temperature_c = microcontroller.cpu.temperature
        except Exception as exc:  # pragma: no cover
            JEBLogger.warning("RSRC", f"Temperature read failed: {exc}")
