# File: src/managers/global_animation_controller.py
"""
Global Animation Controller that orchestrates unified animations across
all registered pixel components (MatrixManager and LEDManager instances).

Assigns a spatial (x, y) coordinate to every pixel in the system, creating
a unified canvas that enables cross-component animations such as global rainbow
waves and falling rain effects.
"""

import asyncio
import time
import random

from utilities.palette import Palette


class GlobalAnimationController:
    """
    Orchestrates global animations spanning MatrixManager and LEDManager instances.

    Builds a unified 2D (x, y) coordinate space by registering managers at
    positional offsets. Animations calculate frame states in the global coordinate
    space and delegate rendering to the appropriate manager.

    Usage:
        controller = GlobalAnimationController()
        controller.register_matrix(matrix_mgr, offset_x=0, offset_y=0)
        controller.register_led_strip(led_mgr, offset_x=0, offset_y=8, orientation='horizontal')
        asyncio.create_task(controller.global_rainbow_wave(speed=30.0, duration=10.0))
    """

    def __init__(self):
        """Initialize an empty global animation controller."""
        self._components = []   # list of component dicts
        self._pixel_map = {}    # (global_x, global_y) -> (manager, pixel_idx)
        self._canvas_width = 0
        self._canvas_height = 0

    @property
    def canvas_width(self):
        """Width of the unified canvas (max X + 1)."""
        return self._canvas_width

    @property
    def canvas_height(self):
        """Height of the unified canvas (max Y + 1)."""
        return self._canvas_height

    @property
    def pixel_count(self):
        """Total number of mapped pixels across all registered components."""
        return len(self._pixel_map)

    def register_matrix(self, matrix_manager, offset_x=0, offset_y=0):
        """
        Register a MatrixManager at a given global position.

        Each pixel (x, y) within the matrix is mapped to the global coordinate
        (offset_x + x, offset_y + y).

        Args:
            matrix_manager: MatrixManager instance to register.
            offset_x: Global X offset of the matrix's top-left corner.
            offset_y: Global Y offset of the matrix's top-left corner.
        """
        self._components.append({
            'type': 'matrix',
            'manager': matrix_manager,
            'offset_x': offset_x,
            'offset_y': offset_y,
        })
        self._rebuild_pixel_map()

    def register_led_strip(self, led_manager, offset_x=0, offset_y=0, orientation='horizontal'):
        """
        Register a LEDManager at a given global position.

        Args:
            led_manager: LEDManager instance to register.
            offset_x: Global X position of the first LED in the strip.
            offset_y: Global Y position of the first LED in the strip.
            orientation: 'horizontal' — LEDs extend right (+X direction).
                         'vertical'   — LEDs extend downward (+Y direction).

        Raises:
            ValueError: If orientation is not 'horizontal' or 'vertical'.
        """
        if orientation not in ('horizontal', 'vertical'):
            raise ValueError("orientation must be 'horizontal' or 'vertical'")

        self._components.append({
            'type': 'led_strip',
            'manager': led_manager,
            'offset_x': offset_x,
            'offset_y': offset_y,
            'orientation': orientation,
        })
        self._rebuild_pixel_map()

    def _rebuild_pixel_map(self):
        """
        Rebuilds the global pixel coordinate map from all registered components.

        Maps each (global_x, global_y) coordinate to (manager, pixel_index).
        Recalculates canvas dimensions after each rebuild.
        """
        self._pixel_map = {}
        max_x = -1
        max_y = -1

        for component in self._components:
            manager = component['manager']
            ox = component['offset_x']
            oy = component['offset_y']

            if component['type'] == 'matrix':
                width = manager.width
                height = manager.height
                for y in range(height):
                    for x in range(width):
                        gx = ox + x
                        gy = oy + y
                        pixel_idx = manager._get_idx(x, y)
                        self._pixel_map[(gx, gy)] = (manager, pixel_idx)
                        if gx > max_x:
                            max_x = gx
                        if gy > max_y:
                            max_y = gy

            elif component['type'] == 'led_strip':
                orientation = component['orientation']
                for i in range(manager.num_pixels):
                    if orientation == 'horizontal':
                        gx = ox + i
                        gy = oy
                    else:  # vertical
                        gx = ox
                        gy = oy + i
                    self._pixel_map[(gx, gy)] = (manager, i)
                    if gx > max_x:
                        max_x = gx
                    if gy > max_y:
                        max_y = gy

        self._canvas_width = max_x + 1 if self._pixel_map else 0
        self._canvas_height = max_y + 1 if self._pixel_map else 0

    def set_pixel(self, global_x, global_y, color):
        """
        Sets a pixel at global (x, y) coordinates directly (no animation slot).

        Useful for frame-by-frame animations that manage their own state.

        Args:
            global_x: Global X coordinate.
            global_y: Global Y coordinate.
            color: RGB tuple (r, g, b).
        """
        entry = self._pixel_map.get((global_x, global_y))
        if entry is not None:
            manager, idx = entry
            manager.pixels[idx] = color

    def clear(self):
        """Clears all pixels across all registered managers."""
        seen = set()
        for component in self._components:
            mgr = component['manager']
            mgr_id = id(mgr)
            if mgr_id not in seen:
                mgr.clear()
                seen.add(mgr_id)

    async def global_rainbow_wave(self, speed=30.0, duration=None, priority=1):
        """
        Drives a rainbow wave that sweeps across all registered pixels globally.

        The wave sweeps horizontally (left to right) across the entire canvas.
        All pixels at the same global X coordinate share a hue, creating vertical
        color bands that travel continuously across the full layout.

        Args:
            speed: Hue rotation speed in degrees per second (default: 30.0).
                   Higher values produce a faster-moving wave.
            duration: Optional duration in seconds. Runs indefinitely if None.
            priority: Animation priority level passed to set_animation().
        """
        if not self._pixel_map:
            return

        canvas_w = max(self._canvas_width, 1)
        start_t = time.monotonic()

        while True:
            now = time.monotonic()
            elapsed = now - start_t

            if duration is not None and elapsed >= duration:
                break

            for (gx, gy), (manager, idx) in self._pixel_map.items():
                # Hue = time-driven offset + spatial offset based on global X.
                # Produces a rainbow band that sweeps left → right across the canvas.
                hue = (elapsed * speed + gx * (360.0 / canvas_w)) % 360.0
                color = Palette.hsv_to_rgb(hue, 1.0, 1.0)
                manager.set_animation(idx, "SOLID", color, priority=priority)

            await asyncio.sleep(0.05)

    async def global_rain(self, color=None, speed=0.15, duration=None, density=0.3):
        """
        Falling rain animation that cascades from the top of the canvas downward,
        seamlessly transitioning from matrix pixels to LED strips positioned below.

        Each tick, active drops advance one row. New drops are randomly spawned at
        the top row of each column based on the density parameter.

        Args:
            color: RGB tuple for rain drops. Defaults to cyan-blue (0, 180, 255).
            speed: Seconds between each row step (default: 0.15). Lower = faster.
            duration: Optional duration in seconds. Runs indefinitely if None.
            density: Probability [0.0, 1.0] of a new drop spawning per column
                     per tick (default: 0.3).
        """
        if not self._pixel_map:
            return

        if color is None:
            color = (0, 180, 255)  # Cyan-blue default

        # Build column structures: gx -> sorted list of gy values present in map
        columns = {}
        for (gx, gy) in self._pixel_map:
            if gx not in columns:
                columns[gx] = []
            columns[gx].append(gy)
        for gx in columns:
            columns[gx].sort()

        # Track active drop positions: {gx: current_gy}
        active_drops = {}

        start_t = time.monotonic()

        while True:
            now = time.monotonic()
            elapsed = now - start_t

            if duration is not None and elapsed >= duration:
                break

            # Clear all pixels for this frame
            for (gx, gy), (manager, idx) in self._pixel_map.items():
                manager.pixels[idx] = (0, 0, 0)

            # Advance existing drops one row down
            new_drops = {}
            for gx, drop_gy in active_drops.items():
                col = columns.get(gx, [])
                next_rows = [gy for gy in col if gy > drop_gy]
                if next_rows:
                    new_drops[gx] = min(next_rows)
            active_drops = new_drops

            # Spawn new drops at the top of each column
            for gx, col_rows in columns.items():
                if gx not in active_drops and col_rows and random.random() < density:
                    active_drops[gx] = col_rows[0]

            # Render active drops
            for gx, drop_gy in active_drops.items():
                entry = self._pixel_map.get((gx, drop_gy))
                if entry is not None:
                    manager, idx = entry
                    manager.pixels[idx] = color

            await asyncio.sleep(speed)
