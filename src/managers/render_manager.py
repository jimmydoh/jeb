# src/managers/render_manager.py
import time
import asyncio
from adafruit_ticks import ticks_ms

class RenderManager:
    """
    Manages the centralized 60Hz render loop, frame sync, and hardware writes.
    """
    RENDER_FRAME_TIME = 1.0 / 60.0
    DRIFT_ADJUSTMENT_FACTOR = 0.1  # 10% adjustment for gradual sync correction

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
        self.sleep_adjustment = 0.0  # For gradual drift correction

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
            
            # Apply drift correction adjustment if set
            if self.sleep_adjustment != 0.0:
                sleep_duration += self.sleep_adjustment
                self.sleep_adjustment = 0.0  # Reset after applying once

            if sleep_duration > 0:
                await asyncio.sleep(sleep_duration)
            else:
                # Lagging: Yield but reset target to prevent death spiral
                next_frame_time = now
                await asyncio.sleep(0)

    def apply_sync(self, core_frame):
        """Called by SLAVE devices when they receive a SYNC packet.
        
        Sync strategy:
        - abs_drift > 2: Snap immediately (prevents large visible desync)
        - abs_drift == 1: Gradual nudge via sleep adjustment (smooth correction)
        - abs_drift == 0 or 2: No correction (stability zone to prevent oscillation)
        
        The 2-frame threshold provides hysteresis to prevent constant micro-adjustments
        that could cause jitter. Only drifts > 2 frames are considered significant enough
        to warrant an immediate snap.
        """
        if self.sync_role == "SLAVE":
            estimated_core = core_frame + 1
            drift = self.frame_counter - estimated_core
            abs_drift = abs(drift)
            
            if abs_drift > 2:
                # Large drift: snap immediately to prevent visible desync
                self.frame_counter = estimated_core
            elif abs_drift == 1:
                # Small drift: gradually adjust via sleep time modification
                # If satellite is ahead (drift > 0), sleep MORE to slow down
                # If satellite is behind (drift < 0), sleep LESS to speed up
                if drift > 0:
                    # Satellite ahead: slow down by sleeping more
                    adjustment = self.DRIFT_ADJUSTMENT_FACTOR * self.RENDER_FRAME_TIME
                else:
                    # Satellite behind: speed up by sleeping less
                    adjustment = -self.DRIFT_ADJUSTMENT_FACTOR * self.RENDER_FRAME_TIME
                self.sleep_adjustment = adjustment
