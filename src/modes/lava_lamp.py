"""Lava Lamp (Metaballs) – Zero Player Cellular Automaton / Math Visualizer.

A classic 1990s demoscene effect utilizing "Metaballs" (iso-surfaces).
It calculates an inverse-square distance field for several moving points.
Where the overlapping fields sum past a certain threshold, the pixels illuminate.
This creates organic, gooey blobs that seamlessly merge and separate.

The RP2350's FPU handles the per-pixel distance calculations across the
entire matrix every frame, creating silky-smooth anti-aliased blobs.

Controls:
    Encoder turn       : change simulation speed (slow ↔ turbo)
    Button 1 (tap)     : cycle color theme (Lava / Ocean / Toxic / Plasma)
    Button 2 (tap)     : reset and randomize blob positions
    Encoder long press : return to Zero Player menu
"""

import asyncio
import gc
import math
import random

from adafruit_ticks import ticks_ms, ticks_diff

from utilities import tones
from utilities.palette import Palette
from utilities.logger import JEBLogger

from .base import BaseMode

# ---------------------------------------------------------------------------
# Tunable constants
# ---------------------------------------------------------------------------

_NUM_BLOBS = 4

# Simulation update intervals in milliseconds (encoder selects index).
_SPEED_LEVELS_MS = [80, 50, 30, 15, 5]
_SPEED_NAMES     = ["SLOW", "MED", "NORM", "FAST", "TURBO"]

# Color Themes: (Display Name, Base Hue, Peak Hue)
# The field intensity interpolates between the Base Hue (edges) and Peak Hue (center).
_THEMES = [
    ("THERMAL", 0.0, 60.0),    # Red to Yellow
    ("OCEAN", 240.0, 180.0),   # Deep Blue to Cyan
    ("TOXIC", 120.0, 80.0),    # Green to Lime
    ("PLASMA", 280.0, 320.0),  # Purple to Pink
]

