"""Reaction-Diffusion (Turing Patterns) – Zero Player Cellular Automaton.

A biological simulation based on Alan Turing's 1952 paper on morphogenesis.
It tracks the concentration of two virtual chemicals (A and B) using the
Gray-Scott model.

Chemical A diffuses faster than B. As B interacts with A, it converts A into
more B, while B also naturally decays. Depending on the "feed rate" (how fast
A is added) and the "kill rate" (how fast B dies), the grid naturally evolves
leopard spots, zebra stripes, or intricate brain-coral labyrinths.

Controls:
    Encoder turn       : change simulation speed (iterations per frame)
    Button 1 (tap)     : cycle parameter presets (Coral / Spots / Maze / Pulse)
    Button 2 (tap)     : reset and drop new chemical seeds
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
# Physics & Visual Constants
# ---------------------------------------------------------------------------

# Diffusion rates
_DA = 1.0
_DB = 0.5

# Simulation iterations per visual frame (encoder selects index)
_SPEED_LEVELS = [1, 2, 4, 8, 15]
_SPEED_NAMES  = ["SLOW", "MED", "NORM", "FAST", "TURBO"]

# Parameter presets: (Display Name, Feed Rate, Kill Rate)
_PRESETS = [
    ("BRAIN CORAL", 0.0545, 0.0620),
    ("LEOPARD SPOTS", 0.0367, 0.0649),
    ("LABYRINTH MAZE", 0.0290, 0.0570),
    ("MITOSIS", 0.0360, 0.0590),
]

# Color Themes: (Display Name, Base Hue, Peak Hue)
# Maps chemical B concentration to a color gradient.
_THEMES = [
    ("BIOLUMINESCENT", 160.0, 80.0),   # Cyan to Lime Green
    ("THERMAL", 240.0, 0.0),           # Blue to Red
    ("AMETHYST", 260.0, 320.0),        # Deep Purple to Pink
    ("MONOCHROME", 0.0, 0.0),          # Handled uniquely in rendering
]


class ReactionDiffusion(BaseMode):
    """Reaction-Diffusion biological morphogen simulator."""

    def __init__(self, core):
        super().__init__(core, "REACTION DIFF.", "Turing Patterns")
        self.width = 0
        self.height = 0

        self._A = None
        self._B = None
        self._nextA = None
        self._nextB = None

        # Pre-calculated 8-neighbor lookup table for the Laplacian convolution
        self._neighbors = []

        self._preset_idx = 0
        self._speed_idx = 2
        self._theme_idx = 0

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _init_buffers(self):
        """Allocate buffers and precalculate toroidal neighbor indices."""
        w, h = self.width, self.height
        size = w * h

        self._A = [1.0] * size
        self._B = [0.0] * size
        self._nextA = [1.0] * size
        self._nextB = [0.0] * size

        # Pre-calculate neighbor indices so the hot loop is just array lookups
        self._neighbors = []
        for y in range(h):
            for x in range(w):
                u = ((y - 1) % h) * w + x
                d = ((y + 1) % h) * w + x
                l = y * w + ((x - 1) % w)
                r = y * w + ((x + 1) % w)
                ul = ((y - 1) % h) * w + ((x - 1) % w)
                ur = ((y - 1) % h) * w + ((x + 1) % w)
                dl = ((y + 1) % h) * w + ((x - 1) % w)
                dr = ((y + 1) % h) * w + ((x + 1) % w)
                self._neighbors.append((u, d, l, r, ul, ur, dl, dr))

    def _reset(self, mode="CENTER"):
        """Seed the grid with chemical B."""
        size = self.width * self.height
        for i in range(size):
            self._A[i] = 1.0
            self._B[i] = 0.0

        if mode == "CENTER":
            # Drop a 4x4 square of Chemical B in the exact center
            cx, cy = self.width // 2, self.height // 2
            for y in range(cy - 2, cy + 2):
                for x in range(cx - 2, cx + 2):
                    self._B[y * self.width + x] = 1.0
        elif mode == "SCATTER":
            # Drop random noise blobs
            for _ in range(8):
                rx = random.randint(0, self.width - 1)
                ry = random.randint(0, self.height - 1)
                self._B[ry * self.width + rx] = 1.0

        gc.collect()

    def _step(self):
        """Advance the Gray-Scott simulation by one iteration."""
        feed = _PRESETS[self._preset_idx][1]
        kill = _PRESETS[self._preset_idx][2]

        A = self._A
        B = self._B
        nextA = self._nextA
        nextB = self._nextB
        neighbors = self._neighbors

        # Micro-optimizations for CircuitPython FPU loop
        # Caching standard weights
        weight_adj = 0.2
        weight_diag = 0.05

        for i in range(self.width * self.height):
            a = A[i]
            b = B[i]
            n = neighbors[i]

            # Calculate 3x3 Laplacian Convolution
            lapA = (A[n[0]] + A[n[1]] + A[n[2]] + A[n[3]]) * weight_adj + \
                   (A[n[4]] + A[n[5]] + A[n[6]] + A[n[7]]) * weight_diag - a

            lapB = (B[n[0]] + B[n[1]] + B[n[2]] + B[n[3]]) * weight_adj + \
                   (B[n[4]] + B[n[5]] + B[n[6]] + B[n[7]]) * weight_diag - b

            abb = a * b * b

            nextA[i] = max(0.0, min(1.0, a + (_DA * lapA - abb + feed * (1.0 - a))))
            nextB[i] = max(0.0, min(1.0, b + (_DB * lapB + abb - (kill + feed) * b)))

        # Swap buffers
        self._A, self._nextA = self._nextA, self._A
        self._B, self._nextB = self._nextB, self._B

    def _render_to_matrix(self):
        """Map Chemical B concentration to RGB and send to matrix."""
        w = self.width
        h = self.height

        theme = _THEMES[self._theme_idx]
        is_mono = (theme[0] == "MONOCHROME")
        base_hue = theme[1]
        peak_hue = theme[2]

        for y in range(h):
            for x in range(w):
                b_val = self._B[y * w + x]

                # B usually stabilizes between 0.0 and 0.5. Normalize it.
                intensity = max(0.0, min(1.0, b_val * 2.5))

                if intensity < 0.05:
                    self.core.matrix.draw_pixel(x, y, (0, 0, 0))
                elif is_mono:
                    val = int(intensity * 255)
                    self.core.matrix.draw_pixel(x, y, (val, val, val))
                else:
                    hue = base_hue + intensity * (peak_hue - base_hue)
                    val = math.pow(intensity, 0.7) # Gamma curve for visual pop
                    r, g, b = Palette.hsv_to_rgb(hue % 360.0, 1.0, val)
                    self.core.matrix.draw_pixel(x, y, (r, g, b))

    def _status_line(self):
        """Return the two status strings."""
        preset_name = _PRESETS[self._preset_idx][0]
        speed_name = _SPEED_NAMES[self._speed_idx]
        return (
            preset_name,
            f"SPEED: {speed_name}",
        )

    # ------------------------------------------------------------------
    # Tutorial
    # ------------------------------------------------------------------

    async def run_tutorial(self):
        """
        Guided demonstration of Reaction-Diffusion.

        The Voiceover Script (audio/tutes/react_tute.wav) ~48 seconds:
            [0:00] "Welcome to the Reaction-Diffusion simulator."
            [0:05] "Proposed by Alan Turing in 1952, this model explains how organic patterns form in biology."
            [0:14] "Leopard spots, zebra stripes, and brain coral all emerge from the mathematical interaction of two diffusing chemicals."
            [0:24] "Chemical A spreads outward, while Chemical B slowly consumes it to replicate."
            [0:32] "Press button one to alter the chemical feed and kill rates, shifting the balance of nature."
            [0:40] "Turn the dial to increase the calculation speed, and press button two to re-seed the petri dish."
            [0:48] (End of file)
        """
        await self.core.clean_slate()
        self.game_state = "TUTORIAL"

        self.core.audio.play("audio/tutes/react_tute.wav", bus_id=self.core.audio.CH_VOICE)

        self.width = self.core.matrix.width
        self.height = self.core.matrix.height

        self._init_buffers()
        self._preset_idx = 0 # Brain Coral
        self._speed_idx = 1  # MED (2 iters per frame so it grows visibly but smoothly)
        self._theme_idx = 0  # Bioluminescent
        self._reset(mode="CENTER")

        self.core.display.use_standard_layout()
        self.core.display.update_header("REACTION DIFFUSION")
        self.core.display.update_footer("B1:Type  B2:Seed")

        def _refresh_ui():
            line1, line2 = self._status_line()
            self.core.display.update_status(line1, line2)

        _refresh_ui()

        async def _sim_wait(duration_s):
            """Runs the math simulation continuously."""
            start_time = ticks_ms()
            last_tick = start_time
            target_ms = int(duration_s * 1000)

            while ticks_diff(ticks_ms(), start_time) < target_ms:
                now = ticks_ms()
                # Run the simulation at ~30 FPS visually
                if ticks_diff(now, last_tick) >= 33:
                    last_tick = now
                    # Perform N mathematical iterations per visual frame
                    iters = _SPEED_LEVELS[self._speed_idx]
                    for _ in range(iters):
                        self._step()
                    self._render_to_matrix()


                await asyncio.sleep(0.01)

        try:
            # [0:00 - 0:14] Intro & Turing Context
            self.core.display.update_status("ALAN TURING 1952", "MORPHOGENESIS")
            await _sim_wait(14.0)

            # [0:14 - 0:24] Biology examples
            self.core.display.update_status("GRAY-SCOTT MODEL", "ORGANIC PATTERNS")
            await _sim_wait(10.0)

            # [0:24 - 0:32] The spreading math
            self.core.display.update_status("CHEMICAL B", "CONSUMES CHEMICAL A")
            await _sim_wait(8.0)

            # [0:32 - 0:40] Button 1: Alter parameters
            self.core.display.update_status("BUTTON 1", "CHANGE PARAMETERS")
            for _ in range(3):
                await _sim_wait(1.0)
                self._preset_idx = (self._preset_idx + 1) % len(_PRESETS)
                self._reset(mode="CENTER")
                _refresh_ui()
                self.core.buzzer.play_sequence(tones.UI_TICK)
                # Briefly turbo the speed so the new pattern forms fast, then slow down
                self._speed_idx = 4
                await _sim_wait(1.5)
                self._speed_idx = 1

            # [0:40 - 0:48] Speed Dial & Reset
            self.core.display.update_status("MAIN DIAL", "CALCULATION SPEED")
            for speed in [2, 3, 4]: # Speed it up!
                self._speed_idx = speed
                _refresh_ui()
                self.core.buzzer.play_sequence(tones.UI_TICK)
                await _sim_wait(1.0)

            self.core.display.update_status("BUTTON 2", "RE-SEED DISH")
            self._reset(mode="SCATTER")
            self.core.buzzer.play_sequence(tones.UI_CONFIRM)
            await _sim_wait(3.0)

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
        """Main Reaction-Diffusion loop."""
        JEBLogger.info("REACT", "[RUN] ReactionDiffusion starting")

        self.width = self.core.matrix.width
        self.height = self.core.matrix.height

        # Initialize buffers if we didn't just inherit them from the tutorial
        if self._A is None:
            self._init_buffers()
            self._preset_idx = 0
            self._speed_idx = 2
            self._theme_idx = 0
            self._reset(mode="SCATTER")

        self.core.display.use_standard_layout()
        self.core.display.update_header("REACTION DIFFUSION")
        line1, line2 = self._status_line()
        self.core.display.update_status(line1, line2)
        self.core.display.update_footer("B1:Type  B2:Seed")

        self.core.hid.flush()
        self.core.hid.reset_encoder(self._speed_idx)
        last_enc = self.core.hid.encoder_position()

        last_frame_tick = ticks_ms()

        while True:
            now = ticks_ms()

            # --- Encoder: adjust simulation speed (iterations per frame) ---
            enc = self.core.hid.encoder_position()
            diff = enc - last_enc
            if diff != 0:
                # Cycle theme when pushing past the edge, or adjust speed
                delta = 1 if diff > 0 else -1

                # Hidden feature: Using encoder to cycle themes if holding Button 1
                if self.core.hid.is_button_pressed(0):
                    self._theme_idx = (self._theme_idx + delta) % len(_THEMES)
                    self.core.hid.reset_encoder(self._speed_idx)
                    last_enc = self._speed_idx
                    self.core.buzzer.play_sequence(tones.UI_TICK)
                else:
                    new_idx = max(0, min(len(_SPEED_LEVELS) - 1, self._speed_idx + delta))
                    self._speed_idx = new_idx
                    self.core.hid.reset_encoder(self._speed_idx)
                    last_enc = self._speed_idx
                    line1, line2 = self._status_line()
                    self.core.display.update_status(line1, line2)
                    self.core.buzzer.play_sequence(tones.UI_TICK)

            # --- Button 1: cycle parameter preset ---
            if self.core.hid.is_button_pressed(0, action="tap"):
                self._preset_idx = (self._preset_idx + 1) % len(_PRESETS)
                line1, line2 = self._status_line()
                self.core.display.update_status(line1, line2)
                self.core.buzzer.play_sequence(tones.UI_TICK)

            # --- Button 2: re-seed the grid ---
            if self.core.hid.is_button_pressed(1, action="tap"):
                self._reset(mode="SCATTER")
                line1, _ = self._status_line()
                self.core.display.update_status(line1, "RE-SEEDED!")
                self.core.buzzer.play_sequence(tones.UI_CONFIRM)

            # --- Encoder long press (2 s): exit to menu ---
            if self.core.hid.is_encoder_button_pressed(long=True, duration=2000):
                JEBLogger.info("REACT", "[EXIT] Returning to Zero Player menu")
                return "SUCCESS"

            # --- Physics & Render step (~30 FPS) ---
            if ticks_diff(now, last_frame_tick) >= 33:
                iters = _SPEED_LEVELS[self._speed_idx]
                for _ in range(iters):
                    self._step()

                self._render_to_matrix()

                last_frame_tick = now

            await asyncio.sleep(0.01)
