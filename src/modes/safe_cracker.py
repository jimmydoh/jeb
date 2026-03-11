#File: src/core/modes/safe_cracker.py
"""Safe Cracker Game Mode."""

import asyncio
import random
import math

from utilities.palette import Palette
from utilities import tones
from utilities.synth_registry import Patches

from .game_mode import GameMode

class SafeCracker(GameMode):
    """Safe Cracker Game Mode."""
    def __init__(self, core):
        super().__init__(core, "SAFE CRACKER", "Crack the safe by turning the dial")
        self.audio_engine = self.core.data.get_setting("SAFE", "audio_engine", "SYNTH")

    async def run_tutorial(self):
        """
        The Voiceover Script (audio/tutes/safe_tute.wav)
            [0:00] "Welcome to Safe Cracker. Your goal is to find the three-number combination."
            [0:05] "Turn the dial right, then left, then right again."
            [0:08] "Listen closely. The clicks will rise in pitch as you get closer to the target number."
            [0:14] "When you hit the sweet spot, hold it steady for a moment to lock it in."
            [0:19] "But be careful. If you turn the wrong way, the lock will reset! Good luck."
            [0:24] (End of file)
        """
        await self.core.clean_slate()

        self.game_state = "TUTORIAL"
        target = 25
        dial_pos = 0

        # 1. Start the voiceover track
        self.core.audio.play("audio/tutes/safe_tute.wav", bus_id=self.core.audio.CH_VOICE)

        self.core.display.update_status("SAFE CRACKER", "FIND THE COMBO")
        self._draw_safe_dial(dial_pos, False)
        self.core.matrix.show_frame()
        await asyncio.sleep(5.0)

        # [0:05 - 0:08] "Turn the dial right, then left..."
        self.core.display.update_status("DIAL POS: 00", "TARGET: ??")
        await asyncio.sleep(3.0)

        # [0:08 - 0:14] Puppeteer turning the dial to the target, demonstrating the pitch rise
        self.core.display.update_status("SAFE CRACKER", "LISTEN TO THE PITCH")
        for i in range(1, target + 1):
            dial_pos = i
            self._draw_safe_dial(dial_pos, False)
            self.core.matrix.show_frame()
            self.core.display.update_status(f"DIAL POS: {dial_pos:02d}", "TARGET: ??")

            # Hot/Cold Pitch mechanic demo
            circ_dist = abs(dial_pos - target)
            base_freq = 200
            freq = base_freq + max(0, (15 - circ_dist) * 30)

            if self.audio_engine == "SYNTH":
                self.core.synth.play_note(freq, patch=Patches.CLICK, duration=0.05)
            else:
                self.core.buzzer.play_note(freq, duration=0.05)

            await asyncio.sleep(0.15) # Smooth turning speed

        # [0:14 - 0:19] "When you hit the sweet spot, hold it steady..."
        self.core.display.update_status("SAFE CRACKER", "HOLD STEADY TO LOCK")

        # Flash white to indicate lock
        for _ in range(3):
            self._draw_safe_dial(dial_pos, True)
            self.core.matrix.show_frame()
            await asyncio.sleep(0.1)
            self._draw_safe_dial(dial_pos, False)
            self.core.matrix.show_frame()
            await asyncio.sleep(0.1)

        self.core.buzzer.play_sequence(tones.SAVE_OK)
        await asyncio.sleep(2.0)

        # [0:19 - 0:24] "But be careful. If you turn the wrong way..."
        self.core.display.update_status("WRONG DIRECTION!", "LOCK RESET")
        self.core.matrix.fill(Palette.RED, show=True)
        self.core.audio.play("audio/safe/sfx/crash.wav", self.core.audio.CH_SFX)
        await asyncio.sleep(0.5)
        self.core.matrix.clear()

        await self.core.clean_slate()
        return "TUTORIAL_COMPLETE"

    def _draw_safe_dial(self, value, highlight):
        """Draws a rotary dial position on the 16x16 Matrix."""
        self.core.matrix.clear()

        w = self.core.matrix.width
        h = self.core.matrix.height
        cx = (w - 1) / 2.0
        cy = (h - 1) / 2.0
        radius = (min(w, h) - 1) / 2.0

        # 1. Draw Hub (Dim Center 2x2 pixels)
        hub_color = (20, 20, 20)
        for x in [w // 2 - 1, w // 2]:
            for y in [h // 2 - 1, h // 2]:
                self.core.matrix.draw_pixel(x, y, hub_color, show=False)

        # 2. Calculate Pointer Position (Map 0-100 to 0-2PI)
        angle = (value / 100.0) * 2 * math.pi
        px = int(cx + radius * math.sin(angle))
        py = int(cy - radius * math.cos(angle))

        px = max(0, min(w - 1, px))
        py = max(0, min(h - 1, py))

        # 3. Draw Pointer
        pointer_color = Palette.WHITE if highlight else Palette.CYAN
        self.core.matrix.draw_pixel(
            px,
            py,
            pointer_color,
            show=False
        )

    async def run(self):
        """Play the Safe Cracker game."""
        combo = [random.randint(1, 99) for _ in range(3)]
        directions = ["RIGHT", "LEFT", "RIGHT"]

        self.step = 0
        self.core.hid.reset_encoder(0)
        last_p = self.core.hid.encoder_position()

        self.core.display.update_status("SAFE MODE", "LISTEN CLOSELY")
        self.core.audio.play("audio/safe/voice/welcome.wav", self.core.audio.CH_VOICE, wait=True)
        await asyncio.sleep(0.5)

        while self.step < 3:
            curr_p = self.core.hid.encoder_position()
            target = combo[self.step]
            dial_pos = curr_p % 100

            # Handle dial movement
            if curr_p != last_p:
                diff = curr_p - last_p
                move = "RIGHT" if diff > 0 else "LEFT"

                # Check if the move is correct for the current step
                if move != directions[self.step]:
                    self.core.audio.play("audio/safe/sfx/crash.wav", self.core.audio.CH_SFX)
                    self.core.matrix.fill(Palette.RED, show=True)
                    self.core.display.update_status("RESET", "WRONG DIRECTION")

                    self.step = 0
                    await asyncio.sleep(1.0)
                    self.core.hid.reset_encoder(0)
                    last_p = 0
                    continue

                # Hot/Cold Pitch logic (Rising pitch as you get closer)
                raw_dist = abs(dial_pos - target)
                circ_dist = min(raw_dist, 100 - raw_dist)

                base_freq = 200
                # Starts ramping up pitch when within 15 ticks
                freq = base_freq + max(0, (15 - circ_dist) * 30)

                if self.audio_engine == "SYNTH":
                    self.core.synth.play_note(freq, patch=Patches.CLICK, duration=0.05)
                else:
                    self.core.buzzer.play_note(freq, duration=0.05)

                last_p = curr_p

            # Render matrix and display
            self._draw_safe_dial(dial_pos, False)
            self.core.matrix.show_frame()

            status_text = f"TARGET: {target:02d}" if self.core.is_debugging else "TARGET: ??"
            self.core.display.update_status(f"DIAL POS: {dial_pos:02d}", status_text)

            # Check Target
            if dial_pos == target:
                # Wait for them to hold steady
                await asyncio.sleep(0.5)

                # If they haven't moved the encoder since pausing on the target
                if self.core.hid.encoder_position() == curr_p:
                    self._draw_safe_dial(dial_pos, True)
                    self.core.matrix.show_frame()
                    self.core.buzzer.play_sequence(tones.SAVE_OK)

                    self.step += 1

                    if self.step < 3:
                        self.core.display.update_status(f"LOCKED: {target:02d}", f"TURN {directions[self.step]}")
                        await asyncio.sleep(1.0)
                        # Reset encoder anchor for the next direction
                        last_p = curr_p

            await asyncio.sleep(0.01) # Yield to event loop

        # Safe Cracked!
        return await self.victory()
