#File: src/core/modes/simon.py
"""Classic Simon Memory Game Mode."""

import asyncio
import random
from adafruit_ticks import ticks_ms, ticks_diff

from utilities.palette import Palette
from .game_mode import GameMode

class Simon(GameMode):
    """
    Classic Simon Memory Game Mode.

    https://www.waitingforfriday.com/?p=586

    Sequence length: 1‐5, tone duration 0.42 seconds, pause between tones 0.05 seconds
    Sequence length: 6‐13, tone duration 0.32 seconds, pause between tones 0.05 seconds
    Sequence length: 14‐31, tone duration 0.22 seconds, pause between tones 0.05 seconds
    """

    METADATA = {
        "id": "SIMON",
        "name": "SIMON",
        "icon": "SIMON",
        "settings": [
            {
                "key": "mode",
                "label": "MODE",
                "options": ["CLASSIC", "REVERSE", "BLIND"],
                "default": "CLASSIC"
            },
            {
                "key": "difficulty",
                "label": "DIFF",
                "options": ["EASY","NORMAL", "HARD", "INSANE"],
                "default": "NORMAL"
            }
        ],
        "requires": ["CORE"] # Always Available
    }

    def __init__(self, core):
        super().__init__(core, "SIMON", "Classic Simon Memory Game")
        # Map 0-3 inputs to colors
        # 0: TopLeft, 1: TopRight, 2: BottomLeft, 3: BottomRight
        self.colors = [Palette.GREEN, Palette.RED, Palette.YELLOW, Palette.BLUE]
        self.colors_tones = [392, 330, 262, 196]
        self.losing_tone = 42

        self.timeout_ms = 3000  # Default timeout for user input (can be adjusted by difficulty)
        self.speed_factor = 0.42 # Base duration for tones, will decrease as sequence gets longer (can be adjusted by difficulty)
        self.speed_step = 0.1  # Speed increase per level (subtracts from tone duration, making it faster)
        self.speed_multiplier = 1.0  # Speed modification from difficulty
        self.score_multiplier = 1.0  # Score multiplier based on difficulty

    async def run(self):
        """Play the classic Simon memory game."""

        # --- LOAD SETTINGS ---
        self.variant = self.core.data.get_setting("SIMON", "mode", "CLASSIC")
        self.difficulty = self.core.data.get_setting("SIMON", "difficulty", "NORMAL")

        # Apply Difficulty
        if self.difficulty == "EASY":
            self.speed_factor = 0.57
            self.timeout_ms = 4000
            self.speed_multiplier = 0.95
            self.score_multiplier = 0.75
        elif self.difficulty == "HARD":
            self.speed_factor = 0.37
            self.timeout_ms = 2000
            self.speed_multiplier = 1.05
            self.score_multiplier = 1.5
        elif self.difficulty == "INSANE":
            self.speed_factor = 0.32
            self.timeout_ms = 1000
            self.speed_multiplier = 1.1
            self.score_multiplier = 2.0
        else: # NORMAL
            self.speed_factor = 0.42
            self.timeout_ms = 3000
            self.speed_multiplier = 1.0
            self.score_multiplier = 1.0

        # Apply Mode Description
        sub_text = "FOLLOW THE LIGHTS"
        if self.variant == "REVERSE":
            sub_text = "INPUT IN REVERSE!"
        elif self.variant == "BLIND":
            sub_text = "LISTEN CLOSELY..."

        sequence = []
        self.score = 0
        self.level = 1

        # --- INTRO ---
        await self.core.display.update_status("SIMON", sub_text)
        await self.core.matrix.show_icon("SIMON", anim="PULSE", speed=2.0)

        # Setup button LEDs
        for i in range(4):
            await self.core.leds.solid_led(i, self.colors[i], brightness=0.5, priority=1)

        await asyncio.sleep(1.5)
        self.core.matrix.clear()

        # --- MAIN GAME LOOP ---
        while True:
            # Add a new random color to the sequence
            sequence.append(random.randint(0, 3))

            # Check for level increase
            if len(sequence) > 5:
                self.level = 2
            if len(sequence) > 13:
                self.level = 3
            if len(sequence) > 31:
                self.level = 4

            # Reset the button LEDs to off state
            for i in range(4):
                await self.core.leds.off_led(i)

            # Confirm final speed factor
            final_speed = (self.speed_factor - (self.speed_step * (self.level - 1))) * self.speed_multiplier

            # Show the sequence to the user
            for val in sequence:
                # Visual: Light up specific quadrant and button LED
                if self.variant != "BLIND":
                    await self.core.matrix.draw_quadrant(
                        val,
                        self.colors[val],
                        brightness = 0.8,
                        anim_mode="SOLID",
                        duration=final_speed
                    )
                    await self.core.leds.set_led(
                        val,
                        self.colors[val],
                        brightness=0.8,
                        anim_mode="FLASH",
                        speed=0.1,
                        duration=final_speed
                    )

                # Audio: Play tone (non-blocking for better timing)
                await self.core.buzzer.tone(
                    self.colors_tones[val],
                    duration=final_speed
                )

                # Hold for duration determined by speed
                await asyncio.sleep(final_speed)

                # Visual: Turn off
                if self.variant != "BLIND":
                    await self.core.matrix.draw_quadrant(val, Palette.OFF)
                    await self.core.leds.off_led(val)

                # Short gap between notes
                await asyncio.sleep(0.05)

            # 3. User Input Phase
            await self.core.display.update_status(f"LEVEL {self.level} - LENGTH {len(sequence)}", "YOUR TURN")

            # Setup button LEDs
            for i in range(4):
                await self.core.leds.breathe_led(
                    i,
                    self.colors[i],
                    brightness=0.5,
                    priority=1,
                    speed=1.0 / self.speed_factor
                )

            # Determine target sequence based on mode
            target_sequence = list(reversed(sequence)) if self.variant == "REVERSE" else sequence

            # Start the timer for scoring
            input_phase_start = ticks_ms()
            # Reset the timeout timer (starts now)
            last_interaction_time = ticks_ms()

            for target_val in target_sequence:
                user_input = -1

                # Wait for valid input
                while user_input == -1:
                    now = ticks_ms()

                    # Check for timeout
                    if ticks_diff(now, last_interaction_time) > self.timeout_ms:
                        await self.core.audio.play(
                            "audio/simon/tooslow.wav",
                            self.core.audio.CH_SFX,
                            level=0.8
                        )
                        await self.core.display.update_status("TIMEOUT!", "TOO SLOW")
                        await asyncio.sleep(1.0)
                        return await self.pre_game_over()

                    # Check all 4 face buttons (Indices 0-3)
                    for i in range(4):
                        if self.core.hid.is_pressed(i):
                            user_input = i
                            last_interaction_time = ticks_ms()

                            # Immediate Feedback
                            await self.core.matrix.draw_quadrant(
                                i,
                                self.colors[i],
                                brightness=0.8,
                                anim_mode="SOLID"
                            )
                            await self.core.leds.set_led(
                                i,
                                self.colors[i],
                                brightness=0.8,
                                anim_mode="FLASH",
                                speed=1.0 / self.speed_factor
                            )
                            await self.core.buzzer.tone(
                                self.colors_tones[i]
                            )

                            # Wait for release (Debounce & Hold Visual)
                            while self.core.hid.is_pressed(i):
                                await asyncio.sleep(0.01)

                            # Turn off the matrix quadrant and restore breathing LED
                            await self.core.matrix.draw_quadrant(i, Palette.OFF)
                            await self.core.leds.off_led(i)
                            await self.core.leds.breathe_led(
                                i,
                                self.colors[i],
                                brightness=0.5,
                                priority=1,
                                speed=2.0 * self.speed_factor
                            )
                            await self.core.buzzer.stop() # Stop tone immediately on release
                            break

                    # Yield to system loop to prevent blocking
                    await asyncio.sleep(0.01)

                # Check correctness
                if user_input != target_val:
                    return await self.pre_game_over()

            # The first beep is 0.02 seconds followed by 5 beeps of 0.07 seconds
            # with a 0.02 second gap between tones the light of the last colour
            # of the sequence is flashed on with each beep. The victory tone is
            # played 0.8 seconds after the last colour of the sequence has been
            # pressed and released.
            await self.core.leds.start_rainbow(
                speed=0.08,
                brightness=0.8,
                duration=0.48
            )
            await self.core.matrix.draw_quadrant(
                sequence[-1],
                self.colors[sequence[-1]],
                brightness=0.8,
                anim_mode="FLASH",
                speed=0.08,
                duration=0.48
            )
            await self.core.buzzer.play_sequence([
                (self.colors_tones[sequence[-1]], 0.02),
                ("-", 0.01),
                (self.colors_tones[sequence[-1]], 0.07),
                ("-", 0.01),
                (self.colors_tones[sequence[-1]], 0.07),
                ("-", 0.01),
                (self.colors_tones[sequence[-1]], 0.07),
                ("-", 0.01),
                (self.colors_tones[sequence[-1]], 0.07),
                ("-", 0.01),
                (self.colors_tones[sequence[-1]], 0.07),
            ])

            # Calculate score based on speed (faster is better)
            round_duration = ticks_diff(ticks_ms(), input_phase_start)

            # Base score
            round_score = 10 * self.level * self.score_multiplier

            # Speed Score
            par_time = self.level * (self.timeout_ms / 3)  # 1/3 of the timeout per note
            if round_duration < par_time:
                bonus = (par_time - round_duration) // 100 * self.score_multiplier
                await self.core.display.update_status(
                    f"ROUND SCORE: {round_score}",
                    f"SPEED BONUS: +{int(bonus)}"
                )
                round_score += int(bonus)
            else:
                bonus = (round_duration - par_time) // 250 * self.score_multiplier
                await self.core.display.update_status(
                    f"ROUND SCORE: {round_score}",
                    f"SPEED PENALTY: -{int(bonus)}"
                )
                round_score -= int(bonus)
            await asyncio.sleep(1)

            self.score += round_score
            await self.core.display.update_status(f"ROUND: {round_score}", f"TOTAL: {self.score}")
            await asyncio.sleep(1)

            await self.core.leds.off_led(-1) # Turn off all button LEDs
            await self.core.matrix.clear()   # Clear matrix before next round

    async def pre_game_over(self):
        """Initial custom end game sequence before showing final score and high score."""
        # Fill matrix with flashing red
        await self.core.matrix.fill(
            Palette.RED,
            anim_mode="BLINK",
            duration=2.0,
            speed=0.5
        )
        await self.core.audio.stop_all()
        await self.core.buzzer.stop()
        await self.core.buzzer.play_song("GAME_OVER")
        await asyncio.sleep(2)
        return await self.game_over()
