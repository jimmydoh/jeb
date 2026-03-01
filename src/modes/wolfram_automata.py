"""Wolfram 1D Cellular Automata – Zero Player Mode."""

import asyncio

from adafruit_ticks import ticks_ms, ticks_diff

from utilities import tones
from utilities.logger import JEBLogger

from .base import BaseMode

# Wolfram elementary automaton rules supported by this mode.
# Rule 90  → Sierpiński triangle fractal (XOR of neighbours).
# Rule 30  → Chaotic / pseudo-random pattern.
# Rule 110 → Complex / Turing-complete structures.
# Rule 184 → Traffic-flow simulation.
_RULE_NUMBERS = [30, 90, 110, 184]
_RULE_NAMES   = ["RULE 30", "RULE 90", "RULE 110", "RULE 184"]

# One distinct palette colour per rule so each has an immediate visual identity.
# Mapping: 14=LASER (red), 51=CYAN, 42=LIME, 22=GOLD
_RULE_COLORS = [14, 51, 42, 22]

# Generation speed levels in milliseconds (encoder selects index).
_SPEED_LEVELS_MS = [800, 400, 150, 60, 20, 5]
_SPEED_NAMES     = ["SLOW", "MED", "NORM", "FAST", "TURBO", "MAX"]

# Throttle the on-screen step-counter refresh to avoid display overhead.
_DISPLAY_UPDATE_INTERVAL = 50


