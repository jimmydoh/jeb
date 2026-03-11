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
    (5, 7),   # Complex knot
    (7, 5),   # Complex knot (inverse ratio)
    (4, 9),   # Nine-lobed
]

_RATIO_NAMES = ["1:2", "1:3", "2:3", "3:4", "3:5", "2:5", "1:4", "1:1", "5:7", "7:5", "4:9"]

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
        Encoder turn       : cycle through a:b frequency ratios or edit custom values
        Button 1 (tap)     : cycle phase-shift speed (SLOW → TURBO)
        Button 2 (tap)     : clear the phosphor buffer (instant reset)
        Button 3 (tap)     : cycle encoder focus (PRESET -> EDIT A -> EDIT B)
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

        # Custom Ratio State
        self._edit_mode = 0          # 0: Presets, 1: Custom A, 2: Custom B
        self._custom_a = 1
        self._custom_b = 2

        # Synth note handles for audio sync
        self._note_a = None
        self._note_b = None

    async def run_tutorial(self):
        """
        Guided demonstration of the Lissajous Curve Generator.

        The Voiceover Script (audio/tutes/lissajous_tute.wav) ~46 seconds:
            [0:00] "Welcome to the Lissajous Curve Generator."
            [0:04] "Named after physicist Jules Antoine Lissajous, these curves visualize the intersection of two complex harmonic waveforms."
            [0:12] "In the analog era, they were frequently generated on oscilloscopes to calibrate frequencies and test radar equipment."
            [0:20] "Turn the main dial to cycle through common preset frequency ratios."
            [0:25] "Press button three to enter custom edit mode, allowing you to dial in your own X and Y variables."
            [0:32] "Button one changes the phase-shift speed, controlling how fast the shape morphs in three-dimensional space."
            [0:39] "And button two instantly clears the phosphor trail buffer."
            [0:43] "Enjoy the mathematics."
            [0:46] (End of file)
        """
        await self.core.clean_slate()

        self.game_state = "TUTORIAL"

        self.core.audio.play(
            "audio/tutes/lissajous_tute.wav",
            bus_id=self.core.audio.CH_VOICE
        )

        # Setup standard display state for the tutorial
        self.width = self.core.matrix.width
        self.height = self.core.matrix.height
        size = self.width * self.height
        self._buf = [[0.0, 0.0, 0.0] for _ in range(size)]

        self._ratio_idx = 0
        self._phase_speed_idx = 2
        self._phase = 0.0
        self._hue = 0.0
        self._edit_mode = 0
        self._custom_a = 1
        self._custom_b = 2

        self.core.display.use_standard_layout()
        self.core.display.update_header("LISSAJOUS")
        self.core.display.update_footer("B1:Spd B2:Rst B3:Mode")

        def _refresh_ui():
            line1, line2 = self._status_line()
            self.core.display.update_status(line1, line2)

        _refresh_ui()
        self._start_audio()

        # Helper to step the visual simulation smoothly while waiting
        async def _sim_frames(frames, dt_ms=33):
            dt_s = dt_ms / 1000.0
            for _ in range(frames):
                self._phase += _PHASE_SPEEDS_MS[self._phase_speed_idx] * dt_ms
                self._hue = (self._hue + _HUE_SPEED * dt_s) % 360.0
                r_dot, g_dot, b_dot = Palette.hsv_to_rgb(self._hue, 1.0, 1.0)

                self._fade_buf()

                a, b = self._get_current_ab()
                half_x = (self.width - 1) / 2.0
                half_y = (self.height - 1) / 2.0
                step = (2.0 * math.pi) / _PLOT_STEPS
                for i in range(_PLOT_STEPS):
                    t = i * step
                    fx = half_x * math.sin(a * t + self._phase) + half_x
                    fy = half_y * math.sin(b * t) + half_y
                    self._plot(fx, fy, r_dot, g_dot, b_dot)

                self._render_to_matrix()
                self.core.matrix.show_frame()
                await asyncio.sleep(dt_s)

        try:
            # [0:00 - 0:20] Intro, history, and base drawing
            self.core.display.update_status("LISSAJOUS CURVES", "MATHEMATICAL ART")
            await _sim_frames(20 * 30) # ~20 seconds at 30fps

            # [0:20 - 0:25] Preset cycling
            self.core.display.update_status("MAIN DIAL", "CYCLE PRESETS")
            for _ in range(3):
                self._ratio_idx = (self._ratio_idx + 1) % len(_RATIOS)
                self._clear_buf()
                self._phase = 0.0
                self._start_audio()
                _refresh_ui()
                self.core.buzzer.play_sequence(tones.UI_TICK)
                await _sim_frames(50) # ~1.6 seconds per preset

            # [0:25 - 0:32] Custom edit mode
            self.core.display.update_status("BUTTON 3", "CUSTOM VARIABLES")
            self._edit_mode = 1 # Switch to Edit A
            self._custom_a, self._custom_b = _RATIOS[self._ratio_idx]
            _refresh_ui()
            self.core.buzzer.play_sequence(tones.COIN)
            await _sim_frames(60)

            # Simulate turning the dial to bump custom variable A
            self._custom_a += 2
            self._clear_buf()
            self._phase = 0.0
            self._start_audio()
            _refresh_ui()
            self.core.buzzer.play_sequence(tones.UI_TICK)
            await _sim_frames(90)

            # [0:32 - 0:39] Speed change
            self.core.display.update_status("BUTTON 1", "CHANGE SPEED")
            self._phase_speed_idx = 4 # Kick it to TURBO
            _refresh_ui()
            self.core.buzzer.play_sequence(tones.UI_TICK)
            await _sim_frames(180)

            # [0:39 - 0:43] Buffer clear
            self.core.display.update_status("BUTTON 2", "CLEAR BUFFER")
            self._clear_buf()
            self._phase = 0.0
            self.core.buzzer.play_sequence(tones.UI_CONFIRM)
            await _sim_frames(120)

            # Wait for audio to finish out if it's still running
            if hasattr(self.core.audio, 'wait_for_bus'):
                await self.core.audio.wait_for_bus(self.core.audio.CH_VOICE)
            else:
                await asyncio.sleep(2.0)

        finally:
            self._stop_audio()
            await self.core.clean_slate()

        return "TUTORIAL_COMPLETE"

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

    def _get_current_ab(self):
        """Return the current (a, b) values based on edit mode."""
        if self._edit_mode == 0:
            return _RATIOS[self._ratio_idx]
        return (self._custom_a, self._custom_b)

    def _start_audio(self):
        """Start two synth drone notes matching the current a:b ratio."""
        self._stop_audio()
        try:
            from utilities.synth_registry import Patches
            a, b = self._get_current_ab()
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
        if self._edit_mode == 0:
            ratio_str = f"PRESET: {_RATIO_NAMES[self._ratio_idx]}"
        elif self._edit_mode == 1:
            ratio_str = f"CUSTOM: >{self._custom_a}< : {self._custom_b}"
        else:
            ratio_str = f"CUSTOM: {self._custom_a} : >{self._custom_b}<"

        return (
            ratio_str,
            f"SPEED:  {_PHASE_SPEED_NAMES[self._phase_speed_idx]}",
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
        self._edit_mode = 0

        # UI setup
        self.core.display.use_standard_layout()
        self.core.display.update_header("LISSAJOUS")
        line1, line2 = self._status_line()
        self.core.display.update_status(line1, line2)
        self.core.display.update_footer("B1:Spd  B2:Rst  B3:Mode")

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

                # --- Encoder: cycle frequency ratio or edit custom values ---
                enc = self.core.hid.encoder_position()
                diff = enc - last_enc
                if diff != 0:
                    delta = 1 if diff > 0 else -1

                    if self._edit_mode == 0:
                        self._ratio_idx = (self._ratio_idx + delta) % len(_RATIOS)
                        self.core.hid.reset_encoder(self._ratio_idx)
                        last_enc = self._ratio_idx
                    elif self._edit_mode == 1:
                        # Clamp custom 'a' between 1 and 20
                        self._custom_a = max(1, min(20, self._custom_a + delta))
                        self.core.hid.reset_encoder(self._custom_a)
                        last_enc = self._custom_a
                    elif self._edit_mode == 2:
                        # Clamp custom 'b' between 1 and 20
                        self._custom_b = max(1, min(20, self._custom_b + delta))
                        self.core.hid.reset_encoder(self._custom_b)
                        last_enc = self._custom_b

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

                # --- Button 3: cycle edit mode (Preset -> Edit A -> Edit B) ---
                if self.core.hid.is_button_pressed(2, action="tap"):
                    old_mode = self._edit_mode
                    self._edit_mode = (self._edit_mode + 1) % 3

                    # If transitioning from Presets to Custom, copy current preset as a starting point
                    if self._edit_mode == 1 and old_mode == 0:
                        self._custom_a, self._custom_b = _RATIOS[self._ratio_idx]

                    # Reset the hardware encoder tracking to match the new focus
                    if self._edit_mode == 0:
                        self.core.hid.reset_encoder(self._ratio_idx)
                        last_enc = self._ratio_idx
                    elif self._edit_mode == 1:
                        self.core.hid.reset_encoder(self._custom_a)
                        last_enc = self._custom_a
                    elif self._edit_mode == 2:
                        self.core.hid.reset_encoder(self._custom_b)
                        last_enc = self._custom_b

                    self._start_audio()
                    line1, line2 = self._status_line()
                    self.core.display.update_status(line1, line2)
                    self.core.buzzer.play_sequence(tones.COIN)

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
