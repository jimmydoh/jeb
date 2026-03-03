"""Wireworld – Zero Player Cellular Automaton.

Wireworld simulates electrons moving through copper tracks using four cell
states.  It fits the JEB electronics-box theme and complements the existing
Conway's Life and Langton's Ant modes.

Cell states (stored as integers 0–3 in a flat bytearray):
    0 – EMPTY  : inert background, never changes.
    1 – HEAD   : electron head (blue), becomes TAIL next step.
    2 – TAIL   : electron tail (cyan), becomes COPPER next step.
    3 – COPPER : conductor (orange); becomes HEAD if exactly 1 or 2
                 of its 8 Moore-neighbourhood cells are HEADs,
                 otherwise stays COPPER.

Controls:
    Encoder turn       : change simulation speed (slow ↔ max)
    Button 1 (tap)     : cycle to the next circuit pattern (resets board)
    Encoder long press : return to Zero Player menu
"""

import asyncio

from adafruit_ticks import ticks_ms, ticks_diff

from utilities import tones
from utilities.logger import JEBLogger

from .base import BaseMode

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Cell-state integer codes
_EMPTY  = 0
_HEAD   = 1
_TAIL   = 2
_COPPER = 3

# Palette indices for each state (mapped to show_frame)
# 0 = off, 61 = BLUE (head), 51 = CYAN (tail), 21 = ORANGE (copper)
_STATE_COLORS = (0, 61, 51, 21)

# Simulation speed levels in milliseconds (encoder selects index)
_SPEED_LEVELS_MS = [800, 400, 200, 100, 50, 20]
_SPEED_NAMES     = ["SLOW", "MED", "NORM", "FAST", "TURBO", "MAX"]

# ---------------------------------------------------------------------------
# Hardcoded circuit patterns
# Each is a 16×16 = 256-byte flat array of state codes (0–3).
# ---------------------------------------------------------------------------

# Pattern 1: Square Orbit – single electron pair circling a 14×14 copper loop.
# The electron propagates clockwise at every simulation step.
_PATTERN_SQUARE_ORBIT = bytes([
      0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
      0,  2,  1,  3,  3,  3,  3,  3,  3,  3,  3,  3,  3,  3,  3,  0,
      0,  3,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  3,  0,
      0,  3,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  3,  0,
      0,  3,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  3,  0,
      0,  3,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  3,  0,
      0,  3,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  3,  0,
      0,  3,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  3,  0,
      0,  3,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  3,  0,
      0,  3,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  3,  0,
      0,  3,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  3,  0,
      0,  3,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  3,  0,
      0,  3,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  3,  0,
      0,  3,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  3,  0,
      0,  3,  3,  3,  3,  3,  3,  3,  3,  3,  3,  3,  3,  3,  3,  0,
      0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
])

# Pattern 2: Twin Pulses – two electron pairs 26 steps apart on the same loop.
# Both electrons race around the perimeter in the same direction.
_PATTERN_TWIN_PULSES = bytes([
      0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
      0,  2,  1,  3,  3,  3,  3,  3,  3,  3,  3,  3,  3,  3,  3,  0,
      0,  3,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  3,  0,
      0,  3,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  3,  0,
      0,  3,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  3,  0,
      0,  3,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  3,  0,
      0,  3,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  3,  0,
      0,  3,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  3,  0,
      0,  3,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  3,  0,
      0,  3,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  3,  0,
      0,  3,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  3,  0,
      0,  3,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  3,  0,
      0,  3,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  3,  0,
      0,  3,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  2,  0,
      0,  3,  3,  3,  3,  3,  3,  3,  3,  3,  3,  3,  3,  3,  1,  0,
      0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
])

# Pattern 3: Three Loops – three independent copper rings each carrying their
# own electron, arranged in a triangular layout across the display.
_PATTERN_THREE_LOOPS = bytes([
      0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
      0,  2,  1,  3,  3,  3,  3,  3,  0,  3,  3,  3,  3,  3,  3,  3,
      0,  3,  0,  0,  0,  0,  0,  3,  0,  3,  0,  0,  0,  0,  0,  3,
      0,  3,  0,  0,  0,  0,  0,  3,  0,  3,  0,  0,  0,  0,  0,  3,
      0,  3,  0,  0,  0,  0,  0,  3,  0,  3,  0,  0,  0,  0,  0,  3,
      0,  3,  0,  0,  0,  0,  0,  3,  0,  3,  0,  0,  0,  0,  0,  3,
      0,  3,  0,  0,  0,  0,  0,  3,  0,  3,  0,  0,  0,  0,  0,  3,
      0,  3,  3,  3,  3,  3,  3,  3,  0,  3,  3,  3,  1,  2,  3,  3,
      0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
      0,  0,  0,  0,  3,  3,  3,  3,  2,  1,  3,  3,  3,  0,  0,  0,
      0,  0,  0,  0,  3,  0,  0,  0,  0,  0,  0,  0,  3,  0,  0,  0,
      0,  0,  0,  0,  3,  0,  0,  0,  0,  0,  0,  0,  3,  0,  0,  0,
      0,  0,  0,  0,  3,  0,  0,  0,  0,  0,  0,  0,  3,  0,  0,  0,
      0,  0,  0,  0,  3,  0,  0,  0,  0,  0,  0,  0,  3,  0,  0,  0,
      0,  0,  0,  0,  3,  3,  3,  3,  3,  3,  3,  3,  3,  0,  0,  0,
      0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
])

# Ordered list of (pattern_bytes, display_name) tuples.
_PATTERNS = [
    (_PATTERN_SQUARE_ORBIT, "SQUARE ORBIT"),
    (_PATTERN_TWIN_PULSES,  "TWIN PULSES"),
    (_PATTERN_THREE_LOOPS,  "THREE LOOPS"),
]


