# File: src/core/managers/matrix_manager.py
"""Manages Matrix style LEDs."""

import asyncio
import math
import sys
import time

from utilities.logger import JEBLogger
from utilities.palette import Palette
from utilities.icons import Icons
from utilities import matrix_animations

from .base_pixel_manager import BasePixelManager, PixelLayout

class PanelLayout:
    Z_PATTERN = "z_pattern"          # [0, 1] / [2, 3] -> Left-to-right, row by row (Current PR)
    SERPENTINE = "serpentine"        # [0, 1] / [3, 2] -> Left-to-right, right-to-left
    CUSTOM = "custom"                # Manual list mapping

class MatrixManager(BasePixelManager):
    """Class to manage Matrix style LED arrays, such as the GlowBit 64 LED Matrix.

    Supports arbitrary matrix configurations including:
    - Single 8x8 matrix (default)
    - Dual or quad 8x8 matrices working together (tiled panels)
    - Multiple 1x8 strips arranged as a matrix
    - Individual LEDs arranged as a matrix

    For tiled panel configurations (e.g., four 8x8 panels forming a 16x16 display),
    the manager handles the physical panel layout correctly, where each panel has
    its own pixel range due to how they are chained together.
    """
    def __init__(self, jeb_pixel, width=8, height=8, panel_width=None, panel_height=None, chain_layout=PanelLayout.Z_PATTERN, custom_chain_map=None):
        """Initialize MatrixManager with configurable dimensions.

        Args:
            jeb_pixel: JEBPixel wrapper object
            width: Width of the entire display in pixels (default: 8)
            height: Height of the entire display in pixels (default: 8)
            panel_width: Width of each physical panel in pixels (default: same as width)
            panel_height: Height of each physical panel in pixels (default: same as height)

        For single panels, panel_width and panel_height default to width and height.
        For tiled configurations (e.g., four 8x8 panels as 16x16), specify:
            MatrixManager(jeb_pixel, width=16, height=16, panel_width=8, panel_height=8)
        """
        JEBLogger.info("MATM", f"[INIT] MatrixManager - width: {width}, height: {height}, panel_width: {panel_width}, panel_height: {panel_height}, chain_layout: {chain_layout}")
        # Declare MATRIX_2D layout with configurable dimensions
        super().__init__(jeb_pixel, layout_type=PixelLayout.MATRIX_2D, dimensions=(width, height))

        # Store display dimensions
        self.width = width
        self.height = height

        # Store panel dimensions (default to display dimensions for single panel)
        self.panel_width = panel_width if panel_width is not None else width
        self.panel_height = panel_height if panel_height is not None else height

        self.palette = Palette.LIBRARY

        self.chain_layout = chain_layout
        self.custom_chain_map = custom_chain_map

        if self.chain_layout == PanelLayout.CUSTOM and not self.custom_chain_map:
            raise ValueError("custom_chain_map must be provided when using CUSTOM layout")

        self._build_index_lut()

        # --- Text Mode State ---
        self._text_mode_active = False
        self._text_last_scroll = 0.0
        self._text_scroll_delay = 0.05  # Default scroll interval in seconds
        self._framebuf = None
        try:
            import adafruit_pixel_framebuf
            self._framebuf = adafruit_pixel_framebuf.PixelFramebuffer(
                self.pixels,
                self.width,
                self.height,
                alternating=(chain_layout == PanelLayout.SERPENTINE)
            )
        except ImportError:
            JEBLogger.warning("MATM", "adafruit_pixel_framebuf not available. Text scrolling features will not be available.")

    def _get_panel_chain_index(self, panel_x, panel_y, panels_per_row):
        """Determines the hardware wiring index for a physical panel position."""
        if self.chain_layout == PanelLayout.Z_PATTERN:
            return panel_y * panels_per_row + panel_x

        elif self.chain_layout == PanelLayout.SERPENTINE:
            if panel_y % 2 == 0:
                # Even rows: Left to right
                return panel_y * panels_per_row + panel_x
            else:
                # Odd rows: Right to left
                return panel_y * panels_per_row + (panels_per_row - 1 - panel_x)

        elif self.chain_layout == PanelLayout.CUSTOM:
            # custom_chain_map is expected to be a 1D list mapped row-major
            # Example for 2x2 grid: [0, 1, 3, 2] means bottom-left panel is 3rd in the chain
            return self.custom_chain_map[panel_y * panels_per_row + panel_x]

    def _build_index_lut(self):
        """Precomputes coordinate mapping to save CPU cycles during rendering."""
        lut = []
        panels_per_row = self.width // self.panel_width
        pixels_per_panel = self.panel_width * self.panel_height

        for y in range(self.height):
            for x in range(self.width):
                panel_x = x // self.panel_width
                panel_y = y // self.panel_height
                local_x = x % self.panel_width
                local_y = y % self.panel_height

                # Use the new layout logic here
                panel_idx = self._get_panel_chain_index(panel_x, panel_y, panels_per_row)

                # Standard serpentine logic WITHIN the individual panel
                if local_y % 2 == 0:
                    local_idx = (local_y * self.panel_width) + local_x
                else:
                    local_idx = (local_y * self.panel_width) + (self.panel_width - 1 - local_x)

                lut.append(panel_idx * pixels_per_panel + local_idx)

        self._idx_map = tuple(lut)

    def _get_idx(self, x, y):
        """
        Maps 2D coordinates to 1D pixel index with panel-aware addressing using
        a precomputed lookup table for efficiency.

        For single panels, uses serpentine (zig-zag) pattern where even rows go
        left-to-right and odd rows go right-to-left.

        For tiled panels (e.g., four 8x8 panels forming 16x16), correctly maps
        coordinates accounting for how panels are physically chained together.
        Each panel has its own pixel range, and serpentine addressing applies
        within each panel.

        Args:
            x: X coordinate (0 to width-1)
            y: Y coordinate (0 to height-1)

        Returns:
            1D pixel index
        """
        return self._idx_map[y * self.width + x]

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

    # TODO draw_line, draw_rect, draw_circle, etc.

    def display_text(self, text, color=(255, 255, 255), scroll_speed=0.05):
        """Display scrolling text on the matrix using adafruit_pixel_framebuf.

        Enables Text Mode, which bypasses standard animation slots until
        stop_text() is called. Supports multiline text via newlines or a list.

        Args:
            text: String (use '\\n' for two lines) or list of up to 2 strings.
            color: RGB tuple (r, g, b), default white.
            scroll_speed: Seconds between each 1-pixel left scroll step.
        """
        if not self._framebuf:
            return

        self.clear()
        self._text_scroll_delay = scroll_speed
        self._text_mode_active = True

        # Support either a string with newlines, or a list of strings
        lines = text.split('\n') if isinstance(text, str) else text

        # Draw each line, offsetting Y by 8 pixels per row
        for i, line in enumerate(lines[:2]):  # Limit to 2 rows to fit 16x16
            y_offset = i * 8
            # The .text() signature takes string, x, y, and color
            self._framebuf.text(line, self.width, y_offset, color, font_name="font5x8.bin")

        self._framebuf.display()
        self._text_last_scroll = time.monotonic()

    def stop_text(self):
        """Stop text mode and return control to the standard animation slots."""
        self._text_mode_active = False
        if self._framebuf:
            self._framebuf.fill(0)
            self._framebuf.display()

    async def animate_loop(self, step=True):
        """Unified background task with text mode bypass.

        When text mode is active, autonomously scrolls the frame buffer at a
        deterministic speed and bypasses the standard animation slot evaluation.
        """
        while True:
            # Text Mode Bypass — skip standard slot evaluation
            if self._text_mode_active and self._framebuf:
                now = time.monotonic()
                if now - self._text_last_scroll >= self._text_scroll_delay:
                    self._framebuf.scroll(-1, 0)  # Shift left 1 pixel
                    self._framebuf.display()       # Push to self.pixels
                    self._text_last_scroll = now
                if step:
                    return
                await asyncio.sleep(0.05)
                continue

            # Standard animation handling (delegate to base class for one step)
            await super().animate_loop(step=True)

            if step:
                return

            await asyncio.sleep(0.05)

    # TODO Refactor progress grid to use animations
    def show_icon(
            self,
            icon_name,
            clear=True,
            anim_mode=None,
            speed=1.0,
            color=None,
            brightness=1.0,
            border_color=None
        ):
        """
        Displays a predefined icon on the matrix with optional animation.
        anim_mode: None, "PULSE", "BLINK" are non-blocking via the animate_loop.
        anim_mode: "SLIDE_LEFT", "SLIDE_RIGHT" are non-blocking (spawned as background tasks).

        border_color: Optional RGB tuple. When provided, a 1-pixel border is drawn
        around the icon footprint using the specified colour. Intended for 14x14
        icons displayed on a 16x16 matrix where the 1px padding on each side
        becomes the border frame.
        """
        if clear:
            self.clear()

        icon_data = Icons.get(icon_name)

        # Handle SLIDE_LEFT Animation - Spawn as background task
        if anim_mode == "SLIDE_LEFT":
            asyncio.create_task(matrix_animations.animate_slide_left(self, icon_data, color, brightness))
            return

        # Handle SLIDE_RIGHT Animation - Spawn as background task
        if anim_mode == "SLIDE_RIGHT":
            asyncio.create_task(matrix_animations.animate_slide_right(self, icon_data, color, brightness))
            return

        data_len = len(icon_data)
        icon_dim = int(math.sqrt(data_len))

        icon_width = icon_dim
        icon_height = icon_dim

        # [CHANGE] Auto-Centering Logic
        offset_x = (self.width - icon_width) // 2
        offset_y = (self.height - icon_height) // 2

        # Iterate over the ICON'S dimensions, not the matrix dimensions
        for y in range(icon_height):
            for x in range(icon_width):
                pixel_value = icon_data[y * icon_width + x]

                if pixel_value != 0:
                    base = color if color else self.palette[pixel_value]

                    # Calculate target position on matrix
                    target_x = x + offset_x
                    target_y = y + offset_y

                    # Only draw if within bounds
                    if 0 <= target_x < self.width and 0 <= target_y < self.height:
                        if anim_mode:
                            self.draw_pixel(target_x, target_y, base, anim_mode=anim_mode, speed=speed, brightness=brightness)
                        else:
                            self.draw_pixel(target_x, target_y, base, brightness=brightness)

        # Draw 1-pixel border around the icon bounding box when border_color is set
        if border_color is not None:
            bx0 = offset_x - 1
            by0 = offset_y - 1
            bx1 = offset_x + icon_width
            by1 = offset_y + icon_height

            # Top and bottom rows
            for bx in range(bx0, bx1 + 1):
                if 0 <= bx < self.width:
                    if 0 <= by0 < self.height:
                        if anim_mode:
                            self.draw_pixel(bx, by0, border_color, anim_mode=anim_mode, speed=speed, brightness=brightness)
                        else:
                            self.draw_pixel(bx, by0, border_color, brightness=brightness)
                    if 0 <= by1 < self.height:
                        if anim_mode:
                            self.draw_pixel(bx, by1, border_color, anim_mode=anim_mode, speed=speed, brightness=brightness)
                        else:
                            self.draw_pixel(bx, by1, border_color, brightness=brightness)

            # Left and right columns (corners already covered above)
            for by in range(by0 + 1, by1):
                if 0 <= by < self.height:
                    if 0 <= bx0 < self.width:
                        if anim_mode:
                            self.draw_pixel(bx0, by, border_color, anim_mode=anim_mode, speed=speed, brightness=brightness)
                        else:
                            self.draw_pixel(bx0, by, border_color, brightness=brightness)
                    if 0 <= bx1 < self.width:
                        if anim_mode:
                            self.draw_pixel(bx1, by, border_color, anim_mode=anim_mode, speed=speed, brightness=brightness)
                        else:
                            self.draw_pixel(bx1, by, border_color, brightness=brightness)

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

    def draw_eq_bands(self, band_heights, colors=None):
        """Draw EQ frequency-band bars on the matrix.

        Renders vertical bars rising from the bottom of the matrix, one bar
        per frequency band.  The number of bars is clamped to the matrix width.

        Args:
            band_heights: Iterable of bar heights (0 to self.height) per band.
            colors: Optional list of (r, g, b) tuples, one per band.
                    When omitted a low=RED / mid=GOLD / high=CYAN gradient is used.
        """
        self.clear()
        num_bands = min(len(band_heights), self.width)

        for x in range(num_bands):
            height = max(0, min(self.height, band_heights[x]))

            if colors and x < len(colors):
                color = colors[x]
            elif x < num_bands // 4:
                color = Palette.RED
            elif x < (num_bands * 3) // 4:
                color = Palette.GOLD
            else:
                color = Palette.CYAN

            for y in range(self.height - height, self.height):
                self.draw_pixel(x, y, color)

    def draw_wedge(self, quad_idx, color, anim_mode=None, speed=1.0, duration=None):
        """Draws a curved wedge (ring-sector) shape in one of four quadrants.

        Unlike draw_quadrant which fills the entire rectangular quadrant, this
        draws a quarter-circle arc shape with:
        - An inner circular gap near the matrix centre
        - A circular outer arc that naturally clips the quadrant corners

        Quadrant indices: 0=TopLeft, 1=TopRight, 2=BottomLeft, 3=BottomRight.
        All bounds derive from self.width and self.height (no hardcoded values).
        """
        cx = self.width / 2
        cy = self.height / 2
        half = min(cx, cy)

        # Radii scale with matrix size
        inner_r = half * 0.3   # Centre gap (~30% of half-dimension)
        outer_r = half         # Outer arc at the half-dimension radius

        quad_width = self.width // 2
        quad_height = self.height // 2

        offsets = [
            (0, 0),                          # Top-left
            (quad_width, 0),                 # Top-right
            (0, quad_height),                # Bottom-left
            (quad_width, quad_height)        # Bottom-right
        ]
        ox, oy = offsets[quad_idx]

        for y in range(quad_height):
            for x in range(quad_width):
                # Use pixel centre for distance calculation (squared to avoid sqrt)
                px = ox + x + 0.5
                py = oy + y + 0.5
                d_sq = (px - cx) ** 2 + (py - cy) ** 2
                if inner_r * inner_r <= d_sq <= outer_r * outer_r:
                    self.draw_pixel(ox + x, oy + y, color, show=False, anim_mode=anim_mode, speed=speed, duration=duration)
        # Note: Hardware write is now handled by CoreManager.render_loop()
