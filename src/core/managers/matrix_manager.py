"""Manages the GlowBit 64 Matrix HUD display."""

import time
import math
import asyncio
import neopixel

from utilities import Palette

class MatrixManager:
    """Class to manage the GlowBit 64 Matrix HUD."""
    def __init__(self, pin, num_pixels=64, brightness=0.2):
        self.pixels = neopixel.NeoPixel(pin, num_pixels, brightness=brightness, auto_write=False)
        self.palette = [Palette.OFF, Palette.RED, Palette.BLUE, Palette.YELLOW, Palette.GREEN, Palette.WHITE, Palette.GOLD]
        # 5x5 Bitmasks for Numbers 0-9
        # TODO Fix up - this is an 8x8 matrix
        self.font = {
            '0': [0x0E, 0x11, 0x11, 0x11, 0x0E],
            '1': [0x04, 0x0C, 0x04, 0x04, 0x0E],
            '2': [0x0E, 0x11, 0x0E, 0x10, 0x1F],
            '3': [0x0E, 0x11, 0x0E, 0x11, 0x0E],
            '4': [0x11, 0x11, 0x1F, 0x01, 0x01],
            '5': [0x1F, 0x10, 0x1E, 0x01, 0x1E],
            '6': [0x0E, 0x10, 0x1E, 0x11, 0x0E],
            '7': [0x1F, 0x01, 0x02, 0x04, 0x08],
            '8': [0x0E, 0x11, 0x0E, 0x11, 0x0E],
            '9': [0x0E, 0x11, 0x0F, 0x01, 0x0E],
        }

        self.icons = {
            "DEFAULT": [
                2,0,0,1,1,0,0,2,
                0,2,0,1,1,0,2,0,
                0,0,2,0,0,2,0,0,
                1,1,0,3,3,0,1,1,
                1,1,0,3,3,0,1,1,
                0,0,2,0,0,2,0,0,
                0,2,0,1,1,0,2,0,
                2,0,0,1,1,0,0,2
            ], # 1:Red, 2:Blue, 3:Green
            "SIMON": [
                0,0,1,1,2,2,0,0,
                0,1,1,1,2,2,2,0,
                1,1,1,1,2,2,2,2,
                1,1,1,1,2,2,2,2,
                3,3,3,3,4,4,4,4,
                3,3,3,3,4,4,4,4,
                0,3,3,3,4,4,4,0,
                0,0,3,3,4,4,0,0
            ], # 1:Red, 2:Blue, 3:Yellow, 4:Green
            "SAFE": [
                0,0,5,5,5,5,0,0,
                0,5,0,0,6,0,5,0,
                5,0,0,0,0,0,0,5,
                5,0,0,0,0,0,0,5,
                5,0,0,0,0,0,0,5,
                5,0,0,0,0,0,0,5,
                0,5,0,0,0,0,5,0,
                0,0,5,5,5,5,0,0
            ], # 5:White, 6:Gold (Indicator)
            "IND":[
                1,1,1,1,1,1,1,1,
                1,0,0,0,3,3,0,1,
                1,0,0,3,3,0,0,1,
                1,0,3,3,3,3,0,1,
                1,0,0,3,3,3,0,1,
                1,0,0,3,3,0,0,1,
                1,0,0,3,0,0,0,1,
                1,1,1,1,1,1,1,1
            ], # 1:Red border, 3:Yellow bolt
            "SUCCESS":  [0x00, 0x01, 0x03, 0x16, 0x1C] # Checkmark
        }

    def _get_idx(self, x, y):
        """Maps 2D (0-7) to Serpentine 1D index."""
        if y % 2 == 0: return (y * 8) + x
        return (y * 8) + (7 - x)

    def draw_pixel(self, x, y, color, show=False):
        """Sets a specific pixel on the matrix."""
        if 0 <= x < 8 and 0 <= y < 8:
            self.pixels[self._get_idx(x, y)] = color
        if show: self.pixels.show()

    def fill(self, color):
        """Fills the entire matrix with a single color."""
        self.pixels.fill(color)
        self.pixels.show()

    def show_font(self, key, color, offset_x=1, offset_y=1):
        """Draws a 5x5 icon from the font library."""
        self.pixels.fill(0)
        if key in self.font:
            for y, row in enumerate(self.font[key]):
                for x in range(5):
                    if (row >> (4 - x)) & 1:
                        self.draw_pixel(x + offset_x, y + offset_y, color)
        self.pixels.show()

    async def show_icon(self, icon_name, clear=True, anim="NONE", speed=1.0, color=(0, 255, 0), brightness=1.0):
        """Displays a predefined icon on the matrix with optional animation."""
        if clear:
            self.pixels.fill((0,0,0))

        if icon_name in self.icons:
            icon_data = self.icons[icon_name]
        else:
            icon_data = self.icons["DEFAULT"]

        if anim == "NONE":
            for y in range(8):
                for x in range(8):
                    pixel_value = icon_data[y * 8 + x]
                    if pixel_value != 0:
                        base = color if color else self.palette[pixel_value]
                        px_color = (tuple(int(c * brightness) for c in base))
                        self.draw_pixel(x, y, px_color)
            self.pixels.show()

        elif anim == "PULSE":
            t = time.monotonic() * speed
            factor = 0.6 + 0.4 * math.sin(t)
            await self.show_icon(icon_name, clear=clear, anim="NONE", brightness=factor)

        elif anim == "SLIDE_LEFT":
            for offset in range(8, -1, -1):  # Slide from right to left
                for y in range(8):
                    for x in range(8):
                        # Calculate the shifted X position
                        target_x = x - offset
                        if 0 <= target_x < 8:
                            pixel_value = icon_data[y * 8 + x]
                            base = color if color else self.palette[pixel_value]
                            px_color = tuple(int(c * brightness) for c in base)
                            self.draw_pixel(target_x, y, px_color)
                self.pixels.show()
                await asyncio.sleep(0.05)
        # TODO: Default behaviour

    def show_progress_grid(self, iterations, total=10, color=(100, 0, 200)):
        """Fills the matrix like a rising 'tank' of fluid."""
        self.pixels.fill(0)
        # Map {total} iterations to 64 pixels (approx 6 pixels per step)
        fill_limit = int((iterations / total) * 64)
        for i in range(fill_limit):
            self.pixels[i] = color
        self.pixels.show()

    def draw_quadrant(self, quad_idx, color):
        """Fills one of four 4x4 quadrants: 0=TopLeft, 1=TopRight, 2=BottomLeft, 3=BottomRight."""
        # Define start X, Y for each quadrant
        offsets = [(0,0), (4,0), (0,4), (4,4)]
        ox, oy = offsets[quad_idx]

        for y in range(4):
            for x in range(4):
                self.draw_pixel(ox + x, oy + y, color)
        self.pixels.show()

    def clear(self):
        """Clears the matrix display."""
        self.pixels.fill((0, 0, 0))
        self.pixels.show()
