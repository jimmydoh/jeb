"""Sorting Algorithm Visualizer – Zero Player Mode.

Visualizes various sorting algorithms on the 16x16 LED matrix. The 16 columns
represent array values from 1 to 16. As the algorithms compare and swap values,
the matrix highlights the active columns and the synthesizer plays a tone
mapped to the column's height.

A scrambled array sounds discordant and chaotic. Once the sort completes, a
final sweep is performed, playing a perfect ascending musical scale.

Controls:
    Encoder turn       : cycle sorting algorithms
    Button 1 (tap)     : trigger scramble and sort sequence
    Encoder long press : return to Zero Player menu
"""

import asyncio
import random

from adafruit_ticks import ticks_ms, ticks_diff

from utilities import tones
from utilities.palette import Palette
from utilities.logger import JEBLogger
from .base import BaseMode

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# 16-note scale (C Major spanning two octaves)
_SCALE_FREQS = [
    130.81, 146.83, 164.81, 174.61, 196.00, 220.00, 246.94, # C3 to B3
    261.63, 293.66, 329.63, 349.23, 392.00, 440.00, 493.88, # C4 to B4
    523.25, 587.33                                          # C5 to D5
]

# (Display Name, Base Delay between steps)
_ALGOS = [
    ("BUBBLE SORT", 0.015),
    ("COCKTAIL SHAKER", 0.015),
    ("INSERTION SORT", 0.025),
    ("SELECTION SORT", 0.035),
    ("QUICK SORT", 0.050),
    ("BITONIC SORT", 0.040),
    ("PANCAKE SORT", 0.060),
    ("GRAVITY SORT", 0.080),
    ("BOGO SORT", 0.010)
]