# ---------------------------------------------------------------------------
# Mode class
# ---------------------------------------------------------------------------

class Wireworld(BaseMode):
    """Wireworld cellular automaton – zero-player simulation mode.

    The 16×16 grid is stored in a flat bytearray (_grid) using state codes
    0–3.  A second scratch buffer (_next) is computed each generation step
    and then swapped with _grid.  A third palette-index buffer (_frame) is
    built before calling matrix.show_frame() so that the LED hardware never
    sees the raw state codes.

    Controls:
        Encoder turn       : change simulation speed (slow ↔ max)
        Button 1 (tap)     : cycle to the next circuit pattern (resets board)
        Encoder long press : return to Zero Player menu
    """

    def __init__(self, core):
        super().__init__(core, "WIREWORLD", "Wireworld Cellular Automaton")
        self.width       = 0
        self.height      = 0
        self._grid       = None   # bytearray: state codes 0–3
        self._next       = None   # scratch buffer for next generation
        self._frame      = None   # palette-index buffer for show_frame()
        self._pattern_idx = 0     # index into _PATTERNS
        self._speed_idx  = 2      # default NORM (200 ms)
        self._generation = 0

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load_pattern(self):
        """Copy the current pattern into _grid and reset the generation counter."""
        self._generation = 0
        src = _PATTERNS[self._pattern_idx][0]
        for i in range(len(self._grid)):
            self._grid[i] = src[i]

    def _count_head_neighbors(self, x, y):
        """Return the count of HEAD cells in the 8-cell Moore neighbourhood of (x, y).

        Edges wrap toroidally so the grid has no boundary effects.
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
                count += 1 if self._grid[ny * w + nx] == _HEAD else 0
        return count

    def _step(self):
        """Advance one generation using the Wireworld rules, then swap buffers."""
        w = self.width
        h = self.height
        for y in range(h):
            for x in range(w):
                state = self._grid[y * w + x]
                if state == _EMPTY:
                    self._next[y * w + x] = _EMPTY
                elif state == _HEAD:
                    self._next[y * w + x] = _TAIL
                elif state == _TAIL:
                    self._next[y * w + x] = _COPPER
                else:  # COPPER
                    n = self._count_head_neighbors(x, y)
                    self._next[y * w + x] = _HEAD if n in (1, 2) else _COPPER
        self._grid, self._next = self._next, self._grid
        self._generation += 1

    def _build_frame(self):
        """Map state codes to palette indices for display via show_frame()."""
        for i in range(len(self._grid)):
            self._frame[i] = _STATE_COLORS[self._grid[i]]

    def _status_line(self):
        """Return the two-line status tuple for the display."""
        pattern_name = _PATTERNS[self._pattern_idx][1]
        speed_name   = _SPEED_NAMES[self._speed_idx]
        ms           = _SPEED_LEVELS_MS[self._speed_idx]
        return pattern_name, f"{speed_name} ({ms}ms)"

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    async def run(self):
        """Main Wireworld simulation loop."""
        JEBLogger.info("WIRE", "[RUN] Wireworld starting")

        self.width  = self.core.matrix.width
        self.height = self.core.matrix.height
        size = self.width * self.height

        self._grid        = bytearray(size)
        self._next        = bytearray(size)
        self._frame       = bytearray(size)
        self._pattern_idx = 0
        self._speed_idx   = 2
        self._generation  = 0

        self._load_pattern()

        self.core.display.use_standard_layout()
        self.core.display.update_header("WIREWORLD")
        line1, line2 = self._status_line()
        self.core.display.update_status(line1, line2)
        self.core.display.update_footer("B1:Pattern  ENC:Speed")

        self.core.hid.flush()
        self.core.hid.reset_encoder(self._speed_idx)
        last_enc = self.core.hid.encoder_position()
        last_step_tick = ticks_ms()
        last_display_gen = -1

        while True:
            now = ticks_ms()

            # --- Encoder: adjust simulation speed ---
            enc  = self.core.hid.encoder_position()
            diff = enc - last_enc
            if diff != 0:
                delta    = 1 if diff > 0 else -1
                new_idx  = max(0, min(len(_SPEED_LEVELS_MS) - 1, self._speed_idx + delta))
                self._speed_idx = new_idx
                self.core.hid.reset_encoder(self._speed_idx)
                last_enc = self._speed_idx
                line1, line2 = self._status_line()
                self.core.display.update_status(line1, line2)
                self.core.buzzer.play_sequence(tones.UI_TICK)

            # --- Button 1: cycle to next circuit pattern ---
            if self.core.hid.is_button_pressed(0, action="tap"):
                self._pattern_idx = (self._pattern_idx + 1) % len(_PATTERNS)
                self._load_pattern()
                last_display_gen = -1
                line1, _ = self._status_line()
                self.core.display.update_status(line1, "LOADED!")
                self.core.buzzer.play_sequence(tones.UI_CONFIRM)

            # --- Encoder long press (2 s): exit to Zero Player menu ---
            if self.core.hid.is_encoder_button_pressed(long=True, duration=2000):
                JEBLogger.info("WIRE", "[EXIT] Returning to Zero Player menu")
                return "SUCCESS"

            # --- Simulation step on interval ---
            interval = _SPEED_LEVELS_MS[self._speed_idx]
            if ticks_diff(now, last_step_tick) >= interval:
                self._step()
                self._build_frame()
                self.core.matrix.show_frame(self._frame)
                last_step_tick = now

                # Throttle display generation counter refresh
                if self._generation - last_display_gen >= 50:
                    line1, _ = self._status_line()
                    self.core.display.update_status(
                        line1,
                        f"GEN:{self._generation}"
                    )
                    last_display_gen = self._generation

            await asyncio.sleep(0.01)
