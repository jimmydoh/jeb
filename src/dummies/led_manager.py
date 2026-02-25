# File: src/dummies/led_manager.py
"""Dummy LEDManager - no-op replacement for isolated hardware testing."""

import asyncio

from dummies.base_pixel_manager import BasePixelManager

class LEDManager(BasePixelManager):
    """Drop-in dummy for LEDManager. All methods are no-ops."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def set_led(self, index, color, brightness=1.0, anim=None, duration=None, priority=2, speed=1.0):
        pass

    def off_led(self, index, priority=99):
        pass

    def apply_command(self, cmd, val):
        pass

    def solid_led(self, index, color, brightness=0.2, duration=None, priority=2):
        pass

    def flash_led(self, index, color, brightness=0.2, duration=None, priority=2, speed=0.1, off_speed=None):
        pass

    def breathe_led(self, index, color, brightness=1.0, duration=None, priority=2, speed=2.0):
        pass

    def start_cylon(self, color, duration=None, speed=0.08):
        pass

    def start_centrifuge(self, color, duration=None, speed=0.1):
        pass

    def start_rainbow(self, duration=None, speed=0.01):
        pass

    def start_glitch(self, colors, duration=None, speed=0.05):
        pass

    async def animate_loop(self, step=True):
        pass
