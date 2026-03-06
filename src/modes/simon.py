#File: src/core/modes/simon.py
"""Classic Simon Memory Game Mode."""

import asyncio
import random
from adafruit_ticks import ticks_ms, ticks_diff

from utilities.palette import Palette
from utilities import tones
from utilities.synth_registry import Patches

from .game_mode import GameMode

class Simon(GameMode):
    """
    Classic Simon Memory Game Mode.

    https://www.waitingforfriday.com/?p=586

    Sequence length: 1‐5, tone duration 0.42 seconds, pause between tones 0.05 seconds
    Sequence length: 6‐13, tone duration 0.32 seconds, pause between tones 0.05 seconds
    Sequence length: 14‐31, tone duration 0.22 seconds, pause between tones 0.05 seconds
    """
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

        self.audio_engine = "MODERN"  # Default audio engine, can be switched to CLASSIC for buzzer-only mode

    async def run_tutorial(self):
        """
        A guided, non-interactive demonstration of Simon.

        The Voiceover Script (audio/tutes/simon_tute.wav)
            [0:00] "Welcome to Simon. Your goal is simple: memorize and repeat."
            [0:04] "First, watch and listen to the sequence of lights."
            [0:08] (Silent for 3 seconds while the game demonstrates a sequence)
            [0:11] "When it's your turn, repeat the exact sequence back by pressing the matching buttons."
            [0:16] (Silent for 5 seconds while the game simulates the player entering the sequence, followed by the success chime)
            [0:21] "The sequences will get longer and faster. Don't take too long, or it's game over. Good luck!"
            [0:26] (End of file)
        """
        await self.core.clean_slate()

        # Load settings to respect the user's audio engine preference
        # (Assuming you added this from our previous discussion)
        self.audio_engine = self.core.data.get_setting("SIMON", "audio_engine", "BUZZER")

        # 1. Start the voiceover track
        tute_audio = asyncio.create_task(
            self.core.audio.play("audio/tutes/simon_tute.wav", bus_id=self.core.audio.CH_VOICE)
        )

        # Helper method to simulate a button press and release perfectly
        async def _demo_press(val, duration, is_player=False):
            # Visuals
            self.core.matrix.draw_wedge(val, self.colors[val], duration=duration)
            self.core.leds.set_led(val, self.colors[val], brightness=0.8, anim_mode="FLASH", speed=0.1, duration=duration)

            # Audio
            self._play_simon_note(self.colors_tones[val], duration=duration)

            await asyncio.sleep(duration)

            # Turn off visuals (Player presses snap off faster)
            self.core.matrix.draw_wedge(val, Palette.OFF)
            if is_player:
                self.core.leds.breathe_led(val, self.colors[val], brightness=0.5, priority=1, speed=2.0)
            else:
                self.core.leds.off_led(val)
            await asyncio.sleep(0.1)

        # [0:00 - 0:04] Intro
        self.core.display.update_status("SIMON TUTORIAL", "MEMORIZE & REPEAT")
        self.core.matrix.show_icon("SIMON", anim_mode="PULSE", speed=2.0)
        await asyncio.sleep(4.0)
        self.core.matrix.clear()

        # [0:04 - 0:08] "First, watch and listen..."
        self.core.display.update_status("SIMON TUTORIAL", "WATCH THE LIGHTS")
        await asyncio.sleep(4.0)

        # [0:08 - 0:11] Demonstrate the Sequence (Green, Red, Yellow)
        # Using 0.42s duration from your level 1 speed settings
        await _demo_press(0, 0.42)
        await asyncio.sleep(0.1)
        await _demo_press(1, 0.42)
        await asyncio.sleep(0.1)
        await _demo_press(2, 0.42)

        # [0:11 - 0:16] "When it's your turn..."
        self.core.display.update_status("SIMON TUTORIAL", "YOUR TURN")
        for i in range(4):
            self.core.leds.breathe_led(i, self.colors[i], brightness=0.5, priority=1, speed=2.0)
        await asyncio.sleep(5.0)

        # [0:16 - 0:19] Simulate the player entering the sequence (faster taps)
        for i in range(4):
            self.core.leds.off_led(i)

        await _demo_press(0, 0.2, is_player=True)
        await asyncio.sleep(0.3)
        await _demo_press(1, 0.2, is_player=True)
        await asyncio.sleep(0.3)
        await _demo_press(2, 0.2, is_player=True)

        # [0:19 - 0:21] The Victory Chime
        self.core.leds.start_rainbow()
        self.core.matrix.draw_wedge(2, self.colors[2], anim_mode="FLASH", speed=0.08, duration=1.0)

        self._play_simon_sequence(
                {
                    "bpm": 120,
                    "sequence": [
                        (self.colors_tones[2], 0.02),
                        ("-", 0.01),
                        (self.colors_tones[2], 0.07),
                        ("-", 0.01),
                        (self.colors_tones[2], 0.07),
                        ("-", 0.01),
                        (self.colors_tones[2], 0.07),
                        ("-", 0.01),
                        (self.colors_tones[2], 0.07),
                    ]
                }
            )

        await asyncio.sleep(1.0)
        self.core.matrix.clear()
        self.core.leds.off_led(-1)

        # [0:21 - 0:26] "The sequences will get longer..."
        self.core.display.update_status("SIMON TUTORIAL", "GOOD LUCK!")

        # Wait for the audio track to finish naturally
        await tute_audio

        # Clean up and return to the menu
        await self.core.clean_slate()
        return "TUTORIAL_COMPLETE"

    def _play_simon_note(self, freq, duration=None):
        """Helper function to play a note with the current audio engine."""
        if self.audio_engine == "MODERN":
            self.core.synth.play_note(freq, patch=Patches.BEEP, duration=duration)
        else:  # CLASSIC
            self.core.buzzer.play_note(freq, duration=duration)

    def _play_simon_sequence(self, sequence):
        """Helper function to play a sequence of notes with the current audio engine."""
        if self.audio_engine == "MODERN":
            self.core.synth.play_sequence(sequence, patch=Patches.BEEP)
        else:  # CLASSIC
            self.core.buzzer.play_sequence(sequence)

    async def run(self):
        """Play the classic Simon memory game."""

        # --- LOAD SETTINGS ---
        self.variant = self.core.data.get_setting("SIMON", "mode", "CLASSIC")
        self.difficulty = self.core.data.get_setting("SIMON", "difficulty", "NORMAL")
        self.audio_engine = self.core.data.get_setting("SIMON", "audio_engine", "MODERN")

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
        self.core.display.update_status("SIMON", sub_text)
        self.core.matrix.show_icon("SIMON", anim_mode="PULSE", speed=2.0)

        # Setup button LEDs
        for i in range(4):
            self.core.leds.solid_led(i, self.colors[i], brightness=0.5, priority=1)

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
                self.core.leds.off_led(i)

            # Confirm final speed factor
            final_speed = (self.speed_factor - (self.speed_step * (self.level - 1))) * self.speed_multiplier

            # Show the sequence to the user
            for val in sequence:
                # Visual: Light up specific quadrant and button LED
                if self.variant != "BLIND":
                    self.core.matrix.draw_wedge(
                        val,
                        self.colors[val],
                        duration=final_speed
                    )
                    self.core.leds.set_led(
                        val,
                        self.colors[val],
                        brightness=0.8,
                        anim_mode="FLASH",
                        speed=0.1,
                        duration=final_speed
                    )

                # Audio: Play tone
                self._play_simon_note(
                    self.colors_tones[val],
                    duration=final_speed
                )

                # Hold for duration determined by speed
                await asyncio.sleep(final_speed)

                # Visual: Turn off
                if self.variant != "BLIND":
                    self.core.matrix.draw_wedge(val, Palette.OFF)
                    self.core.leds.off_led(val)

                # Short gap between notes
                await asyncio.sleep(0.05)

            # 3. User Input Phase
            self.core.display.update_status(f"LEVEL {self.level} - LENGTH {len(sequence)}", "YOUR TURN")

            # Setup button LEDs
            for i in range(4):
                self.core.leds.breathe_led(
                    i,
                    self.colors[i],
                    brightness=0.5,
                    priority=1,
                    speed=10.0 * self.speed_factor
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
                        self.core.audio.play(
                            "audio/simon/tooslow.wav",
                            self.core.audio.CH_SFX,
                            level=0.8
                        )
                        self.core.display.update_status("TIMEOUT!", "TOO SLOW")
                        await asyncio.sleep(1.0)
                        return await self.pre_game_over()

                    # Check all 4 face buttons (Indices 0-3)
                    for i in range(4):
                        if self.core.hid.is_button_pressed(i):
                            user_input = i
                            last_interaction_time = ticks_ms()

                            # Immediate Feedback
                            self.core.matrix.draw_wedge(
                                i,
                                self.colors[i],
                            )
                            self.core.leds.set_led(
                                i,
                                self.colors[i],
                                brightness=0.8,
                                anim_mode="FLASH",
                                speed=1.0 / self.speed_factor
                            )
                            self._play_simon_note(
                                self.colors_tones[i]
                            )

                            # Wait for release (Debounce & Hold Visual)
                            while self.core.hid.is_button_pressed(i):
                                await asyncio.sleep(0.01)

                            # Turn off the matrix quadrant and restore breathing LED
                            self.core.matrix.draw_wedge(i, Palette.OFF)
                            self.core.leds.off_led(i)
                            self.core.leds.breathe_led(
                                i,
                                self.colors[i],
                                brightness=0.5,
                                priority=1,
                                speed=2.0 * self.speed_factor
                            )
                            self.core.buzzer.stop() # Stop tone immediately on release
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
            self.core.leds.start_rainbow()
            self.core.matrix.draw_wedge(
                sequence[-1],
                self.colors[sequence[-1]],
                anim_mode="FLASH",
                speed=0.08,
                duration=0.48
            )

            self._play_simon_sequence(
                {
                    "bpm": 120,
                    "sequence": [
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
                    ]
                }
            )

            # Calculate score based on speed (faster is better)
            round_duration = ticks_diff(ticks_ms(), input_phase_start)

            # Base score
            round_score = 10 * self.level * self.score_multiplier

            # Speed Score
            par_time = self.level * (self.timeout_ms / 3)  # 1/3 of the timeout per note
            if round_duration < par_time:
                bonus = (par_time - round_duration) // 100 * self.score_multiplier
                self.core.display.update_status(
                    f"ROUND SCORE: {round_score}",
                    f"SPEED BONUS: +{int(bonus)}"
                )
                round_score += int(bonus)
            else:
                bonus = (round_duration - par_time) // 250 * self.score_multiplier
                self.core.display.update_status(
                    f"ROUND SCORE: {round_score}",
                    f"SPEED PENALTY: -{int(bonus)}"
                )
                round_score -= int(bonus)
            await asyncio.sleep(1)

            self.score += round_score
            self.core.display.update_status(f"ROUND: {round_score}", f"TOTAL: {self.score}")
            await asyncio.sleep(1)

            self.core.leds.off_led(-1) # Turn off all button LEDs
            self.core.matrix.clear()   # Clear matrix before next round

    async def pre_game_over(self):
        """Initial custom end game sequence before showing final score and high score."""
        # Fill matrix with flashing red
        self.core.matrix.fill(
            Palette.RED,
            anim_mode="BLINK",
            duration=2.0,
            speed=0.5
        )
        self.core.audio.stop_all()
        self.core.buzzer.stop()
        self.core.buzzer.play_sequence(tones.GAME_OVER)
        await asyncio.sleep(2)
        return await self.game_over()
