# File: src/utilities/matrix_animations.py
"""Standalone matrix animation functions for LED matrix displays.

This module provides reusable, asyncio-based animation functions that can be used
with any matrix manager implementation. Animations are designed to be non-blocking
and can run as background tasks.

Future matrix-specific animations (like slide animations, wipes, etc.) should be
added to this module rather than as methods in MatrixManager. This promotes:
- Reusability across different matrix implementations
- Easier testing and maintenance
- Separation of concerns (manager vs. animation logic)
- Extensibility for new animation types
"""

import asyncio
import math
from utilities.palette import Palette


async def animate_slide(matrix_manager, icon_data, direction, color=None, brightness=1.0):
    """
    Performs a SLIDE animation on a matrix display.

    This animation slides an icon from offscreen to the center of the matrix.
    Designed to run as a background asyncio task without blocking the caller.

    Args:
        matrix_manager: Instance of MatrixManager (or compatible class) with:
            - fill(color, show=False) method
            - draw_pixel(x, y, color, brightness=float) method
            - palette: Dictionary mapping pixel values to colors
        icon_data: List/array of 64 pixel values (8x8 matrix)
        direction: String, either 'left' (from offscreen left) or 'right' (from offscreen right)
        color: Optional RGB tuple to override palette colors. If None, uses palette.
        brightness: Float from 0.0 to 1.0 for brightness adjustment

    Raises:
        asyncio.CancelledError: If the task is cancelled during execution
        ValueError: If an invalid direction is provided

    Note:
        Hardware writes are centralized in CoreManager.render_loop().
        This function only updates the pixel buffer.
    """
    try:
        data_len = len(icon_data)
        icon_dim = int(math.sqrt(data_len))
        y_offset_center = (matrix_manager.height - icon_dim) // 2
        center_x = (matrix_manager.width - icon_dim) // 2

        # Configure start, end, and step based on the desired slide direction
        if direction == "left":
            start_x = -icon_dim
            end_x = center_x
            step = 1
        elif direction == "right":
            start_x = matrix_manager.width
            end_x = center_x
            step = -1
        else:
            raise ValueError("Direction must be 'left' or 'right'")

        # The end parameter in range() is exclusive, so we add the step to include end_x
        for current_x in range(start_x, end_x + step, step):
            matrix_manager.fill(Palette.OFF, show=False)
            
            for y in range(icon_dim):
                for x in range(icon_dim):
                    target_x = x + current_x
                    target_y = y + y_offset_center
                    
                    if 0 <= target_x < matrix_manager.width and 0 <= target_y < matrix_manager.height:
                        pixel_value = icon_data[y * icon_dim + x]
                        if pixel_value != 0:
                            base = color if color else matrix_manager.palette.get(pixel_value, (255, 255, 255))
                            matrix_manager.draw_pixel(target_x, target_y, base, brightness=brightness)
            
            await asyncio.sleep(0.01)
            
    except asyncio.CancelledError:
        # Task was cancelled - clean up and exit gracefully
        raise
    except Exception as e:
        # Log error but don't crash - animation is non-critical
        # Note: print() is standard for CircuitPython/embedded systems
        print(f"Error in SLIDE animation ({direction}): {e}")


async def animate_slide_left(matrix_manager, icon_data, color=None, brightness=1.0):
    """
    Performs a SLIDE_LEFT animation on a matrix display.

    This animation slides an icon from the left side of the matrix to the center.
    Designed to run as a background asyncio task without blocking the caller.
    """
    await animate_slide(matrix_manager, icon_data, "left", color=color, brightness=brightness)


async def animate_slide_right(matrix_manager, icon_data, color=None, brightness=1.0):
    """
    Performs a SLIDE_RIGHT animation on a matrix display.

    This animation slides an icon from the right side of the matrix to the center.
    Designed to run as a background asyncio task without blocking the caller.
    """
    await animate_slide(matrix_manager, icon_data, "right", color=color, brightness=brightness)


