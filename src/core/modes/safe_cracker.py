"""
Docstring for core.modes.safe_cracker
"""

import asyncio
import random

class SafeCracker:
    """Safe Cracker Game Mode."""
    def __init__(self, jeb):
        self.name = "SAFE CRACKER"
        self.description = "Crack the safe by turning the dial"
        self.jeb = jeb

    async def run(self):
        """Play the Safe Cracker game."""
        combo = [random.randint(10, 90) for _ in range(3)]
        directions = ["RIGHT", "LEFT", "RIGHT"]
        step = 0
        dial_pos = 0
        last_p = self.jeb.hid.encoder.position
        self.jeb.audio.play_sfx("voice/safe_mode.wav", voice=2)

        while step < 3:
            curr_p = self.jeb.hid.encoder.position
            if curr_p != last_p:
                diff = curr_p - last_p
                move = "RIGHT" if diff > 0 else "LEFT"
                if move != directions[step]:
                    self.jeb.audio.play_sfx("sounds/crash.wav")
                    step = 0
                    await self.jeb.display.update_status("RESET", "WRONG DIR")
                    await asyncio.sleep(1)
                dial_pos = (dial_pos + diff) % 100
                last_p = curr_p
                self.jeb.audio.play_sfx("sounds/tick.wav")

            dist = abs(dial_pos - combo[step])
            if dist == 0:
                self.jeb.audio.play_sfx("sounds/thump.wav", vol=1.0)

            self.jeb.display.update_status(f"DIAL: {dial_pos:02d}", f"TARGET: {combo[step]:02d}")

            if not self.jeb.hid.encoder_button.value:
                if dial_pos == combo[step]:
                    step += 1
                    self.jeb.audio.play_sfx("sounds/power.wav")
                    await self.jeb.display.update_status("LOCKED", "NEXT...")
                    await asyncio.sleep(1)
                else:
                    self.jeb.audio.play_sfx("sounds/fail.wav")
                    step = 0
            await asyncio.sleep(0.05)
