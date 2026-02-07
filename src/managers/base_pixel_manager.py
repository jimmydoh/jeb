# File: src/core/managers/base_pixel_manager.py
"""Base class for managing NeoPixel animations via a non-blocking loop."""

import asyncio
import time
import math
import random

from utilities import Palette

class AnimationSlot:
    """Reusable animation slot to avoid object churn."""
    __slots__ = ('active', 'type', 'color', 'speed', 'start', 'duration', 'priority')
    
    def __init__(self):
        self.active = False
        self.type = None
        self.color = None
        self.speed = 1.0
        self.start = 0.0
        self.duration = None
        self.priority = 0
    
    def set(self, anim_type, color, speed, start, duration, priority):
        """Update slot properties in place."""
        self.active = True
        self.type = anim_type
        self.color = color
        self.speed = speed
        self.start = start
        self.duration = duration
        self.priority = priority
    
    def clear(self):
        """Mark slot as inactive without deallocating."""
        self.active = False

class BasePixelManager:
    """
    Base class for managing NeoPixel animations via a non-blocking loop.
    Supports: BLINK, PULSE, RAINBOW, GLITCH, DECAY, SCANNER (Cylon), CHASER.
    """
    def __init__(self, pixel_object):
        self.pixels = pixel_object # JEBPixel wrapper
        self.num_pixels = self.pixels.n

        # Fixed-size list for animations (one slot per pixel)
        # Each slot is a reusable AnimationSlot object
        self.active_animations = [AnimationSlot() for _ in range(self.num_pixels)]
        
        # Track active animation count to avoid O(n) checks
        self._active_count = 0

    def clear(self):
        """Stops all animations and clears LEDs."""
        for slot in self.active_animations:
            slot.clear()
        self._active_count = 0
        self.pixels.fill((0, 0, 0))
        # Note: Hardware write is now handled by CoreManager.render_loop()

    def clear_animation(self, idx, priority=0):
        """
        Clears the animation for a specific pixel index.
        Respects priority: Only clears if priority is >= current animation priority.
        Returns True if cleared, False otherwise.
        """
        # Validate index bounds
        if idx < 0 or idx >= self.num_pixels:
            return False
        
        slot = self.active_animations[idx]
        if slot.active:
            # Only clear if priority is sufficient
            if priority < slot.priority:
                return False
            slot.clear()
            self._active_count -= 1
            return True
        return False

    def set_animation(self, idx, anim_type, color, speed=1.0, duration=None, priority=0):
        """
        Registers an animation for a specific pixel index.
        Respects priority: Higher priority overwrites lower.
        """
        # Validate index bounds
        if idx < 0 or idx >= self.num_pixels:
            return
        
        # Check priority lock
        slot = self.active_animations[idx]
        if slot.active:
            # If new priority is lower than current running priority, ignore request
            if priority < slot.priority:
                return
        else:
            # Adding a new animation
            self._active_count += 1

        slot.set(anim_type, color, speed, time.monotonic(), duration, priority)

    def fill_animation(self, anim_type, color, speed=1.0, duration=None, priority=0):
        """Applies an animation to ALL pixels."""
        start_t = time.monotonic()
        for i in range(self.num_pixels):
            # Check priority before updating slot
            slot = self.active_animations[i]
            if slot.active:
                if priority < slot.priority:
                    continue
            else:
                # Increment counter when adding to empty slot
                self._active_count += 1

            slot.set(anim_type, color, speed, start_t, duration, priority)

    async def animate_loop(self):
        """Unified background task to handle all pixel animations."""
        while True:
            # Check if any animations are active using counter
            if self._active_count == 0:
                await asyncio.sleep(0.1)
                continue

            now = time.monotonic()
            dirty = False

            for idx in range(self.num_pixels):
                slot = self.active_animations[idx]
                if not slot.active:
                    continue

                # 1. Duration Check
                if slot.duration:
                    elapsed = now - slot.start
                    if elapsed >= slot.duration:
                        self.pixels[idx] = (0, 0, 0)
                        slot.clear()
                        self._active_count -= 1
                        dirty = True
                        continue

                # 2. Animation Logic
                elapsed = now - slot.start

                # --- SOLID ---
                if slot.type == "SOLID":
                    self.pixels[idx] = slot.color
                    dirty = True

                # --- BLINK ---
                elif slot.type == "BLINK":
                    period = 1.0 / slot.speed
                    phase = elapsed % period
                    if phase < (period / 2):
                        self.pixels[idx] = slot.color
                    else:
                        self.pixels[idx] = (0, 0, 0)
                    dirty = True

                # --- PULSE (Breathing) ---
                elif slot.type == "PULSE":
                    t = elapsed * slot.speed
                    factor = 0.5 + 0.5 * math.sin(t * 2 * math.pi)
                    factor = max(0.1, factor)
                    base = slot.color
                    self.pixels[idx] = tuple(int(c * factor) for c in base)
                    dirty = True

                # --- RAINBOW ---
                elif slot.type == "RAINBOW":
                    hue = (elapsed * slot.speed + (idx * 0.05)) % 1.0
                    self.pixels[idx] = Palette.hsv_to_rgb(hue, 1.0, 1.0)
                    dirty = True

                # --- GLITCH ---
                elif slot.type == "GLITCH":
                    if random.random() > 0.9:
                        if random.random() > 0.5:
                             self.pixels[idx] = (255, 255, 255)
                        else:
                             self.pixels[idx] = (0, 0, 0)
                    else:
                        self.pixels[idx] = slot.color
                    dirty = True

                # --- SCANNER (Cylon) ---
                elif slot.type == "SCANNER":
                    # Moves back and forth across the strip
                    cycle = (elapsed * slot.speed) % 2.0
                    if cycle < 1.0:
                        pos = cycle * (self.num_pixels - 1)
                    else:
                        pos = (2.0 - cycle) * (self.num_pixels - 1)

                    dist = abs(idx - pos)
                    brightness = max(0, 1.0 - dist) # Tail length of 1.0
                    base = slot.color
                    self.pixels[idx] = tuple(int(c * brightness) for c in base)
                    dirty = True

                # --- CHASER (Centrifuge) ---
                elif slot.type == "CHASER":
                    # Spins in one direction
                    pos = (elapsed * slot.speed * self.num_pixels) % self.num_pixels
                    # Calculate circular distance
                    dist = (idx - pos) % self.num_pixels
                    if dist > (self.num_pixels / 2): dist -= self.num_pixels
                    dist = abs(dist)

                    brightness = max(0, 1.0 - (dist / 2.0)) # Broader tail
                    base = slot.color
                    self.pixels[idx] = tuple(int(c * brightness) for c in base)
                    dirty = True

                # --- DECAY ---
                elif slot.type == "DECAY":
                    duration = 1.0 / slot.speed
                    if elapsed >= duration:
                        self.pixels[idx] = (0, 0, 0)
                        slot.clear()
                        self._active_count -= 1
                    else:
                        factor = 1.0 - (elapsed / duration)
                        base = slot.color
                        self.pixels[idx] = tuple(int(c * factor) for c in base)
                    dirty = True

            # Note: Hardware write is now handled by CoreManager.render_loop()
            # We only update the memory buffer here

            await asyncio.sleep(0.05)
