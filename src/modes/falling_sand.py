"""Falling Sand – Particle Physics Simulation (Zero Player Mode).

A classic powder-toy / falling-sand simulation where each pixel represents a
particle with simple physical behaviour:

  Sand  (yellow) : Falls straight down.  If the cell directly below is
                   occupied it slides diagonally down-left or down-right.
  Water (blue)   : Falls straight down.  If blocked below it spreads one
                   pixel sideways (left or right) per step.
  Wood  (brown)  : Static wall – never moves or is destroyed by sand/water.
                   Fire can ignite adjacent wood pixels.
  Fire  (red)    : Rises upward, randomly disappears, and can ignite
                   neighbouring wood pixels.

The simulation grid is a flat ``bytearray`` (row-major order) where every
byte is a palette index identical to the value rendered to the LED matrix via
``matrix.show_frame()``.

Controls:
    Encoder turn       : change simulation speed (slow ↔ turbo)
    Button 1 (tap)     : cycle initial-state seed / colour theme
    Button 2 (tap)     : reset / re-randomise the grid
    Encoder long press : return to Zero Player menu
"""

import asyncio
import gc
import random

from adafruit_ticks import ticks_ms, ticks_diff

from utilities import tones
from utilities.logger import JEBLogger

from .base import BaseMode

# ---------------------------------------------------------------------------
# Particle type constants (palette colour indices)
# ---------------------------------------------------------------------------

_EMPTY = 0    # No particle
_SAND  = 31   # YELLOW  – falls down / diagonally
_WATER = 61   # BLUE    – falls down / spreads sideways
_WOOD  = 20   # BROWN   – static wall
_FIRE  = 14   # RED     – rises, spreads to wood, dies randomly

# ---------------------------------------------------------------------------
# Physics tuning constants
# ---------------------------------------------------------------------------

# Probability (0–1) that a fire pixel dies on any given simulation step.
_FIRE_DIE_CHANCE = 0.08

# Probability (0–1) that fire ignites an adjacent wood pixel each step.
_IGNITE_CHANCE = 0.03

# Simulation update intervals in milliseconds (encoder selects index).
_SPEED_LEVELS_MS = [400, 200, 100, 50, 20]
_SPEED_NAMES     = ["SLOW", "MED", "NORM", "FAST", "TURBO"]

# Fraction of the grid to fill with each particle type during randomisation.
_SAND_DENSITY  = 0.35    # upper third fill density
_WATER_DENSITY = 0.20    # upper-mid region fill density


