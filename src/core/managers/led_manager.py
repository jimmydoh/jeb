# File: src/core/managers/led_manager.py
"""Manages Core box NeoPixel animations and global effects (excluding the matrix)."""

from utilities import Palette

from .base_pixel_manager import BasePixelManager

class LEDManager(BasePixelManager):
    """Manages the 4 button NeoPixel animations and global effects (ported from Satellite implementation)."""
    def __init__(self, jeb_pixel):
        super().__init__(jeb_pixel)

    # --- BASIC TRIGGERS ---
    async def off_led(self, index, priority=99):
        """Turns off a specific LED (or all LEDs)."""
        targets = range(len(self.pixels)) if index < 0 or index >= len(self.pixels) else [index]
        # Stop animation by deleting from dict
        for i in targets:
            if i in self.active_animations:
                if priority < self.active_animations[i].get("priority", 0):
                    continue
                del self.active_animations[i]
                self.pixels[i] = Palette.OFF

        self.pixels.show()

    # --- SIMPLE ANIMATION TRIGGERS ---
    async def solid_led(self, index, color, brightness=0.2, duration=None, priority=2):
        """Sets a SOLID animation (static color) to a specific LED (or all LEDs)."""
        targets = range(len(self.pixels)) if index < 0 or index >= len(self.pixels) else [index]
        for i in targets:
            self.set_animation(i, "SOLID", tuple(int(c * brightness) for c in color), duration=duration, priority=priority)

    async def flash_led(self, index, color, brightness=0.2, duration=None, priority=2, speed=0.1, off_speed=None):
        """Flashes a specific LED (or all LEDs) for a duration."""
        targets = range(len(self.pixels)) if index < 0 or index >= len(self.pixels) else [index]
        for i in targets:
            self.set_animation(i, "BLINK", tuple(int(c * brightness) for c in color), duration=duration, speed=speed, priority=priority)

    async def breathe_led(self, index, color, brightness=1.0, duration=None, priority=2, speed=2.0):
        """Commences a breathing animation on a specific LED (or all LEDs)."""
        targets = range(len(self.pixels)) if index < 0 or index >= len(self.pixels) else [index]
        for i in targets:
            self.set_animation(i, "PULSE", tuple(int(c * brightness) for c in color), duration=duration, speed=speed, priority=priority)

    # --- COMPLEX ANIMATION TRIGGERS ---
    async def start_cylon(self, color, duration=None, speed=0.08):
        """Starts a Cylon animation across all LEDs."""
        self.fill_animation("SCANNER", color, speed=speed, duration=duration, priority=1)

    async def start_centrifuge(self, color, duration=None, speed=0.1):
        """A looping 'spinning' effect with motion blur."""
        self.fill_animation("CHASER", color, speed=speed, duration=duration, priority=1)

    async def start_rainbow(self, duration=None, speed=0.01):
        """Smoothly cycles colors across the whole strip."""
        self.fill_animation("RAINBOW", None, speed=speed, duration=duration, priority=1)

    async def start_glitch(self, colors, duration=None, speed=0.05):
        """Randomly 'pops' pixels from a list of colors to simulate instability."""
        self.fill_animation("GLITCH", colors, speed=speed, duration=duration, priority=1)
