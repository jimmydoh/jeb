# File: src/modes/emoji_reveal.py
"""Emoji Reveal – Pixel-by-Pixel Fade Trivia Game Mode.

Players identify an icon on the LED matrix as it slowly fades in pixel-by-pixel.
Four multiple-choice options are shown on the OLED display.  Faster correct
guesses award more points.

Buttons 0-3 (Q/W/E/R on the physical panel) map to choices A/B/C/D.
"""

import asyncio
import random

from adafruit_ticks import ticks_ms, ticks_diff

from utilities import matrix_animations
from utilities.icons import Icons
from utilities.palette import Palette
from .game_mode import GameMode

class EmojiRevealMode(GameMode):
    """Trivia game mode: identify an icon as it reveals itself pixel by pixel.

    Each round a random icon is chosen and its pixels fade in over a set
    duration.  The player scores more points the earlier they submit a correct
    answer.  An incorrect guess ends the game immediately.
    """

    # ------------------------------------------------------------------
    # Question bank: each entry defines an icon key and its display name.
    # The four multiple-choice labels are picked automatically – the
    # correct answer plus three distractors drawn from the same pool.
    # ------------------------------------------------------------------
    QUESTION_POOL = [
        {"icon": "SKULL",  "label": "SKULL"},
        {"icon": "GHOST",  "label": "GHOST"},
        {"icon": "SWORD",  "label": "SWORD"},
        {"icon": "SHIELD", "label": "SHIELD"},
    ]

    # Reveal duration (seconds) per difficulty
    REVEAL_DURATION = {
        "EASY":   20.0,
        "NORMAL": 12.0,
        "HARD":    7.0,
    }

    # Maximum score awarded for an instant correct guess
    MAX_ROUND_SCORE = 500
    # Minimum score awarded for a correct guess at the very end
    MIN_ROUND_SCORE = 50

    def __init__(self, core):
        super().__init__(core, "EMOJI REVEAL", "Pixel Reveal Trivia")

    async def run_tutorial(self):
        """
        A guided, non-interactive demonstration of Emoji Reveal.

        The Voiceover Script (audio/tutes/emoji_tute.wav) ~ 31 seconds:
            [0:00] "Welcome to Emoji Reveal. A test of speed and recognition."
            [0:05] "Watch the LED matrix closely as an image slowly fades in, pixel by pixel."
            [0:10] "Check the screen for four possible answers."
            [0:14] "Press the physical buttons one through four to lock in your guess."
            [0:19] "The faster you answer correctly, the more points you score!"
            [0:24] "But be careful... one wrong guess, and the game is over."
            [0:29] "Good luck!"
            [0:31] (End of file)
        """
        await self.core.clean_slate()
        self.game_state = "TUTORIAL"

        # 1. Start the voiceover track
        self.core.audio.play("audio/tutes/emoji_tute.wav", bus_id=self.core.audio.CH_VOICE)

        # [0:00 - 0:05] "Welcome to Emoji Reveal. A test of speed and recognition."
        self.core.display.update_status("EMOJI REVEAL", "SPEED & RECOGNITION")
        self.core.matrix.show_icon("EMOJI_REVEAL", anim_mode="PULSE", speed=2.0)
        await asyncio.sleep(5.0)

        # [0:05 - 0:10] "Watch the LED matrix closely as an image slowly fades in..."
        self.core.display.update_status("REVEAL", "WATCH THE MATRIX")
        self.core.matrix.clear()

        # Start a slow reveal of the SKULL icon in the background
        icon_data = Icons.get("SKULL")
        reveal_task = asyncio.create_task(
            matrix_animations.animate_random_pixel_reveal(
                self.core.matrix,
                icon_data,
                duration=12.0,  # Slow reveal duration
                brightness=1.0
            )
        )
        await asyncio.sleep(5.0)

        # [0:10 - 0:14] "Check the screen for four possible answers."
        self.core.display.update_header("RND 1/5")
        self.core.display.update_status("A:GHOST   B:SKULL", "C:SWORD   D:SHIELD")
        await asyncio.sleep(4.0)

        # [0:14 - 0:19] "Press the physical buttons one through four..."
        self.core.display.update_footer("PRESS B2 FOR 'SKULL'")

        # Flash the LED for Button 2 (Index 1), which maps to Option B
        self.core.leds.flash_led(1, Palette.WHITE, duration=4.0, speed=0.2)
        await asyncio.sleep(4.0)

        # [0:19 - 0:24] "The faster you answer correctly, the more points..."
        # Cancel the background reveal task to simulate the player locking in an answer
        if not reveal_task.done():
            reveal_task.cancel()
            try:
                await reveal_task
            except asyncio.CancelledError:
                pass

        # Simulate instant success
        self.core.buzzer.play_sequence(tones.UI_CONFIRM)
        self.core.matrix.show_icon("SKULL", anim_mode="PULSE", speed=2.0, border_color=Palette.GREEN)
        self.core.display.update_header("CORRECT! +450")
        self.core.display.update_footer("")
        await asyncio.sleep(5.0)

        # [0:24 - 0:29] "But be careful... one wrong guess, and the game is over."
        self.core.display.update_header("WRONG GUESS =")
        self.core.display.update_status("GAME OVER!", "")
        self.core.matrix.show_icon("SKULL", anim_mode="PULSE", speed=2.0, border_color=Palette.RED)
        self.core.buzzer.play_sequence(tones.ERROR)
        await asyncio.sleep(5.0)

        # [0:29 - 0:31] "Good luck!"
        self.core.display.update_header("-EMOJI REVEAL-")
        self.core.display.update_status("GOOD LUCK!", "")

        # Clean up and return to the menu
        await self.core.clean_slate()
        return "TUTORIAL_COMPLETE"

    # ------------------------------------------------------------------
    # Main game entry point
    # ------------------------------------------------------------------

    async def run(self):
        """Run the full Emoji Reveal game."""

        # Load settings
        self.difficulty = self.core.data.get_setting("EMOJI_REVEAL", "difficulty", "NORMAL")
        rounds_str = self.core.data.get_setting("EMOJI_REVEAL", "rounds", "5")
        total_rounds = int(rounds_str)

        reveal_duration = self.REVEAL_DURATION.get(self.difficulty, 12.0)

        self.score = 0

        # Intro splash
        self.core.display.update_status("EMOJI REVEAL", "IDENTIFY THE ICON!")
        self.core.matrix.show_icon("EMOJI_REVEAL", anim_mode="PULSE", speed=2.0)
        await asyncio.sleep(1.5)

        for round_num in range(1, total_rounds + 1):
            result = await self._play_round(round_num, total_rounds, reveal_duration)

            if result == "WRONG":
                # Wrong answer ends the game
                return await self.game_over()

            # Brief inter-round pause
            await asyncio.sleep(1.0)

        # Survived all rounds
        return await self.victory()

    # ------------------------------------------------------------------
    # Single round
    # ------------------------------------------------------------------

    async def _play_round(self, round_num, total_rounds, reveal_duration):
        """Play one round; return 'CORRECT' or 'WRONG'."""

        # Pick a random question and build shuffled choices
        question = random.choice(self.QUESTION_POOL)
        correct_label = question["label"]
        icon_key = question["icon"]

        # Build choice list: correct answer + 3 distractors
        distractors = [q["label"] for q in self.QUESTION_POOL if q["label"] != correct_label]
        random.shuffle(distractors)
        choices = [correct_label] + distractors[:3]
        random.shuffle(choices)
        correct_idx = choices.index(correct_label)

        # Show choices on OLED
        self._show_choices(round_num, total_rounds, choices)

        # Prepare matrix: clear then start pixel-reveal animation
        self.core.matrix.clear()
        icon_data = Icons.get(icon_key)

        reveal_task = asyncio.create_task(
            matrix_animations.animate_random_pixel_reveal(
                self.core.matrix,
                icon_data,
                duration=reveal_duration,
                brightness=1.0
            )
        )

        round_start = ticks_ms()
        answer_idx = -1

        # Poll for button press while reveal is running
        while not reveal_task.done():
            for btn in range(4):
                if self.core.hid.is_pressed(btn):
                    answer_idx = btn
                    break

            if answer_idx != -1:
                break

            await asyncio.sleep(0.01)

        # Cancel the reveal animation as soon as input is received or time is up
        if not reveal_task.done():
            reveal_task.cancel()
            try:
                await reveal_task
            except asyncio.CancelledError:
                pass

        elapsed_ms = ticks_diff(ticks_ms(), round_start)

        # No input at all (reveal finished without a press) → treat as wrong
        if answer_idx == -1:
            self.core.display.update_status("TIME UP!", "NO ANSWER GIVEN")
            self.core.matrix.show_icon(icon_key, anim_mode="PULSE", speed=2.0, border_color=Palette.RED)
            await asyncio.sleep(1.5)
            return "WRONG"

        # Evaluate answer
        if answer_idx == correct_idx:
            round_score = self._calculate_score(elapsed_ms, reveal_duration)
            self.score += round_score
            self.core.display.update_status(
                f"CORRECT! +{round_score}",
                f"TOTAL: {self.score}"
            )
            self.core.matrix.show_icon(icon_key, anim_mode="PULSE", speed=2.0, border_color=Palette.GREEN)
            self.core.audio.play(
                "audio/general/correct.wav",
                self.core.audio.CH_SFX,
                level=0.8,
                interrupt=True
            )
            await asyncio.sleep(1.5)
            return "CORRECT"

        # Wrong answer
        self.core.display.update_status(
            f"WRONG! It was {correct_label}",
            f"SCORE: {self.score}"
        )
        self.core.matrix.show_icon(icon_key, anim_mode="PULSE", speed=2.0, border_color=Palette.RED)
        self.core.audio.play(
            "audio/general/fail.wav",
            self.core.audio.CH_SFX,
            level=0.8,
            interrupt=True
        )
        await asyncio.sleep(1.5)
        return "WRONG"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _show_choices(self, round_num, total_rounds, choices):
        """Display the 4 multiple-choice options on the OLED."""
        line1 = f"A:{choices[0]}  B:{choices[1]}"
        line2 = f"C:{choices[2]}  D:{choices[3]}"
        self.core.display.update_header(f"RND {round_num}/{total_rounds}")
        self.core.display.update_status(line1, line2)

    def _calculate_score(self, elapsed_ms, reveal_duration):
        """Calculate points based on how quickly the player answered.

        Answering instantly (elapsed ≈ 0) yields MAX_ROUND_SCORE.
        Answering at the very end yields MIN_ROUND_SCORE.
        Score scales linearly between these bounds.
        """
        reveal_ms = reveal_duration * 1000.0
        # Clamp to the reveal window
        t = max(0.0, min(float(elapsed_ms), reveal_ms))
        ratio = 1.0 - (t / reveal_ms)
        score = int(self.MIN_ROUND_SCORE + ratio * (self.MAX_ROUND_SCORE - self.MIN_ROUND_SCORE))
        return max(self.MIN_ROUND_SCORE, score)
