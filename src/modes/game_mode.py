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

    async def game_over(self):
        """Standard Fail State."""
        self.core.matrix.show_icon("FAILURE", anim_mode="PULSE", speed=2.0)
        await self.core.audio.stop_all()
        await self.core.buzzer.stop()
        await self.core.audio.play("audio/general/fail.wav",
                                    self.core.audio.CH_SFX,
                                    level=1.0,
                                    Interrupt=True)
        await self.core.display.update_status("GAME OVER", f"SCORE: {self.score}")
        await asyncio.sleep(2)
        return "GAME_OVER"

    async def victory(self):
        """Standard Win State."""
        self.core.matrix.show_icon("SUCCESS", anim_mode="PULSE", speed=2.0)
        await self.core.audio.stop_all()
        await self.core.buzzer.stop()
        await self.core.audio.play("audio/general/win.wav",
                                    self.core.audio.CH_SFX,
                                    level=1.0,
                                    Interrupt=True)
        await asyncio.sleep(2)
        return "VICTORY"

    async def run(self):
        """Override this method in subclasses."""
        raise NotImplementedError("Subclasses must implement the run() method.")
