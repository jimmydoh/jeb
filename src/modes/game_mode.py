#File: src/core/modes/game_mode.py
"""Game Mode Base Class."""

import asyncio
from .base import BaseMode

class GameMode(BaseMode):
    """Base class for all game modes."""
    def __init__(self, jeb, name, description, total_steps=1):
        super().__init__(jeb, name, description)
        self.score = 0
        self.level = 0
        self.step = 0
        self.total_steps = total_steps

    async def game_over(self):
        """Standard Fail State."""
        self.jeb.matrix.show_icon("FAILURE", anim_mode="PULSE", speed=2.0)
        await self.jeb.audio.stop_all()
        await self.jeb.audio.play("audio/general/fail.wav",
                                    self.jeb.audio.CH_SFX,
                                    level=1.0,
                                    Interrupt=True)
        await self.jeb.display.update_status("GAME OVER", f"SCORE: {self.score}")
        await asyncio.sleep(2)
        return "GAME_OVER"

    async def victory(self):
        """Standard Win State."""
        self.jeb.matrix.show_icon("SUCCESS", anim_mode="PULSE", speed=2.0)
        await self.jeb.audio.stop_all()
        await self.jeb.audio.play("audio/general/win.wav",
                                    self.jeb.audio.CH_SFX,
                                    level=1.0,
                                    Interrupt=True)
        await asyncio.sleep(2)
        return "VICTORY"
