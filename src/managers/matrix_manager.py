# File: src/core/managers/matrix_manager.py
"""Manages Matrix style LEDs."""

import asyncio

from utilities.palette import Palette
from utilities.icons import Icons

from .base_pixel_manager import BasePixelManager, PixelLayout

class MatrixManager(BasePixelManager):
    """Class to manage Matrix style LED arrays, such as the GlowBit 64 LED Matrix."""
    def __init__(self, jeb_pixel):
        # Declare MATRIX_2D layout with 8x8 dimensions
        super().__init__(jeb_pixel, layout_type=PixelLayout.MATRIX_2D, dimensions=(8, 8))

        self.palette = Palette.PALETTE_LIBRARY
        self.icons = Icons.ICON_LIBRARY

    def _get_idx(self, x, y):
        """Maps 2D (0-7) to Serpentine 1D index."""
        if y % 2 == 0:
            return (y * 8) + x
        return (y * 8) + (7 - x)

    def draw_pixel(self, x, y, color, show=False, anim_mode=None, speed=1.0, duration=None, brightness=1.0):
        """Sets a specific pixel on the matrix.

        Note: The 'show' parameter is deprecated and ignored.
        Hardware writes are now centralized in CoreManager.render_loop().
        
        Args:
            x: X coordinate (0-7)
            y: Y coordinate (0-7)
            color: RGB tuple (r, g, b)
            show: Deprecated, ignored
            anim_mode: Animation mode ("SOLID", "PULSE", "BLINK", etc.)
            speed: Animation speed
            duration: Optional duration in seconds
            brightness: Brightness multiplier (0.0-1.0)
        """
        if 0 <= x < 8 and 0 <= y < 8:
            idx = self._get_idx(x, y)
            anim_mode = anim_mode if anim_mode else "SOLID"
            
            # Use base class method with brightness support
            adjusted_color = self._apply_brightness(color, brightness)
            self.set_animation(idx, anim_mode, adjusted_color, speed, duration)

        # Note: 'show' parameter is ignored - render loop handles hardware writes

    def fill(self, color, show=True, anim_mode=None, speed=1.0, duration=None):
        """Fills the entire matrix with a single color or simple animation.

        Note: The 'show' parameter is deprecated and ignored.
        Hardware writes are now centralized in CoreManager.render_loop().
        """
        if anim_mode:
            self.fill_animation(anim_mode, color, speed, duration)
        else:
            self.clear()
            self.pixels.fill(color)
        # Note: 'show' parameter is ignored - render loop handles hardware writes

    # TODO draw_line, draw_rect, draw_circle, draw_text, etc.

    async def _animate_slide_left(self, icon_data, color, brightness):
        """
        Internal method to perform SLIDE_LEFT animation.
        Runs as a background task to avoid blocking the caller.

        Note: Hardware writes are now centralized in CoreManager.render_loop().
        """
        try:
            for offset in range(8, -1, -1):  # Slide from right to left
                self.fill(Palette.OFF, show=False)
                for y in range(8):
                    for x in range(8):
                        target_x = x - offset
                        if 0 <= target_x < 8:
                            pixel_value = icon_data[y * 8 + x]
                            if pixel_value != 0:
                                base = color if color else self.palette[pixel_value]
                                # Use base class brightness calculation
                                self.draw_pixel(target_x, y, base, brightness=brightness)
                # Note: Hardware write is now handled by CoreManager.render_loop()
                await asyncio.sleep(0.05)
        except asyncio.CancelledError:
            # Task was cancelled - clean up and exit gracefully
            raise
        except Exception as e:
            # Log error but don't crash - animation is non-critical
            # Note: print() is standard for CircuitPython/embedded systems
            print(f"Error in SLIDE_LEFT animation: {e}")

    def show_icon(
            self,
            icon_name,
            clear=True,
            anim_mode=None,
            speed=1.0,
            color=None,
            brightness=1.0
        ):
        """
        Displays a predefined icon on the matrix with optional animation.
        anim_mode: None, "PULSE", "BLINK" are non-blocking via the animate_loop.
        anim_mode: "SLIDE_LEFT" is non-blocking (spawned as background task).
        """
        if clear:
            self.clear()

        icon_data = self.icons.get(icon_name, self.icons["DEFAULT"])

        # Handle SLIDE_LEFT Animation - Spawn as background task
        if anim_mode == "SLIDE_LEFT":
            asyncio.create_task(self._animate_slide_left(icon_data, color, brightness))
            return

        for y in range(8):
            for x in range(8):
                idx = self._get_idx(x, y)
                pixel_value = icon_data[y * 8 + x]

                if pixel_value != 0:
                    base = color if color else self.palette[pixel_value]
                    # Use draw_pixel with brightness parameter
                    if anim_mode:
                        self.draw_pixel(x, y, base, anim_mode=anim_mode, speed=speed, brightness=brightness)
                    else:
                        self.draw_pixel(x, y, base, brightness=brightness)

        # Note: Hardware write is now handled by CoreManager.render_loop()

    # TODO Refactor progress grid to use animations
    def show_progress_grid(self, iterations, total=10, color=(100, 0, 200)):
        """Fills the matrix like a rising 'tank' of fluid."""
        self.fill(Palette.OFF, show=False)
        # Map {total} iterations to 64 pixels (approx 6 pixels per step)
        fill_limit = int((iterations / total) * 64)
        for i in range(fill_limit):
            self.draw_pixel(i % 8, 7 - (i // 8), color, show=False)
        # Note: Hardware write is now handled by CoreManager.render_loop()

    def draw_quadrant(self, quad_idx, color, anim_mode=None, speed=1.0, duration=None):
        """Fills one of four 4x4 quadrants: 0=TopLeft, 1=TopRight, 2=BottomLeft, 3=BottomRight."""
        # Define start X, Y for each quadrant
        offsets = [(0,0), (4,0), (0,4), (4,4)]
        ox, oy = offsets[quad_idx]

        for y in range(4):
            for x in range(4):
                self.draw_pixel(ox + x, oy + y, color, show=False, anim_mode=anim_mode, speed=speed, duration=duration)
        # Note: Hardware write is now handled by CoreManager.render_loop()
