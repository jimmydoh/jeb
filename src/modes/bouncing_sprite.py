"""Bouncing Sprite – DVD-logo style screensaver (Zero Player Mode).

A tiny 3×3 pixel-art spaceship travels diagonally across the 16×16 LED
matrix.  When the sprite's bounding box touches any wall the respective
velocity component is negated (perfect reflection) and the sprite's primary
colour palette index advances to the next entry in the colour cycle.

Physics use pure integer arithmetic for position and velocity to avoid any
float allocation inside the hot render loop, satisfying the CircuitPython
memory-pressure constraint.

Controls:
    Encoder turn        : change animation speed (slow ↔ turbo)
    Button 1 (tap)      : manually cycle sprite colour
    Button 2 (tap)      : reset sprite to starting position
    Encoder long press  : return to Zero Player menu
"""

import asyncio
import gc

from adafruit_ticks import ticks_ms, ticks_diff

from utilities import tones
from utilities.logger import JEBLogger

from .base import BaseMode

# ---------------------------------------------------------------------------
# Tunable constants
# ---------------------------------------------------------------------------

# Sprite dimensions in pixels (bounding box).
_SPRITE_W = 3
_SPRITE_H = 3

# Sprite pixel map as a tuple of (dx, dy, pixel_type) triples.
# pixel_type  1 → primary colour (cycles on each wall hit)
#             2 → accent colour  (fixed white cockpit highlight)
#
# The shape is a tiny retro arcade spaceship:
#
#   . C .
#   C W C
#   C . C
#
# where C = primary colour and W = fixed white accent.
_SPRITE_PIXELS = (
    (1, 0, 1),   # nose
    (0, 1, 1),   # left wing
    (1, 1, 2),   # cockpit (accent)
    (2, 1, 1),   # right wing
    (0, 2, 1),   # left engine
    (2, 2, 1),   # right engine
)

# Accent colour palette index (fixed white cockpit highlight).
_ACCENT_INDEX = 4   # WHITE

# Primary colour cycle: RED, CYAN, GREEN, MAGENTA, GOLD, ORANGE.
_COLOR_INDICES = (11, 51, 41, 71, 22, 21)

# Animation step intervals in milliseconds (encoder selects index).
_SPEED_LEVELS_MS = (300, 200, 120, 80, 50)
_SPEED_NAMES = ("SLOW", "MED", "NORM", "FAST", "TURBO")

# Starting position: top-left corner of the 3×3 bounding box.
_START_X = 0
_START_Y = 0

# Starting velocity: one pixel per step in each axis (diagonal movement).
_START_VX = 1
_START_VY = 1


