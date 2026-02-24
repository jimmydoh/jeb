# File: src/core/managers/led_manager.py
"""Manages simple LED arrays, such as individual button LEDs, sticks and strings."""

from utilities.payload_parser import parse_values, get_int, get_float, get_str
from utilities.palette import Palette

from .base_pixel_manager import BasePixelManager, PixelLayout

class LEDManager(BasePixelManager):
    """Class to control a number of individual LED elements in a 'straight line' format."""
    def __init__(self, jeb_pixel):
        # Declare LINEAR layout for LED strips/strings
        super().__init__(jeb_pixel, layout_type=PixelLayout.LINEAR, dimensions=(jeb_pixel.n,))

    # --- BASIC TRIGGERS ---
    def set_led(self, index, color, brightness=1.0, anim=None, duration=None, priority=2, speed=1.0):
        """Sets a specific LED (or all LEDs) to a color with optional animation."""
        targets = range(self.num_pixels) if index < 0 or index >= self.num_pixels else [index]
        for i in targets:
            if anim is None:
                self.solid_led(i, color, brightness=brightness, duration=duration, priority=priority)
            elif anim == "FLASH":
                self.flash_led(i, color, brightness=brightness, duration=duration, priority=priority, speed=speed)
            elif anim == "BREATH":
                self.breathe_led(i, color, brightness=brightness, duration=duration, priority=priority, speed=speed)
            else:
                self.solid_led(i, color, brightness=brightness, duration=duration, priority=priority)

    def off_led(self, index, priority=99):
        """Turns off a specific LED (or all LEDs)."""
        targets = range(self.num_pixels) if index < 0 or index >= self.num_pixels else [index]
        # Stop animation using the base class method
        for i in targets:
            if self.clear_animation(i, priority):
                self.pixels[i] = Palette.OFF

    def apply_command(self, cmd, val):
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
                    self.solid_led(
                        i,
                        Palette.get_color(get_int(values, 1)),
                        brightness=get_float(values, 3, 1.0),
                        duration=get_float(values, 2) if get_float(values, 2) > 0 else None,
                        priority=get_int(values, 4, 2)
                    )
                elif cmd == "LEDFLASH":
                    self.flash_led(i,
                        Palette.get_color(get_int(values, 1)),
                        brightness=get_float(values, 3, 1.0),
                        duration=get_float(values, 2) if get_float(values, 2) > 0 else None,
                        priority=get_int(values, 4, 2),
                        speed=get_float(values, 5, 0.1),
                        off_speed=get_float(values, 6) if get_float(values, 6) > 0 else None
                    )
                elif cmd == "LEDBREATH":
                    self.breathe_led(i,
                        Palette.get_color(get_int(values, 1)),
                        brightness=get_float(values, 3, 1.0),
                        duration=get_float(values, 2) if get_float(values, 2) > 0 else None,
                        priority=get_int(values, 4, 2),
                        speed=get_float(values, 5, 2.0)
                    )

        # 2. Global Strip Animations
        elif cmd == "LEDPROG":
            self.set_progress(
                percentage=get_float(values, 0, 0.0),
                color=Palette.get_color(get_int(values, 1, 0)),
                background=Palette.get_color(get_int(values, 2, 0)),
                priority=get_int(values, 3, 3)
            )
        elif cmd == "LEDVU":
            self.set_vu_meter(
                percentage=get_float(values, 0, 0.0),
                low_color=Palette.get_color(get_int(values, 1, 0)),
                mid_color=Palette.get_color(get_int(values, 2, 0)),
                high_color=Palette.get_color(get_int(values, 3, 0)),
                priority=get_int(values, 4, 3)
            )
        elif cmd == "LEDCYLON":
            self.start_cylon(
                Palette.get_color(get_int(values, 0, 0)),
                duration=get_float(values, 1, 2.0) if get_float(values, 1, 2.0) > 0 else 2.0,
                speed=get_float(values, 2, 0.08)
            )
        elif cmd == "LEDCENTRI":
            self.start_centrifuge(
                Palette.get_color(get_int(values, 0, 0)),
                duration=get_float(values, 1, 2.0) if get_float(values, 1, 2.0) > 0 else 2.0,
                speed=get_float(values, 2, 0.08)
            )
        elif cmd == "LEDRAINBOW":
            self.start_rainbow(
                duration=get_float(values, 0, 2.0) if get_float(values, 0, 2.0) > 0 else 2.0,
                speed=get_float(values, 1, 0.08)
            )
        elif cmd == "LEDGLITCH":
            # Colors will arrive as colon separated Palette indices, e.g. "0:1:2:3"
            color_indices = get_str(values, 0).split(":")
            if color_indices == [""]:
                colors = [Palette.CYAN, Palette.MAGENTA, Palette.YELLOW, Palette.WHITE]  # Handle empty case gracefully
            else:
                colors = [Palette.get_color(int(idx)) for idx in color_indices]
            self.start_glitch(
                colors, # Use parsed colors
                duration=get_float(values, 1, 2.0) if get_float(values, 1, 2.0) > 0 else 2.0,
                speed=get_float(values, 2, 0.08)
            )

    # --- SIMPLE ANIMATION TRIGGERS ---
    def solid_led(self, index, color, brightness=0.2, duration=None, priority=2):
        """Sets a SOLID animation (static color) to a specific LED (or all LEDs)."""
        self.solid(index, color, brightness=brightness, duration=duration, priority=priority)

    def flash_led(self, index, color, brightness=0.2, duration=None, priority=2, speed=0.1, off_speed=None):
        """Flashes a specific LED (or all LEDs) for a duration."""
        # Note: off_speed parameter is ignored (legacy compatibility)
        self.flash(index, color, brightness=brightness, duration=duration, priority=priority, speed=speed)

    def breathe_led(self, index, color, brightness=1.0, duration=None, priority=2, speed=2.0):
        """Commences a breathing animation on a specific LED (or all LEDs)."""
        self.breathe(index, color, brightness=brightness, duration=duration, priority=priority, speed=speed)

    def set_progress(self, percentage, color, background=(0, 0, 0), priority=3):
        """
        Displays a linear progress bar.

        Args:
            percentage: Float from 0.0 (empty) to 1.0 (full).
            color: The RGB tuple for the active progress.
            background: The RGB tuple for the empty portion.
        """
        # Clamp between 0.0 and 1.0
        percentage = max(0.0, min(1.0, float(percentage)))

        # Calculate how many pixels should be lit
        # Using round() ensures a smooth transition across the strip
        lit_pixels = int(round(percentage * self.num_pixels))

        for i in range(self.num_pixels):
            if i < lit_pixels:
                self.solid(i, color, priority=priority)
            else:
                self.solid(i, background, priority=priority)

    def set_vu_meter(self, percentage, low_color=Palette.GREEN, mid_color=Palette.YELLOW, high_color=Palette.RED, priority=3):
        """
        Displays a VU meter that changes color as it gets higher.
        """
        percentage = max(0.0, min(1.0, float(percentage)))
        lit_pixels = int(round(percentage * self.num_pixels))

        for i in range(self.num_pixels):
            if i < lit_pixels:
                # Determine color banding based on pixel position
                ratio = i / max(1, self.num_pixels - 1)
                if ratio < 0.6:
                    c = low_color
                elif ratio < 0.85:
                    c = mid_color
                else:
                    c = high_color

                self.solid(i, c, priority=priority)
            else:
                self.solid(i, (0, 0, 0), priority=priority)

    # --- COMPLEX ANIMATION TRIGGERS ---
    def start_cylon(self, color, duration=None, speed=0.08):
        """Starts a Cylon animation across all LEDs."""
        self.cylon(color, duration=duration, speed=speed, priority=1)

    def start_centrifuge(self, color, duration=None, speed=0.1):
        """A looping 'spinning' effect with motion blur."""
        self.centrifuge(color, duration=duration, speed=speed, priority=1)

    def start_rainbow(self, duration=None, speed=0.01):
        """Smoothly cycles colors across the whole strip."""
        self.rainbow(duration=duration, speed=speed, priority=1)

    def start_glitch(self, colors, duration=None, speed=0.05):
        """Randomly 'pops' pixels from a list of colors to simulate instability."""
        self.glitch(colors, duration=duration, speed=speed, priority=1)