class LavaLampMode(BaseMode):
    """Lava Lamp (Metaballs) visualizer.

    Calculates an inverse-square field for organic, merging blobs.
    Floating-point intensive, relying on the RP2350 hardware FPU.
    """

    def __init__(self, core):
        super().__init__(core, "LAVA LAMP", "Metaball Visualizer")
        self.width = 0
        self.height = 0
        self._buf = None         # Pre-allocated RGB frame buffer

        self._blobs = []         # List of [x, y, vx, vy, radius_sq]
        self._theme_idx = 0      # Default to THERMAL
        self._speed_idx = 2      # Default to NORM

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _reset_blobs(self):
        """Randomize the positions, velocities, and sizes of the blobs."""
        self._blobs = []
        w, h = self.width, self.height

        for _ in range(_NUM_BLOBS):
            x = random.uniform(2.0, w - 2.0)
            y = random.uniform(2.0, h - 2.0)

            # Random velocity
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(0.1, 0.3)
            vx = math.cos(angle) * speed
            vy = math.sin(angle) * speed

            # Blob weight/radius squared
            r_sq = random.uniform(10.0, 25.0)

            self._blobs.append([x, y, vx, vy, r_sq])

        gc.collect()

    def _step_physics(self):
        """Move the blobs and bounce them off the walls."""
        w, h = self.width, self.height

        for blob in self._blobs:
            blob[0] += blob[2]
            blob[1] += blob[3]

            # Soft bouncing off the walls (prevents them getting stuck exactly on the edge)
            if blob[0] <= 1.0:
                blob[0] = 1.0
                blob[2] *= -1
            elif blob[0] >= w - 1.0:
                blob[0] = w - 1.0
                blob[2] *= -1

            if blob[1] <= 1.0:
                blob[1] = 1.0
                blob[3] *= -1
            elif blob[1] >= h - 1.0:
                blob[1] = h - 1.0
                blob[3] *= -1

    def _compute_frame(self):
        """Calculate the scalar field for every pixel and map it to RGB."""
        w = self.width
        h = self.height

        base_hue = _THEMES[self._theme_idx][1]
        peak_hue = _THEMES[self._theme_idx][2]

        idx = 0
        for py in range(h):
            for px in range(w):
                # Calculate the sum of the inverse square distances
                field_value = 0.0
                for blob in self._blobs:
                    bx, by, r_sq = blob[0], blob[1], blob[4]
                    dist_sq = (px - bx) ** 2 + (py - by) ** 2
                    # Add 0.1 to avoid division by zero if pixel is exactly on center
                    field_value += r_sq / (dist_sq + 0.1)

                # Map field value to color.
                # Values < 0.6 are black (empty space).
                # Values > 1.6 are peak color (bright white/yellow center).
                if field_value < 0.6:
                    r, g, b = 0, 0, 0
                else:
                    # Normalize intensity to [0.0, 1.0] band
                    intensity = max(0.0, min(1.0, field_value - 0.6))

                    # Shift hue based on intensity (edges are base_hue, centers are peak_hue)
                    hue = base_hue + intensity * (peak_hue - base_hue)

                    # Brightness curve: sharp ramp up
                    val = math.pow(intensity, 0.5)

                    r, g, b = Palette.hsv_to_rgb(hue, 1.0, val)

                cell = self._buf[idx]
                cell[0] = r
                cell[1] = g
                cell[2] = b
                idx += 1

    def _render_to_matrix(self):
        """Write the RGB buffer to the LED matrix."""
        w = self.width
        h = self.height
        for y in range(h):
            for x in range(w):
                cell = self._buf[y * w + x]
                self.core.matrix.draw_pixel(x, y, (cell[0], cell[1], cell[2]))

    def _status_line(self):
        """Return the two status strings for the current settings."""
        speed_name = _SPEED_NAMES[self._speed_idx]
        ms = _SPEED_LEVELS_MS[self._speed_idx]
        theme_name = _THEMES[self._theme_idx][0]
        return (
            f"SPEED: {speed_name} ({ms}ms)",
            f"THEME: {theme_name}",
        )

    # ------------------------------------------------------------------
    # Tutorial
    # ------------------------------------------------------------------

    async def run_tutorial(self):
        """
        Guided demonstration of the Lava Lamp / Metaballs.

        The Voiceover Script (audio/tutes/lava_tute.wav) ~46 seconds:
            [0:00] "Welcome to the Lava Lamp, driven by Metaball mathematics."
            [0:06] "A classic algorithmic effect from the nineteen-nineties demoscene."
            [0:11] "It calculates an inverse-square distance field for several moving points."
            [0:18] "When these invisible fields overlap, their values add together, crossing a threshold to form these organic, merging blobs."
            [0:28] "Turn the main dial to adjust the simulation speed."
            [0:33] "Press button one to cycle the color theme."
            [0:38] "And press button two to randomize the blobs."
            [0:43] "Enjoy the exhibit."
            [0:46] (End of file)
        """
        await self.core.clean_slate()
        self.game_state = "TUTORIAL"

        # Trigger audio synchronously
        self.core.audio.play("audio/tutes/lava_tute.wav", bus_id=self.core.audio.CH_VOICE)

        self.width = self.core.matrix.width
        self.height = self.core.matrix.height
        size = self.width * self.height

        self._buf = [[0, 0, 0] for _ in range(size)]
        self._speed_idx = 1 # Start on MED so the merging is easy to watch
        self._theme_idx = 0 # THERMAL

        self._reset_blobs()

        self.core.display.use_standard_layout()
        self.core.display.update_header("LAVA LAMP")
        self.core.display.update_footer("B1:Theme  B2:Reset")

        def _refresh_ui():
            line1, line2 = self._status_line()
            self.core.display.update_status(line1, line2)

        _refresh_ui()

        async def _sim_wait(duration_s):
            """Runs the continuous simulation."""
            start_time = ticks_ms()
            last_tick = start_time
            target_ms = int(duration_s * 1000)

            while ticks_diff(ticks_ms(), start_time) < target_ms:
                now = ticks_ms()
                dt_ms = ticks_diff(now, last_tick)

                interval = _SPEED_LEVELS_MS[self._speed_idx]
                if dt_ms >= interval:
                    last_tick = now
                    self._step_physics()
                    self._compute_frame()
                    self._render_to_matrix()


                await asyncio.sleep(0.01)

        try:
            # [0:00 - 0:11] Intro & Context
            self.core.display.update_status("LAVA LAMP", "METABALL MATH")
            await _sim_wait(11.0)

            # [0:11 - 0:28] Field Math explanation
            self.core.display.update_status("DISTANCE FIELD", "ISO-SURFACES")
            await _sim_wait(17.0)

            # [0:28 - 0:33] Speed Dial
            self.core.display.update_status("MAIN DIAL", "SIMULATION SPEED")
            for speed in [2, 3, 4]: # NORM -> TURBO
                self._speed_idx = speed
                _refresh_ui()
                self.core.buzzer.play_sequence(tones.UI_TICK)
                await _sim_wait(1.6)

            # [0:33 - 0:38] Color Theme
            self.core.display.update_status("BUTTON 1", "COLOR THEME")
            for _ in range(3):
                self._theme_idx = (self._theme_idx + 1) % len(_THEMES)
                _refresh_ui()
                self.core.buzzer.play_sequence(tones.UI_TICK)
                await _sim_wait(1.6)

            # [0:38 - 0:43] Reset
            self.core.display.update_status("BUTTON 2", "RANDOMIZE BLOBS")
            await _sim_wait(1.0)
            self._reset_blobs()
            _refresh_ui()
            self.core.buzzer.play_sequence(tones.UI_CONFIRM)
            await _sim_wait(4.0)

            # Wait for audio to finish out
            if hasattr(self.core.audio, 'wait_for_bus'):
                await self.core.audio.wait_for_bus(self.core.audio.CH_VOICE)
            else:
                await asyncio.sleep(2.0)

            # --- SEAMLESS HANDOFF TO MAIN LOOP ---
            self.core.display.update_status("TUTORIAL COMPLETE", "HANDING OVER CONTROL")
            await asyncio.sleep(1.5)

            self.core.hid.flush()
            self.game_state = "RUNNING"
            return await self.run()

        finally:
            await self.core.clean_slate()


    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    async def run(self):
        """Main Lava Lamp loop."""
        JEBLogger.info("LAVA", "[RUN] LavaLampMode starting")

        self.width = self.core.matrix.width
        self.height = self.core.matrix.height
        size = self.width * self.height

        # Pre-allocate the RGB buffer if it doesn't exist
        if self._buf is None:
            self._buf = [[0, 0, 0] for _ in range(size)]

        # Only re-initialize variables if we didn't just come from the tutorial
        if not self._blobs:
            self._speed_idx = 2
            self._theme_idx = 0
            self._reset_blobs()

        self.core.display.use_standard_layout()
        self.core.display.update_header("LAVA LAMP")
        line1, line2 = self._status_line()
        self.core.display.update_status(line1, line2)
        self.core.display.update_footer("B1:Theme  B2:Reset")

        self.core.hid.flush()
        self.core.hid.reset_encoder(self._speed_idx)
        last_enc = self.core.hid.encoder_position()
        last_tick = ticks_ms()

        while True:
            now = ticks_ms()

            # --- Encoder: adjust simulation speed ---
            enc = self.core.hid.encoder_position()
            diff = enc - last_enc
            if diff != 0:
                delta = 1 if diff > 0 else -1
                new_idx = max(0, min(len(_SPEED_LEVELS_MS) - 1, self._speed_idx + delta))
                self._speed_idx = new_idx
                self.core.hid.reset_encoder(self._speed_idx)
                last_enc = self._speed_idx
                line1, line2 = self._status_line()
                self.core.display.update_status(line1, line2)
                self.core.buzzer.play_sequence(tones.UI_TICK)

            # --- Button 1: cycle color theme ---
            if self.core.hid.is_button_pressed(0, action="tap"):
                self._theme_idx = (self._theme_idx + 1) % len(_THEMES)
                line1, line2 = self._status_line()
                self.core.display.update_status(line1, line2)
                self.core.buzzer.play_sequence(tones.UI_TICK)

            # --- Button 2: randomise blobs ---
            if self.core.hid.is_button_pressed(1, action="tap"):
                self._reset_blobs()
                line1, _ = self._status_line()
                self.core.display.update_status(line1, "RANDOMIZED!")
                self.core.buzzer.play_sequence(tones.UI_CONFIRM)

            # --- Encoder long press (2 s): exit to menu ---
            if self.core.hid.is_encoder_button_pressed(long=True, duration=2000):
                JEBLogger.info("LAVA", "[EXIT] Returning to Zero Player menu")
                return "SUCCESS"

            # --- Physics & Render step ---
            dt_ms = ticks_diff(now, last_tick)
            interval = _SPEED_LEVELS_MS[self._speed_idx]

            if dt_ms >= interval:
                self._step_physics()
                self._compute_frame()
                self._render_to_matrix()

                last_tick = now

            await asyncio.sleep(0.01)
