# src/managers/render_manager.py
import time
import asyncio
from adafruit_ticks import ticks_ms
from utilities.logger import JEBLogger

class RenderManager:
    """
    Manages the centralized render loop (default 60Hz), frame sync, and hardware writes.
    """
    DEFAULT_FRAME_RATE = 60  # Default frame rate in Hz
    DRIFT_ADJUSTMENT_FACTOR = 0.1  # 10% adjustment for gradual sync correction
    MIN_SLEEP_DURATION = 0.005  # Minimum sleep to prevent event loop starvation
    MIN_FRAME_RATE = 10  # Minimum frame rate when backing off (Hz)
    BACKOFF_THRESHOLD = 5  # Number of consecutive lag frames before backing off
    BACKOFF_FACTOR = 0.9  # Reduce frame rate by 10% when backing off
    RECOVERY_THRESHOLD = 20  # Number of consecutive good frames before recovering
    RECOVERY_FACTOR = 1.05  # Increase frame rate by 5% when recovering

    def __init__(self, pixel_object, sync_role="NONE", network_manager=None):
        """
        Args:
            pixel_object: The NeoPixel object to call .show() on.
            sync_role: "MASTER" (broadcasts sync), "SLAVE" (tracks drift), or "NONE".
            network_manager: Reference to sat_network (if MASTER) to send broadcasts.
        """
        JEBLogger.info("REND", f"[INIT] RenderManager - sync_role: {sync_role}")
        self.pixels = pixel_object
        self.sync_role = sync_role
        self.network = network_manager

        # Mutable frame rate settings
        self.target_frame_rate = self.DEFAULT_FRAME_RATE

        # List of managers to step() every frame (e.g., LEDManager, MatrixManager)
        self._animators = []

        # List of GlobalAnimationControllers to receive frame counter updates
        self._global_anim_controllers = []

        # Sync State
        self.frame_counter = 0
        self.last_sync_broadcast = 0.0
        self.sleep_adjustment = 0.0  # For gradual drift correction

        # Adaptive frame rate tracking
        self.consecutive_lag_frames = 0
        self.consecutive_good_frames = 0

    def add_animator(self, manager):
        """Register a manager that needs its .animate_loop(step=True) called."""
        JEBLogger.debug("REND", f"Adding animator: {manager.__class__.__name__}")
        self._animators.append(manager)

    def add_global_animation_controller(self, controller):
        """Register a GlobalAnimationController to receive frame counter updates.

        The controller's :meth:`sync_frame` method is called every render frame
        with the current ``frame_counter`` value, enabling deterministic,
        frame-synchronized global animations.

        Args:
            controller: GlobalAnimationController instance to register.
        """
        JEBLogger.debug("REND", f"Adding GlobalAnimationController: {controller.__class__.__name__}")
        self._global_anim_controllers.append(controller)

    async def run(self, heartbeat_callback=None):
        """The main render loop (default 60Hz, configurable via target_frame_rate).

        Automatically adapts frame rate when unable to keep up with target timing.
        """
        next_frame_time = time.monotonic()

        while True:
            if heartbeat_callback:
                heartbeat_callback()

            # 2. Update Animation Logic (No IO)
            for mgr in self._animators:
                # Assuming animate_loop is async; if regular method, remove await
                await mgr.animate_loop(step=True)

            # 3. Hardware Write (IO)
            self.pixels.show()

            # 4. Sync Logic
            self.frame_counter += 1

            # Update all registered GlobalAnimationControllers with the new frame
            for ctrl in self._global_anim_controllers:
                ctrl.sync_frame(self.frame_counter)

            if self.sync_role == "MASTER" and self.network:
                # Broadcast every 1 second
                now = time.monotonic()
                if now - self.last_sync_broadcast >= 1.0:
                    self.network.send_all("SYNC_FRAME", (float(self.frame_counter), now))
                    self.last_sync_broadcast = now

            # 5. Fixed Time Step Timing
            frame_time = 1.0 / self.target_frame_rate
            next_frame_time += frame_time
            now = time.monotonic()
            sleep_duration = next_frame_time - now

            # Apply drift correction adjustment if set
            if self.sleep_adjustment != 0.0:
                sleep_duration += self.sleep_adjustment
                self.sleep_adjustment = 0.0  # Reset after applying once

            if sleep_duration > 0:
                await asyncio.sleep(sleep_duration)
                # Track good frames for potential recovery
                self.consecutive_good_frames += 1
                self.consecutive_lag_frames = 0

                # Gradually recover frame rate if consistently keeping up
                if self.consecutive_good_frames >= self.RECOVERY_THRESHOLD:
                    if self.target_frame_rate < self.DEFAULT_FRAME_RATE:
                        self.target_frame_rate = min(
                            self.target_frame_rate * self.RECOVERY_FACTOR,
                            self.DEFAULT_FRAME_RATE
                        )
                        # Reset both counters after adjustment for clean slate
                        self.consecutive_good_frames = 0
                        self.consecutive_lag_frames = 0
            else:
                # Lagging: Reset target and enforce minimum sleep to prevent event loop starvation
                next_frame_time = now
                await asyncio.sleep(self.MIN_SLEEP_DURATION)

                # Track lag frames for potential backoff
                self.consecutive_lag_frames += 1
                self.consecutive_good_frames = 0

                # Gradually reduce frame rate if consistently lagging
                if self.consecutive_lag_frames >= self.BACKOFF_THRESHOLD:
                    if self.target_frame_rate > self.MIN_FRAME_RATE:
                        self.target_frame_rate = max(
                            self.target_frame_rate * self.BACKOFF_FACTOR,
                            self.MIN_FRAME_RATE
                        )
                        # Reset both counters after adjustment for clean slate
                        self.consecutive_lag_frames = 0
                        self.consecutive_good_frames = 0

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
                frame_time = 1.0 / self.target_frame_rate
                if drift > 0:
                    # Satellite ahead: slow down by sleeping more
                    adjustment = self.DRIFT_ADJUSTMENT_FACTOR * frame_time
                else:
                    # Satellite behind: speed up by sleeping less
                    adjustment = -self.DRIFT_ADJUSTMENT_FACTOR * frame_time
                self.sleep_adjustment = adjustment
