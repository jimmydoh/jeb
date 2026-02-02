#File: src/core/modes/game_mode.py
"""Game Mode Base Class."""

import asyncio
from .base import BaseMode

class GameMode(BaseMode):
    """Base class for all game modes."""
    def __init__(self, jeb, name, description):
        super().__init__(jeb, name, description)
        self.score = 0
        self.level = 0

    async def game_over(self):
        """Standard Fail State."""
        self.jeb.matrix.show_icon("FAIL", anim="PULSE")
        await self.jeb.audio.play_sfx("fail.wav")
        await self.jeb.display.update_status("GAME OVER", f"SCORE: {self.score}")
        await asyncio.sleep(2)
        return "GAME_OVER"

    async def victory(self):
        """Standard Win State."""
        self.jeb.matrix.show_icon("SUCCESS", anim="PULSE")
        await self.jeb.audio.play_sfx("win.wav")
        await asyncio.sleep(2)
        return "VICTORY"
