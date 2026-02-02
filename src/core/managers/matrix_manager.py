# File: src/core/managers/matrix_manager.py
"""Manages the GlowBit 64 Matrix HUD display."""

import time
import math
import asyncio
import neopixel

from utilities import Palette, Icons

class MatrixManager:
    """Class to manage the GlowBit 64 Matrix HUD."""
    def __init__(self, pin, num_pixels=64, brightness=0.2):
        self.pixels = neopixel.NeoPixel(pin, num_pixels, brightness=brightness, auto_write=False)

        # Format: pixel_index: {
        #               "type": "BLINK",
        #               "color": (r,g,b),
        #               "speed": 1.0,
        #               "start": time.monotonic() }
        self.active_animations = {}

        self.palette = Palette.PALETTE_LIBRARY
        self.icons = Icons.ICON_LIBRARY

    def _get_idx(self, x, y):
        """Maps 2D (0-7) to Serpentine 1D index."""
        if y % 2 == 0: return (y * 8) + x
        return (y * 8) + (7 - x)

    def clear(self):
        """Clears the matrix display."""
        self.active_animations.clear()
        self.pixels.fill((0, 0, 0))
        self.pixels.show()

    def draw_pixel(self, x, y, color, show=False, anim_mode=None, speed=1.0):
        """Sets a specific pixel on the matrix."""
        if 0 <= x < 8 and 0 <= y < 8:
            idx = self._get_idx(x, y)

            if anim_mode:
                self.active_animations[idx] = {
                    "type": anim_mode,
                    "color": color,
                    "speed": speed,
                    "start": time.monotonic()
                }
            else:
                if idx in self.active_animations:
                    del self.active_animations[idx]
                self.pixels[idx] = color

        if show:
            self.pixels.show()

    def fill(self, color, show=True, anim_mode=None, speed=1.0):
        """Fills the entire matrix with a single color or simple animation."""
        if anim_mode:
            start_time = time.monotonic()
            for idx in range(64):
                self.active_animations[idx] = {
                    "type": anim_mode,
                    "color": color,
                    "speed": speed,
                    "start": start_time
                }
        else:
            self.active_animations.clear()
            self.pixels.fill(color)
        if show:
            self.pixels.show()

    # TODO draw_line, draw_rect, draw_circle, draw_text, etc.

    async def show_icon(self, icon_name, clear=True, anim_mode=None, speed=1.0, color=None, brightness=1.0):
        """
        Displays a predefined icon on the matrix with optional animation.
        anim_mode: None, "PULSE", "BLINK" are non-blocking via the animate_loop.
        anim_mode: "SLIDE_LEFT" is blocking (transition).
        """
        if clear:
            self.active_animations.clear()
            self.pixels.fill((0,0,0))

        icon_data = self.icons.get(icon_name, self.icons["DEFAULT"])

        # Handle Blocking Animations First
        if anim_mode == "SLIDE_LEFT":
            for offset in range(8, -1, -1):  # Slide from right to left
                self.pixels.fill((0,0,0))
                for y in range(8):
                    for x in range(8):
                        target_x = x - offset
                        if 0 <= target_x < 8:
                            pixel_value = icon_data[y * 8 + x]
                            if pixel_value != 0:
                                base = color if color else self.palette[pixel_value]
                                px_color = tuple(int(c * brightness) for c in base)
                                self.draw_pixel(target_x, y, px_color)
                self.pixels.show()
                await asyncio.sleep(0.05)
            return

        # Non-blocking Animations
        start_time = time.monotonic()

        for y in range(8):
            for x in range(8):
                idx = self._get_idx(x, y)
                pixel_value = icon_data[y * 8 + x]

                if pixel_value != 0:
                    base = color if color else self.palette[pixel_value]
                    px_color = tuple(int(c * brightness) for c in base)

                    if anim_mode:
                        self.active_animations[idx] = {
                            "type": anim_mode,
                            "color": px_color,
                            "speed": speed,
                            "start": start_time
                        }
                    else:
                        self.pixels[idx] = px_color

        self.pixels.show()

    async def show_progress_grid(self, iterations, total=10, color=(100, 0, 200)):
        """Fills the matrix like a rising 'tank' of fluid."""
        self.pixels.fill(0)
        # Map {total} iterations to 64 pixels (approx 6 pixels per step)
        fill_limit = int((iterations / total) * 64)
        for i in range(fill_limit):
            self.pixels[i] = color
        self.pixels.show()

    async def draw_quadrant(self, quad_idx, color):
        """Fills one of four 4x4 quadrants: 0=TopLeft, 1=TopRight, 2=BottomLeft, 3=BottomRight."""
        # Define start X, Y for each quadrant
        offsets = [(0,0), (4,0), (0,4), (4,4)]
        ox, oy = offsets[quad_idx]

        for y in range(4):
            for x in range(4):
                self.draw_pixel(ox + x, oy + y, color)
        self.pixels.show()

    async def animate_loop(self):
        """Background task to handle pixel animations."""
        while True:
            # If nothing is animating, sleep and check back later
            if not self.active_animations:
                await asyncio.sleep(0.1)
                continue

            now = time.monotonic()
            dirty = False

            # Iterate over a copy of items so we can modify if needed (though we aren't deleting here)
            for idx, anim in self.active_animations.items():

                # --- BLINK LOGIC ---
                if anim["type"] == "BLINK":
                    # Cycle duration = 1.0 / speed
                    # 50% Duty Cycle
                    period = 1.0 / anim["speed"]
                    phase = (now - anim["start"]) % period

                    if phase < (period / 2):
                        self.pixels[idx] = anim["color"]
                    else:
                        self.pixels[idx] = (0, 0, 0) # Off
                    dirty = True

                # --- PULSE LOGIC ---
                elif anim["type"] == "PULSE":
                    # Sine wave brightness 0.1 to 1.0
                    t = (now - anim["start"]) * anim["speed"]
                    # Shift sine to 0.0-1.0 range
                    factor = 0.5 + 0.5 * math.sin(t * 2 * math.pi)
                    # Clamp lower bound so it doesn't go fully black
                    factor = max(0.1, factor)

                    base = anim["color"]
                    self.pixels[idx] = (
                        int(base[0] * factor),
                        int(base[1] * factor),
                        int(base[2] * factor)
                    )
                    dirty = True

            if dirty:
                self.pixels.show()

            # Run at ~20 FPS
            await asyncio.sleep(0.05)
