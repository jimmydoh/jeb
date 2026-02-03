#File: src/core/modes/safe_cracker.py
"""Safe Cracker Game Mode."""

import asyncio
import random
import math

from utilities import Palette

from .game_mode import GameMode

class SafeCracker(GameMode):
    """Safe Cracker Game Mode."""
    def __init__(self, jeb):
        super().__init__(jeb, "SAFE CRACKER", "Crack the safe by turning the dial")

    def _draw_safe_dial(self, value, highlight):
        """Draws a rotary dial position on the 8x8 Matrix."""
        # Clear buffer
        self.jeb.matrix.pixels.fill((0, 0, 0))

        # 1. Draw Hub (Dim Center)
        # Center indices are (3,3), (3,4), (4,3), (4,4)
        hub_color = (20, 20, 20)
        for x in [3, 4]:
            for y in [3, 4]:
                self.jeb.matrix.draw_pixel(x, y, hub_color)

        # 2. Calculate Pointer Position
        # Map 0-100 to 0-2PI (Radians)
        # 0 is usually Top (12 o'clock).
        # In Grid: Top is Y=0.
        # Angle 0 -> Sin(0)=0, Cos(0)=1. Y = Cy - R*Cos(0) = Cy - R. Correct.
        angle = (value / 100.0) * 2 * math.pi
        px = int(3.5 + 3.5 * math.sin(angle))
        py = int(3.5 - 3.5 * math.cos(angle))

        # Clamp to 0-7 just in case
        px = max(0, min(7, px))
        py = max(0, min(7, py))

        # 3. Draw Pointer
        pointer_color = (Palette.WHITE) if highlight else (Palette.CYAN) # White if aligned, Cyan otherwise
        self.jeb.matrix.draw_pixel(px, py, pointer_color, show=False, anim_mode="BLINK" if highlight else None, speed=2.0)

        # Push to display
        self.jeb.matrix.pixels.show()

    async def run(self):
        """Play the Safe Cracker game."""
        combo = [random.randint(1, 99) for _ in range(3)]
        directions = ["RIGHT", "LEFT", "RIGHT"]

        self.step = 0
        dial_pos = 0

        self.jeb.hid.reset_encoder(0)
        last_p = 0

        await self.jeb.display.update_status("SAFE MODE", "LISTEN CLOSELY")
        self.jeb.audio.play("audio/safe/voice/welcome.wav",
                            self.jeb.audio.CH_VOICE,
                            vol=1.0,
                            wait=True)
        await asyncio.sleep(0.5)

        while self.step < 3:
            curr_p = self.jeb.hid.encoder_pos
            target = combo[self.step]

            # Handle dial movement
            if curr_p != last_p:
                diff = curr_p - last_p

                # Determine direction and check correctness
                move = "RIGHT" if diff > 0 else "LEFT"

                # Check if the move is correct for the current step
                if move != directions[self.step]:
                    self.jeb.audio.play("audio/safe/sfx/crash.wav",
                                        self.jeb.audio.CH_SFX,
                                        level=1.0,
                                        interrupt=True)
                    self.jeb.matrix.fill((255, 0, 0), show=True, anim_mode="BLINK", speed=2.0) # Red Flash
                    await self.jeb.display.update_status("RESET", "WRONG DIRECTION")

                    self.step = 0
                    await asyncio.sleep(0.5)

                # Check for overshoot
                dist_to_target = 0
                if move == "RIGHT":
                    if target >= dial_pos:
                        dist_to_target = target - dial_pos
                    else:
                        dist_to_target = (100 - dial_pos) + target
                else: # LEFT
                    if target <= dial_pos:
                        dist_to_target = dial_pos - target
                    else:
                        dist_to_target = dial_pos + (100 - target)

                # If the movement overshoots the target, we passed it, reset
                if abs(diff) > dist_to_target:
                    self.jeb.audio.play("audio/safe/sfx/crash.wav",
                                        self.jeb.audio.CH_SFX,
                                        level=1.0,
                                        interrupt=True)
                    self.jeb.matrix.fill((Palette.ORANGE), show=True, anim_mode="BLINK", speed=2.0) # Orange Flash
                    await self.jeb.display.update_status("OVERSHOOT!", "TRY AGAIN")
                    self.step = 0
                    await asyncio.sleep(0.5)
                    last_p = curr_p
                    continue

                # Update dial position
                dial_pos = (dial_pos + diff) % 100
                last_p = curr_p

                # Play tick with dynamic volume
                # Calculate shortest circular distance
                raw_dist = abs(dial_pos - target)
                circ_dist = min(raw_dist, 100 - raw_dist)

                vol = 0.2
                if circ_dist < 15:
                    vol += 0.8 * (15 - circ_dist) / 15

                self.jeb.audio.play("audio/safe/sfx/tick.wav",
                                    self.jeb.audio.CH_SFX,
                                    level=vol,
                                    interrupt=True)

            # Render matrix and display without target highlight
            self._draw_safe_dial(dial_pos, False)
            status_text = f"TARGET: {target:02d}" if self.jeb.is_debugging else "TARGET: ??"
            self.jeb.display.update_status(f"DIAL POS: {dial_pos:02d}", status_text)

            # Check Target
            dist = abs(dial_pos - target)
            is_on_target = dist == 0

            if is_on_target:
                self.jeb.matrix.draw_pixel(3, 3, (255, 255, 255), show=True, anim_mode="BLINK", speed=3.0)
                self.jeb.audio.play("audio/safe/sfx/thump.wav",
                                    self.jeb.audio.CH_SFX,
                                    level=1.0,
                                    interrupt=True)

                # Wait for them to hold steady
                await asyncio.sleep(0.5)
                if (self.jeb.hid.encoder_pos == curr_p): # Still there
                    self._draw_safe_dial(dial_pos, True)
                    self.step += 1
                    await asyncio.sleep(0.1)

            await asyncio.sleep(0.05)

        # Safe Cracked!
        return await self.victory()
