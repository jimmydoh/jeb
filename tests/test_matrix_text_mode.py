#!/usr/bin/env python3
"""Unit tests for MatrixManager text mode functionality."""

import sys
import os
import pytest
import asyncio
import time
from unittest import mock

# Mock CircuitPython modules BEFORE any imports
class MockModule:
    """Generic mock module."""
    def __getattr__(self, name):
        return MockModule()
    
    def __call__(self, *args, **kwargs):
        return MockModule()

# Mock all CircuitPython-specific modules
sys.modules['digitalio'] = MockModule()
sys.modules['busio'] = MockModule()
sys.modules['board'] = MockModule()
sys.modules['adafruit_mcp230xx'] = MockModule()
sys.modules['adafruit_mcp230xx.mcp23017'] = MockModule()
sys.modules['adafruit_ticks'] = MockModule()
sys.modules['audiobusio'] = MockModule()
sys.modules['audiocore'] = MockModule()
sys.modules['audiomixer'] = MockModule()
sys.modules['analogio'] = MockModule()
sys.modules['microcontroller'] = MockModule()
sys.modules['watchdog'] = MockModule()
sys.modules['audiopwmio'] = MockModule()
sys.modules['synthio'] = MockModule()
sys.modules['ulab'] = MockModule()
sys.modules['neopixel'] = MockModule()
sys.modules['adafruit_displayio_ssd1306'] = MockModule()
sys.modules['adafruit_display_text'] = MockModule()
sys.modules['adafruit_display_text.label'] = MockModule()
sys.modules['adafruit_ht16k33'] = MockModule()
sys.modules['adafruit_ht16k33.segments'] = MockModule()

# Add src directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

# Import production MatrixManager
from managers.matrix_manager import MatrixManager


# Mock JEBPixel and neopixel for testing
class MockNeoPixel:
    """Mock neopixel.NeoPixel for testing."""
    def __init__(self, n):
        self.n = n
        self._pixels = [(0, 0, 0)] * n
        self.brightness = 0.3

    def __setitem__(self, idx, color):
        if 0 <= idx < self.n:
            self._pixels[idx] = color

    def __getitem__(self, idx):
        return self._pixels[idx]

    def fill(self, color):
        self._pixels = [color] * self.n

    def show(self):
        pass  # Mock - does nothing


class MockJEBPixel:
    """Mock JEBPixel wrapper for testing."""
    def __init__(self, num_pixels=64):
        self.n = num_pixels
        self._pixels = MockNeoPixel(num_pixels)
        self.brightness = 0.3

    def __setitem__(self, idx, color):
        self._pixels[idx] = color

    def __getitem__(self, idx):
        return self._pixels[idx]

    def fill(self, color):
        self._pixels.fill(color)

    def show(self):
        self._pixels.show()


class MockPixelFramebuffer:
    """Mock for adafruit_pixel_framebuf.PixelFramebuffer."""
    def __init__(self, pixels, width, height, alternating=False, **kwargs):
        self.pixels = pixels
        self.width = width
        self.height = height
        self.alternating = alternating
        self._scroll_x = 0
        self._scroll_y = 0
        self.text_calls = []
        self.display_call_count = 0
        self.scroll_calls = []
        self.fill_calls = []

    def text(self, string, x, y, color, font_name="font5x8.bin"):
        """Mock text rendering method."""
        self.text_calls.append({
            'string': string,
            'x': x,
            'y': y,
            'color': color,
            'font_name': font_name
        })

    def display(self):
        """Mock display update method."""
        self.display_call_count += 1

    def scroll(self, dx, dy):
        """Mock scroll method."""
        self._scroll_x += dx
        self._scroll_y += dy
        self.scroll_calls.append((dx, dy))

    def fill(self, value):
        """Mock fill method."""
        self.fill_calls.append(value)


def create_matrix_with_framebuf(width=8, height=8):
    """Helper to create a MatrixManager with mocked framebuf."""
    mock_pixel = MockJEBPixel(width * height)
    matrix = MatrixManager(mock_pixel, width=width, height=height)
    
    # Inject mock framebuffer
    mock_framebuf = MockPixelFramebuffer(matrix.pixels, width, height)
    matrix._framebuf = mock_framebuf
    
    return matrix, mock_framebuf


