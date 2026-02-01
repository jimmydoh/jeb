""""""

import asyncio
import random

class Simon:
    """Classic Simon Memory Game Mode."""
    def __init__(self, jeb):
        self.name = "SIMON"
        self.description = "Classic Simon Memory Game"
        self.jeb = jeb

    async def run(self):
        """Play the classic Simon memory game."""
        sequence = []
        game_over = False
        speed_factor = 0.5
        await self.jeb.display.update_status("SIMON", "FOLLOW THE LIGHTS")
        await asyncio.sleep(1.5)
        while not game_over:
            # 1. Add a new random color to the sequence
            sequence.append(random.randint(0, 3))
            # 2. Show the sequence to the user
            for val in sequence:
                # TODO Replace neobar with matrix
                self.jeb.audio.play_sfx(f"v_{val}.wav", voice=1) # Match sound to color
                await asyncio.sleep(speed_factor)
                # TODO Replace neobar with matrix
                await asyncio.sleep(0.1)
            # 3. User Input Phase
            for i, seq in enumerate(sequence):
                user_input = -1
                while user_input == -1:
                    # TODO Replace access to _btns with correct class calls
                    for j, btn in enumerate(self.jeb.hid._btns):
                        if not btn.value: # Button Pressed (GND)
                            user_input = j
                            # TODO Replace neobar with matrix
                            self.jeb.audio.play_sfx("click.wav")
                            # Wait for release to prevent double-triggers
                            while not btn.value: await asyncio.sleep(0.01)
                            # TODO Replace neobar with matrix
                            break
                    await asyncio.sleep(0.01)
                # Check if input was correct
                if user_input != seq:
                    self.jeb.audio.play_sfx("fail.wav", voice=1)
                    await self.jeb.display.update_status("GAME OVER", f"SCORE: {len(sequence)-1}")
                    await asyncio.sleep(2)
                    return # Return to Main Menu
            # 4. Success for this round
            self.jeb.audio.play_sfx("win.wav", voice=1, vol=0.5)
            speed_factor = max(0.15, speed_factor - 0.05) # Speed up the game
            await asyncio.sleep(0.8)
