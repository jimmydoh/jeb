"""Lorenz Attractor (Chaos Theory) – Zero Player Cellular Automaton / Math Visualizer.

A pure mathematical simulation of the iconic 1963 differential equations
developed by Edward Lorenz. It traces a continuously orbiting 3D path that
never exactly repeats itself, demonstrating deterministic chaos and the
"Butterfly Effect".

The RP2350's hardware FPU integrates the equations multiple times per frame,
plotting the results using sub-pixel bilinear interpolation and a phosphor
decay buffer to draw a smooth, glowing thread.

Controls:
    Encoder turn       : change simulation speed (integration step size)
    Button 1 (tap)     : cycle camera angle (Front, Top, Side)
    Button 2 (tap)     : reset and clear buffer
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

# Standard Lorenz parameters
_SIGMA = 10.0
_RHO   = 28.0
_BETA  = 8.0 / 3.0

# Simulation integration speeds (dt step size). Encoder selects index.
_SPEED_LEVELS = [0.001, 0.003, 0.006, 0.012, 0.020]
_SPEED_NAMES  = ["SLOW", "MED", "NORM", "FAST", "TURBO"]

# Number of Euler integration sub-steps to perform per visual frame.
# Higher = smoother continuous line instead of dotted points.
_STEPS_PER_FRAME = 8

# Phosphor fade factor applied per tick (leaves a comet trail).
_FADE = 0.92

# Camera projections: (Display Name, x_func, y_func)
# Maps the 3D Lorenz bounding box (roughly x:±20, y:±25, z:0-50) to the 16x16 grid.
_CAMERAS = [
    ("FRONT (X-Z)", lambda x, y, z: ((x + 20.0) / 40.0 * 15.0, 15.0 - (z / 50.0 * 15.0))),
    ("TOP (X-Y)",   lambda x, y, z: ((x + 20.0) / 40.0 * 15.0, (y + 25.0) / 50.0 * 15.0)),
    ("SIDE (Y-Z)",  lambda x, y, z: ((y + 25.0) / 50.0 * 15.0, 15.0 - (z / 50.0 * 15.0))),
]

class LorenzAttractor(BaseMode):
    """Lorenz Attractor Chaos Visualizer."""

    def __init__(self, core):
        super().__init__(core, "LORENZ", "Chaos Theory")
        self.width = 0
        self.height = 0
        self._buf = None         # Floating-point RGB buffer

        # Start coordinates (must be slightly offset from 0,0,0)
        self._x = 0.1
        self._y = 0.0
        self._z = 0.0

        self._speed_idx = 2      # Default to NORM
        self._cam_idx = 0        # Default to FRONT (classic butterfly)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _reset_sim(self):
        """Clear the phosphor buffer and slightly randomize the starting seed."""
        self._x = random.uniform(-0.1, 0.1)
        self._y = random.uniform(-0.1, 0.1)
        self._z = random.uniform(0.0, 0.1)

        if self._buf:
            for cell in self._buf:
                cell[0] = 0.0
                cell[1] = 0.0
                cell[2] = 0.0
        gc.collect()

    def _fade_buf(self):
        """Decay all pixels in the phosphor buffer by _FADE each tick."""
        for cell in self._buf:
            cell[0] *= _FADE
            cell[1] *= _FADE
            cell[2] *= _FADE

    def _plot(self, fx, fy, r, g, b):
        """Plot a sub-pixel point at (fx, fy) using bilinear weight distribution."""
        ix0 = int(fx)
        iy0 = int(fy)
        wx1 = fx - ix0
        wy1 = fy - iy0
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
        """Write the phosphor buffer to the matrix."""
        w = self.width
        h = self.height
        for y in range(h):
            for x in range(w):
                cell = self._buf[y * w + x]
                self.core.matrix.draw_pixel(x, y, (int(cell[0]), int(cell[1]), int(cell[2])))

    def _status_line(self):
        """Return the two status strings for the current settings."""
        speed_name = _SPEED_NAMES[self._speed_idx]
        cam_name = _CAMERAS[self._cam_idx][0]
        return (
            f"SPD: {speed_name}",
            f"CAM: {cam_name}",
        )

    # ------------------------------------------------------------------
    # Tutorial
    # ------------------------------------------------------------------

    async def run_tutorial(self):
        """
        Guided demonstration of the Lorenz Attractor.

        The Voiceover Script (audio/tutes/lorenz_tute.wav) ~48 seconds:
            [0:00] "Welcome to the Lorenz Attractor."
            [0:04] "Developed by meteorologist Edward Lorenz in 1963, this system of equations models atmospheric convection."
            [0:13] "It is the quintessential visual representation of Chaos Theory, often called the Butterfly Effect."
            [0:21] "The glowing dot traces a continuously orbiting three-dimensional path that never exactly repeats itself."
            [0:29] "Turn the main dial to adjust the speed of the mathematical integration."
            [0:35] "Press button one to change the camera projection angle."
            [0:40] "And press button two to reset the simulation from a new origin point."
            [0:45] "Embrace the chaos."
            [0:48] (End of file)
        """
        await self.core.clean_slate()
        self.game_state = "TUTORIAL"

        self.core.audio.play("audio/tutes/lorenz_tute.wav", bus_id=self.core.audio.CH_VOICE)

        self.width = self.core.matrix.width
        self.height = self.core.matrix.height
        size = self.width * self.height

        self._buf = [[0.0, 0.0, 0.0] for _ in range(size)]
        self._speed_idx = 3 # FAST so it draws the butterfly quickly
        self._cam_idx = 0   # FRONT

        self._reset_sim()

        self.core.display.use_standard_layout()
        self.core.display.update_header("LORENZ ATTRACTOR")
        self.core.display.update_footer("B1:Cam  B2:Reset")

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
                if ticks_diff(now, last_tick) >= 33: # ~30fps visual update
                    last_tick = now
                    self._fade_buf()

                    dt = _SPEED_LEVELS[self._speed_idx]
                    project_func = _CAMERAS[self._cam_idx][1]

                    for _ in range(_STEPS_PER_FRAME):
                        dx = _SIGMA * (self._y - self._x) * dt
                        dy = (self._x * (_RHO - self._z) - self._y) * dt
                        dz = (self._x * self._y - _BETA * self._z) * dt

                        self._x += dx
                        self._y += dy
                        self._z += dz

                        # Map Z-depth to Hue for 3D color mapping (0-50 maps to 0-360)
                        hue = (self._z / 50.0) * 360.0
                        r, g, b = Palette.hsv_to_rgb(hue % 360.0, 1.0, 1.0)

                        fx, fy = project_func(self._x, self._y, self._z)
                        self._plot(fx, fy, r, g, b)

                    self._render_to_matrix()
                    self.core.matrix.show_frame()

                await asyncio.sleep(0.01)

        try:
            # [0:00 - 0:13] Intro & History
            self.core.display.update_status("LORENZ ATTRACTOR", "EDWARD LORENZ 1963")
            await _sim_wait(13.0)

            # [0:13 - 0:21] Chaos Theory
            self.core.display.update_status("CHAOS THEORY", "THE BUTTERFLY EFFECT")
            await _sim_wait(8.0)

            # [0:21 - 0:29] The Path
            self.core.display.update_status("STRANGE ATTRACTOR", "INFINITE ORBIT")
            await _sim_wait(8.0)

            # [0:29 - 0:35] Speed Dial
            self.core.display.update_status("MAIN DIAL", "INTEGRATION SPEED")
            for speed in [4, 1, 2]: # TURBO -> SLOW -> MED
                self._speed_idx = speed
                _refresh_ui()
                self.core.buzzer.play_sequence(tones.UI_TICK)
                await _sim_wait(2.0)

            # [0:35 - 0:40] Camera Projection
            self.core.display.update_status("BUTTON 1", "CAMERA ANGLE")
            for _ in range(2):
                self._cam_idx = (self._cam_idx + 1) % len(_CAMERAS)
                _refresh_ui()
                self.core.buzzer.play_sequence(tones.UI_TICK)
                await _sim_wait(2.5)

            # [0:40 - 0:45] Reset
            self.core.display.update_status("BUTTON 2", "RESET ORIGIN")
            await _sim_wait(1.0)
            self._reset_sim()
            self._cam_idx = 0 # Back to classic front view
            _refresh_ui()
            self.core.buzzer.play_sequence(tones.UI_CONFIRM)
            await _sim_wait(4.0)

            # Wait for audio to finish out
            if hasattr(self.core.audio, 'wait_for_bus'):
                await self.core.audio.wait_for_bus(self.core.audio.CH_VOICE)
            else:
                await asyncio.sleep(3.0)

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
        """Main Lorenz Attractor loop."""
        JEBLogger.info("LORENZ", "[RUN] Lorenz starting")

        self.width = self.core.matrix.width
        self.height = self.core.matrix.height
        size = self.width * self.height

        if self._buf is None:
            self._buf = [[0.0, 0.0, 0.0] for _ in range(size)]
            self._speed_idx = 2
            self._cam_idx = 0
            self._reset_sim()

        self.core.display.use_standard_layout()
        self.core.display.update_header("LORENZ ATTRACTOR")
        line1, line2 = self._status_line()
        self.core.display.update_status(line1, line2)
        self.core.display.update_footer("B1:Cam  B2:Reset")

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
                new_idx = max(0, min(len(_SPEED_LEVELS) - 1, self._speed_idx + delta))
                self._speed_idx = new_idx
                self.core.hid.reset_encoder(self._speed_idx)
                last_enc = self._speed_idx
                line1, line2 = self._status_line()
                self.core.display.update_status(line1, line2)
                self.core.buzzer.play_sequence(tones.UI_TICK)

            # --- Button 1: cycle camera angle ---
            if self.core.hid.is_button_pressed(0, action="tap"):
                self._cam_idx = (self._cam_idx + 1) % len(_CAMERAS)
                line1, line2 = self._status_line()
                self.core.display.update_status(line1, line2)
                self.core.buzzer.play_sequence(tones.UI_TICK)

            # --- Button 2: reset sim ---
            if self.core.hid.is_button_pressed(1, action="tap"):
                self._reset_sim()
                line1, _ = self._status_line()
                self.core.display.update_status(line1, "RESET!")
                self.core.buzzer.play_sequence(tones.UI_CONFIRM)

            # --- Encoder long press (2 s): exit to menu ---
            if self.core.hid.is_encoder_button_pressed(long=True, duration=2000):
                JEBLogger.info("LORENZ", "[EXIT] Returning to Zero Player menu")
                return "SUCCESS"

            # --- Physics & Render step (~30 FPS) ---
            if ticks_diff(now, last_tick) >= 33:
                last_tick = now
                self._fade_buf()

                dt = _SPEED_LEVELS[self._speed_idx]
                project_func = _CAMERAS[self._cam_idx][1]

                # Perform multiple Euler integration steps per frame to draw a smooth line
                for _ in range(_STEPS_PER_FRAME):
                    dx = _SIGMA * (self._y - self._x) * dt
                    dy = (self._x * (_RHO - self._z) - self._y) * dt
                    dz = (self._x * self._y - _BETA * self._z) * dt

                    self._x += dx
                    self._y += dy
                    self._z += dz

                    hue = (self._z / 50.0) * 360.0
                    r, g, b = Palette.hsv_to_rgb(hue % 360.0, 1.0, 1.0)

                    fx, fy = project_func(self._x, self._y, self._z)
                    self._plot(fx, fy, r, g, b)

                self._render_to_matrix()
                self.core.matrix.show_frame()

            await asyncio.sleep(0.01)