@pytest.mark.asyncio
async def test_display_text_activates_text_mode():
    """Test that calling display_text() activates text mode."""
    print("Testing display_text activates text mode...")
    
    matrix, mock_framebuf = create_matrix_with_framebuf()
    
    # Initially text mode should be inactive
    assert matrix._text_mode_active is False, "Text mode should start inactive"
    
    # Call display_text
    matrix.display_text("HELLO")
    
    # Text mode should now be active
    assert matrix._text_mode_active is True, "Text mode should be active after display_text()"
    
    print("  ✓ Text mode activated")


@pytest.mark.asyncio
async def test_display_text_no_framebuf_is_noop():
    """Test that display_text() with no framebuf returns without error."""
    print("\nTesting display_text with no framebuf is a noop...")
    
    # Create matrix without framebuf
    mock_pixel = MockJEBPixel(64)
    matrix = MatrixManager(mock_pixel)
    
    # Ensure framebuf is None
    assert matrix._framebuf is None, "Framebuf should be None by default"
    
    # Initially text mode should be inactive
    assert matrix._text_mode_active is False, "Text mode should start inactive"
    
    # Call display_text - should not raise error
    matrix.display_text("HELLO")
    
    # Text mode should remain inactive
    assert matrix._text_mode_active is False, "Text mode should stay inactive when framebuf is None"
    
    print("  ✓ display_text() safely handles missing framebuf")


@pytest.mark.asyncio
async def test_display_text_string_with_newline():
    """Test that display_text() with newline calls text() twice."""
    print("\nTesting display_text with newline string...")
    
    matrix, mock_framebuf = create_matrix_with_framebuf(width=16, height=16)
    
    # Call display_text with newline
    matrix.display_text("LINE1\nLINE2")
    
    # Should have two text calls
    assert len(mock_framebuf.text_calls) == 2, f"Expected 2 text calls, got {len(mock_framebuf.text_calls)}"
    
    # Verify first line
    first_call = mock_framebuf.text_calls[0]
    assert first_call['string'] == "LINE1", f"First line should be 'LINE1', got '{first_call['string']}'"
    assert first_call['y'] == 0, f"First line y should be 0, got {first_call['y']}"
    
    # Verify second line
    second_call = mock_framebuf.text_calls[1]
    assert second_call['string'] == "LINE2", f"Second line should be 'LINE2', got '{second_call['string']}'"
    assert second_call['y'] == 8, f"Second line y should be 8, got {second_call['y']}"
    
    print("  ✓ Newline text split into two lines correctly")


@pytest.mark.asyncio
async def test_display_text_list_input():
    """Test that display_text() with list input calls text() for each item."""
    print("\nTesting display_text with list input...")
    
    matrix, mock_framebuf = create_matrix_with_framebuf(width=16, height=16)
    
    # Call display_text with list
    matrix.display_text(["LINE1", "LINE2"])
    
    # Should have two text calls
    assert len(mock_framebuf.text_calls) == 2, f"Expected 2 text calls, got {len(mock_framebuf.text_calls)}"
    
    # Verify first line
    first_call = mock_framebuf.text_calls[0]
    assert first_call['string'] == "LINE1", f"First line should be 'LINE1', got '{first_call['string']}'"
    assert first_call['y'] == 0, f"First line y should be 0, got {first_call['y']}"
    
    # Verify second line
    second_call = mock_framebuf.text_calls[1]
    assert second_call['string'] == "LINE2", f"Second line should be 'LINE2', got '{second_call['string']}'"
    assert second_call['y'] == 8, f"Second line y should be 8, got {second_call['y']}"
    
    print("  ✓ List text rendered correctly")


@pytest.mark.asyncio
async def test_stop_text_deactivates_text_mode():
    """Test that stop_text() deactivates text mode."""
    print("\nTesting stop_text deactivates text mode...")
    
    matrix, mock_framebuf = create_matrix_with_framebuf()
    
    # Activate text mode
    matrix.display_text("HELLO")
    assert matrix._text_mode_active is True, "Text mode should be active"
    
    # Stop text mode
    matrix.stop_text()
    
    # Text mode should be inactive
    assert matrix._text_mode_active is False, "Text mode should be inactive after stop_text()"
    
    print("  ✓ Text mode deactivated")


