# File: src/dummies/matrix_manager.py
"""Dummy MatrixManager - no-op replacement for isolated hardware testing."""

import asyncio

from dummies.base_pixel_manager import BasePixelManager

class PanelLayout:
    """Dummy PanelLayout constants mirroring the real enum values."""
    Z_PATTERN = "z_pattern"
    SERPENTINE = "serpentine"
    CUSTOM = "custom"


class MatrixManager(BasePixelManager):
    """Drop-in dummy for MatrixManager. All methods are no-ops."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.width = kwargs.get('width', 8)
        self.height = kwargs.get('height', 8)

    def _get_idx(self, x, y):
        return 0

    def draw_pixel(self, x, y, color, show=False, anim_mode=None, speed=1.0, duration=None, brightness=1.0):
        pass

    def fill(self, color, show=True, anim_mode=None, speed=1.0, duration=None):
        pass

    def show_icon(self, icon_name, clear=True, anim_mode=None, speed=1.0, color=None, brightness=1.0):
        pass

    def show_progress_grid(self, iterations, total=10, color=(100, 0, 200)):
        pass

    def draw_quadrant(self, quad_idx, color, anim_mode=None, speed=1.0, duration=None):
        pass

    def draw_eq_bands(self, band_heights, colors=None):
        pass

    def draw_wedge(self, quad_idx, color, anim_mode=None, speed=1.0, duration=None):
        pass

    def display_text(self, text, color=(255, 255, 255), scroll_speed=0.05):
        pass

    def stop_text(self):
        pass

    async def animate_loop(self, step=True):
        pass