class SortingVisualizerMode(BaseMode):
    """Sorting Algorithm Visualizer."""

    def __init__(self, core):
        super().__init__(core, "SORTING VIS", "Algorithm Visualizer")
        self.array = list(range(1, 17))

        self.state = "IDLE" # IDLE, SCRAMBLING, PRE_SWEEP, SORTING, POST_SWEEP
        self.algo_idx = 0

        self._sort_task = None
        self._exit_flag = False

    # ------------------------------------------------------------------
    # Rendering & Audio Helpers
    # ------------------------------------------------------------------

    def _render(self, comp=None, swp=None, sweep_idx=None):
        """Draw the array to the matrix."""
        self.core.matrix.clear()
        comp = comp or []
        swp = swp or []

        for x in range(16):
            val = self.array[x]

            # Determine column color
            if x in swp:
                color = Palette.RED
            elif x in comp:
                color = Palette.YELLOW
            elif sweep_idx is not None and x == sweep_idx:
                color = Palette.WHITE
            elif self.state == "POST_SWEEP":
                # Turn green sequentially as the sweep passes
                color = Palette.GREEN if (sweep_idx is None or x <= sweep_idx) else Palette.CYAN
            elif self.state == "IDLE":
                # Idle state displays the perfect sorted green gradient
                color = Palette.GREEN
            else:
                color = Palette.CYAN

            # Draw the column from the bottom (y=15) upwards
            for y in range(16 - val, 16):
                self.core.matrix.draw_pixel(x, y, color)

        self.core.matrix.show_frame()

    def _play_tone(self, val, duration=0.05):
        """Play a musical note mapped to the column height (1-16)."""
        freq = _SCALE_FREQS[val - 1]
        # Use a short, crisp note. Default synth patch works well for this.
        self.core.synth.play_note(freq, duration=duration)

    async def _visualize(self, comp=None, swp=None, sweep_idx=None, tone_val=None, delay=0.05):
        """Update display, play sound, and await the delay. Checks for exit."""
        if self._exit_flag:
            raise asyncio.CancelledError()

        self._render(comp, swp, sweep_idx)
        if tone_val is not None:
            self._play_tone(tone_val, duration=max(0.02, delay))
        await asyncio.sleep(delay)

    # ------------------------------------------------------------------
    # Sorting Algorithms
    # ------------------------------------------------------------------

    async def _sort_bubble(self, delay):
        n = len(self.array)
        for i in range(n):
            for j in range(0, n - i - 1):
                await self._visualize(comp=[j, j+1], tone_val=self.array[j], delay=delay)
                if self.array[j] > self.array[j+1]:
                    self.array[j], self.array[j+1] = self.array[j+1], self.array[j]
                    await self._visualize(swp=[j, j+1], tone_val=self.array[j+1], delay=delay)

    async def _sort_insertion(self, delay):
        for i in range(1, len(self.array)):
            key = self.array[i]
            j = i - 1
            await self._visualize(comp=[i], tone_val=key, delay=delay)
            while j >= 0 and key < self.array[j]:
                await self._visualize(comp=[j, j+1], tone_val=self.array[j], delay=delay)
                self.array[j + 1] = self.array[j]
                j -= 1
                await self._visualize(swp=[j+1], tone_val=self.array[j+1], delay=delay)
            self.array[j + 1] = key
            await self._visualize(swp=[j+1], tone_val=key, delay=delay)

    async def _sort_selection(self, delay):
        n = len(self.array)
        for i in range(n):
            min_idx = i
            for j in range(i + 1, n):
                await self._visualize(comp=[min_idx, j], tone_val=self.array[j], delay=delay)
                if self.array[j] < self.array[min_idx]:
                    min_idx = j
            if min_idx != i:
                self.array[i], self.array[min_idx] = self.array[min_idx], self.array[i]
                await self._visualize(swp=[i, min_idx], tone_val=self.array[i], delay=delay)

    async def _sort_quick(self, low, high, delay):
        if low < high:
            pi = await self._partition(low, high, delay)
            await self._sort_quick(low, pi - 1, delay)
            await self._sort_quick(pi + 1, high, delay)

    async def _partition(self, low, high, delay):
        pivot = self.array[high]
        i = low - 1
        for j in range(low, high):
            await self._visualize(comp=[j, high], tone_val=self.array[j], delay=delay)
            if self.array[j] < pivot:
                i += 1
                self.array[i], self.array[j] = self.array[j], self.array[i]
                await self._visualize(swp=[i, j], tone_val=self.array[i], delay=delay)
        self.array[i + 1], self.array[high] = self.array[high], self.array[i + 1]
        await self._visualize(swp=[i+1, high], tone_val=self.array[i+1], delay=delay)
        return i + 1

    async def _sort_cocktail(self, delay):
        """Bidirectional bubble sort."""
        n = len(self.array)
        swapped = True
        start = 0
        end = n - 1

        while swapped:
            swapped = False
            # Forward pass
            for i in range(start, end):
                await self._visualize(comp=[i, i+1], tone_val=self.array[i], delay=delay)
                if self.array[i] > self.array[i+1]:
                    self.array[i], self.array[i+1] = self.array[i+1], self.array[i]
                    await self._visualize(swp=[i, i+1], tone_val=self.array[i+1], delay=delay)
                    swapped = True

            if not swapped:
                break

            swapped = False
            end -= 1
            # Backward pass
            for i in range(end - 1, start - 1, -1):
                await self._visualize(comp=[i, i+1], tone_val=self.array[i], delay=delay)
                if self.array[i] > self.array[i+1]:
                    self.array[i], self.array[i+1] = self.array[i+1], self.array[i]
                    await self._visualize(swp=[i, i+1], tone_val=self.array[i+1], delay=delay)
                    swapped = True
            start += 1

    async def _sort_bitonic(self, delay):
        """Parallel-optimized network sort. Creates alien geometric sweeping patterns.
        Only works because our array size (16) is a perfect power of 2!"""
        n = len(self.array)
        k = 2
        while k <= n:
            j = k // 2
            while j > 0:
                for i in range(n):
                    l = i ^ j
                    if l > i:
                        # Determine sort direction based on block index
                        direction = (i & k) == 0
                        await self._visualize(comp=[i, l], tone_val=self.array[i], delay=delay)

                        # Swap if out of order for this direction
                        if (self.array[i] > self.array[l]) == direction:
                            self.array[i], self.array[l] = self.array[l], self.array[i]
                            await self._visualize(swp=[i, l], tone_val=self.array[l], delay=delay)
                j //= 2
            k *= 2

    async def _sort_pancake(self, delay):
        """Sorts by flipping chunks of the array with a virtual spatula."""
        curr_size = len(self.array)

        while curr_size > 1:
            # Find index of max element in the unsorted portion
            max_idx = 0
            for i in range(curr_size):
                await self._visualize(comp=[i, max_idx], tone_val=self.array[i], delay=delay)
                if self.array[i] > self.array[max_idx]:
                    max_idx = i

            # If max element is not already at the end, we need to flip
            if max_idx != curr_size - 1:
                # 1. Flip max element to the very top (index 0) if it isn't there
                if max_idx != 0:
                    flip_range = list(range(max_idx + 1))
                    await self._visualize(swp=flip_range, tone_val=self.array[max_idx], delay=delay*2)
                    self.array[:max_idx+1] = reversed(self.array[:max_idx+1])
                    await self._visualize(swp=flip_range, tone_val=self.array[0], delay=delay)

                # 2. Flip the whole unsorted section to put max at the bottom
                flip_range = list(range(curr_size))
                await self._visualize(swp=flip_range, tone_val=self.array[0], delay=delay*2)
                self.array[:curr_size] = reversed(self.array[:curr_size])
                await self._visualize(swp=flip_range, tone_val=self.array[curr_size-1], delay=delay)

            curr_size -= 1

    async def _sort_gravity(self, delay):
        """Bead sort. Visually rotates the matrix 90 degrees and animates the pixels falling.
        As pixels hit their resting place in the stack, they flash and play a tone."""

        # 1. Convert the 1D array into a 2D boolean grid rotated 90 degrees clockwise.
        # Original vertical columns become horizontal rows extending from the left.
        grid = [[False] * 16 for _ in range(16)]
        for y in range(16):
            for x in range(self.array[y]):
                grid[y][x] = True

        # Pre-calculate how many beads belong in each vertical drop column
        # so we know when a falling bead has reached the top of its stack.
        target_counts = [0] * 16
        for x in range(16):
            target_counts[x] = sum(1 for val in self.array if val > x)

        current_settled = [0] * 16

        # 2. Draw the initial rotated state and hold for half a second
        self.core.matrix.clear()
        for y in range(16):
            for x in range(16):
                if grid[y][x]:
                    self.core.matrix.draw_pixel(x, y, Palette.CYAN)
        self.core.matrix.show_frame()
        await asyncio.sleep(0.5)

        # 3. Animate gravity pulling the beads down
        moved = True
        while moved:
            if self._exit_flag:
                raise asyncio.CancelledError()

            moved = False
            settled_this_frame = []

            # Process bottom-up so falling beads don't block each other in the same frame
            for y in range(14, -1, -1):
                for x in range(16):
                    if grid[y][x] and not grid[y+1][x]:
                        grid[y][x] = False
                        grid[y+1][x] = True
                        moved = True

                        # Check if this bead has hit the top of the settled pile
                        resting_y = 15 - current_settled[x]
                        if (y + 1) == resting_y:
                            current_settled[x] += 1
                            settled_this_frame.append(x)

            if moved:
                self.core.matrix.clear()
                for py in range(16):
                    for px in range(16):
                        if grid[py][px]:
                            # Flash white if it just landed this frame
                            if px in settled_this_frame and py == 15 - (current_settled[px] - 1):
                                self.core.matrix.draw_pixel(px, py, Palette.WHITE)
                            else:
                                self.core.matrix.draw_pixel(px, py, Palette.CYAN)
                self.core.matrix.show_frame()

                if settled_this_frame:
                    # Play a bright tone mapped to the highest column that settled
                    highest_x = max(settled_this_frame)
                    self._play_tone(highest_x + 1, duration=max(0.02, delay))
                else:
                    # Play a low, dull thud for beads in freefall
                    self.core.synth.play_note(60, duration=0.01)

                await asyncio.sleep(delay)

        # 4. Hold the settled pile for a moment so the player can see the sorted shape
        await asyncio.sleep(0.5)

        # 5. Translate the settled 2D grid back into the 1D sorted array.
        # In the rotated view, the horizontal rows (y) are now our array elements.
        for y in range(16):
            self.array[y] = sum(1 for x in range(16) if grid[y][x])

        # A quick final render ensures the UI state perfectly transitions back to standard vertical
        self._render()

    async def _sort_bogo(self, delay):
        """The ultimate joke algorithm. O(n!) time complexity.
        It just randomly shuffles until it miraculously lands in order."""
        n = len(self.array)
        while True:
            # Check if sorted (the manic fast sweep)
            is_sorted = True
            for i in range(n - 1):
                await self._visualize(comp=[i, i+1], tone_val=self.array[i], delay=delay)
                if self.array[i] > self.array[i+1]:
                    is_sorted = False
                    break

            if is_sorted:
                break

            # If not sorted, randomly scramble everything and play a discordant note
            random.shuffle(self.array)
            await self._visualize(swp=list(range(n)), tone_val=random.randint(1, 16), delay=delay*4)

    # ------------------------------------------------------------------
    # Core Sequence Runner
    # ------------------------------------------------------------------

    async def _run_sequence(self):
        """Manages the full Scramble -> Pre-Sweep -> Sort -> Post-Sweep flow."""
        try:
            # 1. Scramble
            self.state = "SCRAMBLING"
            self.core.display.update_status("SCRAMBLING", "")
            random.shuffle(self.array)
            for i in range(16):
                await self._visualize(swp=[i], delay=0.03)

            # 2. Discordant Pre-Sweep
            self.state = "PRE_SWEEP"
            self.core.display.update_status("PRE-SWEEP", "DISCORDANT")
            for i in range(16):
                await self._visualize(sweep_idx=i, tone_val=self.array[i], delay=0.1)
            await asyncio.sleep(0.5)

            # 3. Sort
            self.state = "SORTING"
            algo_name, delay = _ALGOS[self.algo_idx]
            self.core.display.update_status("SORTING", algo_name)

            if self.algo_idx == 0:
                await self._sort_bubble(delay)
            elif self.algo_idx == 1:
                await self._sort_cocktail(delay)
            elif self.algo_idx == 2:
                await self._sort_insertion(delay)
            elif self.algo_idx == 3:
                await self._sort_selection(delay)
            elif self.algo_idx == 4:
                await self._sort_quick(0, 15, delay)
            elif self.algo_idx == 5:
                await self._sort_bitonic(delay)
            elif self.algo_idx == 6:
                await self._sort_pancake(delay)
            elif self.algo_idx == 7:
                await self._sort_gravity(delay)
            elif self.algo_idx == 8:
                await self._sort_bogo(delay)

            # 4. Harmonic Post-Sweep
            self.state = "POST_SWEEP"
            self.core.display.update_status("SORTED!", "PERFECT SCALE")
            await asyncio.sleep(0.5)
            for i in range(16):
                await self._visualize(sweep_idx=i, tone_val=self.array[i], delay=0.1)

            # Done
            self.state = "IDLE"
            self.core.display.update_status("IDLE", "READY")
            self._render()

        except asyncio.CancelledError:
            # Task was cancelled cleanly (e.g. user exited mode)
            pass
        finally:
            self._sort_task = None

    # ------------------------------------------------------------------
    # Tutorial
    # ------------------------------------------------------------------

    async def run_tutorial(self):
        """
        Guided demonstration of the Sorting Visualizer.

        The Voiceover Script (audio/tutes/sort_tute.wav) ~48 seconds:
            [0:00] "Welcome to the Sorting Algorithm Visualizer."
            [0:04] "This exhibit demonstrates how different mathematical algorithms organize data."
            [0:11] "Each column's height is mapped to a specific musical note. Watch as we scramble the array."
            [0:19] "When unsorted, the data sounds completely discordant."
            [0:24] "Let's watch Bubble Sort in action. It repeatedly steps through the list, swapping adjacent elements if they are in the wrong order."
            [0:36] "Once perfectly sorted, the data forms a harmonious ascending scale."
            [0:42] "Turn the dial to select an algorithm, and press button one to begin."
            [0:48] (End of file)
        """
        await self.core.clean_slate()
        self.game_state = "TUTORIAL"

        self.core.audio.play("audio/tutes/sort_tute.wav", bus_id=self.core.audio.CH_VOICE)

        self.array = list(range(1, 17))
        self.algo_idx = 0 # Bubble Sort
        self.state = "IDLE"
        self._exit_flag = False

        self.core.display.use_standard_layout()
        self.core.display.update_header("SORTING VIS")
        self.core.display.update_status("TUTORIAL", "STANDBY")
        self.core.display.update_footer("B1:Sort  ENC:Algo")

        self._render()

        try:
            # [0:00 - 0:11] Intro
            self.core.display.update_status("SORTING VIS", "DATA ORGANIZATION")
            await asyncio.sleep(11.0)

            # [0:11 - 0:19] Scramble
            self.state = "SCRAMBLING"
            self.core.display.update_status("SCRAMBLE", "SHUFFLING DATA")
            random.shuffle(self.array)
            for i in range(16):
                await self._visualize(swp=[i], delay=0.04)
            await asyncio.sleep(1.0)

            # [0:19 - 0:24] Pre-Sweep (Discordant)
            self.state = "PRE_SWEEP"
            self.core.display.update_status("PRE-SWEEP", "DISCORDANT")
            for i in range(16):
                await self._visualize(sweep_idx=i, tone_val=self.array[i], delay=0.1)
            await asyncio.sleep(1.4)

            # [0:24 - 0:36] Bubble Sort Active
            self.state = "SORTING"
            self.core.display.update_status("BUBBLE SORT", "COMPARE & SWAP")
            await self._sort_bubble(delay=0.015)
            await asyncio.sleep(0.5)

            # [0:36 - 0:42] Post-Sweep (Harmonic)
            self.state = "POST_SWEEP"
            self.core.display.update_status("SORTED!", "ASCENDING SCALE")
            for i in range(16):
                await self._visualize(sweep_idx=i, tone_val=self.array[i], delay=0.1)
            await asyncio.sleep(0.5)

            # [0:42 - 0:48] UI Instructions
            self.state = "IDLE"
            self.core.display.update_status("MAIN DIAL", "CHANGE ALGORITHM")
            for _ in range(3):
                await asyncio.sleep(1.0)
                self.algo_idx = (self.algo_idx + 1) % len(_ALGOS)
                self.core.display.update_status("MAIN DIAL", _ALGOS[self.algo_idx][0])
                self.core.buzzer.play_sequence(tones.UI_TICK)
            await asyncio.sleep(1.0)

            if hasattr(self.core.audio, 'wait_for_bus'):
                await self.core.audio.wait_for_bus(self.core.audio.CH_VOICE)
            else:
                await asyncio.sleep(2.0)

            # --- SEAMLESS HANDOFF TO MAIN LOOP ---
            self.core.display.update_status("TUTORIAL COMPLETE", "HANDING OVER CONTROL")
            await asyncio.sleep(1.5)

            self.core.hid.flush()
            self.game_state = "RUNNING"
            return await self.run()

        except asyncio.CancelledError:
            pass
        finally:
            self._exit_flag = True
            await self.core.clean_slate()

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    async def run(self):
        """Main visualizer loop."""
        JEBLogger.info("SORT", "[RUN] Sorting Visualizer starting")

        self._exit_flag = False

        if self.state != "IDLE":
            self.array = list(range(1, 17))
            self.algo_idx = 0
            self.state = "IDLE"

        self.core.display.use_standard_layout()
        self.core.display.update_header("SORTING VIS")
        self.core.display.update_status("IDLE", _ALGOS[self.algo_idx][0])
        self.core.display.update_footer("B1:Sort  ENC:Algo")

        self.core.hid.flush()
        self.core.hid.reset_encoder(self.algo_idx)
        last_enc = self.core.hid.encoder_position()

        self._render()

        try:
            while True:
                # 1. Handle hardware exit
                if self.core.hid.is_encoder_button_pressed(long=True, duration=2000):
                    JEBLogger.info("SORT", "[EXIT] Returning to Zero Player menu")
                    self._exit_flag = True
                    if self._sort_task:
                        self._sort_task.cancel()
                    return "SUCCESS"

                # 2. UI interaction is only allowed when IDLE
                if self.state == "IDLE":

                    # Ensure static array is drawn while waiting
                    #self._render()

                    # --- Encoder: cycle algorithm ---
                    enc = self.core.hid.encoder_position()
                    diff = enc - last_enc
                    if diff != 0:
                        delta = 1 if diff > 0 else -1
                        new_idx = (self.algo_idx + delta) % len(_ALGOS)
                        self.algo_idx = new_idx
                        self.core.hid.reset_encoder(self.algo_idx)
                        last_enc = self.algo_idx

                        self.core.display.update_status("IDLE", _ALGOS[self.algo_idx][0])
                        self.core.buzzer.play_sequence(tones.UI_TICK)

                    # --- Button 1: trigger sort sequence ---
                    if self.core.hid.is_button_pressed(0, action="tap"):
                        self.core.buzzer.play_sequence(tones.UI_CONFIRM)
                        self._sort_task = asyncio.create_task(self._run_sequence())

                await asyncio.sleep(0.01)

        finally:
            self._exit_flag = True
            if self._sort_task:
                self._sort_task.cancel()