async def animate_random_pixel_reveal(matrix_manager, icon_data, duration, color=None, brightness=1.0):
    """
    Gradually reveals an icon by randomly illuminating its active pixels over a set duration.

    Active pixels (non-zero values in icon_data) are shuffled and lit one by one at
    equal time intervals so that the full image is visible by the end of the duration.

    Args:
        matrix_manager: Instance of MatrixManager (or compatible class) with:
            - draw_pixel(x, y, color, brightness=float) method
            - palette: Dictionary mapping pixel values to colors
            - width, height: Matrix dimensions
        icon_data: List/array of pixel values (must be a perfect square, e.g. 64 or 256)
        duration: Total reveal time in seconds (float)
        color: Optional RGB tuple to override palette colors. If None, uses palette.
        brightness: Float from 0.0 to 1.0 for brightness adjustment

    Raises:
        asyncio.CancelledError: If the task is cancelled during execution
        ValueError: If icon_data length is not a perfect square

    Note:
        Hardware writes are centralised in CoreManager.render_loop().
        This function only updates the pixel buffer.
    """
    import random

    try:
        data_len = len(icon_data)
        icon_dim = int(math.sqrt(data_len))
        if icon_dim * icon_dim != data_len:
            raise ValueError("icon_data length must be a perfect square")

        x_offset = (matrix_manager.width - icon_dim) // 2
        y_offset = (matrix_manager.height - icon_dim) // 2

        # Collect indices of active (non-zero) pixels
        active = [i for i in range(data_len) if icon_data[i] != 0]

        if not active:
            return

        # Shuffle for random reveal order
        random.shuffle(active)

        delay_per_pixel = duration / len(active)

        for idx in active:
            px = idx % icon_dim
            py = idx // icon_dim
            target_x = px + x_offset
            target_y = py + y_offset

            if 0 <= target_x < matrix_manager.width and 0 <= target_y < matrix_manager.height:
                pixel_value = icon_data[idx]
                base = color if color else matrix_manager.palette.get(pixel_value, (255, 255, 255))
                matrix_manager.draw_pixel(target_x, target_y, base, brightness=brightness)

            await asyncio.sleep(delay_per_pixel)

    except asyncio.CancelledError:
        raise
    except Exception as e:
        print(f"Error in RANDOM_PIXEL_REVEAL animation: {e}")


def animate_radar_sweep(matrix_manager, sweep_angle, bogeys=None, interceptors=None, trail_steps=4):
    """
    Renders a single frame of a radial radar sweep on a square LED matrix.

    Draws a rotating sweep line (like a radar dish) from the center outward, with
    fading trail pixels behind the leading edge. Bogeys (threats) are drawn as red
    pixels and interceptors (missiles in flight) as blue pixels.

    Designed to be called once per game tick from a synchronous game loop. The caller
    is responsible for scheduling display refreshes.

    Args:
        matrix_manager: Instance of MatrixManager (or compatible class) with:
            - fill(color, show=False) method
            - draw_pixel(x, y, color, brightness=float) method
            - width, height: Matrix dimensions
        sweep_angle: Current sweep angle in degrees (0 = top/north, clockwise).
        bogeys: Optional list of dicts with 'x' and 'y' keys (float, 0.0–1.0 normalized).
            Each bogey may also have an optional 'jammed' key (bool).
        interceptors: Optional list of dicts with 'x' and 'y' keys (float, 0.0–1.0 normalized).
        trail_steps: Number of trailing sweep steps to render (default 4, each dimmer).

    Note:
        Hardware writes are centralised in CoreManager.render_loop().
        This function only updates the pixel buffer.
    """
    import math

    try:
        w = matrix_manager.width
        h = matrix_manager.height
        cx = (w - 1) / 2.0
        cy = (h - 1) / 2.0
        max_r = min(cx, cy)

        matrix_manager.fill(Palette.OFF, show=False)

        # Draw fading sweep trail (behind the leading edge)
        trail_spread = 25.0  # degrees of trail arc
        for step in range(trail_steps, 0, -1):
            trail_angle_deg = sweep_angle - (step * (trail_spread / trail_steps))
            trail_angle_rad = math.radians(trail_angle_deg)
            brightness = 0.1 + 0.4 * (1.0 - step / trail_steps)
            trail_color = (0, int(80 * brightness), 0)

            # Draw pixels along the trail line from center outward
            for r_step in range(1, int(max_r) + 1):
                px = int(cx + r_step * math.sin(trail_angle_rad) + 0.5)
                py = int(cy - r_step * math.cos(trail_angle_rad) + 0.5)
                if 0 <= px < w and 0 <= py < h:
                    matrix_manager.draw_pixel(px, py, trail_color, brightness=brightness)

        # Draw the leading sweep line (bright green)
        sweep_rad = math.radians(sweep_angle)
        for r_step in range(1, int(max_r) + 1):
            px = int(cx + r_step * math.sin(sweep_rad) + 0.5)
            py = int(cy - r_step * math.cos(sweep_rad) + 0.5)
            if 0 <= px < w and 0 <= py < h:
                matrix_manager.draw_pixel(px, py, (0, 200, 0), brightness=1.0)

        # Draw base (center pixel) in white
        matrix_manager.draw_pixel(int(cx + 0.5), int(cy + 0.5), Palette.WHITE, brightness=0.8)

        # Draw bogeys as red pixels
        if bogeys:
            for bogey in bogeys:
                bx = int(bogey['x'] * (w - 1) + 0.5)
                by = int(bogey['y'] * (h - 1) + 0.5)
                if 0 <= bx < w and 0 <= by < h:
                    # Jammed bogeys flicker at reduced brightness
                    b = 0.5 if bogey.get('jammed', False) else 1.0
                    matrix_manager.draw_pixel(bx, by, Palette.RED, brightness=b)

        # Draw interceptors as blue pixels
        if interceptors:
            for interceptor in interceptors:
                ix = int(interceptor['x'] * (w - 1) + 0.5)
                iy = int(interceptor['y'] * (h - 1) + 0.5)
                if 0 <= ix < w and 0 <= iy < h:
                    matrix_manager.draw_pixel(ix, iy, Palette.BLUE, brightness=1.0)

    except Exception as e:
        print(f"Error in RADAR_SWEEP animation: {e}")


