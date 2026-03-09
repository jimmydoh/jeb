# File: src/modes/abyssal_rover.py
"""Abyssal Rover – Blind Maze-Navigation Game Mode.

The player drives a rover through a pitch-black procedurally generated maze.
The 16x16 LED matrix shows only a 5x5 viewport centered on the rover;
everything outside that illuminated area is void.

The OLED acts as a sonar/proximity sensor, showing the distance (in grid cells)
to the nearest wall in the direction the rover is currently facing.

An Emergency Flare reveals the full maze overview for exactly one second.
Players get three flares per game.

Hardware mapping
----------------
Core (required):
    - 16x16 Matrix: 5x5 lit viewport centered on rover; rest is off
    - OLED: distance to nearest wall in current facing direction
    - Core Encoder: rotate rover facing direction (N → E → S → W)
    - B1 (index 0): drive rover backward
    - B2 (index 1): drive rover forward
    - B3 (index 2): fire Emergency Flare

Industrial Satellite (SAT-01, optional – enhanced feedback):
    - 14-Segment Display: distance to nearest wall in facing direction
    - Satellite Encoder (index 0): CW = forward, CCW = backward
    - Guarded Toggle (index 8) + Big Button (index 0): fire Emergency Flare
"""

import asyncio
import random

from adafruit_ticks import ticks_ms, ticks_diff

from utilities.palette import Palette
from utilities import tones

from .game_mode import GameMode

# ---------------------------------------------------------------------------
# Hardware indices
# ---------------------------------------------------------------------------
_BTN_BACKWARD  = 0      # B1 – drive rover backward
_BTN_FORWARD   = 1      # B2 – drive rover forward
_BTN_FLARE     = 2      # B3 – fire Emergency Flare (core-only)
_ENC_CORE      = 0      # Core encoder index → rotate facing direction
_ENC_SAT       = 0      # Satellite encoder index → drive forward/backward
_SW_ARM        = 8      # Satellite guarded toggle → arm flare
_BTN_SAT_FLARE = 0      # Satellite big button → fire flare

# ---------------------------------------------------------------------------
# World / maze constants
# ---------------------------------------------------------------------------
_VIEWPORT_RADIUS = 2    # Half-size of lit viewport → 2 gives a 5×5 window
_MATRIX_CENTER_X = 7    # Centre column on 16×16 matrix (0-indexed)
_MATRIX_CENTER_Y = 7    # Centre row on 16×16 matrix (0-indexed)
_MATRIX_W        = 16
_MATRIX_H        = 16

_MAX_FLARES      = 3    # Emergency flare uses allowed per game
_FLARE_DURATION  = 1.0  # Seconds the full maze overview is visible
_MOVE_COOLDOWN_MS = 150 # Minimum ms between movement steps

# ---------------------------------------------------------------------------
# Difficulty tuning table
# ---------------------------------------------------------------------------
_DIFF_PARAMS = {
    "NORMAL": {"world": 25},   # 12×12-room maze  (25×25 pixel world)
    "HARD":   {"world": 31},   # 15×15-room maze  (31×31 pixel world)
    "INSANE": {"world": 37},   # 18×18-room maze  (37×37 pixel world)
}

# ---------------------------------------------------------------------------
# Phase identifiers
# ---------------------------------------------------------------------------
_PHASE_NAVIGATE = "NAVIGATE"
_PHASE_FLARE    = "FLARE"

# ---------------------------------------------------------------------------
# Direction constants: N, E, S, W
# ---------------------------------------------------------------------------
_DIRECTIONS = [(0, -1), (1, 0), (0, 1), (-1, 0)]
_DIR_NAMES  = ["N", "E", "S", "W"]

# ---------------------------------------------------------------------------
# Palette colours used in rendering
# ---------------------------------------------------------------------------
_COL_WALL        = Palette.OFF       # Wall cell inside viewport: black
_COL_PASSAGE     = Palette.TEAL      # Open cell inside viewport: dim teal
_COL_ROVER       = Palette.CYAN      # Rover cell: bright cyan
_COL_EXIT        = Palette.GOLD      # Exit cell: gold
_COL_FLARE_WALL  = Palette.CHARCOAL  # Wall during flare overview: charcoal
_COL_FLARE_PASS  = Palette.NAVY      # Open cell during flare overview: navy
_COL_FLARE_ROVER = Palette.GREEN     # Rover during flare overview: green
_COL_FLARE_EXIT  = Palette.GOLD      # Exit during flare overview: gold


