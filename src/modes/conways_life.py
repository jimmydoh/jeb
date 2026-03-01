"""Conway's Game of Life - Zero Player Cellular Automaton."""

import asyncio
import random

from adafruit_ticks import ticks_ms, ticks_diff

from utilities import tones
from utilities.logger import JEBLogger

from .base import BaseMode

# Alive cell colour cycle as palette indices (button 1 steps through these).
# Each value maps to a colour in Palette.LIBRARY (0 = off, so all values > 0).
# Mapping: 41=GREEN, 51=CYAN, 42=LIME, 22=GOLD, 71=MAGENTA, 21=ORANGE, 4=WHITE
_ALIVE_COLOR_INDICES = [41, 51, 42, 22, 71, 21, 4]

# Generation speed levels in milliseconds (encoder selects index)
_SPEED_LEVELS_MS = [800, 500, 300, 150, 80, 40]
_SPEED_NAMES = ["SLOW", "MED", "NORM", "FAST", "TURBO", "MAX"]


class ConwaysLife(BaseMode):
    """Conway's Game of Life - a zero-player cellular automaton.

    The game grid is stored as a flat bytearray (row-major order) where each
    byte is a palette index: 0 = dead cell, non-zero = alive cell with that
    colour.  This doubles as the render frame passed to matrix.show_frame(),
    eliminating the need for a separate render buffer.  A second scratch buffer
    (_next) is kept for the generation-step computation.

    Controls:
        Encoder turn      : change generation speed (slow ↔ fast)
        Button 1 (tap)    : cycle alive-cell colour
        Button 2 (tap)    : reset / randomise the grid
        Encoder long press: return to the Zero Player menu
    """

    def __init__(self, core):
        super().__init__(core, "GAME OF LIFE", "Conway's Game of Life")
        self.width = 0
        self.height = 0
        self._grid = None
        self._next = None
        self._color_idx = 0
        self._speed_idx = 2   # Default: NORM (300 ms)
        self._generation = 0

    def _randomize(self):
        """Fill the grid with random alive cells (~35 % density)."""
        self._generation = 0
        color_val = _ALIVE_COLOR_INDICES[self._color_idx]
        size = self.width * self.height
        for i in range(size):
            self._grid[i] = color_val if random.random() < 0.35 else 0

    def _count_neighbors(self, x, y):
        """Return the number of alive neighbours for cell (x, y).

        Edges wrap around (toroidal topology).
        """
        count = 0
        w = self.width
        h = self.height
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                nx = (x + dx) % w
                ny = (y + dy) % h
                count += 1 if self._grid[ny * w + nx] else 0
        return count

    def _step(self):
        """Advance one generation using the standard Conway rules, then swap buffers."""
        w = self.width
        h = self.height
        color_val = _ALIVE_COLOR_INDICES[self._color_idx]
        for y in range(h):
            for x in range(w):
                n = self._count_neighbors(x, y)
                alive = self._grid[y * w + x]
                if alive:
                    # Survive with 2 or 3 neighbours
                    self._next[y * w + x] = color_val if n in (2, 3) else 0
                else:
                    # Born with exactly 3 neighbours
                    self._next[y * w + x] = color_val if n == 3 else 0
        self._grid, self._next = self._next, self._grid
        self._generation += 1

    def _apply_color(self):
        """Update all alive cells in the grid to the current colour index.

        Called when the user cycles the alive colour (Button 1 tap) so that
        existing cells immediately reflect the new palette selection without
        waiting for the next generation step.
        """
        color_val = _ALIVE_COLOR_INDICES[self._color_idx]
        for i in range(len(self._grid)):
            if self._grid[i]:
                self._grid[i] = color_val

    def _status_line(self):
        """Return the two-line status string for the current state."""
        name = _SPEED_NAMES[self._speed_idx]
        ms = _SPEED_LEVELS_MS[self._speed_idx]
        return f"{name} ({ms}ms)", f"GEN: {self._generation}"

    async def run(self):
        """Main game-of-life loop."""
        JEBLogger.info("LIFE", "[RUN] ConwaysLife starting")

        self.width = self.core.matrix.width
        self.height = self.core.matrix.height
        size = self.width * self.height

        self._grid = bytearray(size)
        self._next = bytearray(size)
        self._color_idx = 0
        self._speed_idx = 2
        self._generation = 0

        self._randomize()

        self.core.display.use_standard_layout()
        self.core.display.update_header("GAME OF LIFE")
        line1, line2 = self._status_line()
        self.core.display.update_status(line1, line2)
        self.core.display.update_footer("B1:Color  B2:Reset")

        self.core.hid.flush()
        self.core.hid.reset_encoder(self._speed_idx)
        last_enc = self.core.hid.encoder_position()
        last_gen_tick = ticks_ms()

        while True:
            now = ticks_ms()

            # --- Encoder: adjust generation speed ---
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

            # --- Button 1: cycle alive colour ---
            if self.core.hid.is_button_pressed(0, action="tap"):
                self._color_idx = (self._color_idx + 1) % len(_ALIVE_COLOR_INDICES)
                self._apply_color()
                self.core.buzzer.play_sequence(tones.UI_TICK)

            # --- Button 2: reset / randomise ---
            if self.core.hid.is_button_pressed(1, action="tap"):
                self._randomize()
                line1, _ = self._status_line()
                self.core.display.update_status(line1, "RANDOMIZED!")
                self.core.buzzer.play_sequence(tones.UI_CONFIRM)

            # --- Encoder long press (2 s): exit back to menu ---
            if self.core.hid.is_encoder_button_pressed(long=True, duration=2000):
                JEBLogger.info("LIFE", "[EXIT] Returning to Zero Player menu")
                return "SUCCESS"

            # --- Game logic: step on interval ---
            interval = _SPEED_LEVELS_MS[self._speed_idx]
            if ticks_diff(now, last_gen_tick) >= interval:
                self._step()
                self.core.matrix.show_frame(self._grid)
                last_gen_tick = now

            await asyncio.sleep(0.01)

