"""Lissajous Curve Generator – Zero Player Retro Screensaver."""

import asyncio
import math
import time

from adafruit_ticks import ticks_ms, ticks_diff

from utilities import tones
from utilities.palette import Palette
from utilities.logger import JEBLogger

from .base import BaseMode

# Frequency ratio presets (a : b).
# Each pair creates a distinct Lissajous figure.
_RATIOS = [
    (1, 2),   # Figure-8 / bow-tie
    (1, 3),   # Three-lobed curve
    (2, 3),   # Classic knot
    (3, 4),   # Star-like
    (3, 5),   # Five-petal
    (2, 5),   # Five-loop
    (1, 4),   # Four-lobed
    (1, 1),   # Circle / lemniscate (phase-dependent)
]

_RATIO_NAMES = ["1:2", "1:3", "2:3", "3:4", "3:5", "2:5", "1:4", "1:1"]

# Base audio frequency for the synth drone channels (Hz).
_BASE_FREQ = 110.0   # A2

# Phase-shift speed presets (radians per millisecond).
# Controls how fast the Lissajous figure morphs between frames.
_PHASE_SPEEDS_MS = [0.00005, 0.0001, 0.0002, 0.0005, 0.001]
_PHASE_SPEED_NAMES = ["SLOW", "MED", "NORM", "FAST", "TURBO"]

# Phosphor fade factor applied per tick (~30 fps → 0.88^30 ≈ 5 % residual after 1 s).
_FADE = 0.88

# Hue rotation speed (degrees per second).
_HUE_SPEED = 20.0

# Number of parametric sub-steps plotted per frame.
# More steps → denser, smoother trails; 64 gives a good balance.
_PLOT_STEPS = 64