class AbyssalRover(GameMode):
    """Abyssal Rover – blind maze-navigation game.

    The player steers a rover through a procedurally generated maze using
    only a tiny 5×5 viewport and an OLED sonar reading for spatial awareness.
    Emergency Flares (3 per game) reveal the full maze for exactly one second.

    Can be played on Core alone; connecting an Industrial Satellite unlocks
    an additional 14-segment distance display and satellite encoder driving.
    """

    def __init__(self, core):
        super().__init__(core, "ABYSSAL ROVER", "Blind Maze Navigation")

        # Find the first Industrial satellite (optional)
        self.sat = None
        for sat in self.core.satellites.values():
            if sat.sat_type_name == "INDUSTRIAL":
                self.sat = sat
                break

        # Maze state
        self._world = None
        self._world_size = 0

        # Rover state
        self._rover_x = 1
        self._rover_y = 1
        self._facing = 0   # 0=N, 1=E, 2=S, 3=W

        # Flare state
        self._flares_remaining = _MAX_FLARES
        self._phase = _PHASE_NAVIGATE

        # Input tracking
        self._last_encoder_pos = 0
        self._last_sat_enc_pos = 0
        self._last_move_ms = 0
        self._last_sat_flare_btn = False

    # -----------------------------------------------------------------------
    # Maze generation
    # -----------------------------------------------------------------------

    def _generate_maze(self, world_size):
        """Generate a perfect maze using iterative DFS (memory-safe).

        The world is ``world_size × world_size`` pixels.  Rooms sit at
        odd-indexed positions; the cells between them are walls (even indices).
        Returns a ``bytearray``: 0 = wall, 1 = open passage.

        Uses bytearrays for the visited flags and stack to keep heap pressure
        low on CircuitPython.
        """
        world = bytearray(world_size * world_size)  # all walls initially
        rooms = world_size // 2                     # rooms per axis

        def to_world(rx, ry):
            """Convert room-grid coordinates to world-pixel coordinates."""
            return rx * 2 + 1, ry * 2 + 1

        def idx(wx, wy):
            return wy * world_size + wx

        visited = bytearray(rooms * rooms)

        # Stack stored as a flat bytearray (rx, ry) pairs – avoids Python list
        # allocation overhead on CircuitPython.
        stack_buf = bytearray(rooms * rooms * 2)
        stack_top = 0

        # Open the starting room (room 0,0 → world pixel 1,1)
        visited[0] = 1
        sx, sy = to_world(0, 0)
        world[idx(sx, sy)] = 1
        stack_buf[0] = 0
        stack_buf[1] = 0
        stack_top = 1

        dir_indices = [0, 1, 2, 3]  # reused list for direction shuffling

        while stack_top > 0:
            # Peek at the top of the stack
            rx = stack_buf[(stack_top - 1) * 2]
            ry = stack_buf[(stack_top - 1) * 2 + 1]

            # Shuffle directions (Fisher-Yates) to get random maze topology
            for i in range(3, 0, -1):
                j = random.randint(0, i)
                dir_indices[i], dir_indices[j] = dir_indices[j], dir_indices[i]

            found = False
            for d in dir_indices:
                ddx, ddy = _DIRECTIONS[d]
                nrx = rx + ddx
                nry = ry + ddy
                if (0 <= nrx < rooms and 0 <= nry < rooms
                        and visited[nry * rooms + nrx] == 0):
                    # Carve through the wall between current room and neighbour
                    cwx, cwy = to_world(rx, ry)
                    nwx, nwy = to_world(nrx, nry)
                    world[idx(cwx + ddx, cwy + ddy)] = 1   # wall between
                    world[idx(nwx, nwy)] = 1               # neighbour room

                    visited[nry * rooms + nrx] = 1
                    stack_buf[stack_top * 2]     = nrx
                    stack_buf[stack_top * 2 + 1] = nry
                    stack_top += 1
                    found = True
                    break

            if not found:
                stack_top -= 1

        return world

    # -----------------------------------------------------------------------
    # World queries
    # -----------------------------------------------------------------------

    def _world_at(self, wx, wy):
        """Return 1 if ``(wx, wy)`` is an open cell; 0 if wall or out of bounds."""
        if 0 <= wx < self._world_size and 0 <= wy < self._world_size:
            return self._world[wy * self._world_size + wx]
        return 0  # treat out-of-bounds as wall

    def _distance_to_wall(self):
        """Return the number of open cells in the facing direction before hitting a wall."""
        ddx, ddy = _DIRECTIONS[self._facing]
        dist = 0
        wx = self._rover_x + ddx
        wy = self._rover_y + ddy
        while self._world_at(wx, wy) == 1:
            dist += 1
            wx += ddx
            wy += ddy
        return dist

    # -----------------------------------------------------------------------
    # Movement
    # -----------------------------------------------------------------------

    def _try_move(self, forward=True):
        """Attempt to move the rover one cell. Returns ``True`` on success."""
        if forward:
            ddx, ddy = _DIRECTIONS[self._facing]
        else:
            backward_facing = (self._facing + 2) % 4
            ddx, ddy = _DIRECTIONS[backward_facing]

        nx = self._rover_x + ddx
        ny = self._rover_y + ddy

        if self._world_at(nx, ny) == 1:
            self._rover_x = nx
            self._rover_y = ny
            return True
        return False

    # -----------------------------------------------------------------------
    # Rendering
    # -----------------------------------------------------------------------

    def _render_viewport(self):
        """Render the 5×5 lit viewport centered on the rover to the LED matrix.

        All matrix pixels outside the viewport are left dark.
        A single 'nose' indicator pixel (yellow) marks the facing direction.
        """
        r        = _VIEWPORT_RADIUS
        cx, cy   = _MATRIX_CENTER_X, _MATRIX_CENTER_Y
        ws       = self._world_size
        exit_wx  = ws - 2
        exit_wy  = ws - 2

        self.core.matrix.clear()

        for vdy in range(-r, r + 1):
            for vdx in range(-r, r + 1):
                mx = cx + vdx
                my = cy + vdy
                wx = self._rover_x + vdx
                wy = self._rover_y + vdy

                if not (0 <= mx < _MATRIX_W and 0 <= my < _MATRIX_H):
                    continue

                if vdx == 0 and vdy == 0:
                    color = _COL_ROVER
                elif wx == exit_wx and wy == exit_wy:
                    color = _COL_EXIT
                elif self._world_at(wx, wy) == 1:
                    color = _COL_PASSAGE
                else:
                    color = _COL_WALL

                if color != Palette.OFF:
                    self.core.matrix.draw_pixel(mx, my, color)

        # Draw a single 'nose' pixel to show the rover's facing direction.
        # Uses separate variables so the loop variables above are not shadowed.
        ndx, ndy = _DIRECTIONS[self._facing]
        nose_mx  = _MATRIX_CENTER_X + ndx
        nose_my  = _MATRIX_CENTER_Y + ndy
        if 0 <= nose_mx < _MATRIX_W and 0 <= nose_my < _MATRIX_H:
            self.core.matrix.draw_pixel(nose_mx, nose_my, Palette.YELLOW)

    def _render_flare(self):
        """Scale the entire maze to 16×16 and render it (flare overview)."""
        ws      = self._world_size
        exit_wx = ws - 2
        exit_wy = ws - 2

        for my in range(_MATRIX_H):
            for mx in range(_MATRIX_W):
                # Nearest-neighbour sample from world
                wx = mx * ws // _MATRIX_W
                wy = my * ws // _MATRIX_H

                if wx == self._rover_x and wy == self._rover_y:
                    color = _COL_FLARE_ROVER
                elif wx == exit_wx and wy == exit_wy:
                    color = _COL_FLARE_EXIT
                elif self._world_at(wx, wy) == 1:
                    color = _COL_FLARE_PASS
                else:
                    color = _COL_FLARE_WALL

                if color != Palette.OFF:
                    self.core.matrix.draw_pixel(mx, my, color)

    # -----------------------------------------------------------------------
    # Display helpers
    # -----------------------------------------------------------------------

    def _update_oled(self):
        """Refresh the OLED with current sonar reading."""
        dist     = self._distance_to_wall()
        dir_name = _DIR_NAMES[self._facing]
        self.core.display.update_status(
            f"SONAR {dir_name}: {dist:>2d} CELLS",
            f"FLARES: {self._flares_remaining}/{_MAX_FLARES}"
        )

    def _send_segment(self, text):
        """Send a short string to the satellite 14-segment display (safe)."""
        if self.sat:
            try:
                self.sat.send("DSP", text[:8])
            except Exception:  # noqa: BLE001
                pass

    def _update_segment(self):
        """Refresh the satellite 14-segment display with distance info."""
        if self.sat:
            dist     = self._distance_to_wall()
            dir_name = _DIR_NAMES[self._facing]
            self._send_segment(f"{dir_name}   {dist:>3d}")

    # -----------------------------------------------------------------------
    # Satellite input helpers
    # -----------------------------------------------------------------------

    def _sat_button(self, btn_idx=0):
        """Return ``True`` if the satellite button at *btn_idx* is pressed."""
        if not self.sat:
            return False
        try:
            return bool(self.sat.hid.buttons_values[btn_idx])
        except (IndexError, AttributeError):
            return False

    def _sat_latching(self, toggle_idx):
        """Return the state of a satellite latching toggle (safe fallback)."""
        if not self.sat:
            return False
        try:
            return bool(self.sat.hid.latching_values[toggle_idx])
        except (IndexError, AttributeError):
            return False

    def _sat_encoder(self):
        """Return the current satellite encoder position."""
        if not self.sat:
            return 0
        try:
            return self.sat.hid.encoder_positions[_ENC_SAT]
        except (IndexError, AttributeError):
            return 0

    # -----------------------------------------------------------------------
    # Flare mechanic
    # -----------------------------------------------------------------------

    async def _fire_flare(self):
        """Deploy a flare: reveal the full maze overview for ``_FLARE_DURATION`` seconds."""
        if self._flares_remaining <= 0:
            self.core.buzzer.play_sequence(tones.ERROR)
            return

        self._flares_remaining -= 1
        self._phase = _PHASE_FLARE

        self.core.display.update_status(
            "!! FLARE DEPLOYED !!",
            f"FLARES LEFT: {self._flares_remaining}"
        )
        self._send_segment(f"FLARE {self._flares_remaining}")

        asyncio.create_task(
            self.core.audio.play(
                "audio/general/flare.wav",
                self.core.audio.CH_SFX,
                interrupt=True
            )
        )

        self.core.matrix.clear()
        self._render_flare()
        self.core.matrix.show_frame()

        await asyncio.sleep(_FLARE_DURATION)

        self._phase = _PHASE_NAVIGATE

    # -----------------------------------------------------------------------
    # Tutorial
    # -----------------------------------------------------------------------

    async def run_tutorial(self):
        """
        A guided, non-interactive demonstration of Abyssal Rover.

        The Voiceover Script (audio/tutes/rover_tute.wav) ~ 35 seconds:
            [0:00] "Welcome to Abyssal Rover. You must navigate a dark maze in complete blindness."
            [0:05] "The small illuminated window shows only the five cells immediately around you."
            [0:10] "Rotate the dial to change your facing direction. North, East, South, or West."
            [0:15] "Press B2 to drive forward. Press B1 to reverse."
            [0:20] "Your OLED sonar displays the distance to the nearest wall ahead."
            [0:25] "Use your three Emergency Flares wisely. Each one reveals the full maze for one second."
            [0:30] "Find the golden exit to escape. Good luck."
            [0:35] (End of file)
        """
        await self.core.clean_slate()
        self.game_state = "TUTORIAL"

        tute_audio = asyncio.create_task(
            self.core.audio.play(
                "audio/tutes/rover_tute.wav",
                bus_id=self.core.audio.CH_VOICE
            )
        )

        # Set up a small demo maze for illustration
        self._world_size = _DIFF_PARAMS["NORMAL"]["world"]
        self._world = self._generate_maze(self._world_size)
        self._rover_x = 1
        self._rover_y = 1
        self._facing = 1   # Face EAST for demo
        self._flares_remaining = _MAX_FLARES

        # [0:00 – 0:05] Welcome
        self.core.display.update_status("ABYSSAL ROVER", "BLIND NAVIGATION")
        self.core.matrix.show_icon("ABYSSAL_ROVER", anim_mode="PULSE", speed=2.0)
        await asyncio.sleep(5.0)

        # [0:05 – 0:10] Show viewport concept
        self.core.display.update_status("VIEWPORT", "5x5 ILLUMINATED AREA")
        self._render_viewport()
        self.core.matrix.show_frame()
        await asyncio.sleep(5.0)

        # [0:10 – 0:15] Demonstrate direction change
        self.core.display.update_status("TURN DIAL", "ROTATE FACING")
        for new_facing in [2, 3, 0, 1]:   # S, W, N, E
            self._facing = new_facing
            self._update_oled()
            self._render_viewport()
            self.core.matrix.show_frame()
            self.core.synth.play_note(800.0, "UI_SELECT", duration=0.02)
            await asyncio.sleep(1.2)

        # [0:15 – 0:20] Drive forward a few cells
        self.core.display.update_status("DRIVE FORWARD", "PRESS B2")
        self._facing = 1   # EAST
        for _ in range(3):
            if self._try_move(forward=True):
                self.core.synth.play_note(600.0, "UI_SELECT", duration=0.03)
            self._render_viewport()
            self.core.matrix.show_frame()
            await asyncio.sleep(0.8)

        # [0:20 – 0:25] Show sonar reading
        self._update_oled()
        self.core.display.update_status(
            f"SONAR E: {self._distance_to_wall():>2d} CELLS",
            "DISTANCE TO WALL"
        )
        await asyncio.sleep(5.0)

        # [0:25 – 0:30] Fire a demo flare
        self.core.display.update_status("FIRE FLARE", "B3 – 1 SEC REVEAL")
        await self._fire_flare()
        self._render_viewport()
        self.core.matrix.show_frame()
        await asyncio.sleep(3.0)

        # [0:30 – 0:35] Point at exit
        self.core.display.update_status("FIND THE EXIT", "GOLDEN CELL = ESCAPE")
        await asyncio.sleep(5.0)

        await tute_audio
        await self.core.clean_slate()
        return "TUTORIAL_COMPLETE"

    # -----------------------------------------------------------------------
    # Main game loop
    # -----------------------------------------------------------------------

    async def run(self):
        """Main Abyssal Rover game loop."""

        # --- Setup ---
        self.difficulty = self.core.data.get_setting(
            "ABYSSAL_ROVER", "difficulty", "NORMAL"
        )
        params     = _DIFF_PARAMS.get(self.difficulty, _DIFF_PARAMS["NORMAL"])
        world_size = params["world"]
        self.variant = self.difficulty

        # Loading screen while generating maze
        self.core.display.use_standard_layout()
        self.core.display.update_status("ABYSSAL ROVER", "GENERATING MAZE...")
        self.core.matrix.show_icon("ABYSSAL_ROVER", anim_mode="PULSE", speed=2.0)
        await asyncio.sleep(0.1)

        # Generate maze
        self._world_size = world_size
        self._world      = self._generate_maze(world_size)

        # Place rover at the top-left open cell
        self._rover_x = 1
        self._rover_y = 1
        self._facing  = 0   # Face NORTH initially

        self._flares_remaining = _MAX_FLARES
        self._phase            = _PHASE_NAVIGATE
        self.score             = 0

        # Reset input state
        self.core.hid.reset_encoder(_ENC_CORE)
        self._last_encoder_pos  = 0
        self._last_sat_enc_pos  = self._sat_encoder()
        self._last_move_ms      = ticks_ms()

        # Intro banner
        linked = " | SAT LINKED" if (self.sat and self.sat.is_active) else ""
        self.core.display.update_status(
            "ABYSSAL ROVER",
            f"{self.difficulty}{linked}"
        )
        asyncio.create_task(
            self.core.synth.play_sequence(tones.POWER_UP, patch="SCANNER")
        )
        await asyncio.sleep(2.0)

        # Initial render
        self._render_viewport()
        self.core.matrix.show_frame()
        self._update_oled()
        self._update_segment()

        exit_wx     = world_size - 2
        exit_wy     = world_size - 2
        move_count  = 0
        start_ms    = ticks_ms()

        self._last_sat_flare_btn = False

        # ----------------------------------------------------------------
        # Main loop
        # ----------------------------------------------------------------
        while True:
            now = ticks_ms()

            # 1. Check win condition
            if self._rover_x == exit_wx and self._rover_y == exit_wy:
                elapsed_s = ticks_diff(now, start_ms) / 1000.0
                # Score: base + efficiency bonus (fewer moves is better)
                efficiency_bonus = max(0, 2000 - move_count * 5)
                time_bonus       = max(0, 500 - int(elapsed_s * 2))
                self.score       = 1000 + efficiency_bonus + time_bonus

                self.core.display.update_status(
                    f"EXIT FOUND! SCORE: {self.score}",
                    f"MOVES: {move_count}  TIME: {int(elapsed_s)}s"
                )
                self.core.matrix.show_icon("SUCCESS", anim_mode="PULSE", speed=3.0)
                self.core.matrix.show_frame()
                await asyncio.sleep(1.0)
                return await self.victory()

            # 2. Skip input during flare reveal phase
            if self._phase == _PHASE_FLARE:
                await asyncio.sleep(0.016)
                continue

            # 3. Direction control via Core encoder
            enc_now   = self.core.hid.encoder_positions[_ENC_CORE]
            enc_delta = enc_now - self._last_encoder_pos
            if enc_delta != 0:
                if enc_delta > 0:
                    self._facing = (self._facing + 1) % 4
                else:
                    self._facing = (self._facing - 1) % 4
                self._last_encoder_pos = enc_now
                self._update_oled()
                self._update_segment()
                self.core.synth.play_note(800.0, "UI_SELECT", duration=0.02)
                self._render_viewport()
                self.core.matrix.show_frame()

            # 4. Movement control
            moved    = False
            can_move = ticks_diff(now, self._last_move_ms) >= _MOVE_COOLDOWN_MS

            if can_move:
                b_forward  = self.core.hid.is_button_pressed(_BTN_FORWARD,  action="tap")
                b_backward = self.core.hid.is_button_pressed(_BTN_BACKWARD, action="tap")

                # Satellite encoder: CW delta = forward, CCW delta = backward
                sat_enc_now   = self._sat_encoder()
                sat_enc_delta = sat_enc_now - self._last_sat_enc_pos
                if sat_enc_delta >= 1:
                    b_forward  = True
                    self._last_sat_enc_pos = sat_enc_now
                elif sat_enc_delta <= -1:
                    b_backward = True
                    self._last_sat_enc_pos = sat_enc_now

                if b_forward:
                    if self._try_move(forward=True):
                        moved = True
                        move_count += 1
                        self._last_move_ms = now
                        self.core.synth.play_note(600.0, "UI_SELECT", duration=0.03)
                    else:
                        self.core.buzzer.play_sequence(tones.ERROR)
                elif b_backward:
                    if self._try_move(forward=False):
                        moved = True
                        move_count += 1
                        self._last_move_ms = now
                        self.core.synth.play_note(400.0, "UI_SELECT", duration=0.03)
                    else:
                        self.core.buzzer.play_sequence(tones.ERROR)

            # 5. Flare control
            b_flare = self.core.hid.is_button_pressed(_BTN_FLARE, action="tap")

            # Satellite: guarded arm toggle + big button (with edge detection)
            sat_flare_now = self._sat_button(_BTN_SAT_FLARE)
            if self._sat_latching(_SW_ARM) and sat_flare_now and not self._last_sat_flare_btn:
                b_flare = True
            self._last_sat_flare_btn = sat_flare_now

            if b_flare:
                if self._flares_remaining > 0:
                    await self._fire_flare()
                    # Re-render viewport after flare
                    self._render_viewport()
                    self.core.matrix.show_frame()
                    self._update_oled()
                    self._update_segment()
                else:
                    self.core.buzzer.play_sequence(tones.ERROR)

            # 6. Render if rover moved
            elif moved:
                self._render_viewport()
                self.core.matrix.show_frame()
                self._update_oled()
                self._update_segment()

            await asyncio.sleep(0.016)  # ~60 fps polling
