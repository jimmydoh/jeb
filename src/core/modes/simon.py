#File: src/core/modes/simon.py
"""Classic Simon Memory Game Mode."""

import asyncio
import random
from adafruit_ticks import ticks_ms, ticks_diff

from utilities import Palette

from .game_mode import GameMode

class Simon(GameMode):
    """Classic Simon Memory Game Mode."""
    def __init__(self, jeb, speed_factor=0.5, timeout_ms=3000):
        super().__init__(jeb, "SIMON", "Classic Simon Memory Game")
        # Map 0-3 inputs to colors
        # 0: TopLeft, 1: TopRight, 2: BottomLeft, 3: BottomRight
        self.colors = [Palette.RED, Palette.BLUE, Palette.YELLOW, Palette.GREEN]
        self.speed_factor = speed_factor  # Initial speed factor
        self.timeout_ms = timeout_ms  # 3 seconds to respond

    async def run(self):
        """Play the classic Simon memory game."""
        sequence = []

        await self.jeb.display.update_status("SIMON", "FOLLOW THE LIGHTS")
        await self.jeb.matrix.show_icon("SIMON", anim="PULSE", speed=2.0)
        await asyncio.sleep(1.5)
        self.jeb.matrix.clear()

        while True:
            # 1. Add a new random color to the sequence
            self.level += 1
            sequence.append(random.randint(0, 3))

            # 2. Show the sequence to the user
            for val in sequence:
                # Visual: Light up specific quadrant
                self.jeb.matrix.draw_quadrant(val, self.colors[val])

                # Audio: Play tone (non-blocking for better timing)
                await self.jeb.audio.play(f"audio/simon/v_{val}.wav", self.jeb.audio.CH_SFX, level=0.7)

                # Hold for duration determined by speed
                await asyncio.sleep(self.speed_factor)

                # Visual: Turn off
                self.jeb.matrix.draw_quadrant(val, Palette.OFF)

                # Short gap between notes
                await asyncio.sleep(0.15)

            # 3. User Input Phase
            await self.jeb.display.update_status(f"LEVEL {self.level}", "YOUR TURN")

            # Start the timer for scoring
            input_phase_start = ticks_ms()
            # Reset the timeout timer (starts now)
            last_interaction_time = ticks_ms()

            for target_val in sequence:
                user_input = -1

                # Wait for valid input
                while user_input == -1:
                    now = ticks_ms()

                    # Check for timeout
                    if ticks_diff(now, last_interaction_time) > self.timeout_ms:
                        await self.jeb.audio.play("audio/simon/tooslow.wav", self.jeb.audio.CH_SFX, level=0.8)
                        await self.jeb.display.update_status("TIMEOUT!", "TOO SLOW")
                        await asyncio.sleep(1.5)
                        return await self.game_over()

                    # Check all 4 face buttons (Indices 0-3)
                    for i in range(4):
                        if self.jeb.hid.is_pressed(i):
                            user_input = i

                            last_interaction_time = ticks_ms()

                            # Immediate Feedback
                            self.jeb.matrix.draw_quadrant(i, self.colors[i])
                            await self.jeb.audio.play(f"audio/simon/v_{i}.wav", self.jeb.audio.CH_SFX, level=0.7)

                            # Wait for release (Debounce & Hold Visual)
                            while self.jeb.hid.is_pressed(i):
                                await asyncio.sleep(0.01)

                            await asyncio.sleep(0.1)
                            # Turn off visual on release
                            self.jeb.matrix.draw_quadrant(i, Palette.OFF)
                            break

                    # Yield to system loop to prevent blocking
                    await asyncio.sleep(0.01)

                # Check correctness
                if user_input != target_val:
                    return await self.game_over()

            # 4. Success for this round, calculate score
            await self.jeb.audio.play("audio/simon/round_win.wav", self.jeb.audio.CH_SFX, level=0.6)
            round_duration = ticks_diff(ticks_ms(), input_phase_start)
            round_score = 10 * self.level
            await self.jeb.display.update_status("ROUND COMPLETE!", f"TIME: {round_duration}ms")
            await asyncio.sleep(1.0)
            par_time = self.level * (self.timeout_ms / 3)  # 1/3 of the timeout per note
            if round_duration < par_time:
                bonus = (par_time - round_duration) // 100
                await self.jeb.display.update_status(f"ROUND SCORE: {round_score}", f"SPEED BONUS: +{int(bonus)}")
                round_score += int(bonus)
            else:
                bonus = (round_duration - par_time) // 250  # Penalty for being slow
                await self.jeb.display.update_status(f"ROUND SCORE: {round_score}", f"SPEED PENALTY: -{int(bonus)}")
                round_score -= int(bonus)
            await asyncio.sleep(1)

            self.score += round_score
            await self.jeb.display.update_status(f"ROUND: {round_score}", "TOTAL: {self.score}")
            await asyncio.sleep(1)

            # Increase speed for next round (cap at 0.15s)
            self.speed_factor = max(0.15, self.speed_factor * 0.9)

            await asyncio.sleep(0.5)
            self.jeb.matrix.clear()
