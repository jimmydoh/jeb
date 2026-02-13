#File: src/core/modes/game_mode.py
"""Game Mode Base Class."""

import asyncio
from .base import BaseMode

class GameMode(BaseMode):
    """Base class for all game modes."""

    def __init__(self, core, name, description, total_steps=1):
        super().__init__(core, name, description)
        self.score = 0
        self.level = 0
        self.step = 0
        self.total_steps = total_steps
        self.difficulty = "NORMAL"

    @property
    def score_key(self):
        """
        Generates the unique key for high score tracking.
        Current: Tracks by Variant (e.g. 'CLASSIC', 'REVERSE').

        To track by difficulty later, change this to:
        return f"{self.variant}_{self.difficulty}"
        """
        return self.variant

    def get_high_score(self):
        """Helper to get the high score for the current setup."""
        return self.core.data.get_high_score(self.name, self.score_key)

    def save_high_score(self):
        """Helper to save the high score if it's a new record."""
        is_new_record = self.core.data.save_high_score(self.name, self.score_key, self.score)
        if is_new_record:
            return True
        return False

    async def game_over(self):
        """Standard Game Over State with High Score handling."""

        # Stop existing audio and buzzer
        await self.core.audio.stop_all()
        await self.core.buzzer.stop()

        # Show high score animation if we beat the record
        if self.save_high_score():
            await self.core.display.update_status(
                "GAME OVER - NEW HIGH SCORE!",
                f"SCORE: {self.score}"
            )
            await self.core.matrix.show_icon(
                "HIGH_SCORE",
                anim_mode="PULSE",
                speed=2.0)
            await self.core.audio.play(
                "audio/general/new_record.wav",
                self.core.audio.CH_SFX,
                level=1.0,
                Interrupt=True
            )
            await asyncio.sleep(2)
        # Show regular game over if we didn't beat the record
        else:
            await self.core.display.update_status(
                f"GAME OVER - SCORE: {self.score}",
                f"HIGH SCORE: {self.get_high_score()}"
            )
            await self.core.matrix.show_icon(
                "FAILURE",
                anim_mode="PULSE",
                speed=2.0
            )
            await self.core.audio.play(
                "audio/general/fail.wav",
                self.core.audio.CH_SFX,
                level=1.0,
                Interrupt=True
            )
            await asyncio.sleep(2)

        return "GAME_OVER"

    async def victory(self):
        """Standard Win State with high score handling."""

        await self.core.audio.stop_all()
        await self.core.buzzer.stop()

        # Show high score animation if we beat the record
        if self.save_high_score():
            await self.core.display.update_status(
                "VICTORY - NEW HIGH SCORE!",
                f"SCORE: {self.score}"
            )
            await self.core.matrix.show_icon(
                "HIGH_SCORE",
                anim_mode="PULSE",
                speed=2.0)
            await self.core.audio.play(
                "audio/general/new_record.wav",
                self.core.audio.CH_SFX,
                level=1.0,
                Interrupt=True
            )
            await asyncio.sleep(2)
        # Show regular victory if we didn't beat the record
        else:
            await self.core.display.update_status(
                f"VICTORY! SCORE: {self.score}",
                f"HIGH SCORE: {self.get_high_score()}"
            )
            await self.core.matrix.show_icon(
                "SUCCESS",
                anim_mode="PULSE",
                speed=2.0
            )
            await self.core.audio.play(
                "audio/general/win.wav",
                self.core.audio.CH_SFX,
                level=1.0,
                Interrupt=True
            )
            await asyncio.sleep(2)
        return "VICTORY"

    async def run(self):
        """Override this method in subclasses."""
        raise NotImplementedError("Subclasses must implement the run() method.")
