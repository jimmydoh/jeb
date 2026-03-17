"""Demoscene Plasma Visualizer – Zero Player Mode.

Classic 16-bit demoscene plasma effect using intersecting sine and cosine
waves to generate continuously shifting, wavy colour blobs.  The RP2350's
hardware FPU keeps the per-frame trigonometry fast enough for silky-smooth
animation.

The plasma value for each pixel (x, y) is calculated as:

    v = sin(x * freq + t)
      + cos(y * freq + t * 0.7)
      + sin((x + y) * freq * 0.5 + t * 1.3)
      + sin(sqrt(x² + y²) * freq + t * 0.9)

The result is normalised to [0, 1] and used to index into a continuously
cycling HSV colour palette, producing the signature plasma colour waves.

Controls:
    Encoder turn       : shift palette hue offset in real-time
    Button 1 (tap)     : cycle wave frequency (WIDE → MICRO)
    Button 2 (tap)     : toggle colour speed (DRIFT ↔ STORM)
    Encoder long press : return to Zero Player menu
"""

import asyncio
import gc
import math

from adafruit_ticks import ticks_ms, ticks_diff

from utilities import tones
from utilities.palette import Palette
from utilities.logger import JEBLogger

from .base import BaseMode

# ---------------------------------------------------------------------------
# Tunable constants
# ---------------------------------------------------------------------------

# Wave frequency presets – controls how tightly packed the plasma blobs are.
_FREQ_LEVELS = [0.3, 0.5, 0.8, 1.2, 1.8]
_FREQ_NAMES = ["WIDE", "MED", "NORM", "TIGHT", "MICRO"]

# Colour cycle speed presets (hue degrees per second).
_HUE_SPEEDS = [15.0, 45.0]
_HUE_SPEED_NAMES = ["DRIFT", "STORM"]

# Time advance per frame (controls animation speed, seconds per second).
_TIME_SCALE = 1.2

# Target frame interval in milliseconds (~33 fps).
_FRAME_MS = 30


