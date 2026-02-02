"""Manages Industrial Satellite NeoPixel animations and global effects."""

import asyncio
import math
import random
import time

import neopixel

from utilities import Palette

class LEDManager:
    """Manages Industrial Satellite NeoPixel animations and global effects."""
    def __init__(self, pin, num_pixels=6):
        self.pixels = neopixel.NeoPixel(pin, num_pixels, brightness=0.2, auto_write=True)
        self._tasks = [None] * num_pixels        # Individual LED tasks (e.g., breathing)
        self._priorities = [0] * num_pixels  # 0: Idle, 1: Animation, 2: Targeted, 3: Critical
        self._global_task = None # Global tasks (e.g., Cylon, Strobe)

    async def _cancel(self, index):
        """Internal helper to clear a specific LED's animation."""
        if self._tasks[index]:
            self._tasks[index].cancel()
            self._tasks[index] = None
            self._priorities[index] = 0

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
    async def solid_led(self, index, color, brightness=0.2, duration=None, priority=2):
        """Sets a static color to a specific LED as a task."""
        targets = range(len(self.pixels)) if index < 0 or index >= len(self.pixels) else [index]
        for i in targets:
            if (self._priorities[i] <= priority):
                await self._cancel(i)
                self._tasks[i] = asyncio.create_task(self._solid_led_logic(i, color, brightness, duration))
                self._priorities[i] = priority

    async def flash_led(self, index, color, brightness=0.2, duration=None, priority=2, speed=0.1, off_speed=None):
        """Flashes a specific LED for a duration as a task."""
        targets = range(len(self.pixels)) if index < 0 or index >= len(self.pixels) else [index]
        for i in targets:
            if (self._priorities[i] <= priority):
                await self._cancel(i)
                self._tasks[i] = asyncio.create_task(self._flash_led_logic(i, color, brightness, duration, speed, off_speed))
                self._priorities[i] = priority

    async def breathe_led(self, index, color, brightness=1.0, duration=None, priority=2, speed=2.0):
        """Commences a breathing animation on a specific LED or all LEDs."""
        targets = range(len(self.pixels)) if index < 0 or index >= len(self.pixels) else [index]
        for i in targets:
            if (self._priorities[i] <= priority):
                await self._cancel(i)
                self._tasks[i] = asyncio.create_task(self._breath_led_logic(i, color, brightness, duration, speed))
                self._priorities[i] = priority

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
    async def start_cylon(self, color, duration=None, speed=0.08):
        """Starts a Cylon animation across all LEDs."""
        if self._global_task:
            self._global_task.cancel()
        self._global_task = asyncio.create_task(self._cylon_logic(color, duration, speed))

    async def start_centrifuge(self, color, duration=None, speed=0.1):
        """A looping 'spinning' effect with motion blur."""
        if self._global_task:
            self._global_task.cancel()
        self._global_task = asyncio.create_task(self._centrifuge_logic(color, duration, speed))

    async def start_rainbow(self, duration=None, speed=0.01):
        """Smoothly cycles colors across the whole strip."""
        if self._global_task:
            self._global_task.cancel()
        self._global_task = asyncio.create_task(self._rainbow_logic(duration,speed))

    async def start_glitch(self, colors, duration=None, speed=0.05):
        """Randomly 'pops' pixels from a list of colors to simulate instability."""
        if self._global_task:
            self._global_task.cancel()
        self._global_task = asyncio.create_task(self._glitch_logic(colors, duration, speed))

    # --- GLOBAL ANIMATION ASYNC LOGIC ---
    async def _cylon_logic(self, color, duration, speed=0.08):
        start_time = time.monotonic()
        pos, direction = 0, 1
        r, g, b = color
        while time.monotonic() - start_time < duration:
            if self._priorities[pos] < 2:
                await self._set_pixel(pos, (r, g, b), brightness=0.2)
                await asyncio.sleep(speed)
                if self._priorities[pos] < 2:
                    await self._set_pixel(pos, (0, 0, 0), 0)
            else:
                await asyncio.sleep(speed)

            pos += direction
            if pos == (len(self.pixels) - 1) or pos == 0:
                direction *= -1

    async def _centrifuge_logic(self, color, duration, speed=0.1):
        start_time = time.monotonic()
        num_pixels = len(self.pixels)
        r, g, b = color
        while time.monotonic() - start_time < duration:
            for i in range(num_pixels):
                if self._priorities[i] < 2:
                    brightness = max(0.1, 1.0 - (abs((i - (time.monotonic() * 10) % num_pixels)) / num_pixels))
                    await self._set_pixel(i, (r, g, b), brightness=brightness * 0.2)
            await asyncio.sleep(speed)
            for i in range(num_pixels):
                if self._priorities[i] < 2:
                    await self._set_pixel(i, (0, 0, 0), 0)

    async def _rainbow_logic(self, duration, speed=0.01):
        start_time = time.monotonic()
        num_pixels = len(self.pixels)
        while time.monotonic() - start_time < duration:
            for i in range(num_pixels):
                if self._priorities[i] < 2:
                    hue = (i * 360 / num_pixels + (time.monotonic() * 100) % 360) % 360
                    color = Palette.hsv_to_rgb(hue, 1.0, 1.0)
                    await self._set_pixel(i, color, brightness=0.2)
            await asyncio.sleep(speed)

    async def _glitch_logic(self, colors, duration, speed=0.05):
        start_time = time.monotonic()
        num_pixels = len(self.pixels)
        while time.monotonic() - start_time < duration:
            for i in range(num_pixels):
                if self._priorities[i] < 2:
                    color = random.choice(colors)
                    await self._set_pixel(i, color, brightness=0.2)
            await asyncio.sleep(speed)
            for i in range(num_pixels):
                if self._priorities[i] < 2:
                    await self._set_pixel(i, (0, 0, 0), 0)
