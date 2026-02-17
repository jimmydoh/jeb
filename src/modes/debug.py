#File: src/core/modes/debug.py
"""Debug Mode for Jeb Core."""

import asyncio
from .utility_mode import UtilityMode

class DebugMode(UtilityMode):
    """Debug Mode for testing and diagnostics."""

    def __init__(self, core):
        super().__init__(
            core,
            name="DEBUG MODE",
            description="Diagnostics and Testing",
            timeout=None
        )

    async def run(self):
        """Run the Debug Mode."""
        self.core.display.update_status("DEBUG MODE", "RUNNING DIAGNOSTICS")
        self.core.matrix.show_icon("DEBUG", anim_mode="BLINK", speed=1.0)

        # Example diagnostic routine
        for i in range(5):
            self.core.display.update_status("DEBUG MODE", f"TEST {i+1}/5")
            await self.core.audio.play_sfx("debug_beep.wav")
            await asyncio.sleep(1)

        self.core.display.update_status("DEBUG MODE", "DIAGNOSTICS COMPLETE")
        await asyncio.sleep(2)
        return "DEBUG_COMPLETE"
