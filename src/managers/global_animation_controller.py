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
        self._frame_counter = 0  # Synchronized frame counter (updated via sync_frame())

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

    def sync_frame(self, frame):
        """Update the synchronized frame counter used by deterministic animations.

        Called by RenderManager (Core) each frame, or by satellite firmware after
        receiving a SYNC_FRAME packet, to keep animations temporally aligned.

        Args:
            frame: Integer frame counter from the Master (Core) RenderManager.
        """
        self._frame_counter = frame

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

    def register_discrete_leds(self, led_manager, pixel_coordinates):
        """
        Register a LEDManager with arbitrarily placed pixels in the global canvas.

        Each entry in *pixel_coordinates* maps a hardware pixel (by list index)
        to a specific global ``(x, y)`` position.  Pixels do not need to be
        contiguous or aligned — they can be scattered anywhere on the canvas,
        which is useful for hardware layouts where a single data line routes to
        LEDs in different physical locations around a component.

        Args:
            led_manager: LEDManager instance to register.
            pixel_coordinates: List of ``(global_x, global_y)`` tuples.
                               ``pixel_coordinates[i]`` is the global coordinate
                               of hardware pixel index ``i``.

        Raises:
            ValueError: If the number of coordinates does not match
                        ``led_manager.num_pixels``.
        """
        if len(pixel_coordinates) != led_manager.num_pixels:
            raise ValueError(
                f"pixel_coordinates length ({len(pixel_coordinates)}) must match "
                f"led_manager.num_pixels ({led_manager.num_pixels})"
            )

        self._components.append({
            'type': 'custom_leds',
            'manager': led_manager,
            'coordinates': list(pixel_coordinates),
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
            ox = component.get('offset_x', 0)
            oy = component.get('offset_y', 0)

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

            elif component['type'] == 'custom_leds':
                for i, (gx, gy) in enumerate(component['coordinates']):
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

        When ``_frame_counter`` has been set via :meth:`sync_frame` to a non-zero
        value, the hue is computed from the integer frame counter at an assumed
        60 Hz rate, making it deterministic and reproducible across the Core and
        any satellite that shares the same synchronized frame counter.  If the
        counter is 0 (never updated), the animation falls back to
        ``time.monotonic()`` for standalone / non-networked use.

        Duration is always measured in wall-clock time via ``time.monotonic()``.

        Args:
            speed: Hue rotation speed in degrees per second (default: 30.0).
                   Higher values produce a faster-moving wave.
            duration: Optional duration in seconds. Runs indefinitely if None.
            priority: Animation priority level passed to set_animation().
        """
        if not self._pixel_map:
            return

        canvas_w = max(self._canvas_width, 1)
        _FRAME_RATE = 60.0  # Assumed frame rate for frame-counter-to-seconds conversion
        start_t = time.monotonic()

        while True:
            now = time.monotonic()
            elapsed = now - start_t

            if duration is not None and elapsed >= duration:
                break

            # Use synchronized frame counter when available (non-zero), otherwise
            # fall back to wall-clock elapsed time for standalone operation.
            if self._frame_counter != 0:
                t = self._frame_counter / _FRAME_RATE
            else:
                t = elapsed

            for (gx, gy), (manager, idx) in self._pixel_map.items():
                # Hue = time-driven offset + spatial offset based on global X.
                # Produces a rainbow band that sweeps left → right across the canvas.
                hue = (t * speed + gx * (360.0 / canvas_w)) % 360.0
                color = Palette.hsv_to_rgb(hue, 1.0, 1.0)
                manager.set_animation(idx, "SOLID", color, priority=priority)

            await asyncio.sleep(0.05)

    async def global_rain(self, color=None, speed=0.15, duration=None, density=0.3):
        """
        Falling rain animation that cascades from the top of the canvas downward,
        seamlessly transitioning from matrix pixels to LED strips positioned below.

        Each tick, active drops advance one row. New drops are randomly spawned at
        the top row of each column based on the density parameter.

        When ``_frame_counter`` has been set via :meth:`sync_frame` and is
        advancing each render frame, the step interval is computed from ``speed``
        and an assumed 60 Hz rate so that drops advance at frame boundaries.
        If the frame counter is not advancing (e.g., standalone mode), the
        animation falls back to wall-clock timing via ``time.monotonic()``.

        Duration is always measured in wall-clock time.

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

        _FRAME_RATE = 60.0
        step_frames = max(1, round(speed * _FRAME_RATE))  # frames per drop-advance step
        start_frame = self._frame_counter
        last_step_frame = start_frame - step_frames  # ensure first step runs immediately
        start_t = time.monotonic()
        last_step_t = start_t - speed  # fallback: ensure first step runs immediately

        while True:
            now = time.monotonic()
            elapsed = now - start_t

            if duration is not None and elapsed >= duration:
                break

            # Use frame counter for step timing if it is advancing; otherwise
            # fall back to wall-clock timing for standalone operation.
            frame_advancing = self._frame_counter != start_frame
            if frame_advancing:
                time_to_step = (self._frame_counter - last_step_frame) >= step_frames
            else:
                time_to_step = (now - last_step_t) >= speed

            if time_to_step:
                if frame_advancing:
                    last_step_frame = self._frame_counter
                else:
                    last_step_t = now

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

            await asyncio.sleep(0.016)  # ~60 Hz yield to keep event loop responsive