class LissajousMode(BaseMode):
    """Lissajous Curve Generator – zero-player retro oscilloscope screensaver.

    Plots the parametric equations

        x(t) = A · sin(a·t + δ)
        y(t) = B · sin(b·t)

    on the LED matrix.  Three visual techniques make the low-resolution grid
    look great:

    1. **Phosphor fade** – pixels decay rather than the screen being cleared,
       producing a glowing comet trail that the eye fills in.
    2. **Sub-pixel anti-aliasing** – fractional pixel positions distribute
       brightness across the four surrounding LEDs for smooth motion.
    3. **Hue rotation** – the active dot colour cycles through the full
       spectrum, adding a 3-D depth illusion as the curve overlaps itself.

    When the SynthManager is available, two sustained drone notes are played
    whose frequency ratio mirrors the Lissajous a:b parameter, turning the
    matrix into a live XY-oscilloscope audio visualiser.

    Controls:
        Encoder turn       : cycle through a:b frequency ratios
        Button 1 (tap)     : cycle phase-shift speed (SLOW → TURBO)
        Button 2 (tap)     : clear the phosphor buffer (instant reset)
        Encoder long press : return to Zero Player menu
    """

    def __init__(self, core):
        super().__init__(core, "LISSAJOUS", "Retro Screensaver")
        self.width = 0
        self.height = 0
        # Floating-point RGB buffer – one [r, g, b] list per pixel.
        self._buf = None
        self._ratio_idx = 0
        self._phase_speed_idx = 2    # Default: NORM
        self._phase = 0.0            # Current phase offset δ (radians)
        self._hue = 0.0              # Current hue angle (degrees)
        # Synth note handles for audio sync
        self._note_a = None
        self._note_b = None

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _clear_buf(self):
        """Zero the phosphor buffer."""
        for cell in self._buf:
            cell[0] = 0.0
            cell[1] = 0.0
            cell[2] = 0.0

    def _fade_buf(self):
        """Decay all pixels in the phosphor buffer by _FADE each tick."""
        for cell in self._buf:
            cell[0] *= _FADE
            cell[1] *= _FADE
            cell[2] *= _FADE

    def _plot(self, fx, fy, r, g, b):
        """Plot a sub-pixel point at (fx, fy) using bilinear weight distribution.

        Distributes brightness across the four nearest integer pixels according
        to their fractional distance from (fx, fy), smoothing the dot's apparent
        position between physical LEDs.
        """
        ix0 = int(fx)
        iy0 = int(fy)
        wx1 = fx - ix0   # fractional weight for the right neighbour
        wy1 = fy - iy0   # fractional weight for the bottom neighbour
        wx0 = 1.0 - wx1
        wy0 = 1.0 - wy1
        w = self.width
        h = self.height
        for px, wx in ((ix0, wx0), (ix0 + 1, wx1)):
            for py, wy in ((iy0, wy0), (iy0 + 1, wy1)):
                if 0 <= px < w and 0 <= py < h:
                    weight = wx * wy
                    cell = self._buf[py * w + px]
                    cell[0] = min(255.0, cell[0] + r * weight)
                    cell[1] = min(255.0, cell[1] + g * weight)
                    cell[2] = min(255.0, cell[2] + b * weight)

    def _render_to_matrix(self):
        """Write the phosphor buffer to the matrix animation slots."""
        w = self.width
        h = self.height
        for y in range(h):
            for x in range(w):
                cell = self._buf[y * w + x]
                self.core.matrix.draw_pixel(x, y, (int(cell[0]), int(cell[1]), int(cell[2])))

    def _start_audio(self):
        """Start two synth drone notes matching the current a:b ratio."""
        self._stop_audio()
        try:
            from utilities.synth_registry import Patches
            a, b = _RATIOS[self._ratio_idx]
            self._note_a = self.core.synth.play_note(_BASE_FREQ * a, Patches.ENGINE_HUM)
            self._note_b = self.core.synth.play_note(_BASE_FREQ * b, Patches.ENGINE_HUM)
        except Exception:
            pass

    def _stop_audio(self):
        """Release the two drone notes if they are active."""
        try:
            if self._note_a is not None:
                self.core.synth.stop_note(self._note_a)
                self._note_a = None
            if self._note_b is not None:
                self.core.synth.stop_note(self._note_b)
                self._note_b = None
        except Exception:
            pass

    def _status_line(self):
        """Return the two status strings for the current state."""
        return (
            f"RATIO {_RATIO_NAMES[self._ratio_idx]}",
            f"SPEED {_PHASE_SPEED_NAMES[self._phase_speed_idx]}",
        )

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    async def run(self):
        """Main Lissajous simulation loop."""
        JEBLogger.info("LISS", "[RUN] LissajousMode starting")

        self.width = self.core.matrix.width
        self.height = self.core.matrix.height
        size = self.width * self.height

        # Initialise the floating-point RGB phosphor buffer
        self._buf = [[0.0, 0.0, 0.0] for _ in range(size)]
        self._ratio_idx = 0
        self._phase_speed_idx = 2
        self._phase = 0.0
        self._hue = 0.0

        # UI setup
        self.core.display.use_standard_layout()
        self.core.display.update_header("LISSAJOUS")
        line1, line2 = self._status_line()
        self.core.display.update_status(line1, line2)
        self.core.display.update_footer("B1:Speed  B2:Reset")

        self.core.hid.flush()
        self.core.hid.reset_encoder(self._ratio_idx)
        last_enc = self.core.hid.encoder_position()

        # Start audio sync
        self._start_audio()

        last_tick = ticks_ms()

        try:
            while True:
                now = ticks_ms()
                dt_ms = ticks_diff(now, last_tick)
                if dt_ms < 1:
                    await asyncio.sleep(0.01)
                    continue
                last_tick = now
                dt_s = dt_ms / 1000.0

                # --- Encoder: cycle frequency ratio ---
                enc = self.core.hid.encoder_position()
                diff = enc - last_enc
                if diff != 0:
                    delta = 1 if diff > 0 else -1
                    self._ratio_idx = (self._ratio_idx + delta) % len(_RATIOS)
                    self.core.hid.reset_encoder(self._ratio_idx)
                    last_enc = self._ratio_idx
                    self._clear_buf()
                    self._phase = 0.0
                    self._start_audio()
                    line1, line2 = self._status_line()
                    self.core.display.update_status(line1, line2)
                    self.core.buzzer.play_sequence(tones.UI_TICK)

                # --- Button 1: cycle phase-shift speed ---
                if self.core.hid.is_button_pressed(0, action="tap"):
                    self._phase_speed_idx = (self._phase_speed_idx + 1) % len(_PHASE_SPEEDS_MS)
                    line1, line2 = self._status_line()
                    self.core.display.update_status(line1, line2)
                    self.core.buzzer.play_sequence(tones.UI_TICK)

                # --- Button 2: clear the phosphor buffer ---
                if self.core.hid.is_button_pressed(1, action="tap"):
                    self._clear_buf()
                    self._phase = 0.0
                    line1, _ = self._status_line()
                    self.core.display.update_status(line1, "CLEARED!")
                    self.core.buzzer.play_sequence(tones.UI_CONFIRM)

                # --- Encoder long press (2 s): exit to Zero Player menu ---
                if self.core.hid.is_encoder_button_pressed(long=True, duration=2000):
                    JEBLogger.info("LISS", "[EXIT] Returning to Zero Player menu")
                    return "SUCCESS"

                # --- Simulation: fade → hue advance → plot → render ---

                # Advance phase offset (drives the morphing animation)
                self._phase += _PHASE_SPEEDS_MS[self._phase_speed_idx] * dt_ms

                # Advance hue (Z-axis colour modulation)
                self._hue = (self._hue + _HUE_SPEED * dt_s) % 360.0
                r_dot, g_dot, b_dot = Palette.hsv_to_rgb(self._hue, 1.0, 1.0)

                # Phosphor decay
                self._fade_buf()

                # Plot _PLOT_STEPS sub-steps of the parametric curve
                a, b = _RATIOS[self._ratio_idx]
                half_x = (self.width - 1) / 2.0
                half_y = (self.height - 1) / 2.0
                step = (2.0 * math.pi) / _PLOT_STEPS
                for i in range(_PLOT_STEPS):
                    t = i * step
                    fx = half_x * math.sin(a * t + self._phase) + half_x
                    fy = half_y * math.sin(b * t) + half_y
                    self._plot(fx, fy, r_dot, g_dot, b_dot)

                # Push buffer to matrix
                self._render_to_matrix()

                await asyncio.sleep(0.01)

        finally:
            self._stop_audio()
