# File: src/core/managers/base_pixel_manager.py
"""Dummy BasePixelManager - no-op replacement for isolated hardware testing."""

import asyncio
from enum import Enum

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
    def __init__(self, pixel_object, layout_type=PixelLayout.LINEAR, dimensions=None):
        self.pixels = pixel_object # JEBPixel wrapper
        self.num_pixels = self.pixels.n

        # Shape/layout properties
        self._layout_type = layout_type
        self._dimensions = dimensions or (self.num_pixels,)

        JEBLogger.info("PXLM", f"[INIT] DummyBasePixelManager")

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
        pass

    def clear_animation(self, idx, priority=0):
        return True

    def set_animation(self, idx, anim_type, color, speed=1.0, duration=None, priority=0):
        pass

    def fill_animation(self, anim_type, color, speed=1.0, duration=None, priority=0):
        pass

    def _apply_brightness(self, base_color, brightness):
        return tuple(0,0,0)

    # --- COMMON ANIMATION TRIGGERS ---
    # These methods provide convenient wrappers for common animation patterns
    # and can be used by all subclasses regardless of layout type.

    def solid(self, index, color, brightness=1.0, duration=None, priority=2):
        pass

    def flash(self, index, color, brightness=1.0, duration=None, priority=2, speed=1.0):
        pass

    def breathe(self, index, color, brightness=1.0, duration=None, priority=2, speed=2.0):
        pass

    def cylon(self, color, duration=None, speed=0.08, priority=1):
        pass

    def centrifuge(self, color, duration=None, speed=0.1, priority=1):
        pass

    def rainbow(self, duration=None, speed=0.01, priority=1):
        pass

    def glitch(self, colors, duration=None, speed=0.05, priority=1):
        pass

    async def animate_loop(self, step=True):
        pass
