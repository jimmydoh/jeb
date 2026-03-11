"""Vector Flow Field – Zero Player Cellular Automaton / Math Visualizer.

Simulates the swirling, turbulent motion of wind, water currents, or
magnetic fields. Glowing particles are dropped onto the grid and swept
away by an invisible 2D vector field.

The angle of the field at any point is determined by a continuous 3D noise
function (X, Y, and Time). To maximize the performance of the RP2350 FPU,
this mode uses a trigonometric pseudo-noise approximation rather than
traditional lattice-hash Perlin noise, allowing for high particle counts
with silky-smooth sub-pixel FPU interpolation.

Controls:
    Encoder turn       : change noise evolution speed (wind shifting)
    Button 1 (tap)     : cycle color mapping (Rainbow / Thermal / Ocean / Cyber)
    Button 2 (tap)     : scatter / respawn all particles
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

_NUM_PARTICLES = 60

# Simulation update intervals in milliseconds (encoder selects index).
# This controls the *evolution* of the noise field over time (how fast the wind shifts).
_SPEED_LEVELS = [0.005, 0.015, 0.030, 0.060, 0.120]
_SPEED_NAMES  = ["STILL", "BREEZE", "WINDY", "GALE", "STORM"]

# Phosphor fade factor applied per tick (leaves a sweeping comet trail).
_FADE = 0.88

# Color Themes: (Display Name, Base Hue, Range)
# The angle of the vector (0 to 2*PI) is mapped to this hue range.
_THEMES = [
    ("RAINBOW", 0.0, 360.0),    # Full spectrum
    ("THERMAL", 0.0, 60.0),     # Red to Yellow
    ("OCEANIC", 180.0, 60.0),   # Cyan to Deep Blue
    ("CYBER", 280.0, 80.0),     # Purple to Pink/Red
]

class VectorFlowMode(BaseMode):
    """Perlin Vector Flow Field visualizer."""

    def __init__(self, core):
        super().__init__(core, "FLOW FIELD", "Vector Flow Visualizer")
        self.width = 0
        self.height = 0
        self._buf = None         # Floating-point RGB buffer

        # Particle list: [x, y, age, max_age]
        self._particles = []

        self._speed_idx = 2      # Default: WINDY
        self._theme_idx = 0      # Default: RAINBOW
        self._time = 0.0

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _pseudo_noise(self, x, y, z):
        """
        Trigonometric approximation of 3D continuous noise.
        Executes extremely fast on the RP2350 FPU compared to array-hash Perlin.
        Returns a value roughly between -1.0 and 1.0.
        """
        scale = 0.25
        v = (math.sin(x * scale + z) +
             math.sin(y * scale - z * 0.8) +
             math.cos((x + y) * scale * 0.7 + z * 1.1) +
             math.sin((x - y) * scale * 0.9 - z * 0.9))
        return v * 0.25

    def _spawn_particle(self):
        """Return a newly spawned particle [x, y, age, max_age]."""
        w, h = self.width, self.height
        x = random.uniform(0.0, w - 1.0)
        y = random.uniform(0.0, h - 1.0)
        age = 0
        max_age = random.randint(20, 100)
        return [x, y, age, max_age]

    def _reset_sim(self):
        """Clear the phosphor buffer and respawn all particles."""
        self._particles = [self._spawn_particle() for _ in range(_NUM_PARTICLES)]

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
        theme_name = _THEMES[self._theme_idx][0]
        return (
            f"WIND: {speed_name}",
            f"MAP:  {theme_name}",
        )

    # ------------------------------------------------------------------
    # Tutorial
    # ------------------------------------------------------------------

    async def run_tutorial(self):
        """
        Guided demonstration of the Vector Flow Field.

        The Voiceover Script (audio/tutes/flow_tute.wav) ~52 seconds:
            [0:00] "Welcome to the Vector Flow Field."
            [0:04] "Using mathematical algorithms, like those developed by Ken Perlin for the movie Tron, we can generate smooth, invisible currents."
            [0:15] "Millions of virtual forces push our glowing particles across the matrix, creating swirling, turbulent eddies."
            [0:26] "Turn the main dial to adjust the evolution speed of the noise field, making the wind shift faster."
            [0:34] "Press button one to cycle the color mapping, which assigns a specific hue to the current direction of the wind."
            [0:43] "And press button two to scatter the particles."
            [0:48] "Observe the flow."
            [0:52] (End of file)
        """
        await self.core.clean_slate()
        self.game_state = "TUTORIAL"

        self.core.audio.play("audio/tutes/flow_tute.wav", bus_id=self.core.audio.CH_VOICE)

        self.width = self.core.matrix.width
        self.height = self.core.matrix.height
        size = self.width * self.height

        self._buf = [[0.0, 0.0, 0.0] for _ in range(size)]
        self._speed_idx = 1 # Start on BREEZE so the patterns are easily tracked
        self._theme_idx = 0 # RAINBOW
        self._time = 0.0

        self._reset_sim()

        self.core.display.use_standard_layout()
        self.core.display.update_header("FLOW FIELD")
        self.core.display.update_footer("B1:Color  B2:Reset")

        def _refresh_ui():
            line1, line2 = self._status_line()
            self.core.display.update_status(line1, line2)

        _refresh_ui()

        async def _sim_wait(duration_s):
            """Runs the continuous simulation."""
            start_time = ticks_ms()
            last_tick = start_time
            target_ms = int(duration_s * 1000)

            base_hue = _THEMES[self._theme_idx][1]
            hue_range = _THEMES[self._theme_idx][2]

            while ticks_diff(ticks_ms(), start_time) < target_ms:
                now = ticks_ms()
                if ticks_diff(now, last_tick) >= 33: # ~30fps visual update
                    last_tick = now
                    self._fade_buf()

                    dt = _SPEED_LEVELS[self._speed_idx]
                    self._time += dt

                    for i in range(len(self._particles)):
                        p = self._particles[i]
                        x, y, age, max_age = p[0], p[1], p[2], p[3]

                        # Sample the noise field to get an angle (-PI to PI)
                        noise_val = self._pseudo_noise(x, y, self._time)
                        angle = noise_val * math.pi * 2.0

                        # Move particle
                        speed = 0.5
                        nx = x + math.cos(angle) * speed
                        ny = y + math.sin(angle) * speed

                        # Map direction angle to color theme
                        normalized_angle = (angle + math.pi) / (2.0 * math.pi)
                        hue = (base_hue + normalized_angle * hue_range) % 360.0

                        # Fade out smoothly as they near max age
                        brightness = 1.0 - (age / max_age)
                        r, g, b = Palette.hsv_to_rgb(hue, 1.0, brightness)

                        self._plot(nx, ny, r, g, b)

                        age += 1
                        if age > max_age or nx < 0 or nx >= self.width or ny < 0 or ny >= self.height:
                            self._particles[i] = self._spawn_particle()
                        else:
                            p[0], p[1], p[2] = nx, ny, age

                    self._render_to_matrix()
                    self.core.matrix.show_frame()

                await asyncio.sleep(0.01)

        try:
            # [0:00 - 0:15] Intro & Tron context
            self.core.display.update_status("VECTOR FLOW", "KEN PERLIN (TRON)")
            await _sim_wait(15.0)

            # [0:15 - 0:26] The swirling eddies
            self.core.display.update_status("TURBULENCE", "INVISIBLE CURRENTS")
            await _sim_wait(11.0)

            # [0:26 - 0:34] Speed Dial (Noise evolution time-step)
            self.core.display.update_status("MAIN DIAL", "SHIFTING WINDS")
            for speed in [2, 3, 4]: # WINDY -> STORM
                self._speed_idx = speed
                _refresh_ui()
                self.core.buzzer.play_sequence(tones.UI_TICK)
                await _sim_wait(2.6)

            # [0:34 - 0:43] Color Mapping
            self.core.display.update_status("BUTTON 1", "COLOR MAPPING")
            for _ in range(3):
                self._theme_idx = (self._theme_idx + 1) % len(_THEMES)
                _refresh_ui()
                self.core.buzzer.play_sequence(tones.UI_TICK)
                await _sim_wait(3.0)

            # [0:43 - 0:48] Reset
            self.core.display.update_status("BUTTON 2", "SCATTER PARTICLES")
            await _sim_wait(1.0)
            self._reset_sim()
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
        """Main Vector Flow Field loop."""
        JEBLogger.info("FLOW", "[RUN] Flow Field starting")

        self.width = self.core.matrix.width
        self.height = self.core.matrix.height
        size = self.width * self.height

        if self._buf is None:
            self._buf = [[0.0, 0.0, 0.0] for _ in range(size)]
            self._speed_idx = 2
            self._theme_idx = 0
            self._time = 0.0
            self._reset_sim()

        self.core.display.use_standard_layout()
        self.core.display.update_header("FLOW FIELD")
        line1, line2 = self._status_line()
        self.core.display.update_status(line1, line2)
        self.core.display.update_footer("B1:Color  B2:Reset")

        self.core.hid.flush()
        self.core.hid.reset_encoder(self._speed_idx)
        last_enc = self.core.hid.encoder_position()
        last_tick = ticks_ms()

        while True:
            now = ticks_ms()

            # --- Encoder: adjust wind shifting speed ---
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

            # --- Button 1: cycle color mapping ---
            if self.core.hid.is_button_pressed(0, action="tap"):
                self._theme_idx = (self._theme_idx + 1) % len(_THEMES)
                line1, line2 = self._status_line()
                self.core.display.update_status(line1, line2)
                self.core.buzzer.play_sequence(tones.UI_TICK)

            # --- Button 2: scatter particles ---
            if self.core.hid.is_button_pressed(1, action="tap"):
                self._reset_sim()
                line1, _ = self._status_line()
                self.core.display.update_status(line1, "SCATTERED!")
                self.core.buzzer.play_sequence(tones.UI_CONFIRM)

            # --- Encoder long press (2 s): exit to menu ---
            if self.core.hid.is_encoder_button_pressed(long=True, duration=2000):
                JEBLogger.info("FLOW", "[EXIT] Returning to Zero Player menu")
                return "SUCCESS"

            # --- Physics & Render step (~30 FPS) ---
            if ticks_diff(now, last_tick) >= 33:
                last_tick = now
                self._fade_buf()

                dt = _SPEED_LEVELS[self._speed_idx]
                self._time += dt

                base_hue = _THEMES[self._theme_idx][1]
                hue_range = _THEMES[self._theme_idx][2]

                for i in range(len(self._particles)):
                    p = self._particles[i]
                    x, y, age, max_age = p[0], p[1], p[2], p[3]

                    noise_val = self._pseudo_noise(x, y, self._time)
                    angle = noise_val * math.pi * 2.0

                    speed = 0.5
                    nx = x + math.cos(angle) * speed
                    ny = y + math.sin(angle) * speed

                    normalized_angle = (angle + math.pi) / (2.0 * math.pi)
                    hue = (base_hue + normalized_angle * hue_range) % 360.0

                    brightness = 1.0 - (age / max_age)
                    r, g, b = Palette.hsv_to_rgb(hue, 1.0, brightness)

                    self._plot(nx, ny, r, g, b)

                    age += 1
                    if age > max_age or nx < 0 or nx >= self.width or ny < 0 or ny >= self.height:
                        self._particles[i] = self._spawn_particle()
                    else:
                        p[0], p[1], p[2] = nx, ny, age

                self._render_to_matrix()
                self.core.matrix.show_frame()

            await asyncio.sleep(0.01)