@pytest.mark.asyncio
async def test_stop_text_clears_framebuf():
    """Test that stop_text() clears the framebuffer."""
    print("\nTesting stop_text clears framebuf...")
    
    matrix, mock_framebuf = create_matrix_with_framebuf()
    
    # Activate text mode
    matrix.display_text("HELLO")
    
    # Clear call history
    mock_framebuf.fill_calls = []
    mock_framebuf.display_call_count = 0
    
    # Stop text mode
    matrix.stop_text()
    
    # Verify fill(0) was called
    assert len(mock_framebuf.fill_calls) == 1, f"Expected 1 fill call, got {len(mock_framebuf.fill_calls)}"
    assert mock_framebuf.fill_calls[0] == 0, f"Fill should be called with 0, got {mock_framebuf.fill_calls[0]}"
    
    # Verify display() was called
    assert mock_framebuf.display_call_count == 1, f"Expected 1 display call, got {mock_framebuf.display_call_count}"
    
    print("  ✓ Framebuffer cleared and displayed")


@pytest.mark.asyncio
async def test_animate_loop_text_mode_scrolls():
    """Test that animate_loop scrolls when in text mode."""
    print("\nTesting animate_loop in text mode scrolls...")
    
    matrix, mock_framebuf = create_matrix_with_framebuf()
    
    # Activate text mode
    matrix.display_text("HELLO", scroll_speed=0.01)
    
    # Clear scroll history
    mock_framebuf.scroll_calls = []
    mock_framebuf.display_call_count = 0
    
    # Wait a bit to ensure scroll delay has passed
    await asyncio.sleep(0.02)
    
    # Run one step of animate_loop
    await matrix.animate_loop(step=True)
    
    # Verify scroll was called
    assert len(mock_framebuf.scroll_calls) >= 1, f"Expected at least 1 scroll call, got {len(mock_framebuf.scroll_calls)}"
    
    # Verify scroll direction (left = -1, 0)
    first_scroll = mock_framebuf.scroll_calls[0]
    assert first_scroll == (-1, 0), f"Expected scroll(-1, 0), got scroll{first_scroll}"
    
    # Verify display was called
    assert mock_framebuf.display_call_count >= 1, f"Expected at least 1 display call, got {mock_framebuf.display_call_count}"
    
    print("  ✓ Text mode scrolling works")


@pytest.mark.asyncio
async def test_animate_loop_standard_mode_delegates():
    """Test that animate_loop delegates to base class when not in text mode."""
    print("\nTesting animate_loop in standard mode delegates...")
    
    matrix, mock_framebuf = create_matrix_with_framebuf()
    
    # Ensure text mode is not active
    assert matrix._text_mode_active is False, "Text mode should be inactive"
    
    # Clear scroll history
    mock_framebuf.scroll_calls = []
    
    # Run one step of animate_loop
    await matrix.animate_loop(step=True)
    
    # In standard mode, scroll should NOT be called
    assert len(mock_framebuf.scroll_calls) == 0, f"Expected 0 scroll calls in standard mode, got {len(mock_framebuf.scroll_calls)}"
    
    print("  ✓ Standard mode delegates to base class")


@pytest.mark.asyncio
async def test_display_text_scroll_speed_stored():
    """Test that scroll_speed parameter is stored correctly."""
    print("\nTesting display_text scroll_speed parameter...")
    
    matrix, mock_framebuf = create_matrix_with_framebuf()
    
    # Call with custom scroll speed
    custom_speed = 0.1
    matrix.display_text("HELLO", scroll_speed=custom_speed)
    
    # Verify scroll speed was stored
    assert matrix._text_scroll_delay == custom_speed, \
        f"Expected scroll delay {custom_speed}, got {matrix._text_scroll_delay}"
    
    print("  ✓ Scroll speed stored correctly")


@pytest.mark.asyncio
async def test_display_text_color_parameter():
    """Test that color parameter is passed to framebuf.text()."""
    print("\nTesting display_text color parameter...")
    
    matrix, mock_framebuf = create_matrix_with_framebuf()
    
    # Call with custom color
    custom_color = (255, 0, 0)  # Red
    matrix.display_text("HELLO", color=custom_color)
    
    # Verify color was passed to text()
    assert len(mock_framebuf.text_calls) == 1, f"Expected 1 text call, got {len(mock_framebuf.text_calls)}"
    text_call = mock_framebuf.text_calls[0]
    assert text_call['color'] == custom_color, \
        f"Expected color {custom_color}, got {text_call['color']}"
    
    print("  ✓ Color parameter passed correctly")