def animate_static_resolve(matrix_manager, icon_data, clarity, color=None, brightness=1.0):
    """
    Renders a single frame that blends random static with a target icon.

    At clarity=0.0 every pixel shows random coloured noise; at clarity=1.0
    only the correct icon pixels are visible.  Values between 0 and 1 produce
    a probabilistic mix: each pixel independently shows either its correct icon
    colour or a random static colour, weighted by the clarity value.

    Designed to be called once per display frame from a game loop (synchronous).
    The caller is responsible for scheduling display refreshes.

    Args:
        matrix_manager: Instance of MatrixManager (or compatible class) with:
            - fill(color, show=False) method
            - draw_pixel(x, y, color, brightness=float) method
            - palette: Dictionary mapping pixel values to colours
            - width, height: Matrix dimensions
        icon_data: List/array of pixel values (must be a perfect square, e.g. 64 or 256)
        clarity: Float from 0.0 (full static) to 1.0 (full icon).  Clamped automatically.
        color: Optional RGB tuple to override palette colours for icon pixels. If None, uses palette.
        brightness: Float from 0.0 to 1.0 for icon-pixel brightness.

    Note:
        Hardware writes are centralised in CoreManager.render_loop().
        This function only updates the pixel buffer.
    """
    import random

    try:
        data_len = len(icon_data)
        icon_dim = int(math.sqrt(data_len))
        if icon_dim * icon_dim != data_len:
            raise ValueError("icon_data length must be a perfect square")

        x_offset = (matrix_manager.width - icon_dim) // 2
        y_offset = (matrix_manager.height - icon_dim) // 2

        clarity = max(0.0, min(1.0, clarity))

        matrix_manager.fill(Palette.OFF, show=False)

        for y in range(icon_dim):
            for x in range(icon_dim):
                target_x = x + x_offset
                target_y = y + y_offset

                if not (0 <= target_x < matrix_manager.width and 0 <= target_y < matrix_manager.height):
                    continue

                pixel_value = icon_data[y * icon_dim + x]

                if random.random() < clarity:
                    # Show the correct icon pixel
                    if pixel_value != 0:
                        base = color if color else matrix_manager.palette.get(pixel_value, (255, 255, 255))
                        matrix_manager.draw_pixel(target_x, target_y, base, brightness=brightness)
                else:
                    # Show random static noise
                    static_color = (
                        random.randint(0, 255),
                        random.randint(0, 255),
                        random.randint(0, 255),
                    )
                    matrix_manager.draw_pixel(target_x, target_y, static_color, brightness=brightness * 0.5)

    except Exception as e:
        print(f"Error in STATIC_RESOLVE animation: {e}")
