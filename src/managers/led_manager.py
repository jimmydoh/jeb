# File: src/core/managers/led_manager.py
"""Manages simple LED arrays, such as individual button LEDs, sticks and strings."""

from utilities.payload_parser import parse_values, get_int, get_float, get_str
from utilities.palette import Palette

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
        # Stop animation using the base class method
        for i in targets:
            if self.clear_animation(i, priority):
                self.pixels[i] = Palette.OFF

    async def apply_command(self, cmd, val):
        """
        Parses and executes a raw protocol command.
        Handles both text (CSV string) and binary (Tuple) payloads.
        """
        # robustly handle val whether it's a string, bytes, or tuple
        if isinstance(val, (list, tuple)):
            values = val
        else:
            values = parse_values(val)

        # 1. Targeted Commands (Index-based)
        if cmd in ("LED", "LEDFLASH", "LEDBREATH"):
            idx_raw = get_str(values, 0)
            target_indices = range(len(self.pixels)) if idx_raw == "ALL" else [get_int(values, 0)]

            for i in target_indices:
                if cmd == "LED":
                    await self.solid_led(i,
                        (get_int(values, 1), get_int(values, 2), get_int(values, 3)),
                        brightness=get_float(values, 5, 1.0),
                        duration=get_float(values, 4) if get_float(values, 4) > 0 else None,
                        priority=get_int(values, 6, 2)
                    )
                elif cmd == "LEDFLASH":
                    await self.flash_led(i,
                        (get_int(values, 1), get_int(values, 2), get_int(values, 3)),
                        brightness=get_float(values, 5, 1.0),
                        duration=get_float(values, 4) if get_float(values, 4) > 0 else None,
                        priority=get_int(values, 6, 2),
                        speed=get_float(values, 7, 0.1),
                        off_speed=get_float(values, 8) if get_float(values, 8) > 0 else None
                    )
                elif cmd == "LEDBREATH":
                    await self.breathe_led(i,
                        (get_int(values, 1), get_int(values, 2), get_int(values, 3)),
                        brightness=get_float(values, 5, 1.0),
                        duration=get_float(values, 4) if get_float(values, 4) > 0 else None,
                        priority=get_int(values, 6, 2),
                        speed=get_float(values, 7, 2.0)
                    )

        # 2. Global Strip Animations
        elif cmd == "LEDCYLON":
            await self.start_cylon(
                (get_int(values, 0), get_int(values, 1), get_int(values, 2)),
                duration=get_float(values, 3, 2.0) if get_float(values, 3, 2.0) > 0 else 2.0,
                speed=get_float(values, 4, 0.08)
            )
        elif cmd == "LEDCENTRI":
            await self.start_centrifuge(
                (get_int(values, 0), get_int(values, 1), get_int(values, 2)),
                duration=get_float(values, 3, 2.0) if get_float(values, 3, 2.0) > 0 else 2.0,
                speed=get_float(values, 4, 0.08)
            )
        elif cmd == "LEDRAINBOW":
            await self.start_rainbow(
                duration=get_float(values, 0, 2.0) if get_float(values, 0, 2.0) > 0 else 2.0,
                speed=get_float(values, 1, 0.08)
            )
        elif cmd == "LEDGLITCH":
            await self.start_glitch(
                [Palette.YELLOW, Palette.CYAN, Palette.WHITE, Palette.MAGENTA], # Default colors
                duration=get_float(values, 0, 2.0) if get_float(values, 0, 2.0) > 0 else 2.0,
                speed=get_float(values, 1, 0.08)
            )

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