class BouncingSprite(BaseMode):
    """DVD-logo style bouncing sprite screensaver.

    A 3×3 pixel-art spaceship travels diagonally across the LED matrix.
    On every wall collision the impacted velocity component is negated and
    the sprite's primary colour palette index advances to the next entry.

    Integer position and velocity vectors are used throughout the update
    loop to avoid float allocations on the CircuitPython heap.

    Controls:
        Encoder turn        : change animation speed (slow ↔ turbo)
        Button 1 (tap)      : manually cycle sprite colour
        Button 2 (tap)      : reset sprite to starting position
        Encoder long press  : return to Zero Player menu
    """

    def __init__(self, core):
        super().__init__(core, "BOUNCING SPRITE", "Bouncing Sprite Screensaver")
        self.width = 0
        self.height = 0
        self._frame = None       # bytearray: palette-indexed render buffer
        self._x = 0              # integer x position (top-left of bounding box)
        self._y = 0              # integer y position
        self._vx = _START_VX     # integer x velocity (+1 or -1)
        self._vy = _START_VY     # integer y velocity (+1 or -1)
        self._color_idx = 0      # index into _COLOR_INDICES
        self._speed_idx = 2      # default: NORM

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _reset(self):
        """Reset sprite to its starting position and velocity.

        A gc.collect() is triggered here (a safe, low-frequency moment)
        to relieve GC pressure before the main render loop begins.
        """
        self._x = _START_X
        self._y = _START_Y
        self._vx = _START_VX
        self._vy = _START_VY
        gc.collect()

    def _step(self):
        """Advance the sprite by one pixel step.

        After moving, checks whether the bounding box has reached or
        exceeded any wall.  On a collision the offending velocity component
        is negated and the primary colour index is cycled once.  Corner
        hits (both axes simultaneously) count as a single colour cycle.
        """
        max_x = self.width - _SPRITE_W
        max_y = self.height - _SPRITE_H

        bounced = False

        nx = self._x + self._vx
        ny = self._y + self._vy

        # Horizontal wall check.
        if nx <= 0:
            nx = 0
            self._vx = 1
            bounced = True
        elif nx >= max_x:
            nx = max_x
            self._vx = -1
            bounced = True

        # Vertical wall check.
        if ny <= 0:
            ny = 0
            self._vy = 1
            bounced = True
        elif ny >= max_y:
            ny = max_y
            self._vy = -1
            bounced = True

        self._x = nx
        self._y = ny

        if bounced:
            self._color_idx = (self._color_idx + 1) % len(_COLOR_INDICES)

    def _build_frame(self):
        """Write the sprite into the palette-indexed frame buffer.

        The buffer is cleared first (all zeroes = off), then each
        non-transparent sprite pixel is written at its current position.
        """
        # Clear the frame.
        for i in range(len(self._frame)):
            self._frame[i] = 0

        primary = _COLOR_INDICES[self._color_idx]
        w = self.width
        x0 = self._x
        y0 = self._y

        for dx, dy, ptype in _SPRITE_PIXELS:
            color = primary if ptype == 1 else _ACCENT_INDEX
            self._frame[(y0 + dy) * w + (x0 + dx)] = color

    def _status_line(self):
        """Return two-line status tuple for the current simulation state."""
        name = _SPEED_NAMES[self._speed_idx]
        ms = _SPEED_LEVELS_MS[self._speed_idx]
        return f"{name} ({ms}ms)", f"POS:{self._x},{self._y}"

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    async def run(self):
        """Main bouncing sprite animation loop."""
        JEBLogger.info("BOUNCE", "[RUN] BouncingSprite starting")

        self.width = self.core.matrix.width
        self.height = self.core.matrix.height

        self._frame = bytearray(self.width * self.height)
        self._color_idx = 0
        self._speed_idx = 2

        self._reset()
        self._build_frame()

        self.core.display.use_standard_layout()
        self.core.display.update_header("BOUNCING SPRITE")
        line1, line2 = self._status_line()
        self.core.display.update_status(line1, line2)
        self.core.display.update_footer("B1:Color  B2:Reset")

        self.core.hid.flush()
        self.core.hid.reset_encoder(self._speed_idx)
        last_enc = self.core.hid.encoder_position()
        last_step_tick = ticks_ms()

        while True:
            now = ticks_ms()

            # --- Encoder: adjust animation speed ---
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

            # --- Button 1: manually cycle sprite colour ---
            if self.core.hid.is_button_pressed(0, action="tap"):
                self._color_idx = (self._color_idx + 1) % len(_COLOR_INDICES)
                self._build_frame()
                self.core.matrix.show_frame(self._frame)
                self.core.buzzer.play_sequence(tones.UI_TICK)

            # --- Button 2: reset sprite position ---
            if self.core.hid.is_button_pressed(1, action="tap"):
                self._reset()
                self._build_frame()
                line1, _ = self._status_line()
                self.core.display.update_status(line1, "RESET!")
                self.core.buzzer.play_sequence(tones.UI_CONFIRM)

            # --- Encoder long press (2 s): exit to Zero Player menu ---
            if self.core.hid.is_encoder_button_pressed(long=True, duration=2000):
                JEBLogger.info("BOUNCE", "[EXIT] Returning to Zero Player menu")
                gc.collect()
                return "SUCCESS"

            # --- Animation step on interval ---
            interval = _SPEED_LEVELS_MS[self._speed_idx]
            if ticks_diff(now, last_step_tick) >= interval:
                self._step()
                self._build_frame()
                self.core.matrix.show_frame(self._frame)
                self.core.display.update_status(*self._status_line())
                last_step_tick = now

            await asyncio.sleep(0.01)
