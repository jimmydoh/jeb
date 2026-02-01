"""
Classic Simon Memory Game Mode.
"""

import asyncio
import random

from utilities import Palette

class Simon:
    """Classic Simon Memory Game Mode."""
    def __init__(self, jeb):
        self.name = "SIMON"
        self.description = "Classic Simon Memory Game"
        self.jeb = jeb
        # Map 0-3 inputs to colors
        # 0: TopLeft, 1: TopRight, 2: BottomLeft, 3: BottomRight
        self.colors = [Palette.RED, Palette.BLUE, Palette.YELLOW, Palette.GREEN]

    async def run(self):
        """Play the classic Simon memory game."""
        sequence = []
        game_over = False
        speed_factor = 0.5

        await self.jeb.display.update_status("SIMON", "FOLLOW THE LIGHTS")
        await self.jeb.matrix.show_icon("SIMON", anim="PULSE", speed=2.0)
        await asyncio.sleep(1.5)
        self.jeb.matrix.clear()

        while not game_over:
            # 1. Add a new random color to the sequence
            sequence.append(random.randint(0, 3))

            # 2. Show the sequence to the user
            for val in sequence:
                # Visual: Light up specific quadrant
                self.jeb.matrix.draw_quadrant(val, self.colors[val])

                # Audio: Play tone (non-blocking for better timing)
                asyncio.create_task(self.jeb.audio.play_sfx(f"v_{val}.wav", voice=1))

                # Hold for duration determined by speed
                await asyncio.sleep(speed_factor)

                # Visual: Turn off
                self.jeb.matrix.draw_quadrant(val, Palette.OFF)

                # Short gap between notes
                await asyncio.sleep(0.15)

            # 3. User Input Phase
            await self.jeb.display.update_status(f"LEVEL {len(sequence)}", "YOUR TURN")

            for target_val in sequence:
                user_input = -1

                # Wait for valid input
                while user_input == -1:
                    # Check all 4 face buttons (Indices 0-3)
                    for i in range(4):
                        if self.jeb.hid.is_pressed(i):
                            user_input = i

                            # Immediate Feedback
                            self.jeb.matrix.draw_quadrant(i, self.colors[i])
                            asyncio.create_task(self.jeb.audio.play_sfx(f"v_{i}.wav", voice=1))

                            # Wait for release (Debounce & Hold Visual)
                            while self.jeb.hid.is_pressed(i):
                                await asyncio.sleep(0.01)

                            # Turn off visual on release
                            self.jeb.matrix.draw_quadrant(i, Palette.OFF)
                            break

                    # Yield to system loop to prevent blocking
                    await asyncio.sleep(0.01)

                # Check correctness
                if user_input != target_val:
                    # FAILURE SEQUENCE
                    self.jeb.matrix.fill(Palette.RED) # Flash whole screen Red
                    # TODO Implement flashing of matrix fill method
                    await self.jeb.audio.play_sfx("fail.wav", voice=1)
                    await self.jeb.display.update_status("GAME OVER", f"SCORE: {len(sequence)-1}")
                    await asyncio.sleep(2)
                    self.jeb.matrix.clear()
                    return # Exit to Main Menu

            # 4. Success for this round
            await self.jeb.audio.play_sfx("win.wav", voice=1, vol=0.6)

            # Increase speed for next round (cap at 0.15s)
            speed_factor = max(0.15, speed_factor * 0.9)

            await asyncio.sleep(0.5)
            self.jeb.matrix.clear()
