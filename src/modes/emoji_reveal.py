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
        icon_data = Icons.ICON_LIBRARY.get(icon_key, Icons.DEFAULT)

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
            await self.core.audio.play(
                "audio/general/correct.wav",
                self.core.audio.CH_SFX,
                level=0.8,
                Interrupt=True
            )
            await asyncio.sleep(1.5)
            return "CORRECT"

        # Wrong answer
        self.core.display.update_status(
            f"WRONG! It was {correct_label}",
            f"SCORE: {self.score}"
        )
        self.core.matrix.show_icon(icon_key, anim_mode="PULSE", speed=2.0, border_color=Palette.RED)
        await self.core.audio.play(
            "audio/general/fail.wav",
            self.core.audio.CH_SFX,
            level=0.8,
            Interrupt=True
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
