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

    async def run_tutorial(self):
        """
        Guided demonstration of Conway's Game of Life with choreographed rules.

        The Voiceover Script (audio/tutes/conway_tute.wav) ~64 seconds:
            [0:00] "Welcome to Conway's Game of Life."
            [0:05] "Invented by mathematician John Horton Conway in 1970, this is a zero-player cellular automaton."
            [0:12] "The grid evolves based on three simple rules."
            [0:16] "First, death. A cell with too few or too many neighbors perishes from isolation or overpopulation."
            [0:24] "Second, survival. A cell with exactly two or three neighbors lives on to the next generation."
            [0:32] "Third, reproduction. An empty space surrounded by exactly three neighbors will spawn a new cell."
            [0:40] "From these simple rules, complex, moving structures can emerge."
            [0:46] "Turn the main dial to adjust the speed of generations."
            [0:51] "Press button one to cycle the color of the living cells."
            [0:56] "And press button two to reseed the grid with a new random population."
            [1:01] "Observe the evolution."
            [1:04] (End of file)
        """
        await self.core.clean_slate()

        self.game_state = "TUTORIAL"

        # Trigger audio synchronously (fire-and-forget)
        self.core.audio.play(
            "audio/tutes/conway_tute.wav",
            bus_id=self.core.audio.CH_VOICE
        )

        # Setup standard display state for the tutorial
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
        self.core.display.update_footer("B1:Color  B2:Reset")

        def _refresh_ui():
            line1, line2 = self._status_line()
            self.core.display.update_status(line1, line2)

        _refresh_ui()

        # --- Helpers for the Choreography ---

        async def _sim_wait(duration_s):
            """Runs the cellular automaton continuously for the specified duration."""
            start_time = ticks_ms()
            last_gen_tick = start_time
            target_ms = int(duration_s * 1000)

            while ticks_diff(ticks_ms(), start_time) < target_ms:
                now = ticks_ms()
                interval = _SPEED_LEVELS_MS[self._speed_idx]
                if ticks_diff(now, last_gen_tick) >= interval:
                    self._step()
                    self.core.matrix.show_frame(self._grid)
                    _refresh_ui() # Updates generation count
                    last_gen_tick = now
                await asyncio.sleep(0.01)

        def _draw_pattern(coords):
            """Clears the grid and draws specific alive cells from an (x,y) list."""
            for i in range(len(self._grid)):
                self._grid[i] = 0
            color_val = _ALIVE_COLOR_INDICES[self._color_idx]
            for cx, cy in coords:
                if 0 <= cx < self.width and 0 <= cy < self.height:
                    self._grid[cy * self.width + cx] = color_val
            self.core.matrix.show_frame(self._grid)
            self._generation = 0
            _refresh_ui()

        try:
            # [0:00 - 0:12] Intro & History
            self.core.display.update_status("GAME OF LIFE", "JOHN CONWAY (1970)")
            await _sim_wait(12.0)

            # [0:12 - 0:16] Transition to rules
            self.core.display.update_status("CELLULAR AUTOMATON", "THREE SIMPLE RULES")
            _draw_pattern([]) # Clear the board for the demonstration
            await asyncio.sleep(4.0)

            # [0:16 - 0:24] Rule 1: Death
            self.core.display.update_status("RULE 1: DEATH", "ISOLATION / OVERCROWD")
            # Draw one lonely cell (left) and an overcrowded cross (right)
            _draw_pattern([(3, 7), (11, 6), (10, 7), (11, 7), (12, 7), (11, 8)])
            self.core.buzzer.play_sequence(tones.UI_TICK)
            await asyncio.sleep(4.0)
            # Step the simulation once to show them die
            self._step()
            self.core.matrix.show_frame(self._grid)
            self.core.buzzer.play_sequence(tones.UI_CONFIRM)
            await asyncio.sleep(4.0)

            # [0:24 - 0:32] Rule 2: Survival
            self.core.display.update_status("RULE 2: SURVIVAL", "2 OR 3 NEIGHBORS")
            # Draw a stable 2x2 block
            _draw_pattern([(7, 7), (8, 7), (7, 8), (8, 8)])
            self.core.buzzer.play_sequence(tones.UI_TICK)
            await asyncio.sleep(4.0)
            # Step the simulation once to show it doesn't change
            self._step()
            self.core.matrix.show_frame(self._grid)
            self.core.buzzer.play_sequence(tones.UI_CONFIRM)
            await asyncio.sleep(4.0)

            # [0:32 - 0:40] Rule 3: Reproduction
            self.core.display.update_status("RULE 3: BIRTH", "EXACTLY 3 NEIGHBORS")
            # Draw an L-shaped corner (3 cells)
            _draw_pattern([(7, 7), (8, 7), (7, 8)])
            self.core.buzzer.play_sequence(tones.UI_TICK)
            await asyncio.sleep(4.0)
            # Step once to show the 4th cell being born
            self._step()
            self.core.matrix.show_frame(self._grid)
            self.core.buzzer.play_sequence(tones.ONE_UP)
            await asyncio.sleep(4.0)

            # [0:40 - 0:46] Emergent complexity (Show a Glider pattern moving!)
            self.core.display.update_status("EMERGENT PATTERNS", "COMPLEX STRUCTURES")
            _draw_pattern([(2, 1), (3, 2), (1, 3), (2, 3), (3, 3)])
            # Speed it up slightly so it sails across the screen
            self._speed_idx = 3
            await _sim_wait(6.0)

            # [0:46 - 0:51] Speed dial demonstration
            self._randomize() # Fill the screen back up
            self.core.display.update_status("MAIN DIAL", "CHANGE SPEED")
            for speed in [3, 4, 1, 2]: # Cycle FAST -> TURBO -> MED -> NORM
                self._speed_idx = speed
                _refresh_ui()
                self.core.buzzer.play_sequence(tones.UI_TICK)
                await _sim_wait(1.25)

            # [0:51 - 0:56] Color cycling demonstration
            self.core.display.update_status("BUTTON 1", "CYCLE COLOR")
            for _ in range(4):
                self._color_idx = (self._color_idx + 1) % len(_ALIVE_COLOR_INDICES)
                self._apply_color()
                self.core.matrix.show_frame(self._grid)
                self.core.buzzer.play_sequence(tones.UI_TICK)
                await _sim_wait(1.25)

            # [0:56 - 1:04] Reseed demonstration
            self.core.display.update_status("BUTTON 2", "RESEED GRID")
            await _sim_wait(1.0)
            self._randomize()
            self.core.matrix.show_frame(self._grid)
            self.core.display.update_status("BUTTON 2", "RANDOMIZED!")
            self.core.buzzer.play_sequence(tones.UI_CONFIRM)
            await _sim_wait(7.0)

            # Wait for audio to finish out if it's still running
            if hasattr(self.core.audio, 'wait_for_bus'):
                await self.core.audio.wait_for_bus(self.core.audio.CH_VOICE)
            else:
                await asyncio.sleep(2.0)

        finally:
            await self.core.clean_slate()

        return "TUTORIAL_COMPLETE"

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
                self.core.display.update_status(*self._status_line()) # Update GEN count
                last_gen_tick = now

            await asyncio.sleep(0.01)
