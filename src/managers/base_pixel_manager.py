# File: src/core/managers/base_pixel_manager.py
"""Base class for managing NeoPixel animations via a non-blocking loop."""

import asyncio
import time
import math
import random

from utilities import Palette

class BasePixelManager:
    """
    Base class for managing NeoPixel animations via a non-blocking loop.
    Supports: BLINK, PULSE, RAINBOW, GLITCH, DECAY, SCANNER (Cylon), CHASER.
    """
    def __init__(self, pixel_object):
        self.pixels = pixel_object # JEBPixel wrapper
        self.num_pixels = self.pixels.n

        # Fixed-size list for animation storage (None = inactive)
        # Format: [None or { type, color, speed, start, duration, priority }]
        self.active_animations = [None] * self.num_pixels

    def clear(self):
        """Stops all animations and clears LEDs."""
        for i in range(self.num_pixels):
            self.active_animations[i] = None
        self.pixels.fill((0, 0, 0))
        self.pixels.show()

    def set_animation(self, idx, anim_type, color, speed=1.0, duration=None, priority=0):
        """
        Registers an animation for a specific pixel index.
        Respects priority: Higher priority overwrites lower.
        """
        # Check priority lock
        current = self.active_animations[idx]
        if current is not None:
            # If new priority is lower than current running priority, ignore request
            if priority < current.get("priority", 0):
                return

        self.active_animations[idx] = {
            "type": anim_type,
            "color": color,
            "speed": speed,
            "start": time.monotonic(),
            "duration": duration,
            "priority": priority
        }

    def fill_animation(self, anim_type, color, speed=1.0, duration=None, priority=0):
        """Applies an animation to ALL pixels."""
        start_t = time.monotonic()
        for i in range(self.num_pixels):
            # We construct dict manually to sync start_time perfectly
            current = self.active_animations[i]
            if current is not None:
                if priority < current.get("priority", 0):
                    continue

            self.active_animations[i] = {
                "type": anim_type,
                "color": color,
                "speed": speed,
                "start": start_t,
                "duration": duration,
                "priority": priority
            }

    async def animate_loop(self):
        """Unified background task to handle all pixel animations."""
        while True:
            # Quick check if any animations are active
            has_active = False
            for anim in self.active_animations:
                if anim is not None:
                    has_active = True
                    break
            
            if not has_active:
                await asyncio.sleep(0.1)
                continue

            now = time.monotonic()
            dirty = False

            # Iterate over all pixel indices directly
            for idx in range(self.num_pixels):
                anim = self.active_animations[idx]
                if anim is None:
                    continue

                # 1. Duration Check
                if anim["duration"]:
                    elapsed = now - anim["start"]
                    if elapsed >= anim["duration"]:
                        self.pixels[idx] = (0, 0, 0)
                        self.active_animations[idx] = None
                        dirty = True
                        continue

                # 2. Animation Logic
                elapsed = now - anim["start"]

                # --- SOLID ---
                if anim["type"] == "SOLID":
                    self.pixels[idx] = anim["color"]
                    dirty = True

                # --- BLINK ---
                elif anim["type"] == "BLINK":
                    period = 1.0 / anim["speed"]
                    phase = elapsed % period
                    if phase < (period / 2):
                        self.pixels[idx] = anim["color"]
                    else:
                        self.pixels[idx] = (0, 0, 0)
                    dirty = True

                # --- PULSE (Breathing) ---
                elif anim["type"] == "PULSE":
                    t = elapsed * anim["speed"]
                    factor = 0.5 + 0.5 * math.sin(t * 2 * math.pi)
                    factor = max(0.1, factor)
                    base = anim["color"]
                    self.pixels[idx] = tuple(int(c * factor) for c in base)
                    dirty = True

                # --- RAINBOW ---
                elif anim["type"] == "RAINBOW":
                    hue = (elapsed * anim["speed"] + (idx * 0.05)) % 1.0
                    self.pixels[idx] = Palette.hsv_to_rgb(hue, 1.0, 1.0)
                    dirty = True

                # --- GLITCH ---
                elif anim["type"] == "GLITCH":
                    if random.random() > 0.9:
                        if random.random() > 0.5:
                             self.pixels[idx] = (255, 255, 255)
                        else:
                             self.pixels[idx] = (0, 0, 0)
                    else:
                        self.pixels[idx] = anim["color"]
                    dirty = True

                # --- SCANNER (Cylon) ---
                elif anim["type"] == "SCANNER":
                    # Moves back and forth across the strip
                    cycle = (elapsed * anim["speed"]) % 2.0
                    if cycle < 1.0:
                        pos = cycle * (self.num_pixels - 1)
                    else:
                        pos = (2.0 - cycle) * (self.num_pixels - 1)

                    dist = abs(idx - pos)
                    brightness = max(0, 1.0 - dist) # Tail length of 1.0
                    base = anim["color"]
                    self.pixels[idx] = tuple(int(c * brightness) for c in base)
                    dirty = True

                # --- CHASER (Centrifuge) ---
                elif anim["type"] == "CHASER":
                    # Spins in one direction
                    pos = (elapsed * anim["speed"] * self.num_pixels) % self.num_pixels
                    # Calculate circular distance
                    dist = (idx - pos) % self.num_pixels
                    if dist > (self.num_pixels / 2): dist -= self.num_pixels
                    dist = abs(dist)

                    brightness = max(0, 1.0 - (dist / 2.0)) # Broader tail
                    base = anim["color"]
                    self.pixels[idx] = tuple(int(c * brightness) for c in base)
                    dirty = True

                # --- DECAY ---
                elif anim["type"] == "DECAY":
                    duration = 1.0 / anim["speed"]
                    if elapsed >= duration:
                        self.pixels[idx] = (0, 0, 0)
                        self.active_animations[idx] = None
                    else:
                        factor = 1.0 - (elapsed / duration)
                        base = anim["color"]
                        self.pixels[idx] = tuple(int(c * factor) for c in base)
                    dirty = True

            if dirty:
                self.pixels.show()

            await asyncio.sleep(0.05)
