"""Parallax Starfield / Warp Core – Zero Player Mode.

Simulates a 3D star-flight screensaver.  Stars are stored as (x, y, z)
world-space coordinates and projected onto the LED matrix via:

    screen_x = (x / z) * SCALE + half_x
    screen_y = (y / z) * SCALE + half_y

Decreasing z each tick moves stars "toward the camera".  The depth value
is mapped to a palette colour so distant stars are dim (CHARCOAL) and
close stars blaze bright white, giving a genuine parallax-warp feeling.

The simulation uses a 1D ``bytearray`` frame buffer (palette indices) that
is written to the hardware in one call via ``matrix.show_frame()``,
matching the pattern of FallingSandMode for maximum performance.

Controls:
    Encoder turn       : increase / decrease warp speed
    Button 1 (tap)     : cycle star density (SPARSE / NORMAL / DENSE)
    Button 2 (tap)     : reset / re-scatter all stars
    Encoder long press : return to Zero Player menu
"""

import asyncio
import random
import gc

from adafruit_ticks import ticks_ms, ticks_diff

from utilities import tones
from utilities.logger import JEBLogger

from .base import BaseMode

# ---------------------------------------------------------------------------
# Simulation constants
# ---------------------------------------------------------------------------

# Stars are spawned with z values drawn uniformly across this range.
_Z_MAX = 15.0
# Minimum z before a star is recycled (re-spawned at the far end).
_Z_MIN = 0.5

# Scale factor for the perspective projection.
# Larger value → stars diverge faster as they approach the camera.
_SCALE = 8.0

# Warp-speed presets: z decrement per simulation tick (~30 fps).
# The rotary encoder selects the active level.
_WARP_LEVELS = [0.05, 0.1, 0.2, 0.4, 0.8, 1.5]
_WARP_NAMES  = ["1", "2", "3", "4", "5", "MAX"]
_DEFAULT_WARP_IDX = 2   # "Speed 3" on startup

# Star-count presets (encoder cycles Button 1 through these).
_STAR_COUNTS = [30, 60, 100]
_STAR_NAMES  = ["SPARSE", "NORMAL", "DENSE"]
_DEFAULT_STAR_IDX = 1   # NORMAL

# Palette indices for depth colouring, ordered farthest → closest.
# Drawn from the Palette grayscale band:
#   1 = CHARCOAL (30,30,30)   – distant/dim
#   2 = GRAY     (100,100,100)
#   3 = SILVER   (180,180,180)
#   4 = WHITE    (255,255,255) – close/bright
_DEPTH_PALETTE = [1, 1, 2, 3, 4]

# Target milliseconds between simulation steps (~30 fps).
_TICK_MS = 33