class FallingSandMode(BaseMode):
    """Falling Sand – Particle Physics Simulation.

    A zero-player powder-toy simulation where sand, water, wood and fire
    interact on the LED matrix according to simple physical rules.  Sand
    and water fall under gravity; water spreads sideways when blocked; wood
    acts as static walls; fire rises, flickers, and can ignite wood.

    The simulation uses a double-buffer strategy: particle logic reads from
    the *current* grid and writes to a *next* grid, then swaps, to avoid
    in-place update artefacts (a particle moving into an already-processed
    cell).

    Controls:
        Encoder turn       : change simulation speed (slow ↔ turbo)
        Button 1 (tap)     : cycle colour / re-seed theme
        Button 2 (tap)     : reset / re-randomise the grid
        Encoder long press : return to Zero Player menu
    """

    def __init__(self, core):
        super().__init__(core, "FALLING SAND", "Particle Simulation")
        self.width  = 0
        self.height = 0
        self._grid      = None   # bytearray: current particle state
        self._next_grid = None   # bytearray: pre-allocated swap buffer (avoids per-step allocs)
        self._speed_idx = 2      # default NORM (100 ms)
        self._tick      = 0

    async def run_tutorial(self):
        """
        Guided demonstration of the Falling Sand Simulation.

        The Voiceover Script (audio/tutes/sand_tute.wav) ~40 seconds:
            [0:00] "Welcome to Falling Sand."
            [0:03] "This is a micro-particle simulation driven by cellular physics."
            [0:09] "Yellow sand falls and stacks. Blue water flows to seek the lowest point."
            [0:16] "Brown wood acts as a static barrier, while red fire rises and consumes the wood."
            [0:24] "Turn the dial to adjust the speed of the simulation."
            [0:29] "Press button one or two to generate a new random diorama."
            [0:35] "Watch the elements interact."
            [0:38] (End of file)
        """
        await self.core.clean_slate()

        self.game_state = "TUTORIAL"

        # Trigger audio synchronously (fire-and-forget)
        self.core.audio.play(
            "audio/tutes/sand_tute.wav",
            bus_id=self.core.audio.CH_VOICE
        )

        # Setup standard display state for the tutorial
        self.width = self.core.matrix.width
        self.height = self.core.matrix.height
        size = self.width * self.height

        self._grid = bytearray(size)
        self._next_grid = bytearray(size)
        self._speed_idx = 2 # NORM speed
        self._tick = 0

        self.core.display.use_standard_layout()
        self.core.display.update_header("FALLING SAND")
        self.core.display.update_footer("B1:Seed  B2:Reset")

        def _refresh_ui():
            line1, line2 = self._status_line()
            self.core.display.update_status(line1, line2)

        async def _sim_wait(duration_s):
            """Runs the particle simulation continuously for the specified duration."""
            start_time = ticks_ms()
            last_step_tick = start_time
            target_ms = int(duration_s * 1000)

            while ticks_diff(ticks_ms(), start_time) < target_ms:
                now = ticks_ms()
                interval = _SPEED_LEVELS_MS[self._speed_idx]
                if ticks_diff(now, last_step_tick) >= interval:
                    self._step()
                    self.core.matrix.show_frame(self._grid)
                    _refresh_ui()
                    last_step_tick = now
                await asyncio.sleep(0.01)

        # --- Choreography Helpers ---
        def _clear_grid():
            for i in range(len(self._grid)): self._grid[i] = _EMPTY

        def _draw_wood_cup():
            _clear_grid()
            # Draw a U-shape cup out of wood
            for x in range(4, 12): self._grid[12 * self.width + x] = _WOOD
            for y in range(8, 12):
                self._grid[y * self.width + 4] = _WOOD
                self._grid[y * self.width + 11] = _WOOD

        def _drop_sand():
            # Spawn a block of sand above the cup
            for y in range(2, 5):
                for x in range(6, 10):
                    self._grid[y * self.width + x] = _SAND

        def _drop_water():
            # Spawn a block of water above the cup
            for y in range(0, 3):
                for x in range(5, 11):
                    if self._grid[y * self.width + x] == _EMPTY:
                        self._grid[y * self.width + x] = _WATER

        def _ignite_cup():
            # Spark fire at the bottom corners of the wood cup
            self._grid[13 * self.width + 5] = _FIRE
            self._grid[13 * self.width + 10] = _FIRE

        try:
            # [0:00 - 0:09] Intro & Setup
            self.core.display.update_status("FALLING SAND", "MICRO PHYSICS")
            _draw_wood_cup()
            self.core.matrix.show_frame(self._grid)
            await _sim_wait(9.0)

            # [0:09 - 0:16] Sand & Water
            self.core.display.update_status("GRAVITY", "SAND AND WATER")
            _drop_sand()
            self.core.buzzer.play_sequence(tones.UI_TICK)
            await _sim_wait(3.0)
            _drop_water() # Water will hit the sand and spill over the edges
            self.core.buzzer.play_sequence(tones.UI_TICK)
            await _sim_wait(4.0)

            # [0:16 - 0:24] Wood & Fire
            self.core.display.update_status("COMBUSTION", "FIRE BURNS WOOD")
            _ignite_cup() # Fire will burn the cup, dropping the sand/water
            self.core.buzzer.play_sequence(tones.UI_TICK)
            await _sim_wait(8.0)

            # [0:24 - 0:29] Speed dial
            self.core.display.update_status("MAIN DIAL", "CLOCK SPEED")
            for speed in [3, 4, 1, 2]: # Cycle speeds
                self._speed_idx = speed
                self.core.buzzer.play_sequence(tones.UI_TICK)
                await _sim_wait(1.25)

            # [0:29 - 0:38] Randomize
            self.core.display.update_status("BUTTON 1 & 2", "RANDOM DIORAMA")
            await _sim_wait(1.0)
            self._randomize()
            self.core.buzzer.play_sequence(tones.UI_CONFIRM)
            await _sim_wait(8.0)

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

    def _randomize(self):
        """Seed the grid with a mix of sand, water, wood and fire particles."""
        w, h = self.width, self.height
        self._tick = 0
        grid = bytearray(w * h)

        # --- Horizontal wood platforms in the middle third ---------------
        platform_y_min = h // 3
        platform_y_max = (2 * h) // 3
        num_platforms  = max(2, h // 4)
        for _ in range(num_platforms):
            py = random.randint(platform_y_min, platform_y_max)
            px = random.randint(0, max(0, w - 4))
            length = random.randint(w // 4, (3 * w) // 4)
            for dx in range(length):
                if px + dx < w:
                    grid[py * w + (px + dx)] = _WOOD

        # --- Sand scattered in the upper third ---------------------------
        sand_rows = max(1, h // 3)
        for y in range(sand_rows):
            for x in range(w):
                if random.random() < _SAND_DENSITY:
                    if grid[y * w + x] == _EMPTY:
                        grid[y * w + x] = _SAND

        # --- Water scattered in the upper-mid region ---------------------
        water_y_start = h // 4
        water_y_end   = h // 2
        water_x_start = w // 2
        for y in range(water_y_start, water_y_end):
            for x in range(water_x_start, w):
                if random.random() < _WATER_DENSITY:
                    if grid[y * w + x] == _EMPTY:
                        grid[y * w + x] = _WATER

        # --- Small fire seeds near the bottom ----------------------------
        fire_y_start = (2 * h) // 3
        for y in range(fire_y_start, h):
            for x in range(w):
                if grid[y * w + x] == _EMPTY and random.random() < 0.04:
                    grid[y * w + x] = _FIRE

        self._grid = grid
        # Ensure the double-buffer partner is allocated at the same size.
        # This avoids allocating a new bytearray on every _step() call.
        if self._next_grid is None or len(self._next_grid) != w * h:
            self._next_grid = bytearray(w * h)
        # Collect garbage at this safe, infrequent moment so the render loop
        # runs without GC interruptions.
        gc.collect()

    def _step(self):
        """Advance the simulation by one step using a double-buffer strategy.

        Reads particle types from the current grid (``self._grid``) and
        writes the next-state into a copy (``new``), then replaces
        ``self._grid`` with ``new``.

        Processing order:
          1. Sand and water – iterated bottom-to-top so that cascades
             (consecutive empty cells) are resolved in a single step.
          2. Fire – iterated top-to-bottom so that upward movement
             propagates naturally.
        """
        w, h = self.width, self.height
        src  = self._grid
        # Reuse the pre-allocated swap buffer instead of allocating a new
        # bytearray on every step.  Lazily initialize on the first call so
        # that the test helper (which bypasses _randomize) still works.
        if self._next_grid is None or len(self._next_grid) != len(src):
            self._next_grid = bytearray(len(src))
        new = self._next_grid
        new[:] = src

        # --- Sand and water (bottom-to-top) ------------------------------
        for y in range(h - 2, -1, -1):
            for x in range(w):
                p = src[y * w + x]
                if p == _SAND:
                    below = (y + 1) * w + x
                    if new[below] == _EMPTY:
                        new[below]      = _SAND
                        new[y * w + x]  = _EMPTY
                    else:
                        # Slide diagonally – randomise preferred direction
                        if random.random() < 0.5:
                            dirs = (-1, 1)
                        else:
                            dirs = (1, -1)
                        for dx in dirs:
                            nx = x + dx
                            if 0 <= nx < w and new[(y + 1) * w + nx] == _EMPTY:
                                new[(y + 1) * w + nx] = _SAND
                                new[y * w + x]        = _EMPTY
                                break

                elif p == _WATER:
                    below = (y + 1) * w + x
                    if new[below] == _EMPTY:
                        new[below]     = _WATER
                        new[y * w + x] = _EMPTY
                    else:
                        # Spread sideways – randomise preferred direction
                        if random.random() < 0.5:
                            dirs = (-1, 1)
                        else:
                            dirs = (1, -1)
                        for dx in dirs:
                            nx = x + dx
                            if 0 <= nx < w and new[y * w + nx] == _EMPTY:
                                new[y * w + nx] = _WATER
                                new[y * w + x]  = _EMPTY
                                break

        # --- Fire (top-to-bottom for upward movement) --------------------
        for y in range(1, h):
            for x in range(w):
                if src[y * w + x] != _FIRE:
                    continue
                if new[y * w + x] != _FIRE:
                    continue   # already moved or extinguished in this step

                # Ignite adjacent wood
                for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < w and 0 <= ny < h:
                        if new[ny * w + nx] == _WOOD:
                            if random.random() < _IGNITE_CHANCE:
                                new[ny * w + nx] = _FIRE

                # Randomly die
                if random.random() < _FIRE_DIE_CHANCE:
                    new[y * w + x] = _EMPTY
                    continue

                # Try to rise one cell
                above = (y - 1) * w + x
                if new[above] == _EMPTY:
                    new[above]     = _FIRE
                    new[y * w + x] = _EMPTY

        self._grid, self._next_grid = new, src
        self._tick += 1

    def _count_particles(self):
        """Return the count of each particle type in the current grid."""
        sand = water = wood = fire = 0
        for b in self._grid:
            if b == _SAND:
                sand += 1
            elif b == _WATER:
                water += 1
            elif b == _WOOD:
                wood += 1
            elif b == _FIRE:
                fire += 1
        return sand, water, wood, fire

    def _status_line(self):
        """Return a two-line status tuple for the display."""
        name = _SPEED_NAMES[self._speed_idx]
        ms   = _SPEED_LEVELS_MS[self._speed_idx]
        return f"{name} ({ms}ms)", f"TICK:{self._tick}"

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    async def run(self):
        """Main Falling Sand simulation loop."""
        JEBLogger.info("SAND", "[RUN] FallingSandMode starting")

        self.width  = self.core.matrix.width
        self.height = self.core.matrix.height

        self._speed_idx = 2
        self._tick      = 0

        self._randomize()

        self.core.display.use_standard_layout()
        self.core.display.update_header("FALLING SAND")
        line1, line2 = self._status_line()
        self.core.display.update_status(line1, line2)
        self.core.display.update_footer("B1:Seed  B2:Reset")

        self.core.hid.flush()
        self.core.hid.reset_encoder(self._speed_idx)
        last_enc       = self.core.hid.encoder_position()
        last_step_tick = ticks_ms()

        while True:
            now = ticks_ms()

            # --- Encoder: adjust simulation speed ---
            enc  = self.core.hid.encoder_position()
            diff = enc - last_enc
            if diff != 0:
                delta   = 1 if diff > 0 else -1
                new_idx = max(0, min(len(_SPEED_LEVELS_MS) - 1,
                                     self._speed_idx + delta))
                self._speed_idx = new_idx
                self.core.hid.reset_encoder(self._speed_idx)
                last_enc = self._speed_idx
                line1, line2 = self._status_line()
                self.core.display.update_status(line1, line2)
                self.core.buzzer.play_sequence(tones.UI_TICK)

            # --- Button 1: re-seed with a fresh random configuration ---
            if self.core.hid.is_button_pressed(0, action="tap"):
                self._randomize()
                line1, _ = self._status_line()
                self.core.display.update_status(line1, "NEW SEED!")
                self.core.buzzer.play_sequence(tones.UI_TICK)

            # --- Button 2: full reset ---
            if self.core.hid.is_button_pressed(1, action="tap"):
                self._randomize()
                line1, _ = self._status_line()
                self.core.display.update_status(line1, "RESET!")
                self.core.buzzer.play_sequence(tones.UI_CONFIRM)

            # --- Encoder long press (2 s): exit to Zero Player menu ---
            if self.core.hid.is_encoder_button_pressed(long=True, duration=2000):
                JEBLogger.info("SAND", "[EXIT] Returning to Zero Player menu")
                gc.collect()
                return "SUCCESS"

            # --- Simulation step on interval ---
            interval = _SPEED_LEVELS_MS[self._speed_idx]
            if ticks_diff(now, last_step_tick) >= interval:
                self._step()
                self.core.matrix.show_frame(self._grid)
                last_step_tick = now

            await asyncio.sleep(0.01)
