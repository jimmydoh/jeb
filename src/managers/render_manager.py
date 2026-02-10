# src/managers/render_manager.py
import time
import asyncio
from adafruit_ticks import ticks_ms

class RenderManager:
    """
    Manages the centralized 60Hz render loop, frame sync, and hardware writes.
    """
    RENDER_FRAME_TIME = 1.0 / 60.0

    def __init__(self, pixel_object, watchdog_flags=None, sync_role="NONE", network_manager=None):
        """
        Args:
            pixel_object: The NeoPixel object to call .show() on.
            watchdog_flags: Dictionary to set 'render': True.
            sync_role: "MASTER" (broadcasts sync), "SLAVE" (tracks drift), or "NONE".
            network_manager: Reference to sat_network (if MASTER) to send broadcasts.
        """
        self.pixels = pixel_object
        self.watchdog = watchdog_flags
        self.sync_role = sync_role
        self.network = network_manager

        # List of managers to step() every frame (e.g., LEDManager, MatrixManager)
        self._animators = []

        # Sync State
        self.frame_counter = 0
        self.last_sync_broadcast = 0.0

    def add_animator(self, manager):
        """Register a manager that needs its .animate_loop(step=True) called."""
        self._animators.append(manager)

    async def run(self):
        """The main 60Hz loop."""
        next_frame_time = time.monotonic()

        while True:
            # 1. Watchdog
            if self.watchdog is not None:
                self.watchdog["render"] = True

            # 2. Update Animation Logic (No IO)
            for mgr in self._animators:
                # Assuming animate_loop is async; if regular method, remove await
                await mgr.animate_loop(step=True)

            # 3. Hardware Write (IO)
            self.pixels.show()

            # 4. Sync Logic
            self.frame_counter += 1

            if self.sync_role == "MASTER" and self.network:
                # Broadcast every 1 second
                now = time.monotonic()
                if now - self.last_sync_broadcast >= 1.0:
                    self.network.send_all("SYNC_FRAME", (float(self.frame_counter), now))
                    self.last_sync_broadcast = now

            # 5. Fixed Time Step Timing
            next_frame_time += self.RENDER_FRAME_TIME
            now = time.monotonic()
            sleep_duration = next_frame_time - now

            if sleep_duration > 0:
                await asyncio.sleep(sleep_duration)
            else:
                # Lagging: Yield but reset target to prevent death spiral
                next_frame_time = now
                await asyncio.sleep(0)

    def apply_sync(self, core_frame):
        """Called by SLAVE devices when they receive a SYNC packet."""
        if self.sync_role == "SLAVE":
            estimated_core = core_frame + 1
            drift = abs(self.frame_counter - estimated_core)
            # Only snap if drift is noticeable (>2 frames) to prevent micro-stutters
            if drift > 2:
                self.frame_counter = estimated_core