class StarfieldMode(BaseMode):
    """Parallax Starfield / Warp Core – zero-player retro screensaver.

    Stars are projected from 3-D world space onto the 2-D LED matrix using
    a simple perspective divide.  Decreasing z per frame moves each star
    towards the viewer; the depth is also mapped to brightness so the scene
    reads as true 3-D motion.

    The simulation uses a 1-D ``bytearray`` frame buffer (palette indices)
    written to the hardware in a single call to ``matrix.show_frame()``.

    Controls:
        Encoder turn       : faster / slower warp speed
        Button 1 (tap)     : cycle star density (SPARSE / NORMAL / DENSE)
        Button 2 (tap)     : reset / re-scatter all stars
        Encoder long press : return to Zero Player menu
    """

    def __init__(self, core):
        super().__init__(core, "STARFIELD", "Warp Core Screensaver")
        self.width     = 0
        self.height    = 0
        self._stars    = None   # list of [x, y, z] floats, one per star
        self._frame    = None   # bytearray: palette-index frame buffer
        self._zero_frame = None   # bytearray of all-0s for quick clearing
        self._warp_idx = _DEFAULT_WARP_IDX
        self._star_idx = _DEFAULT_STAR_IDX

    async def run_tutorial(self):
        """
        Guided demonstration of the Parallax Starfield.

        The Voiceover Script (audio/tutes/starfield_tute.wav) ~45 seconds:
            [0:00] "Welcome to the Parallax Starfield."
            [0:04] "This simulation uses a true three-dimensional coordinate system to project stars onto the matrix."
            [0:12] "As stars move toward the camera, their depth is mapped to brightness."
            [0:18] "Distant stars are dim, while close stars blaze bright white, creating the illusion of infinite space."
            [0:26] "Turn the main dial to adjust your warp speed."
            [0:32] "Press button one to cycle the density of the starfield."
            [0:37] "And press button two to randomly re-scatter the stars."
            [0:42] "Engage warp drive."
            [0:45] (End of file)
        """
        await self.core.clean_slate()

        self.game_state = "TUTORIAL"

        # Trigger audio synchronously (fire-and-forget)
        self.core.audio.play(
            "audio/tutes/starfield_tute.wav",
            bus_id=self.core.audio.CH_VOICE
        )

        # Setup standard display state for the tutorial
        self.width  = self.core.matrix.width
        self.height = self.core.matrix.height
        self._zero_frame = b'\x00' * (self.width * self.height)

        self._warp_idx = 1 # Start slower than default (Speed 2) to show the depth clearly
        self._star_idx = 1 # NORMAL density
        self._reset_stars()

        self.core.display.use_standard_layout()
        self.core.display.update_header("STARFIELD")
        self.core.display.update_footer("B1:Stars  B2:Reset")

        def _refresh_ui():
            line1, line2 = self._status_line()
            self.core.display.update_status(line1, line2)

        _refresh_ui()

        async def _sim_wait(duration_s):
            """Runs the starfield simulation continuously for the specified duration."""
            start_time = ticks_ms()
            last_tick = start_time
            target_ms = int(duration_s * 1000)

            while ticks_diff(ticks_ms(), start_time) < target_ms:
                now = ticks_ms()
                if ticks_diff(now, last_tick) >= _TICK_MS:
                    self._step()
                    self.core.matrix.show_frame(self._frame)
                    last_tick = now
                await asyncio.sleep(0.01)

        try:
            # [0:00 - 0:12] Intro & 3D Math
            self.core.display.update_status("PARALLAX", "3D PROJECTION")
            await _sim_wait(12.0)

            # [0:12 - 0:26] Depth / Brightness explanation
            self.core.display.update_status("DEPTH MAPPING", "DIM TO BRIGHT")
            await _sim_wait(14.0)

            # [0:26 - 0:32] Main Dial: Warp speed demo
            self.core.display.update_status("MAIN DIAL", "WARP SPEED")
            for speed in [2, 3, 4, 5]: # Cycle up to MAX speed
                await _sim_wait(1.0)
                self._warp_idx = speed
                _refresh_ui()
                self.core.buzzer.play_sequence(tones.UI_TICK)
            await _sim_wait(2.0)

            # [0:32 - 0:37] Button 1: Star Density
            self.core.display.update_status("BUTTON 1", "STAR DENSITY")
            for density in [2, 0, 1]: # DENSE -> SPARSE -> NORMAL
                await _sim_wait(1.5)
                self._star_idx = density
                self._reset_stars()
                _refresh_ui()
                self.core.buzzer.play_sequence(tones.UI_TICK)
            await _sim_wait(0.5)

            # [0:37 - 0:42] Button 2: Reset Demo
            self.core.display.update_status("BUTTON 2", "SCATTER STARS")
            await _sim_wait(1.0)
            self._reset_stars()
            self.core.display.update_status("BUTTON 2", "SCATTERED!")
            self.core.buzzer.play_sequence(tones.UI_CONFIRM)
            await _sim_wait(4.0)

            # Wait for audio to finish out if it's still running
            if hasattr(self.core.audio, 'wait_for_bus'):
                await self.core.audio.wait_for_bus(self.core.audio.CH_VOICE)
            else:
                await asyncio.sleep(2.0)

            # --- SEAMLESS HANDOFF TO MAIN LOOP ---
            self.core.display.update_status("TUTORIAL COMPLETE", "HANDING OVER CONTROL")
            await asyncio.sleep(1.5)

            self.core.hid.flush()

            self.game_state = "RUNNING"
            return await self.run()

        finally:
            await self.core.clean_slate()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _reset_stars(self):
        """Scatter all stars randomly across the full depth range."""
        count = _STAR_COUNTS[self._star_idx]
        half  = _Z_MAX * 0.5
        self._stars = [
            [random.uniform(-half, half),
             random.uniform(-half, half),
             random.uniform(_Z_MIN + 1.0, _Z_MAX)]
            for _ in range(count)
        ]
        size = self.width * self.height
        if self._frame is None or len(self._frame) != size:
            self._frame = bytearray(size)
        gc.collect()

    def _depth_color(self, z):
        """Map a z-depth value to a palette color index.

        Returns a higher (brighter) index the closer the star is to the
        camera (smaller z).

        Args:
            z: Current depth value, expected in [_Z_MIN, _Z_MAX].

        Returns:
            int: Palette index from _DEPTH_PALETTE.
        """
        # t = 0.0 → farthest (z near _Z_MAX), t = 1.0 → closest (z near _Z_MIN)
        t   = max(0.0, min(1.0, 1.0 - (z - _Z_MIN) / (_Z_MAX - _Z_MIN)))
        idx = min(len(_DEPTH_PALETTE) - 1, int(t * len(_DEPTH_PALETTE)))
        return _DEPTH_PALETTE[idx]

    def _step(self):
        """Advance every star by one physics tick and rebuild the frame buffer.

        Each star's z coordinate is decreased by the current warp speed.
        Stars that cross z <= _Z_MIN are recycled to the far end of the
        field with a fresh random (x, y) position.  The resulting visible
        positions are projected onto the 2-D matrix and written into the
        palette-index frame buffer.
        """
        w      = self.width
        h      = self.height
        half_x = (w - 1) / 2.0
        half_y = (h - 1) / 2.0
        speed  = _WARP_LEVELS[self._warp_idx]
        frame  = self._frame
        half   = _Z_MAX * 0.5

        # Clear the frame buffer before rendering this tick.
        frame[:] = self._zero_frame

        for star in self._stars:
            # Cache list elements to local variables (faster lookups)
            z = star[2] - speed

            if z <= _Z_MIN:
                star[0] = random.uniform(-half, half)
                star[1] = random.uniform(-half, half)
                star[2] = _Z_MAX
                continue

            star[2] = z  # Write back once

            # Calculate scale once
            scale_factor = _SCALE / z
            sx = int(star[0] * scale_factor + half_x + 0.5)
            sy = int(star[1] * scale_factor + half_y + 0.5)

            if 0 <= sx < w and 0 <= sy < h:
                color = self._depth_color(star[2])
                idx   = sy * w + sx
                # When two stars overlap keep the brighter one.
                if color > frame[idx]:
                    frame[idx] = color

    def _status_line(self):
        """Return the two HUD status strings for the current state."""
        return (
            f"WARP {_WARP_NAMES[self._warp_idx]}",
            _STAR_NAMES[self._star_idx],
        )

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    async def run(self):
        """Main starfield simulation loop."""
        JEBLogger.info("STAR", "[RUN] StarfieldMode starting")

        self.width  = self.core.matrix.width
        self.height = self.core.matrix.height
        self._zero_frame = b'\x00' * (self.width * self.height)  # all-0s for quick clearing

        self._warp_idx = _DEFAULT_WARP_IDX
        self._star_idx = _DEFAULT_STAR_IDX
        self._frame    = bytearray(self.width * self.height)
        self._reset_stars()

        # UI
        self.core.display.use_standard_layout()
        self.core.display.update_header("STARFIELD")
        line1, line2 = self._status_line()
        self.core.display.update_status(line1, line2)
        self.core.display.update_footer("B1:Stars  B2:Reset")

        self.core.hid.flush()
        self.core.hid.reset_encoder(self._warp_idx)
        last_enc  = self.core.hid.encoder_position()
        last_tick = ticks_ms()

        while True:
            now = ticks_ms()

            # --- Encoder: adjust warp speed ---
            enc  = self.core.hid.encoder_position()
            diff = enc - last_enc
            if diff != 0:
                delta      = 1 if diff > 0 else -1
                new_idx    = max(0, min(len(_WARP_LEVELS) - 1,
                                        self._warp_idx + delta))
                self._warp_idx = new_idx
                self.core.hid.reset_encoder(self._warp_idx)
                last_enc   = self._warp_idx
                line1, line2 = self._status_line()
                self.core.display.update_status(line1, line2)
                self.core.buzzer.play_sequence(tones.UI_TICK)

            # --- Button 1: cycle star density ---
            if self.core.hid.is_button_pressed(0, action="tap"):
                self._star_idx = (self._star_idx + 1) % len(_STAR_COUNTS)
                self._reset_stars()
                line1, line2 = self._status_line()
                self.core.display.update_status(line1, line2)
                self.core.buzzer.play_sequence(tones.UI_TICK)

            # --- Button 2: reset / re-scatter all stars ---
            if self.core.hid.is_button_pressed(1, action="tap"):
                self._reset_stars()
                line1, _ = self._status_line()
                self.core.display.update_status(line1, "RESET!")
                self.core.buzzer.play_sequence(tones.UI_CONFIRM)

            # --- Encoder long press (2 s): exit to Zero Player menu ---
            if self.core.hid.is_encoder_button_pressed(long=True, duration=2000):
                JEBLogger.info("STAR", "[EXIT] Returning to Zero Player menu")
                gc.collect()
                return "SUCCESS"

            # --- Simulation step on interval ---
            if ticks_diff(now, last_tick) >= _TICK_MS:
                self._step()
                self.core.matrix.show_frame(self._frame)
                last_tick = now

            await asyncio.sleep(0.01)
