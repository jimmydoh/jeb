# File: src/core/managers/matrix_manager.py
"""Manages Matrix style LEDs."""

import asyncio

from utilities.palette import Palette
from utilities.icons import Icons
from utilities import matrix_animations

from .base_pixel_manager import BasePixelManager, PixelLayout

class MatrixManager(BasePixelManager):
    """Class to manage Matrix style LED arrays, such as the GlowBit 64 LED Matrix.
    
    Supports arbitrary matrix configurations including:
    - Single 8x8 matrix (default)
    - Dual or quad 8x8 matrices working together
    - Multiple 1x8 strips arranged as a matrix
    - Individual LEDs arranged as a matrix
    """
    def __init__(self, jeb_pixel, width=8, height=8):
        """Initialize MatrixManager with configurable dimensions.
        
        Args:
            jeb_pixel: JEBPixel wrapper object
            width: Width of the matrix in pixels (default: 8)
            height: Height of the matrix in pixels (default: 8)
        """
        # Declare MATRIX_2D layout with configurable dimensions
        super().__init__(jeb_pixel, layout_type=PixelLayout.MATRIX_2D, dimensions=(width, height))
        
        # Store dimensions for easy access
        self.width = width
        self.height = height

        self.palette = Palette.PALETTE_LIBRARY
        self.icons = Icons.ICON_LIBRARY

    def _get_idx(self, x, y):
        """Maps 2D coordinates to Serpentine 1D index.
        
        Uses serpentine (zig-zag) pattern where even rows go left-to-right
        and odd rows go right-to-left.
        
        Args:
            x: X coordinate (0 to width-1)
            y: Y coordinate (0 to height-1)
            
        Returns:
            1D pixel index
        """
        if y % 2 == 0:
            return (y * self.width) + x
        return (y * self.width) + (self.width - 1 - x)

    def draw_pixel(self, x, y, color, show=False, anim_mode=None, speed=1.0, duration=None, brightness=1.0):
        """Sets a specific pixel on the matrix.

        Note: The 'show' parameter is deprecated and ignored.
        Hardware writes are now centralized in CoreManager.render_loop().
        
        Args:
            x: X coordinate (0 to width-1)
            y: Y coordinate (0 to height-1)
            color: RGB tuple (r, g, b)
            show: Deprecated, ignored
            anim_mode: Animation mode ("SOLID", "PULSE", "BLINK", etc.)
            speed: Animation speed
            duration: Optional duration in seconds
            brightness: Brightness multiplier (0.0-1.0)
        """
        if 0 <= x < self.width and 0 <= y < self.height:
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
        
        Note: Icons are designed for 8x8 matrices. On larger matrices, the icon
        is displayed in the top-left corner. On smaller matrices, the icon is clipped.
        """
        if clear:
            self.clear()

        icon_data = self.icons.get(icon_name, self.icons["DEFAULT"])

        # Handle SLIDE_LEFT Animation - Spawn as background task
        if anim_mode == "SLIDE_LEFT":
            asyncio.create_task(matrix_animations.animate_slide_left(self, icon_data, color, brightness))
            return

        # Icon data is 8x8, so we need to handle different matrix sizes
        icon_width = 8
        icon_height = 8
        
        for y in range(min(icon_height, self.height)):
            for x in range(min(icon_width, self.width)):
                idx = self._get_idx(x, y)
                pixel_value = icon_data[y * icon_width + x]

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
        """Fills the matrix like a rising 'tank' of fluid.
        
        Fills from bottom to top, adapting to any matrix size.
        """
        self.fill(Palette.OFF, show=False)
        # Map {total} iterations to total pixels
        fill_limit = int((iterations / total) * self.num_pixels)
        for i in range(fill_limit):
            # Fill from bottom-left, going right then up
            x = i % self.width
            y = self.height - 1 - (i // self.width)
            self.draw_pixel(x, y, color, show=False)
        # Note: Hardware write is now handled by CoreManager.render_loop()

    def draw_quadrant(self, quad_idx, color, anim_mode=None, speed=1.0, duration=None):
        """Fills one of four quadrants: 0=TopLeft, 1=TopRight, 2=BottomLeft, 3=BottomRight.
        
        Quadrant size is calculated as half the matrix dimensions, rounded down.
        Works with any matrix size, not just 8x8.
        """
        # Calculate quadrant dimensions
        quad_width = self.width // 2
        quad_height = self.height // 2
        
        # Define start X, Y for each quadrant based on calculated dimensions
        offsets = [
            (0, 0),                          # Top-left
            (quad_width, 0),                 # Top-right
            (0, quad_height),                # Bottom-left
            (quad_width, quad_height)        # Bottom-right
        ]
        ox, oy = offsets[quad_idx]

        for y in range(quad_height):
            for x in range(quad_width):
                self.draw_pixel(ox + x, oy + y, color, show=False, anim_mode=anim_mode, speed=speed, duration=duration)
        # Note: Hardware write is now handled by CoreManager.render_loop()
