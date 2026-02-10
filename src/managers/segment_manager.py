#File: src/satellite/managers/segment_manager.py
"""Manages dual 14-segment displays."""

import asyncio
import random
import time

from adafruit_ht16k33.segments import Seg14x4

from utilities import parse_values, get_float, get_str

class SegmentManager:
    """Manages dual 14-segment displays."""
    def __init__(self, i2c):
        self._display_right = Seg14x4(i2c, address=0x70)
        self._display_right.brightness = 0.5
        self._display_left = Seg14x4(i2c, address=0x71)
        self._display_left.brightness = 0.5

        self._display_task = None

    # --- BASIC TRIGGERS ---
    async def start_message(self, message, loop=False, speed=0.3, direction="L"):
        """Starts a marquee message as a task."""
        if self._display_task and not self._display_task.done():
            self._display_task.cancel()
            await asyncio.sleep(0.1)
        self._display_task = asyncio.create_task(self._message_logic(message, loop, speed, direction))

    async def apply_command(self, cmd, val):
        """Parses and executes a raw protocol command."""
        if isinstance(val, (list, tuple)):
            values = val
        else:
            values = parse_values(val)

        if cmd == "DSP":
            self.start_message(
                message=get_str(values, 0),
                loop=(get_str(values, 1) == "1"),
                speed=get_float(values, 2, 0.3),
                direction=get_str(values, 3, "L")
            )
        elif cmd == "DSPCORRUPT":
            duration = get_float(values, 0, 2.0)
            self.start_corruption(duration if duration > 0 else 2.0)
        elif cmd == "DSPMATRIX":
            duration = get_float(values, 0, 2.0)
            self.start_matrix(duration if duration > 0 else 2.0)

    # --- BASIC LOGIC ---
    async def _message_logic(self, text, loop=False, speed=0.3, direction="L"):
        """Advanced Marquee for dual 14-segment displays."""
        text = text.upper()

        # 1. Handle Static Right-Justified (Short & No Loop)
        if len(text) <= 8 and not loop:
            self._display_left.fill(0)
            self._display_right.fill(0)
            # Pad left with spaces to right-justify
            padded = text.rjust(8)
            self._display_left.print(padded[:4])
            self._display_right.print(padded[4:])
            return

        # 2. Handle Marquee (Looping or Long Strings)
        # Pad with 8 spaces on either side to allow "scrolling in/out"
        display_text = "        " + text + "        "

        while True:
            # Range calculation for direction
            indices = range(len(display_text) - 7)
            if direction == "R":
                indices = reversed(indices)

            for i in indices:
                chunk = display_text[i:i+8]
                self._display_left.print(chunk[:4])
                self._display_right.print(chunk[4:])
                await asyncio.sleep(speed)

            if not loop:
                break # Exit after one pass if loop is false

    # --- ANIMATION TRIGGERS ---
    async def start_corruption(self, duration=None):
        """Starts the display corruption animation as a task."""
        if self._display_task and not self._display_task.done():
            self._display_task.cancel()
            await asyncio.sleep(0.1)
        self._display_task = asyncio.create_task(self._corruption_logic(duration))

    async def start_matrix(self, duration=None):
        """Starts the matrix rain animation as a task."""
        if self._display_task and not self._display_task.done():
            self._display_task.cancel()
            await asyncio.sleep(0.1)
        self._display_task = asyncio.create_task(self._matrix_logic(duration))

    # --- ANIMATION LOGIC ---
    async def _corruption_logic(self, duration=None):
        """Flickers random segments to simulate data corruption."""
        if duration:
            end_time = time.monotonic() + duration
        else:
            end_time = float('inf')

        while time.monotonic() < end_time:
            # Generate 4 random 16-bit integers for each display
            # This lights up random physical segments
            for i in range(4):
                self._display_left.set_digit_raw(i, random.getrandbits(16))
                self._display_right.set_digit_raw(i, random.getrandbits(16))

            self._display_left.show()
            self._display_right.show()
            # Fast, erratic flickering
            await asyncio.sleep(random.uniform(0.05, 0.15))

        # Clear when done
        self._display_left.fill(0)
        self._display_right.fill(0)
        self._display_left.show()
        self._display_right.show()

    async def _matrix_logic(self, duration=None):
        """Creates a 'falling' segment effect across all 8 digits."""
        if duration:
            end_time = time.monotonic() + duration
        else:
            end_time = float('inf')

        # Masks for Top, Middle, and Bottom horizontal bars
        # (Based on standard HT16K33 14-segment mapping)
        frames = [0x0001, 0x0040, 0x0008] # Top -> Middle -> Bottom

        while time.monotonic() < end_time:
            for frame in frames:
                for i in range(4):
                    self._display_left.set_digit_raw(i, frame)
                    self._display_right.set_digit_raw(i, frame)
                self._display_left.show()
                self._display_right.show()
                await asyncio.sleep(0.1)

        self._display_left.fill(0)
        self._display_right.fill(0)
        self._display_left.show()
        self._display_right.show()
