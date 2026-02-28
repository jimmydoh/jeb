# File: src/managers/watchdog_manager.py
"""
WatchdogManager - A 'Flag Pattern' implementation for managing the Watchdog Timer.
Instead of blindly feeding the dog, this manager requires all registered
critical tasks to 'check-in' (set a flag) during their loop. The dog is
only fed if ALL tasks have checked in since the last feed. This ensures that
if any task is hanging, the watchdog will not be fed and will eventually reset
the system, providing a more robust and reliable way to manage the watchdog timer.
"""
import asyncio
import time
from adafruit_ticks import ticks_ms, ticks_diff

try:
    from microcontroller import watchdog as w
except ImportError:
    # Mock watchdog for non-hardware environments (e.g., testing)
    class MockWatchdog:
        def __init__(self):
            self.timeout = None
            self.mode = None
            self._feed_count = 0

        def feed(self):
            self._feed_count += 1  # In a real implementation, this would reset the watchdog timer

        @property
        def feed_count(self):
            return self._feed_count

    w = MockWatchdog()

try:
    from watchdog import WatchDogMode
except ImportError:
    # Mock WatchDogMode enum
    class WatchDogMode:
        RESET = 0
        RAISE = 1

from utilities.logger import JEBLogger


class WatchDogTimeout(RuntimeError):
    """Raised by the software watchdog monitor when the loop has been starved."""
    pass


class WatchdogManager:
    """
    Manages the Watchdog Timer using a 'Flag Pattern'.

    Instead of blindly feeding the dog, this manager requires all registered
    critical tasks to 'check-in' (set a flag) during their loop.
    The dog is only fed if ALL tasks have checked in since the last feed.
    """
    def __init__(self, task_names, timeout=None, mode="RAISE"):
        # Initialize flags for all tasks as False
        self._flags = {name: False for name in task_names}
        # Flag to indicate if a reboot is in progress
        self._rebooting = False

        # Starvation tracking properties
        self._starving = False
        self._starvation_start = 0

        # Watchdog operation mode: "RESET", "RAISE", "LOG_ONLY"
        self._mode = mode.upper()

        # Software watchdog fallback (used when hardware RAISE is not supported)
        self._software_mode = False
        self._last_fed_time = time.monotonic()
        self.timeout = timeout

        JEBLogger.info("WDOG", f"[INIT] WatchdogManager - timeout: {timeout}s, mode: {self._mode}")

        if timeout and w and WatchDogMode:
            if self._mode != "LOG_ONLY":
                w.timeout = timeout
                if self._mode == "RAISE":
                    try:
                        w.mode = WatchDogMode.RAISE
                    except NotImplementedError:
                        JEBLogger.warning("WDOG", "Hardware RAISE not supported, falling back to software watchdog")
                        self._software_mode = True
                        asyncio.create_task(self._software_watchdog_monitor())
                else:
                    w.mode = WatchDogMode.RESET
                if not self._software_mode:
                    w.feed()
            else:
                JEBLogger.warning("WDOG", "Hardware watchdog disabled (LOG_ONLY mode active)")
        elif timeout:
            JEBLogger.warning("WDOG", "Watchdog hardware not available (Emulator)")

    def register_flags(self, task_names):
        """Register additional tasks to monitor."""
        for name in task_names:
            if name not in self._flags:
                JEBLogger.info("WDOG", f"Registering task '{name}'")
                self._flags[name] = False

    def unregister_flags(self, task_names):
        """Unregister tasks that no longer need monitoring."""
        for name in task_names:
            if name in self._flags:
                JEBLogger.info("WDOG", f"Unregistering task '{name}'")
                del self._flags[name]

    def check_in(self, task_name):
        """Called by a task to indicate it is alive."""
        if task_name in self._flags:
            self._flags[task_name] = True

    def safe_feed(self):
        """
        Feeds the watchdog ONLY if all tasks have checked in.
        Returns True if fed, False if a task is hanging
        (which will eventually cause a reset).
        """
        if all(self._flags.values()):
            if not self._rebooting and self._mode != "LOG_ONLY":
                if self._software_mode:
                    self._last_fed_time = time.monotonic()
                elif w:
                    w.feed()

            # Reset flags for the next cycle
            for name in self._flags:
                self._flags[name] = False

            # Clear starvation state if we just recovered
            if self._starving:
                JEBLogger.info("WDOG", "Watchdog recovered! All tasks checked in.")
                self._starving = False

            return True
        else:
            # --- BLAME ATTRIBUTION ---
            now = ticks_ms()
            stuck_tasks = [name for name, flag in self._flags.items() if not flag]

            if not self._starving:
                # Log immediately on the first missed feed
                JEBLogger.error("WDOG", f"🚨 STARVATION DETECTED! Stuck tasks: {stuck_tasks}")
                self._starving = True
                self._starvation_start = now
            elif ticks_diff(now, self._starvation_start) > 1000:
                # Throttle the reminder logs to once per second
                JEBLogger.error("WDOG", f"Still starving... Stuck tasks: {stuck_tasks}")
                self._starvation_start = now

            return False

    async def _software_watchdog_monitor(self):
        """Background task that raises WatchDogTimeout if safe_feed() is not called in time."""
        while True:
            if time.monotonic() - self._last_fed_time > self.timeout:
                raise WatchDogTimeout("Software Watchdog Timeout: Loop starved!")
            await asyncio.sleep(0.5)

    def force_reboot(self):
        """Force a reboot by not feeding the watchdog."""
        JEBLogger.critical("WDOG", "Force reboot triggered!")
        time.sleep(2)  # Give the console 2 seconds to flush the log

        if w and WatchDogMode and self._mode != "LOG_ONLY":
            w.timeout = 1
            w.mode = WatchDogMode.RESET
        self._rebooting = True
