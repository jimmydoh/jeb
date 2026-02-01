"""
Docstring for satellite.managers.segment_manager
"""

import asyncio
import random
import time

from adafruit_ht16k33.segments import Seg14x4

class SegmentManager:
    """
    Docstring for SegmentManager
    """
    def __init__(self, i2c):
        self.display_right = Seg14x4(i2c, address=0x70)
        self.display_right.brightness = 0.5
        self.display_left = Seg14x4(i2c, address=0x71)
        self.display_left.brightness = 0.5

        self.display_loop = False

    async def display_corruption_anim(self,duration=2.0):
        """Flickers random segments to simulate data corruption."""
        self.display_loop = True
        end_time = time.monotonic() + duration

        while time.monotonic() < end_time and self.display_loop:
            # Generate 4 random 16-bit integers for each display
            # This lights up random physical segments
            for i in range(4):
                self.display_left.set_digit_raw(i, random.getrandbits(16))
                self.display_right.set_digit_raw(i, random.getrandbits(16))

            self.display_left.show()
            self.display_right.show()
            # Fast, erratic flickering
            await asyncio.sleep(random.uniform(0.05, 0.15))

        # Clear when done
        self.display_left.fill(0)
        self.display_right.fill(0)
        self.display_left.show()
        self.display_right.show()
        self.display_loop = False

    async def display_matrix_rain(self,duration=3.0):
        """Creates a 'falling' segment effect across all 8 digits."""
        self.display_loop = True
        end_time = time.monotonic() + duration

        # Masks for Top, Middle, and Bottom horizontal bars
        # (Based on standard HT16K33 14-segment mapping)
        frames = [0x0001, 0x0040, 0x0008] # Top -> Middle -> Bottom

        while time.monotonic() < end_time and self.display_loop:
            for frame in frames:
                if not self.display_loop:
                    break
                for i in range(4):
                    self.display_left.set_digit_raw(i, frame)
                    self.display_right.set_digit_raw(i, frame)
                self.display_left.show()
                self.display_right.show()
                await asyncio.sleep(0.1)

        self.display_left.fill(0)
        self.display_right.fill(0)
        self.display_left.show()
        self.display_right.show()
        self.display_loop = False

    async def segment_message(self, text, loop=False, speed=0.3, direction="L"):
        """Advanced Marquee for dual 14-segment displays."""
        self.display_loop = loop
        text = text.upper()

        # 1. Handle Static Right-Justified (Short & No Loop)
        if len(text) <= 8 and not loop:
            self.display_left.fill(0)
            self.display_right.fill(0)
            # Pad left with spaces to right-justify
            padded = text.rjust(8)
            self.display_left.print(padded[:4])
            self.display_right.print(padded[4:])
            return

        # 2. Handle Marquee (Looping or Long Strings)
        # Pad with 4 spaces on either side to allow "scrolling in/out"
        display_text = "    " + text + "    "

        while True:
            # Range calculation for direction
            indices = range(len(display_text) - 7)
            if direction == "R":
                indices = reversed(indices)

            for i in indices:
                # Check if a new message has overridden this loop
                if not self.display_loop and loop:
                    return

                chunk = display_text[i:i+8]
                self.display_left.print(chunk[:4])
                self.display_right.print(chunk[4:])
                await asyncio.sleep(speed)

            if not loop:
                break # Exit after one pass if loop is false