class WolframAutomata(BaseMode):
    """1D Cellular Automata using Wolfram's Elementary Automata rules.

    A single center-pixel seed is placed at the top of the display.  Each
    step applies the selected elementary rule to the current bottom-most row
    to produce the next row.  New rows fill downward from the top; once the
    display is full they scroll upward, creating a continuously evolving
    picture.

    Rule 90  → Sierpiński triangle fractal (default)
    Rule 30  → Chaotic / pseudo-random pattern
    Rule 110 → Complex / Turing-complete structures
    Rule 184 → Traffic-flow simulation

    Controls:
        Encoder turn       : change simulation speed (slow ↔ max)
        Button 1 (tap)     : cycle Wolfram rule (and recolour visible cells)
        Button 2 (tap)     : reset / new single-pixel seed
        Encoder long press : return to Zero Player menu
    """

    def __init__(self, core):
        super().__init__(core, "WOLFRAM 1D", "1D Cellular Automata")
        self.width = 0
        self.height = 0
        self._grid = None           # Display buffer (height × width bytearray)
        self._current_row = None    # Row used as seed for the next computation
        self._rule_idx = 1          # Default: Rule 90
        self._speed_idx = 2         # Default: NORM (150 ms)
        self._step_count = 0
        self._fill_row = 0          # Index of the next empty row during initial fill

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _color(self):
        """Return the palette colour index for the active rule."""
        return _RULE_COLORS[self._rule_idx]

    def _apply_rule(self, row):
        """Compute and return the next row bytearray by applying the current rule.

        Uses toroidal (wrap-around) edge handling so the leftmost and rightmost
        cells are treated as neighbours of each other.  Each cell in *row* is
        considered alive (1) when non-zero, dead (0) otherwise.  The 3-bit
        neighbourhood pattern selects a bit from the Wolfram rule number; the
        output cell is set to the current colour index when that bit is 1, or
        to 0 (dead) when it is 0.
        """
        w = self.width
        color_val = self._color()
        rule = _RULE_NUMBERS[self._rule_idx]
        new_row = bytearray(w)
        for x in range(w):
            left   = 1 if row[(x - 1) % w] else 0
            center = 1 if row[x]            else 0
            right  = 1 if row[(x + 1) % w] else 0
            pattern = (left << 2) | (center << 1) | right
            new_row[x] = color_val if (rule >> pattern) & 1 else 0
        return new_row

    def _reset(self):
        """Clear the display and plant a single center-pixel seed at the top."""
        self._step_count = 0
        self._fill_row = 1
        self._grid[:] = bytearray(len(self._grid))
        # Seed: one alive pixel at the horizontal centre
        self._current_row = bytearray(self.width)
        self._current_row[self.width // 2] = self._color()
        # Place seed in the first display row
        self._grid[0:self.width] = self._current_row

    def _step(self):
        """Advance one generation: compute the next row and update the display."""
        w = self.width
        h = self.height
        new_row = self._apply_rule(self._current_row)
        if self._fill_row < h:
            # Buffer not yet full: write new row at the next empty position
            self._grid[self._fill_row * w:(self._fill_row + 1) * w] = new_row
            self._fill_row += 1
        else:
            # Buffer full: scroll everything up by one row, append new row at bottom
            for r in range(h - 1):
                self._grid[r * w:(r + 1) * w] = self._grid[(r + 1) * w:(r + 2) * w]
            self._grid[(h - 1) * w:h * w] = new_row
        self._current_row = new_row
        self._step_count += 1

    def _recolor(self):
        """Update all alive cells in the grid and current row to the active colour."""
        color_val = self._color()
        for i in range(len(self._grid)):
            if self._grid[i]:
                self._grid[i] = color_val
        for i in range(len(self._current_row)):
            if self._current_row[i]:
                self._current_row[i] = color_val

    def _status_line(self):
        """Return the two-line status tuple for the display."""
        rule_name  = _RULE_NAMES[self._rule_idx]
        speed_name = _SPEED_NAMES[self._speed_idx]
        ms = _SPEED_LEVELS_MS[self._speed_idx]
        return rule_name, f"{speed_name} ({ms}ms)"

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    async def run(self):
        """Main Wolfram automata loop."""
        JEBLogger.info("WOLFRAM", "[RUN] WolframAutomata starting")

        self.width  = self.core.matrix.width
        self.height = self.core.matrix.height
        size = self.width * self.height

        self._grid        = bytearray(size)
        self._current_row = bytearray(self.width)
        self._speed_idx   = 2
        self._step_count  = 0

        # Read the initial rule from mode settings (default: Rule 90)
        try:
            rule_num = int(self.core.data.get_setting("WOLFRAM_AUTOMATA", "rule", "90"))
            if rule_num in _RULE_NUMBERS:
                self._rule_idx = _RULE_NUMBERS.index(rule_num)
            else:
                self._rule_idx = 1
        except Exception:
            self._rule_idx = 1

        self._reset()

        self.core.display.use_standard_layout()
        self.core.display.update_header("WOLFRAM 1D")
        line1, line2 = self._status_line()
        self.core.display.update_status(line1, line2)
        self.core.display.update_footer("B1:Rule  B2:Reset")

        self.core.hid.flush()
        self.core.hid.reset_encoder(self._speed_idx)
        last_enc = self.core.hid.encoder_position()
        last_step_tick = ticks_ms()
        last_display_step = -1

        while True:
            now = ticks_ms()

            # --- Encoder: adjust simulation speed ---
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

            # --- Button 1: cycle Wolfram rule ---
            if self.core.hid.is_button_pressed(0, action="tap"):
                self._rule_idx = (self._rule_idx + 1) % len(_RULE_NUMBERS)
                self._recolor()
                line1, line2 = self._status_line()
                self.core.display.update_status(line1, line2)
                self.core.buzzer.play_sequence(tones.UI_TICK)

            # --- Button 2: reset / new seed ---
            if self.core.hid.is_button_pressed(1, action="tap"):
                self._reset()
                line1, line2 = self._status_line()
                self.core.display.update_status(line1, "RESET!")
                last_display_step = -1
                self.core.buzzer.play_sequence(tones.UI_CONFIRM)

            # --- Encoder long press (2 s): exit to Zero Player menu ---
            if self.core.hid.is_encoder_button_pressed(long=True, duration=2000):
                JEBLogger.info("WOLFRAM", "[EXIT] Returning to Zero Player menu")
                return "SUCCESS"

            # --- Simulation step on interval ---
            interval = _SPEED_LEVELS_MS[self._speed_idx]
            if ticks_diff(now, last_step_tick) >= interval:
                self._step()
                self.core.matrix.show_frame(self._grid)
                last_step_tick = now

                # Throttle the step-counter display update
                if self._step_count - last_display_step >= _DISPLAY_UPDATE_INTERVAL:
                    _, line2 = self._status_line()
                    self.core.display.update_status(_RULE_NAMES[self._rule_idx], line2)
                    last_display_step = self._step_count

            await asyncio.sleep(0.01)
