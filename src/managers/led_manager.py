# File: src/core/managers/led_manager.py
"""Manages simple LED arrays, such as individual button LEDs, sticks and strings."""

from utilities import Palette

from .base_pixel_manager import BasePixelManager

class LEDManager(BasePixelManager):
    """Class to control a number of individual LED elements in a 'straight line' format."""
    def __init__(self, jeb_pixel):
        super().__init__(jeb_pixel)

    # --- BASIC TRIGGERS ---
    async def set_led(self, index, color, brightness=1.0, anim=None, duration=None, priority=2, speed=1.0):
        """Sets a specific LED (or all LEDs) to a color with optional animation."""
        targets = range(len(self.pixels)) if index < 0 or index >= len(self.pixels) else [index]
        for i in targets:
            if anim is None:
                await self.solid_led(i, color, brightness=brightness, duration=duration, priority=priority)
            elif anim == "FLASH":
                await self.flash_led(i, color, brightness=brightness, duration=duration, priority=priority, speed=speed)
            elif anim == "BREATH":
                await self.breathe_led(i, color, brightness=brightness, duration=duration, priority=priority, speed=speed)
            else:
                await self.solid_led(i, color, brightness=brightness, duration=duration, priority=priority)

    async def off_led(self, index, priority=99):
        """Turns off a specific LED (or all LEDs)."""
        targets = range(len(self.pixels)) if index < 0 or index >= len(self.pixels) else [index]
        # Stop animation by setting to None in list
        for i in targets:
            current = self.active_animations[i]
            if current is not None:
                if priority < current.get("priority", 0):
                    continue
                self.active_animations[i] = None
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
