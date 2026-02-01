"""Manages Industrial Satellite NeoPixel animations and global effects."""

import asyncio
import math
import time

import neopixel

from utilities import Palette

class LEDManager:
    """Manages Industrial Satellite NeoPixel animations and global effects."""
    def __init__(self, pin, num_pixels=6):
        self.pixels = neopixel.NeoPixel(pin, num_pixels, brightness=0.2, auto_write=True)
        self._tasks = [None] * num_pixels        # Individual LED tasks (e.g., breathing)
        self._global_task = None # Global tasks (e.g., Cylon, Strobe)

    async def _cancel(self, index):
        """Internal helper to clear a specific LED's animation."""
        if self._tasks[index]:
            self._tasks[index].cancel()
            self._tasks[index] = None

    async def _cancel_all(self):
        """Internal helper to clear all running animations."""
        if self._global_task:
            self._global_task.cancel()
            self._global_task = None
        for i in range(len(self._tasks)):
            self._cancel(i)

    async def _set_pixel(self, index, color, brightness=0.2):
        """Internal helper to set a specific pixel color and stop its animation."""
        await self._cancel(index)
        pixel_color = tuple(int(c * brightness) for c in color)
        self.pixels[index] = pixel_color

    async def _fill(self, color, brightness=0.2):
        """Internal helper to fill all pixels and stop all animations."""
        await self._cancel_all()
        pixel_color = tuple(int(c * brightness) for c in color)
        self.pixels.fill(pixel_color)

    # --- BASIC TRIGGERS ---
    async def solid_led(self, index, color, brightness=0.2, duration=None):
        """Sets a static color to a specific LED as a task."""
        targets = range(len(self.pixels)) if index < 0 or index >= len(self.pixels) else [index]
        for i in targets:
            await self._cancel(i)
            self._tasks[i] = asyncio.create_task(self._solid_led_logic(i, color, brightness, duration))

    async def flash_led(self, index, color, brightness=0.2, duration=None):
        """Flashes a specific LED for a duration as a task."""
        targets = range(len(self.pixels)) if index < 0 or index >= len(self.pixels) else [index]
        for i in targets:
            await self._cancel(i)
            self._tasks[i] = asyncio.create_task(self._flash_led_logic(i, color, brightness, duration))

    async def breathe_led(self, index, color, brightness=1.0, duration=None):
        """Commences a breathing animation on a specific LED or all LEDs."""
        targets = range(len(self.pixels)) if index < 0 or index >= len(self.pixels) else [index]
        for i in targets:
            await self._cancel(i)
            self._tasks[i] = asyncio.create_task(self._breath_led_logic(i, color, brightness, duration))

    # --- BASIC ASYNC LOGIC ---
    async def _solid_led_logic(self, index, color, brightness=0.2, duration=None):
        pixel_color = tuple(int(c * brightness) for c in color)
        self.pixels[index] = pixel_color
        if duration:
            await asyncio.sleep(duration)
            self.pixels[index] = Palette.OFF

    async def _flash_led_logic(self, index, color, brightness=0.2, duration=None, speed=0.1, off_speed=None):
        pixel_color = tuple(int(c * brightness) for c in color)
        # Check for a limited run
        if duration:
            end_time = time.monotonic() + duration
        else:
            end_time = None
        # Check for asymmetric on/off speed
        if not off_speed:
            off_speed = speed
        # Main flash loop
        while not end_time or time.monotonic() < end_time:
            self.pixels[index] = pixel_color
            await asyncio.sleep(speed)
            self.pixels[index] = Palette.OFF
            await asyncio.sleep(off_speed)

    async def _breath_led_logic(self, index, color, brightness=1.0, duration=None, speed=2.0):
        start_time = time.monotonic()

        # Check for a limited run
        if duration:
            end_time = time.monotonic() + duration
        else:
            end_time = None

        # Frequency = 2pi / speed to ensure one full breath per speed cycle
        frequency = (2 * math.pi) / speed

        # Main breath loop
        while not end_time or time.monotonic() < end_time:
            elapsed = time.monotonic() - start_time
            # Sine wave shifted to 0.0-1.0 range
            pulse = (math.sin(elapsed * frequency) + 1) / 2
            pixel_color = tuple(int(c * pulse * brightness) for c in color)
            self.pixels[index] = pixel_color
            await asyncio.sleep(0.02)

    # --- GLOBAL ANIMATION TRIGGERS ---
    def start_cylon(self, color, duration=3.0):
        self._cancel_all()
        self._global_task = asyncio.create_task(self._cylon_logic(color, duration))

    def start_strobe(self, color, duration=2.0):
        self._cancel_all()
        self._global_task = asyncio.create_task(self._strobe_logic(color, duration))

    # --- GLOBAL ANIMATION ASYNC LOGIC ---
    async def _cylon_logic(self, color, duration):
        start_time = time.monotonic()
        pos, direction = 0, 1
        r, g, b = color
        while time.monotonic() - start_time < duration:
            self.pixels.fill((0, 0, 0))
            self.pixels[pos] = (int(r*0.2), int(g*0.2), int(b*0.2))
            pos += direction
            if pos == 5 or pos == 0: direction *= -1
            await asyncio.sleep(0.08)
        self.pixels.fill((0, 0, 0))

    async def _strobe_logic(self, color, duration):
        end_time = time.monotonic() + duration
        r, g, b = [int(c * 0.2) for c in color]
        while time.monotonic() < end_time:
            # Group 1: Toggle LEDs (0-3)
            for i in range(4): self.pixels[i] = (r, g, b)
            for i in range(4, 6): self.pixels[i] = (0, 0, 0)
            await asyncio.sleep(0.1)
            # Group 2: Momentary LEDs (4-5)
            for i in range(4): self.pixels[i] = (0, 0, 0)
            for i in range(4, 6): self.pixels[i] = (r, g, b)
            await asyncio.sleep(0.1)
        self.pixels.fill((0, 0, 0))
