# File: src/core/managers/base_pixel_manager.py
"""Base class for managing NeoPixel animations via a non-blocking loop."""

import asyncio
import time
import math
import random
from enum import Enum

from utilities.palette import Palette
from utilities.logger import JEBLogger

class PixelLayout(Enum):
    """Defines the physical layout type of pixel arrays."""
    LINEAR = "linear"           # 1D strip, string, or straight line
    MATRIX_2D = "matrix_2d"     # 2D grid/matrix (e.g., 8x8)
    CIRCLE = "circle"           # Circular/ring arrangement
    CUSTOM = "custom"           # Custom/irregular layout

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
        """Update slot properties in place.

        Args:
            color: Can be a single color tuple (r,g,b), a list/tuple of colors,
                   or None for effects like RAINBOW.
                   Lists are converted to tuples for immutability.
        """
        self.active = True
        self.type = anim_type
        # Convert lists to tuples to prevent accidental mutation
        # Tuples and None are kept as-is (already immutable)
        self.color = tuple(color) if isinstance(color, list) else color
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
    Supports: SOLID, BLINK, PULSE, RAINBOW, GLITCH, DECAY, SCANNER (Cylon), CHASER.

    Provides shape/layout awareness for implementing subclasses to enable
    layout-specific animation behavior.
    """
    def __init__(self, pixel_object, layout_type=PixelLayout.LINEAR, dimensions=None):
        """
        Initialize pixel manager with shape/layout awareness.

        Args:
            pixel_object: JEBPixel wrapper object
            layout_type: PixelLayout enum indicating physical arrangement
            dimensions: Tuple of dimensions, e.g., (width, height) for MATRIX_2D,
                       (radius,) for CIRCLE, or (length,) for LINEAR
        """
        self.pixels = pixel_object # JEBPixel wrapper
        self.num_pixels = self.pixels.n

        # Shape/layout properties
        self._layout_type = layout_type
        self._dimensions = dimensions or (self.num_pixels,)

        JEBLogger.info("PXLM", f"[INIT] BasePixelManager - layout: {self._layout_type} dimensions: {self._dimensions}")

        # Fixed-size list for animations (one slot per pixel)
        # Each slot is a reusable AnimationSlot object
        self.active_animations = [AnimationSlot() for _ in range(self.num_pixels)]

        # Track active animation count to avoid O(n) checks
        self._active_count = 0

    def get_layout_type(self):
        """Returns the layout type (PixelLayout enum)."""
        return self._layout_type

    def get_dimensions(self):
        """Returns the dimensions tuple for this pixel array."""
        return self._dimensions

    def get_shape(self):
        """
        Returns shape information as a dict for convenience.

        Returns:
            dict with 'type' (PixelLayout) and 'dimensions' (tuple)
        """
        return {
            'type': self._layout_type,
            'dimensions': self._dimensions
        }

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

    def _apply_brightness(self, base_color, brightness):
        """
        Stateless, highly optimized brightness calculation.

        Args:
            base_color: Tuple of (r, g, b) values
            brightness: Float from 0.0 to 1.0 (values outside range are clamped)

        Returns:
            Tuple of brightness-adjusted (r, g, b) values

        Note:
            - Clamps brightness to [0.0, 1.0] to prevent NeoPixel ValueErrors
            - Uses explicit tuple indexing for better performance on RP2350
            - Avoids generator comprehensions to reduce heap fragmentation
        """
        # Clamp brightness to prevent NeoPixel ValueErrors
        brightness = max(0.0, min(1.0, brightness))

        if brightness >= 1.0:
            return base_color
        if brightness <= 0.0:
            return (0, 0, 0)

        # Explicit tuple indexing is significantly faster on RP2350
        # and avoids generator comprehensions in memory
        return (
            int(base_color[0] * brightness),
            int(base_color[1] * brightness),
            int(base_color[2] * brightness)
        )

    # --- COMMON ANIMATION TRIGGERS ---
    # These methods provide convenient wrappers for common animation patterns
    # and can be used by all subclasses regardless of layout type.

    def solid(self, index, color, brightness=1.0, duration=None, priority=2):
        """
        Sets a SOLID animation (static color) to a specific pixel or all pixels.

        Args:
            index: Pixel index, or -1/out-of-range for all pixels
            color: RGB tuple (r, g, b)
            brightness: Brightness multiplier (0.0-1.0)
            duration: Optional duration in seconds
            priority: Animation priority level
        """
        targets = range(self.num_pixels) if index < 0 or index >= self.num_pixels else [index]
        adjusted_color = self._apply_brightness(color, brightness)
        for i in targets:
            self.set_animation(i, "SOLID", adjusted_color, duration=duration, priority=priority)

    def flash(self, index, color, brightness=1.0, duration=None, priority=2, speed=1.0):
        """
        Flashes a specific pixel or all pixels (BLINK animation).

        Args:
            index: Pixel index, or -1/out-of-range for all pixels
            color: RGB tuple (r, g, b)
            brightness: Brightness multiplier (0.0-1.0)
            duration: Optional duration in seconds
            priority: Animation priority level
            speed: Blink speed (flashes per second)
        """
        targets = range(self.num_pixels) if index < 0 or index >= self.num_pixels else [index]
        adjusted_color = self._apply_brightness(color, brightness)
        for i in targets:
            self.set_animation(i, "BLINK", adjusted_color, duration=duration, speed=speed, priority=priority)

    def breathe(self, index, color, brightness=1.0, duration=None, priority=2, speed=2.0):
        """
        Commences a breathing/pulse animation on a specific pixel or all pixels.

        Args:
            index: Pixel index, or -1/out-of-range for all pixels
            color: RGB tuple (r, g, b)
            brightness: Brightness multiplier (0.0-1.0)
            duration: Optional duration in seconds
            priority: Animation priority level
            speed: Breathing speed (cycles per second)
        """
        targets = range(self.num_pixels) if index < 0 or index >= self.num_pixels else [index]
        adjusted_color = self._apply_brightness(color, brightness)
        for i in targets:
            self.set_animation(i, "PULSE", adjusted_color, duration=duration, speed=speed, priority=priority)

    def cylon(self, color, duration=None, speed=0.08, priority=1):
        """
        Starts a Cylon/scanner animation across all pixels.
        Animation behavior adapts to layout type.

        Args:
            color: RGB tuple (r, g, b)
            duration: Optional duration in seconds
            speed: Scanner speed
            priority: Animation priority level
        """
        self.fill_animation("SCANNER", color, speed=speed, duration=duration, priority=priority)

    def centrifuge(self, color, duration=None, speed=0.1, priority=1):
        """
        A looping 'spinning' effect with motion blur (CHASER animation).

        Args:
            color: RGB tuple (r, g, b)
            duration: Optional duration in seconds
            speed: Spin speed
            priority: Animation priority level
        """
        self.fill_animation("CHASER", color, speed=speed, duration=duration, priority=priority)

    def rainbow(self, duration=None, speed=0.01, priority=1):
        """
        Smoothly cycles colors across all pixels (RAINBOW animation).

        Args:
            duration: Optional duration in seconds
            speed: Color cycle speed
            priority: Animation priority level
        """
        self.fill_animation("RAINBOW", None, speed=speed, duration=duration, priority=priority)

    def glitch(self, colors, duration=None, speed=0.05, priority=1):
        """
        Randomly 'pops' pixels from a list of colors to simulate instability.

        Args:
            colors: List of RGB tuples to randomly display
            duration: Optional duration in seconds
            speed: Glitch speed
            priority: Animation priority level
        """
        self.fill_animation("GLITCH", colors, speed=speed, duration=duration, priority=priority)

    async def animate_loop(self, step=True):
        """Unified background task to handle all pixel animations."""
        while True:
            # Check if any animations are active using counter
            if self._active_count == 0:
                if step:
                    return
                await asyncio.sleep(0.05)
                continue

            now = time.monotonic()

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
                        continue

                # 2. Animation Logic
                elapsed = now - slot.start

                # --- SOLID ---
                if slot.type == "SOLID":
                    self.pixels[idx] = slot.color

                # --- BLINK ---
                elif slot.type == "BLINK":
                    period = 1.0 / slot.speed
                    phase = elapsed % period
                    if phase < (period / 2):
                        self.pixels[idx] = slot.color
                    else:
                        self.pixels[idx] = (0, 0, 0)

                # --- PULSE (Breathing) ---
                elif slot.type == "PULSE":
                    t = elapsed * slot.speed
                    factor = 0.5 + 0.5 * math.sin(t * 2 * math.pi)
                    factor = max(0.1, factor)
                    base = slot.color
                    self.pixels[idx] = tuple(int(c * factor) for c in base)

                # --- RAINBOW ---
                elif slot.type == "RAINBOW":
                    hue = (elapsed * slot.speed + (idx * 0.05)) % 1.0
                    self.pixels[idx] = Palette.hsv_to_rgb(hue, 1.0, 1.0)

                # --- GLITCH ---
                elif slot.type == "GLITCH":
                    # TODO: GLITCH animation may have a bug - if slot.color is a list/tuple of colors,
                    # line 183 assigns the entire collection to the pixel instead of randomly selecting
                    # one color. This should probably be: self.pixels[idx] = random.choice(slot.color)
                    # For now, this works when slot.color is a single color tuple.
                    if random.random() > 0.9:
                        if random.random() > 0.5:
                             self.pixels[idx] = (255, 255, 255)
                        else:
                             self.pixels[idx] = (0, 0, 0)
                    else:
                        self.pixels[idx] = slot.color

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

            if step:
                return

            await asyncio.sleep(0.05)
