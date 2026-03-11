"""Matrix Digital Rain – Zero Player Cellular Automaton / Visualizer.

The iconic falling code effect. While not a deep scientific simulation, it is
the quintessential hacker screensaver.

It works by spawning "droplets" above the matrix. Each droplet has a randomized
downward speed and tail length. The head of the droplet is drawn in pure white,
while the tail calculates a fading intensity curve mapped to the current color
theme (e.g., neon green).

Controls:
    Encoder turn       : change data flow speed (slow ↔ max)
    Button 1 (tap)     : cycle system color theme
    Button 2 (tap)     : flush buffers (resets all droplets)
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

# Number of simultaneous droplets on the 16x16 grid
_NUM_DROPS = 16

# Speed multipliers for the falling droplets (encoder selects index)
_SPEED_LEVELS = [0.4, 0.7, 1.0, 1.6, 2.5]
_SPEED_NAMES  = ["TRICKLE", "STEADY", "NORM", "FAST", "TORRENT"]

# Color Themes: (Display Name, Hue)
_THEMES = [
    ("NEON GREEN", 120.0), # Classic Matrix
    ("BLOOD RED", 0.0),    # Cyberpunk/Vampire
    ("DEEP BLUE", 240.0),  # Oceanic/Mainframe
    ("GOLDEN", 40.0),      # Deus Ex
    ("AMETHYST", 280.0),   # Synthwave
]

class DigitalRainMode(BaseMode):
    """Matrix Digital Rain visualizer."""

    def __init__(self, core):
        super().__init__(core, "DIGITAL RAIN", "Hacker Visualizer")
        self.width = 0
        self.height = 0
        self._buf = None         # Floating-point RGB buffer

        # Droplet list: [x (int), y (float), speed (float), length (int)]
        self._drops = []

        self._speed_idx = 2      # Default: NORM
        self._theme_idx = 0      # Default: NEON GREEN

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _spawn_drop(self, initial_stagger=False):
        """Return a newly spawned droplet array.

        If initial_stagger is True, they spawn spread out across the vertical
        space so the rain starts immediately instead of all falling from the top.
        """
        x = random.randint(0, self.width - 1)
        speed = random.uniform(8.0, 18.0) # Base pixels per second
        length = random.randint(4, 12)

        if initial_stagger:
            y = random.uniform(-10.0, self.height)
        else:
            y = random.uniform(-15.0, -1.0)

        return [x, y, speed, length]

    def _reset_sim(self, initial_stagger=False):
        """Clear the buffer and respawn all droplets."""
        self._drops = [self._spawn_drop(initial_stagger) for _ in range(_NUM_DROPS)]

        if self._buf:
            for cell in self._buf:
                cell[0] = 0
                cell[1] = 0
                cell[2] = 0
        gc.collect()

    def _step(self, dt_s):
        """Advance all droplets based on their speed and the global multiplier."""
        speed_mult = _SPEED_LEVELS[self._speed_idx]

        for p in self._drops:
            p[1] += p[2] * speed_mult * dt_s

            # If the entire tail has cleared the bottom of the screen, recycle it
            if p[1] - p[3] > self.height:
                new_p = self._spawn_drop(initial_stagger=False)
                p[0], p[1], p[2], p[3] = new_p[0], new_p[1], new_p[2], new_p[3]

    def _render_frame(self):
        """Draw the droplets to the RGB buffer."""
        # 1. Clear the buffer to black
        for cell in self._buf:
            cell[0] = 0
            cell[1] = 0
            cell[2] = 0

        base_hue = _THEMES[self._theme_idx][1]
        w, h = self.width, self.height

        # 2. Draw drops
        for p in self._drops:
            x = int(p[0])
            y = p[1]
            length = p[3]

            head_y = int(y)

            # Draw the tail
            for i in range(1, length + 1):
                ty = head_y - i
                if 0 <= ty < h and 0 <= x < w:
                    # Calculate fade: 1.0 near the head, 0.0 at the end of the tail
                    fraction = max(0.0, 1.0 - (i / length))

                    # Square the fraction for an exponential fade (looks more natural)
                    brightness = fraction * fraction

                    r, g, b = Palette.hsv_to_rgb(base_hue, 1.0, brightness)

                    cell = self._buf[ty * w + x]
                    # Use max() to blend overlapping tails
                    cell[0] = max(cell[0], r)
                    cell[1] = max(cell[1], g)
                    cell[2] = max(cell[2], b)

            # Draw the head (pure white)
            if 0 <= head_y < h and 0 <= x < w:
                cell = self._buf[head_y * w + x]
                cell[0], cell[1], cell[2] = 255, 255, 255

    def _push_to_matrix(self):
        """Write the RGB buffer to the LED matrix."""
        w, h = self.width, self.height
        for y in range(h):
            for x in range(w):
                cell = self._buf[y * w + x]
                self.core.matrix.draw_pixel(x, y, (int(cell[0]), int(cell[1]), int(cell[2])))

    def _status_line(self):
        """Return the two status strings for the current settings."""
        speed_name = _SPEED_NAMES[self._speed_idx]
        theme_name = _THEMES[self._theme_idx][0]
        return (
            f"FLOW: {speed_name}",
            f"SYS:  {theme_name}",
        )

    # ------------------------------------------------------------------
    # Tutorial
    # ------------------------------------------------------------------

    async def run_tutorial(self):
        """
        Guided demonstration of the Digital Rain visualizer.

        The Voiceover Script (audio/tutes/rain_tute.wav) ~41 seconds:
            [0:00] "Welcome to the Digital Rain."
            [0:03] "Popularized by the 1999 film The Matrix, this visual represents raw data flowing through a mainframe."
            [0:12] "Observe the structure: a bright white head leads the sequence, followed by a fading trail of code."
            [0:21] "Turn the main dial to adjust the data flow rate, from a slow trickle to a massive torrent."
            [0:29] "Press button one to cycle the interface color."
            [0:34] "And press button two to flush the memory buffers."
            [0:38] "Enter the construct."
            [0:41] (End of file)
        """
        await self.core.clean_slate()
        self.game_state = "TUTORIAL"

        self.core.audio.play("audio/tutes/rain_tute.wav", bus_id=self.core.audio.CH_VOICE)

        self.width = self.core.matrix.width
        self.height = self.core.matrix.height
        size = self.width * self.height

        self._buf = [[0, 0, 0] for _ in range(size)]
        self._speed_idx = 2 # NORM
        self._theme_idx = 0 # NEON GREEN

        self.core.display.use_standard_layout()
        self.core.display.update_header("DIGITAL RAIN")
        self.core.display.update_footer("B1:Color  B2:Flush")

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
                if dt_ms >= 33: # ~30fps visual update
                    dt_s = dt_ms / 1000.0
                    last_tick = now

                    self._step(dt_s)
                    self._render_frame()
                    self._push_to_matrix()
                    self.core.matrix.show_frame()

                await asyncio.sleep(0.01)

        try:
            # [0:00 - 0:12] Intro & History
            self.core.display.update_status("DIGITAL RAIN", "THE MATRIX (1999)")
            # Inject a single drop so the structure is incredibly obvious to the viewer
            self._drops = [[8, -2.0, 8.0, 7]]
            await _sim_wait(12.0)

            # [0:12 - 0:21] Structure explanation
            self.core.display.update_status("DATA STREAM", "RAW MAINFRAME FEED")
            self._reset_sim(initial_stagger=True) # Bring the full rain!
            await _sim_wait(9.0)

            # [0:21 - 0:29] Speed Dial
            self.core.display.update_status("MAIN DIAL", "DATA FLOW RATE")
            for speed in [0, 3, 4]: # TRICKLE -> FAST -> TORRENT
                self._speed_idx = speed
                _refresh_ui()
                self.core.buzzer.play_sequence(tones.UI_TICK)
                await _sim_wait(2.6)

            # [0:29 - 0:34] Theme Toggle
            self.core.display.update_status("BUTTON 1", "INTERFACE COLOR")
            for _ in range(3):
                self._theme_idx = (self._theme_idx + 1) % len(_THEMES)
                _refresh_ui()
                self.core.buzzer.play_sequence(tones.UI_TICK)
                await _sim_wait(1.6)

            # [0:34 - 0:38] Reset Flush
            self.core.display.update_status("BUTTON 2", "FLUSH BUFFERS")
            await _sim_wait(1.0)
            self._reset_sim(initial_stagger=False) # Drops will fall uniformly from the top
            _refresh_ui()
            self.core.buzzer.play_sequence(tones.UI_CONFIRM)
            await _sim_wait(3.0)

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
        """Main Digital Rain loop."""
        JEBLogger.info("RAIN", "[RUN] Digital Rain starting")

        self.width = self.core.matrix.width
        self.height = self.core.matrix.height
        size = self.width * self.height

        if self._buf is None:
            self._buf = [[0, 0, 0] for _ in range(size)]
            self._speed_idx = 2
            self._theme_idx = 0
            self._reset_sim(initial_stagger=True)

        self.core.display.use_standard_layout()
        self.core.display.update_header("DIGITAL RAIN")
        line1, line2 = self._status_line()
        self.core.display.update_status(line1, line2)
        self.core.display.update_footer("B1:Color  B2:Flush")

        self.core.hid.flush()
        self.core.hid.reset_encoder(self._speed_idx)
        last_enc = self.core.hid.encoder_position()
        last_tick = ticks_ms()

        while True:
            now = ticks_ms()
            dt_ms = ticks_diff(now, last_tick)

            # --- Encoder: adjust flow speed ---
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

            # --- Button 1: cycle color theme ---
            if self.core.hid.is_button_pressed(0, action="tap"):
                self._theme_idx = (self._theme_idx + 1) % len(_THEMES)
                line1, line2 = self._status_line()
                self.core.display.update_status(line1, line2)
                self.core.buzzer.play_sequence(tones.UI_TICK)

            # --- Button 2: flush buffers ---
            if self.core.hid.is_button_pressed(1, action="tap"):
                self._reset_sim(initial_stagger=False)
                line1, _ = self._status_line()
                self.core.display.update_status(line1, "FLUSHED!")
                self.core.buzzer.play_sequence(tones.UI_CONFIRM)

            # --- Encoder long press (2 s): exit to menu ---
            if self.core.hid.is_encoder_button_pressed(long=True, duration=2000):
                JEBLogger.info("RAIN", "[EXIT] Returning to Zero Player menu")
                return "SUCCESS"

            # --- Physics & Render step (~30 FPS) ---
            if dt_ms >= 33:
                dt_s = dt_ms / 1000.0
                last_tick = now

                self._step(dt_s)
                self._render_frame()
                self._push_to_matrix()
                self.core.matrix.show_frame()

            await asyncio.sleep(0.01)
