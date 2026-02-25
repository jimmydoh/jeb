# File: src/core/managers/base_pixel_manager.py
"""Dummy BasePixelManager - no-op replacement for isolated hardware testing."""

import asyncio

from utilities.logger import JEBLogger

class BasePixelManager:
    def __init__(self, *args, **kwargs):
        JEBLogger.info("PXLM", f"[INIT] DummyBasePixelManager")

    def get_layout_type(self, *args, **kwargs):
        return "custom"  # Default to CUSTOM for dummy

    def get_dimensions(self, *args, **kwargs):
        return (0, 0)  # No pixels in dummy

    def get_shape(self, *args, **kwargs):
        return {
            'type': self.get_layout_type(),
            'dimensions': self.get_dimensions()
        }

    def clear(self, *args, **kwargs):
        pass

    def clear_animation(self, *args, **kwargs):
        return True

    def set_animation(self, *args, **kwargs):
        pass

    def fill_animation(self, *args, **kwargs):
        pass

    def _apply_brightness(self, *args, **kwargs):
        return tuple(0,0,0)

    def solid(self, *args, **kwargs):
        pass

    def flash(self, *args, **kwargs):
        pass

    def breathe(self, *args, **kwargs):
        pass

    def cylon(self, *args, **kwargs):
        pass

    def centrifuge(self, *args, **kwargs):
        pass

    def rainbow(self, *args, **kwargs):
        pass

    def glitch(self, *args, **kwargs):
        pass

    async def animate_loop(self, *args, **kwargs):
        pass