@pytest.mark.asyncio
async def test_display_text_limits_to_two_lines():
    """Test that display_text limits output to 2 lines maximum."""
    print("\nTesting display_text limits to 2 lines...")
    
    matrix, mock_framebuf = create_matrix_with_framebuf(width=16, height=16)
    
    # Call with 3+ lines
    matrix.display_text(["LINE1", "LINE2", "LINE3", "LINE4"])
    
    # Should only render first 2 lines
    assert len(mock_framebuf.text_calls) == 2, \
        f"Expected 2 text calls (max), got {len(mock_framebuf.text_calls)}"
    
    # Verify only first two lines were rendered
    assert mock_framebuf.text_calls[0]['string'] == "LINE1"
    assert mock_framebuf.text_calls[1]['string'] == "LINE2"
    
    print("  ✓ Text limited to 2 lines correctly")


@pytest.mark.asyncio
async def test_display_text_x_position():
    """Test that text is positioned at the right edge (width) for scrolling."""
    print("\nTesting display_text x position...")
    
    matrix, mock_framebuf = create_matrix_with_framebuf(width=16, height=16)
    
    # Call display_text
    matrix.display_text("HELLO")
    
    # Verify text x position equals matrix width (for scroll-in effect)
    assert len(mock_framebuf.text_calls) == 1
    text_call = mock_framebuf.text_calls[0]
    assert text_call['x'] == matrix.width, \
        f"Expected x={matrix.width}, got x={text_call['x']}"
    
    print("  ✓ Text positioned at right edge for scrolling")


@pytest.mark.asyncio
async def test_text_mode_scroll_timing():
    """Test that text scrolling respects the scroll delay timing."""
    print("\nTesting text scroll timing...")
    
    matrix, mock_framebuf = create_matrix_with_framebuf()
    
    # Activate text mode with very slow scroll
    matrix.display_text("HELLO", scroll_speed=1.0)  # 1 second delay
    
    # Clear scroll history
    mock_framebuf.scroll_calls = []
    
    # Run animate_loop immediately (should not scroll yet)
    await matrix.animate_loop(step=True)
    
    # Should not have scrolled yet (timing not met)
    assert len(mock_framebuf.scroll_calls) == 0, \
        f"Expected 0 scroll calls (timing not met), got {len(mock_framebuf.scroll_calls)}"
    
    # Now with a very fast scroll speed
    matrix._text_scroll_delay = 0.001  # 1ms
    matrix._text_last_scroll = time.monotonic() - 0.01  # Force timing to be met
    
    # Run animate_loop again
    await matrix.animate_loop(step=True)
    
    # Should have scrolled now
    assert len(mock_framebuf.scroll_calls) >= 1, \
        f"Expected at least 1 scroll call (timing met), got {len(mock_framebuf.scroll_calls)}"
    
    print("  ✓ Scroll timing respected")


@pytest.mark.asyncio
async def test_stop_text_without_framebuf():
    """Test that stop_text() safely handles missing framebuf."""
    print("\nTesting stop_text without framebuf...")
    
    # Create matrix without framebuf
    mock_pixel = MockJEBPixel(64)
    matrix = MatrixManager(mock_pixel)
    
    # Manually activate text mode (shouldn't happen in practice, but test safety)
    matrix._text_mode_active = True
    
    # Call stop_text - should not raise error
    matrix.stop_text()
    
    # Text mode should be deactivated
    assert matrix._text_mode_active is False, "Text mode should be deactivated"
    
    print("  ✓ stop_text() safely handles missing framebuf")


async def run_async_tests():
    """Run all async tests."""
    print("=" * 60)
    print("MatrixManager Text Mode Test Suite")
    print("=" * 60)

    try:
        await test_display_text_activates_text_mode()
        await test_display_text_no_framebuf_is_noop()
        await test_display_text_string_with_newline()
        await test_display_text_list_input()
        await test_stop_text_deactivates_text_mode()
        await test_stop_text_clears_framebuf()
        await test_animate_loop_text_mode_scrolls()
        await test_animate_loop_standard_mode_delegates()
        await test_display_text_scroll_speed_stored()
        await test_display_text_color_parameter()
        await test_display_text_limits_to_two_lines()
        await test_display_text_x_position()
        await test_text_mode_scroll_timing()
        await test_stop_text_without_framebuf()

        print("\n" + "=" * 60)
        print("✓ All text mode tests passed!")
        print("=" * 60)
        return True

    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    # Run async tests
    success = asyncio.run(run_async_tests())
    sys.exit(0 if success else 1)
