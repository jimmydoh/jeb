# File: src/utilities/matrix_animations.py
"""Standalone matrix animation functions for LED matrix displays.

This module provides reusable, asyncio-based animation functions that can be used
with any matrix manager implementation. Animations are designed to be non-blocking
and can run as background tasks.
"""

import asyncio
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
        for offset in range(8, -1, -1):  # Slide from right to left
            matrix_manager.fill(Palette.OFF, show=False)
            for y in range(8):
                for x in range(8):
                    target_x = x - offset
                    if 0 <= target_x < 8:
                        pixel_value = icon_data[y * 8 + x]
                        if pixel_value != 0:
                            base = color if color else matrix_manager.palette[pixel_value]
                            # Use the manager's draw_pixel with brightness parameter
                            matrix_manager.draw_pixel(target_x, y, base, brightness=brightness)
            # Note: Hardware write is now handled by CoreManager.render_loop()
            await asyncio.sleep(0.05)
    except asyncio.CancelledError:
        # Task was cancelled - clean up and exit gracefully
        raise
    except Exception as e:
        # Log error but don't crash - animation is non-critical
        # Note: print() is standard for CircuitPython/embedded systems
        print(f"Error in SLIDE_LEFT animation: {e}")
