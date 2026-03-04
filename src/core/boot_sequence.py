# File: src/core/boot_sequence.py
"""Synchronized audiovisual boot animation for the JEB console power-on experience.

Runs immediately after power integrity is confirmed and before the main mode loop.
Coordinates a matrix curtain animation, OLED splash screen, synthesizer swell,
and a buzzer accent ping — all via asyncio so background tasks (e.g. watchdog
feeding) continue uninterrupted during the sequence.
"""

import asyncio

from utilities.icons import Icons
from utilities.logger import JEBLogger
from utilities.palette import Palette
from utilities import tones


class BootSequence:
    """Console power-on boot animation sequence.

    Combines three concurrent effects that play simultaneously via
    asyncio.gather, then fires a single buzzer ping when all visuals
    have settled into their final positions.

    Usage::

        seq = BootSequence(matrix, display, synth, buzzer)
        await seq.play("v0.8.0")
    """

    def __init__(self, matrix, display, synth, buzzer):
        """Initialise with the required hardware managers.

        Args:
            matrix: MatrixManager instance (16×16 NeoPixel array).
            display: DisplayManager instance (128×64 OLED).
            synth: SynthManager instance (I2S synthesiser).
            buzzer: BuzzerManager instance (piezo buzzer).
        """
        self.matrix = matrix
        self.display = display
        self.synth = synth
        self.buzzer = buzzer

    async def play(self, version=""):
        """Run the full boot sequence, then return.

        Runs the matrix curtain reveal, OLED splash, and synth swell
        concurrently.  Once all three are settled the buzzer fires a
        sharp accent ping.

        Args:
            version: Optional version string to display (e.g. ``"v0.8.0"``).
        """
        JEBLogger.info("BOOT", "Starting boot sequence")

        # Run visuals and audio concurrently — non-blocking to background tasks
        await asyncio.gather(
            self._matrix_curtain_reveal(),
            self._oled_splash(version),
            self._synth_swell(),
        )

        # Ping fires exactly as matrix logo and OLED text lock into position
        self._buzzer_ping()
        await asyncio.sleep(0.5)

        JEBLogger.info("BOOT", "Boot sequence complete")

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _matrix_curtain_reveal(self):
        """Curtain-drop wipe followed by a column-by-column logo reveal.

        Phase 1: A solid cyan curtain falls row by row from the top edge.
        Phase 2: The JEBRIS logo replaces the curtain one column at a time,
                 sliding in from the left.
        """
        accent = Palette.CYAN

        # Phase 1 — curtain drop (top → bottom)
        for row in range(self.matrix.height):
            for col in range(self.matrix.width):
                self.matrix.draw_pixel(col, row, accent)
            await asyncio.sleep(0.03)

        # Phase 2 — logo reveal (left → right column wipe)
        icon = Icons.DEFAULT
        # Calculate max steps for a 16x16 matrix from bottom-center
        # Max row dist (15) + Max col dist (7) = 22. Range is 0 to 22 (23 steps).
        for step in range(23):
            for row in range(self.matrix.height):
                for col in range(self.matrix.width):
                    # Calculate Manhattan distance from bottom-center
                    row_dist = (self.matrix.height - 1) - row

                    # Center columns are 7 and 8 (0-indexed).
                    # This math creates distance 0 for cols 7&8, 1 for 6&9, etc.
                    col_dist = abs(col * 2 - (self.matrix.width - 1)) // 2

                    # If this pixel's distance equals the current animation step, draw it
                    if row_dist + col_dist == step:
                        palette_idx = icon[row * self.matrix.width + col]
                        color = Palette.get_color(palette_idx)
                        self.matrix.draw_pixel(col, row, color)

            # 23 steps * 0.03s = 0.69s total (keeps timing synced with the audio swell!)
            await asyncio.sleep(0.03)

    async def _oled_splash(self, version=""):
        """OLED version text drops from the top with a brief pixel bounce settle.

        The status label slides down from y=2 to y=24 (its resting position)
        with a small overshoot that snaps back, mimicking a physical curtain
        settling into place.

        Args:
            version: Version string appended to ``"JEB OS"`` (e.g. ``"v0.8.0"``).
        """
        title = f"JEB OS {version}".strip() if version else "JEB OS"

        self.display.use_standard_layout()

        # Drop positions: start at top (y=2), slide to rest (y=24), overshoot, bounce
        drop_positions = [2, 6, 10, 14, 18, 22, 26, 28, 24]
        for y_pos in drop_positions:
            self.display.status.y = y_pos
            self.display.status.text = title
            await asyncio.sleep(0.05)

        # Settle: ensure text and position are locked
        self.display.update_status(title, "")

    async def _synth_swell(self):
        """Warm 3-note FM-style synth swell via SynthManager.

        Uses the PAD patch (slow 0.5 s attack) for a gradually building
        textural effect that swells alongside the visual curtain drop.
        """
        await self.synth.play_sequence(tones.CONSOLE_BOOT_SWELL)

    def _buzzer_ping(self):
        """Sharp high-pitched accent ping via BuzzerManager.

        Fires a brief C8 tone (4186 Hz) to accentuate the moment the
        matrix logo and OLED text lock into their final positions.
        """
        self.buzzer.play_note(4186, duration=0.15)