class PlasmaMode(BaseMode):
    """Demoscene Plasma Visualizer – zero-player retro graphics showpiece.

    Renders the classic plasma effect by evaluating a sum of sine and cosine
    waves at every LED pixel each frame.  The continuously advancing time
    variable causes the waves to ripple and shimmer.

    The encoder shifts the palette hue offset in real-time; Button 1 changes
    wave frequency so the blobs can range from wide, lazy swells to tight,
    flickering crackle.

    Controls:
        Encoder turn       : shift palette hue offset in real-time
        Button 1 (tap)     : cycle wave frequency (WIDE → MICRO)
        Button 2 (tap)     : toggle colour speed (DRIFT ↔ STORM)
        Encoder long press : return to Zero Player menu
    """

    def __init__(self, core):
        super().__init__(core, "PLASMA", "Demoscene Plasma")
        self.width = 0
        self.height = 0
        # Pre-allocated RGB frame buffer – one [r, g, b] list per pixel.
        # Avoids per-frame heap allocation to minimise GC pressure.
        self._buf = None
        self._freq_idx = 2       # Default: NORM
        self._hue_speed_idx = 0  # Default: DRIFT
        self._time = 0.0         # Animation clock (seconds)
        self._hue_offset = 0.0   # Palette hue shift driven by encoder (degrees)

    async def run_tutorial(self):
        """
        Guided demonstration of the Demoscene Plasma Visualizer.

        The Voiceover Script (audio/tutes/plasma_tute.wav) ~48 seconds:
            [0:00] "Welcome to the Demoscene Plasma Visualizer."
            [0:05] "A staple of 1990s demoscene coding, this effect is generated entirely by math in real-time."
            [0:12] "It calculates intersecting sine and cosine waves at every single pixel to create continuously shifting color blobs."
            [0:21] "Press button one to change the wave frequency, morphing from wide, lazy swells to tight, flickering static."
            [0:31] "Press button two to toggle the color cycling speed between a gentle drift and a raging storm."
            [0:39] "And turn the main dial to manually push the palette through the color spectrum."
            [0:45] "Enjoy the visualizer."
            [0:48] (End of file)
        """
        await self.core.clean_slate()

        self.game_state = "TUTORIAL"

        # Trigger audio synchronously (fire-and-forget)
        self.core.audio.play(
            "audio/tutes/plasma_tute.wav",
            bus_id=self.core.audio.CH_VOICE
        )

        # Setup standard display state for the tutorial
        self.width = self.core.matrix.width
        self.height = self.core.matrix.height
        size = self.width * self.height

        self._buf = [[0, 0, 0] for _ in range(size)]
        self._freq_idx = 0       # Start on WIDE so the math is obvious
        self._hue_speed_idx = 0  # Start on DRIFT
        self._time = 0.0
        self._hue_offset = 0.0

        self.core.display.use_standard_layout()
        self.core.display.update_header("PLASMA")
        self.core.display.update_footer("B1:Freq  B2:Speed")

        def _refresh_ui():
            line1, line2 = self._status_line()
            self.core.display.update_status(line1, line2)

        _refresh_ui()

        async def _sim_wait(duration_s):
            """Runs the plasma simulation continuously for the specified duration."""
            start_time = ticks_ms()
            last_tick = start_time
            target_ms = int(duration_s * 1000)

            while ticks_diff(ticks_ms(), start_time) < target_ms:
                now = ticks_ms()
                dt_ms = ticks_diff(now, last_tick)

                if dt_ms >= _FRAME_MS:
                    dt_s = dt_ms / 1000.0
                    last_tick = now

                    # Advance animation clock
                    self._time += dt_s * _TIME_SCALE

                    # Advance hue offset for automatic colour cycling
                    hue_speed = _HUE_SPEEDS[self._hue_speed_idx]
                    self._hue_offset = (self._hue_offset + hue_speed * dt_s) % 360.0

                    self._compute_frame()
                    self._render_to_matrix()


                await asyncio.sleep(0.01)

        try:
            # [0:00 - 0:12] Intro & Demoscene Context
            self.core.display.update_status("PLASMA VISUALIZER", "1990s DEMOSCENE")
            await _sim_wait(12.0)

            # [0:12 - 0:21] Math explanation
            self.core.display.update_status("REAL-TIME MATH", "SINE & COSINE WAVES")
            await _sim_wait(9.0)

            # [0:21 - 0:31] Button 1: Frequency Cycle
            self.core.display.update_status("BUTTON 1", "CYCLE FREQUENCY")
            for _ in range(4):
                await _sim_wait(2.0)
                self._freq_idx = (self._freq_idx + 1) % len(_FREQ_LEVELS)
                _refresh_ui()
                self.core.buzzer.play_sequence(tones.UI_TICK)
            await _sim_wait(2.0)

            # [0:31 - 0:39] Button 2: Color Speed Toggle
            self.core.display.update_status("BUTTON 2", "COLOR SPEED")
            await _sim_wait(1.5)
            self._hue_speed_idx = 1 # Toggle to STORM
            _refresh_ui()
            self.core.buzzer.play_sequence(tones.UI_TICK)
            await _sim_wait(6.5)

            # [0:39 - 0:45] Main Dial: Hue shift
            self.core.display.update_status("MAIN DIAL", "SHIFT HUE")
            # Simulate the user spinning the dial by rapidly shifting the offset
            spin_start = ticks_ms()
            while ticks_diff(ticks_ms(), spin_start) < 6000:
                self._hue_offset = (self._hue_offset + 10.0) % 360.0
                await _sim_wait(0.1)

            # Wait for audio to finish out if it's still running
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
    # Private helpers
    # ------------------------------------------------------------------

    def _compute_frame(self):
        """Evaluate the plasma equation and write RGB values into _buf.

        For each pixel (x, y) the four-wave plasma value is computed,
        normalised to [0, 1], and converted to an HSV colour whose hue
        cycles continuously.  Results are stored as integer RGB tuples in
        the pre-allocated buffer.
        """
        freq = _FREQ_LEVELS[self._freq_idx]
        t = self._time
        hue_off = self._hue_offset
        w = self.width
        h = self.height
        idx = 0
        for y in range(h):
            for x in range(w):
                # Evaluate four overlapping waves.
                v = (math.sin(x * freq + t)
                     + math.cos(y * freq + t * 0.7)
                     + math.sin((x + y) * freq * 0.5 + t * 1.3)
                     + math.sin(math.sqrt(x * x + y * y) * freq + t * 0.9))
                # Normalise from [-4, 4] to [0, 1].
                v = (v + 4.0) * 0.125
                # Map to hue (0–360 degrees) with palette offset applied.
                hue = (v * 360.0 + hue_off) % 360.0
                r, g, b = Palette.hsv_to_rgb(hue, 1.0, 1.0)
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
        return (
            f"FREQ {_FREQ_NAMES[self._freq_idx]}",
            f"CLR {_HUE_SPEED_NAMES[self._hue_speed_idx]}",
        )

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    async def run(self):
        """Main plasma simulation loop."""
        JEBLogger.info("PLASMA", "[RUN] PlasmaMode starting")

        self.width = self.core.matrix.width
        self.height = self.core.matrix.height
        size = self.width * self.height

        # Allocate the RGB frame buffer once; reuse every frame.
        self._buf = [[0, 0, 0] for _ in range(size)]
        self._freq_idx = 2
        self._hue_speed_idx = 0
        self._time = 0.0
        self._hue_offset = 0.0

        # Trigger a GC pass now rather than mid-animation.
        gc.collect()

        # UI setup
        self.core.display.use_standard_layout()
        self.core.display.update_header("PLASMA")
        line1, line2 = self._status_line()
        self.core.display.update_status(line1, line2)
        self.core.display.update_footer("B1:Freq  B2:Speed")

        self.core.hid.flush()
        self.core.hid.reset_encoder(0)
        last_enc = self.core.hid.encoder_position()
        last_tick = ticks_ms()

        try:
            while True:
                now = ticks_ms()
                dt_ms = ticks_diff(now, last_tick)
                if dt_ms < _FRAME_MS:
                    await asyncio.sleep(0.01)
                    continue
                last_tick = now
                dt_s = dt_ms / 1000.0

                # --- Encoder: shift hue palette offset ---
                enc = self.core.hid.encoder_position()
                diff = enc - last_enc
                if diff != 0:
                    self._hue_offset = (self._hue_offset + diff * 5.0) % 360.0
                    self.core.hid.reset_encoder(0)
                    last_enc = 0

                # --- Button 1: cycle wave frequency ---
                if self.core.hid.is_button_pressed(0, action="tap"):
                    self._freq_idx = (self._freq_idx + 1) % len(_FREQ_LEVELS)
                    line1, line2 = self._status_line()
                    self.core.display.update_status(line1, line2)
                    self.core.buzzer.play_sequence(tones.UI_TICK)

                # --- Button 2: toggle colour speed ---
                if self.core.hid.is_button_pressed(1, action="tap"):
                    self._hue_speed_idx = (self._hue_speed_idx + 1) % len(_HUE_SPEEDS)
                    line1, line2 = self._status_line()
                    self.core.display.update_status(line1, line2)
                    self.core.buzzer.play_sequence(tones.UI_TICK)

                # --- Encoder long press (2 s): exit to Zero Player menu ---
                if self.core.hid.is_encoder_button_pressed(long=True, duration=2000):
                    JEBLogger.info("PLASMA", "[EXIT] Returning to Zero Player menu")
                    return "SUCCESS"

                # --- Advance animation clock ---
                self._time += dt_s * _TIME_SCALE

                # --- Advance hue offset for automatic colour cycling ---
                hue_speed = _HUE_SPEEDS[self._hue_speed_idx]
                self._hue_offset = (self._hue_offset + hue_speed * dt_s) % 360.0

                # --- Evaluate plasma and push to matrix ---
                self._compute_frame()
                self._render_to_matrix()

        finally:
            pass
