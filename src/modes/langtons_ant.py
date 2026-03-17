"""Langton's Ant – Zero Player Cellular Automaton."""

import asyncio

from adafruit_ticks import ticks_ms, ticks_diff

from utilities import tones
from utilities.logger import JEBLogger

from .base import BaseMode

# Trail colour cycle as palette indices (Button 1 steps through these).
# Each value maps to a colour in Palette.LIBRARY (0 = off, so all > 0).
# Mapping: 41=GREEN, 51=CYAN, 42=LIME, 22=GOLD, 71=MAGENTA, 21=ORANGE
_TRAIL_COLOR_INDICES = [41, 51, 42, 22, 71, 21]

# Ant marker colour: WHITE (index 4) always stands out from any trail colour.
_ANT_MARKER_COLOR = 4

# Generation speed levels in milliseconds (encoder selects index)
_SPEED_LEVELS_MS = [500, 200, 100, 50, 20, 5]
_SPEED_NAMES = ["SLOW", "MED", "NORM", "FAST", "TURBO", "MAX"]

# Cardinal direction vectors indexed 0=N, 1=E, 2=S, 3=W
_DX = (0, 1, 0, -1)
_DY = (-1, 0, 1, 0)


class LangtonsAnt(BaseMode):
    """Langton's Ant – a zero-player cellular automaton.

    Every cell starts black (0).  At each step the ant:
      • Lands on a black cell → turns 90° right, flips cell to white, moves forward.
      • Lands on a white cell → turns 90° left,  flips cell to black, moves forward.

    After a few hundred steps a symmetric pattern forms, then apparent chaos
    takes over, and around step 10 000 the ant settles into a regular diagonal
    "highway" that repeats indefinitely.  The grid has toroidal (wrap-around)
    edges so the simulation never terminates.

    Multiple ants (configured via the ANTS setting) are placed symmetrically
    and share the same grid, interacting through it.

    Controls:
        Encoder turn       : change simulation speed (slow ↔ max)
        Button 1 (tap)     : cycle trail colour
        Button 2 (tap)     : reset grid and restart ant(s)
        Encoder long press : return to Zero Player menu
    """

    def __init__(self, core):
        super().__init__(core, "LANGTON'S ANT", "Langton's Ant Simulation")
        self.width = 0
        self.height = 0
        self._grid = None       # bytearray: 0=black cell, non-zero=white/trail
        self._frame = None      # render buffer (grid + ant markers overlaid)
        self._color_idx = 0     # index into _TRAIL_COLOR_INDICES
        self._speed_idx = 2     # default NORM (100 ms)
        self._step_count = 0
        self._ants = []         # list of [x, y, direction] lists

    async def run_tutorial(self):
        """
        Guided demonstration of Langton's Ant.

        The Voiceover Script (audio/tutes/ant_tute.wav) ~63 seconds:
            [0:00] "Welcome to Langton's Ant."
            [0:04] "Invented by Chris Langton in 1986, this is a two-dimensional Turing machine."
            [0:11] "The ant follows two simple rules based on the color of the square it lands on."
            [0:17] "On a dark square, it turns right, flips the color, and moves forward."
            [0:24] "On a lit square, it turns left, flips the color, and moves forward."
            [0:31] "At first, the patterns appear perfectly symmetric. But soon, they descend into apparent chaos."
            [0:40] "Eventually, the ant will build a repeating diagonal highway, marching endlessly."
            [0:48] "Turn the main dial to adjust the simulation speed."
            [0:53] "Press button one to change the trail color, and button two to reset the grid."
            [0:59] "Watch the chaos unfold."
            [1:03] (End of file)
        """
        await self.core.clean_slate()

        self.game_state = "TUTORIAL"

        # Trigger audio synchronously (fire-and-forget)
        self.core.audio.play(
            "audio/tutes/ant_tute.wav",
            bus_id=self.core.audio.CH_VOICE
        )

        # Setup standard display state for the tutorial
        self.width = self.core.matrix.width
        self.height = self.core.matrix.height
        size = self.width * self.height

        self._grid = bytearray(size)
        self._frame = bytearray(size)
        self._color_idx = 0
        self._step_count = 0

        # Start very SLOW so the player can actually see the rules in action
        self._speed_idx = 0

        # Force exactly 1 ant in the center for the tutorial clarity
        self._ants = [[self.width // 2, self.height // 2, 0]]

        self.core.display.use_standard_layout()
        self.core.display.update_header("LANGTON'S ANT")
        self.core.display.update_footer("B1:Color  B2:Reset")

        def _refresh_ui():
            line1, line2 = self._status_line()
            self.core.display.update_status(line1, line2)

        _refresh_ui()

        async def _sim_wait(duration_s):
            """Runs the ant simulation continuously for the specified duration."""
            start_time = ticks_ms()
            last_step_tick = start_time
            target_ms = int(duration_s * 1000)

            while ticks_diff(ticks_ms(), start_time) < target_ms:
                now = ticks_ms()
                interval = _SPEED_LEVELS_MS[self._speed_idx]
                if ticks_diff(now, last_step_tick) >= interval:
                    self._step()
                    self._build_frame()
                    self.core.matrix.show_frame(self._frame)

                    # Update UI roughly every 10 steps during fast modes, or every step during slow
                    if interval >= 100 or self._step_count % 10 == 0:
                        _refresh_ui()

                    last_step_tick = now
                await asyncio.sleep(0.01)

        try:
            # [0:00 - 0:17] Intro & Turing machine context
            self.core.display.update_status("LANGTON'S ANT", "TURING MACHINE")
            await _sim_wait(17.0)

            # [0:17 - 0:24] Rule 1: Dark Square (Right turn)
            self.core.display.update_status("RULE 1: DARK", "TURN RIGHT, FLIP")
            await _sim_wait(7.0)

            # [0:24 - 0:31] Rule 2: Lit Square (Left turn)
            self.core.display.update_status("RULE 2: LIT", "TURN LEFT, FLIP")
            await _sim_wait(7.0)

            # [0:31 - 0:40] Symmetry into chaos
            self.core.display.update_status("EMERGENT", "SYMMETRY TO CHAOS")
            self._speed_idx = 3 # Kick it to FAST to speed up the visual evolution
            _refresh_ui()
            await _sim_wait(9.0)

            # [0:40 - 0:48] The Highway
            self.core.display.update_status("10,000 STEPS", "THE HIGHWAY")
            self._speed_idx = 5 # Kick to MAX speed! Let it zoom.
            _refresh_ui()
            await _sim_wait(8.0)

            # [0:48 - 0:53] Speed dial demonstration
            self.core.display.update_status("MAIN DIAL", "CHANGE SPEED")
            for speed in [3, 4, 1, 2]: # Cycle FAST -> TURBO -> MED -> NORM
                self._speed_idx = speed
                _refresh_ui()
                self.core.buzzer.play_sequence(tones.UI_TICK)
                await _sim_wait(1.25)

            # [0:53 - 0:59] Color cycling and Reset demonstration
            self.core.display.update_status("BUTTON 1", "CYCLE COLOR")
            for _ in range(4):
                self._color_idx = (self._color_idx + 1) % len(_TRAIL_COLOR_INDICES)
                self._recolor_trail()
                self._build_frame()
                self.core.matrix.show_frame(self._frame)
                self.core.buzzer.play_sequence(tones.UI_TICK)
                await _sim_wait(1.0)

            self.core.display.update_status("BUTTON 2", "RESET GRID")
            await _sim_wait(1.0)

            # Clear the grid
            for i in range(len(self._grid)): self._grid[i] = 0
            self._ants = [[self.width // 2, self.height // 2, 0]]
            self._step_count = 0
            self._build_frame()
            self.core.matrix.show_frame(self._frame)

            self.core.display.update_status("BUTTON 2", "RESET!")
            self.core.buzzer.play_sequence(tones.UI_CONFIRM)
            await _sim_wait(3.0)

            # Wait for audio to finish out if it's still running
            if hasattr(self.core.audio, 'wait_for_bus'):
                await self.core.audio.wait_for_bus(self.core.audio.CH_VOICE)
            else:
                await asyncio.sleep(2.0)

            # --- SEAMLESS HANDOFF TO MAIN LOOP ---
            self.core.display.update_status("TUTORIAL COMPLETE", "HANDING OVER CONTROL")
            await asyncio.sleep(1.5)

            self.core.hid.flush()

            # Re-run the proper reset to apply the user's custom ANTS setting
            # (since we forced exactly 1 ant for the tutorial clarity)
            self._reset()

            self.game_state = "RUNNING"
            return await self.run()

        finally:
            await self.core.clean_slate()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _reset(self):
        """Clear the grid and place ant(s) at their starting positions."""
        self._step_count = 0
        w, h = self.width, self.height
        for i in range(len(self._grid)):
            self._grid[i] = 0

        try:
            count = int(self.core.data.get_setting("LANGTONS_ANT", "ants", "1"))
        except Exception:
            count = 1

        self._ants = []
        if count >= 4:
            # Four ants at the quadrant centres, each facing outward
            self._ants.append([w // 4,         h // 4,         0])  # N
            self._ants.append([3 * w // 4,     h // 4,         1])  # E
            self._ants.append([3 * w // 4,     3 * h // 4,     2])  # S
            self._ants.append([w // 4,         3 * h // 4,     3])  # W
        elif count == 2:
            # Two ants on opposite sides of the horizontal midline
            self._ants.append([w // 4,         h // 2,         0])  # N
            self._ants.append([3 * w // 4,     h // 2,         2])  # S
        else:
            # Single ant at centre, heading North
            self._ants.append([w // 2, h // 2, 0])

    def _step(self):
        """Advance all ants by one Langton step."""
        w = self.width
        trail_color = _TRAIL_COLOR_INDICES[self._color_idx]
        for ant in self._ants:
            x, y, d = ant[0], ant[1], ant[2]
            idx = y * w + x
            if self._grid[idx] == 0:
                # Black cell: turn right, flip to white, advance
                ant[2] = (d + 1) % 4
                self._grid[idx] = trail_color
            else:
                # White cell: turn left, flip to black, advance
                ant[2] = (d - 1) % 4
                self._grid[idx] = 0
            ant[0] = (x + _DX[ant[2]]) % self.width
            ant[1] = (y + _DY[ant[2]]) % self.height
        self._step_count += 1

    def _recolor_trail(self):
        """Update all white cells to the current trail colour.

        Called when the user cycles the trail colour (Button 1 tap) so that
        existing trail cells immediately reflect the new selection without
        waiting for the next step.
        """
        new_color = _TRAIL_COLOR_INDICES[self._color_idx]
        for i in range(len(self._grid)):
            if self._grid[i] != 0:
                self._grid[i] = new_color

    def _build_frame(self):
        """Copy the grid into the render buffer and overlay ant markers."""
        self._frame[:] = self._grid
        for ant in self._ants:
            self._frame[ant[1] * self.width + ant[0]] = _ANT_MARKER_COLOR

    def _status_line(self):
        """Return a two-line status tuple for the current simulation state."""
        name = _SPEED_NAMES[self._speed_idx]
        ms = _SPEED_LEVELS_MS[self._speed_idx]
        return f"{name} ({ms}ms)", f"STEP:{self._step_count}"

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    async def run(self):
        """Main Langton's Ant simulation loop."""
        JEBLogger.info("ANT", "[RUN] LangtonsAnt starting")

        self.width = self.core.matrix.width
        self.height = self.core.matrix.height
        size = self.width * self.height

        self._grid = bytearray(size)
        self._frame = bytearray(size)
        self._color_idx = 0
        self._speed_idx = 2
        self._step_count = 0

        self._reset()

        self.core.display.use_standard_layout()
        self.core.display.update_header("LANGTON'S ANT")
        line1, line2 = self._status_line()
        self.core.display.update_status(line1, line2)
        self.core.display.update_footer("B1:Color  B2:Reset")

        self.core.hid.flush()
        self.core.hid.reset_encoder(self._speed_idx)
        last_enc = self.core.hid.encoder_position()
        last_step_tick = ticks_ms()
        last_display_step = -1

        while True:
            now = ticks_ms()

            # --- Encoder: adjust simulation speed ---
            enc = self.core.hid.encoder_position()
            diff = enc - last_enc
            if diff != 0:
                delta = 1 if diff > 0 else -1
                new_idx = max(0, min(len(_SPEED_LEVELS_MS) - 1, self._speed_idx + delta))
                self._speed_idx = new_idx
                self.core.hid.reset_encoder(self._speed_idx)
                last_enc = self._speed_idx
                line1, line2 = self._status_line()
                self.core.display.update_status(line1, line2)
                self.core.buzzer.play_sequence(tones.UI_TICK)

            # --- Button 1: cycle trail colour ---
            if self.core.hid.is_button_pressed(0, action="tap"):
                self._color_idx = (self._color_idx + 1) % len(_TRAIL_COLOR_INDICES)
                self._recolor_trail()
                self.core.buzzer.play_sequence(tones.UI_TICK)

            # --- Button 2: reset grid and restart ants ---
            if self.core.hid.is_button_pressed(1, action="tap"):
                self._reset()
                line1, _ = self._status_line()
                self.core.display.update_status(line1, "RESET!")
                last_display_step = -1
                self.core.buzzer.play_sequence(tones.UI_CONFIRM)

            # --- Encoder long press (2 s): exit to Zero Player menu ---
            if self.core.hid.is_encoder_button_pressed(long=True, duration=2000):
                JEBLogger.info("ANT", "[EXIT] Returning to Zero Player menu")
                return "SUCCESS"

            # --- Simulation step on interval ---
            interval = _SPEED_LEVELS_MS[self._speed_idx]
            if ticks_diff(now, last_step_tick) >= interval:
                self._step()
                self._build_frame()
                self.core.matrix.show_frame(self._frame)
                last_step_tick = now

                # Update the step counter on the display every 100 steps
                if self._step_count - last_display_step >= 100:
                    _, line2 = self._status_line()
                    name = _SPEED_NAMES[self._speed_idx]
                    ms = _SPEED_LEVELS_MS[self._speed_idx]
                    self.core.display.update_status(f"{name} ({ms}ms)", line2)
                    last_display_step = self._step_count

            await asyncio.sleep(0.01)
