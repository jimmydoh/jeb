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


async def animate_slide_left(matrix_manager, icon_data, color=None, brightness=1.0):
    """
    Performs a SLIDE_LEFT animation on a matrix display.

    This animation slides an icon from right to left across the matrix.
    Designed to run as a background asyncio task without blocking the caller.

    Args:
        matrix_manager: Instance of MatrixManager (or compatible class) with:
            - fill(color, show=False) method
            - draw_pixel(x, y, color, brightness=float) method
            - palette: Dictionary mapping pixel values to colors
        icon_data: List/array of 64 pixel values (8x8 matrix)
        color: Optional RGB tuple to override palette colors. If None, uses palette.
        brightness: Float from 0.0 to 1.0 for brightness adjustment

    Raises:
        asyncio.CancelledError: If the task is cancelled during execution

    Note:
        Hardware writes are centralized in CoreManager.render_loop().
        This function only updates the pixel buffer.
    """
    try:
        data_len = len(icon_data)
        icon_dim = int(math.sqrt(data_len))
        y_offset_center = (matrix_manager.height - icon_dim) // 2

        #Calculate steps to center the icon on the matrix
        steps = icon_dim + (matrix_manager.width - icon_dim) // 2
        left_edge_end = steps - icon_dim

        for offset in range(icon_dim, -1 - left_edge_end, -1):
            matrix_manager.fill(Palette.OFF, show=False)
            for y in range(icon_dim):
                for x in range(icon_dim):
                    target_x = x - offset
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
        print(f"Error in SLIDE_LEFT animation: {e}")


async def animate_slide_right(matrix_manager, icon_data, color=None, brightness=1.0):
    """
    Performs a SLIDE_RIGHT animation on a matrix display.

    This animation slides an icon from the right side of the matrix to the centre.
    Designed to run as a background asyncio task without blocking the caller.

    Args:
        matrix_manager: Instance of MatrixManager (or compatible class) with:
            - fill(color, show=False) method
            - draw_pixel(x, y, color, brightness=float) method
            - palette: Dictionary mapping pixel values to colors
        icon_data: List/array of 64 pixel values (8x8 matrix)
        color: Optional RGB tuple to override palette colors. If None, uses palette.
        brightness: Float from 0.0 to 1.0 for brightness adjustment

    Raises:
        asyncio.CancelledError: If the task is cancelled during execution

    Note:
        Hardware writes are centralized in CoreManager.render_loop().
        This function only updates the pixel buffer.
    """
    try:
        data_len = len(icon_data)
        icon_dim = int(math.sqrt(data_len))
        y_offset_center = (matrix_manager.height - icon_dim) // 2

        # Calculate the final centered x offset
        center_offset = (matrix_manager.width - icon_dim) // 2

        for offset in range(matrix_manager.width, center_offset - 1, -1):
            matrix_manager.fill(Palette.OFF, show=False)
            for y in range(icon_dim):
                for x in range(icon_dim):
                    target_x = x + offset
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
        print(f"Error in SLIDE_RIGHT animation: {e}")
