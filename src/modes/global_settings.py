# File: src/modes/global_settings.py
"""Global Settings Mode for Jeb Core."""

import asyncio
from .utility_mode import UtilityMode


class GlobalSettings(UtilityMode):
    """Global Settings Mode for system-wide configuration.

    Placeholder for future system-wide settings management.

    Controls
    --------
    * **Button B long press (2 s)** – exit back to Admin Menu.
    """

    def __init__(self, core):
        super().__init__(
            core,
            name="GLOBAL SETTINGS",
            description="System-wide configuration",
            timeout=None
        )

    async def run(self):
        """Run the Global Settings Mode."""
        self.core.display.use_standard_layout()
        self.core.display.update_header("GLOBAL SETTINGS")
        self.core.display.update_status("COMING SOON", "Not yet implemented")
        self.core.display.update_footer("Hold 'W' to exit")

        self.core.hid.flush()

        while True:
            btn_b_long = self.core.hid.is_button_pressed(1, long=True, duration=2000)

            if btn_b_long:
                self.core.mode = "DASHBOARD"
                await self.core.audio.play("audio/menu/close.wav", self.core.audio.CH_SFX, level=0.8)
                return "EXIT"

            await asyncio.sleep(0.05)
