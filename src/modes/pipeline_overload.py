"""Pipeline Overload – Rapid-fire Pipe Routing Puzzle.

The player must guide volatile fluid from the top of the 16×16 LED matrix
to the bottom by flipping the 8 physical latching toggles on the Industrial
Satellite to open the correct pipe junctions before the fluid arrives.

Hardware Mapping
----------------
Core:
    - 16×16 Matrix: descending fluid blob traversing a generated pipe maze
    - OLED: score, current level, flow speed
    - Rotary Encoder (index 0): turn to increase fluid flow speed for a score
      multiplier (releasing speed reduces it)

Industrial Satellite (SAT-01):
    - 8× Latching Toggles (0-7): one per column section
      Toggle N controls the valve junction in matrix columns 2N … 2N+1.
      Toggle UP (ON)  → junction bends the pipe to the RIGHT.
      Toggle DOWN (OFF) → junction bends the pipe to the LEFT.

Gameplay
--------
1. A pipe maze is generated with a series of junction rows spaced down the
   matrix.  The correct toggle pattern to route the fluid safely to the
   bottom is unique to every generated level.
2. Fluid descends continuously from the top at the current flow speed.
3. When the fluid reaches a junction row the toggle for that column section
   is sampled:
     • Correct state → fluid routes safely, score awarded.
     • Wrong state   → fluid spills → GAME OVER.
4. Completing a level (fluid exits the bottom) awards bonus points and
   advances to the next, harder level.
5. Turning the rotary encoder clockwise increases flow speed, raising the
   per-junction score multiplier at the cost of less reaction time.
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
_NUM_TOGGLES  = 8   # Latching toggles 0-7 on the Industrial Satellite
_ENC_SPEED    = 0   # Core encoder index for flow speed boost

# ---------------------------------------------------------------------------
# Matrix geometry
# ---------------------------------------------------------------------------
_MATRIX_W     = 16
_MATRIX_H     = 16
_NUM_SECTIONS = 8                        # One section per toggle
_SECTION_W    = _MATRIX_W // _NUM_SECTIONS   # 2 columns per section

# ---------------------------------------------------------------------------
# Fluid physics
# ---------------------------------------------------------------------------
_ENC_SPEED_STEP     = 0.5   # Extra rows/sec per positive encoder step
_MAX_SPEED          = 14.0  # Hard cap (rows/sec)

# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------
_POINTS_PER_JUNCTION = 75   # Base points per correctly routed junction
_POINTS_LEVEL_CLEAR  = 250  # Bonus points for completing a level

# ---------------------------------------------------------------------------
# Difficulty parameters
# ---------------------------------------------------------------------------
_DIFF_PARAMS = {
    "NORMAL": {"junctions": 4, "speed": 3.0},
    "HARD":   {"junctions": 6, "speed": 4.5},
    "INSANE": {"junctions": 8, "speed": 6.5},
}


class PipelineOverload(GameMode):
    """Pipeline Overload: Guide volatile fluid through a dynamic pipe maze.

    Hardware:
        Core:
            - 16×16 Matrix: pipe maze with descending fluid blob
            - OLED: score, level, speed readout
            - Rotary Encoder: turn to increase flow speed (score multiplier)
        Industrial Satellite (SAT-01):
            - 8× Latching Toggles (0-7): pipe valve per column section
    """

    def __init__(self, core):
        super().__init__(core, "PIPELINE OVERLOAD", "Pipe Routing Puzzle")
        self.sat = None
        self.junctions = []       # List of junction dicts for current level
        self.path_segments = []   # Pre-computed correct-path pipe segments
        self.fluid_y = 0.0        # Current fluid row position (float)
        self.fluid_section = 4    # Current fluid column section (0-7)
        self.next_junc_idx = 0    # Index of the next uncleared junction
        self.speed = _DIFF_PARAMS["NORMAL"]["speed"]  # Current flow speed (rows/sec)
        self.base_speed = self.speed                  # Difficulty base speed
        self._trail_history = [] # Tracks (col, row) tuples

    # -----------------------------------------------------------------------
    # Satellite helpers
    # -----------------------------------------------------------------------

    def _init_satellite(self):
        """Find and cache the Industrial Satellite, if present."""
        self.sat = None
        if not hasattr(self.core, 'satellites'):
            return
        for sat in self.core.satellites:
            if sat.sat_type_name == "INDUSTRIAL" and sat.is_active:
                self.sat = sat
                break

    def _toggle_state(self, section):
        """Return the latching toggle state for *section* (True = UP/ON)."""
        if not self.sat:
            return False
        try:
            return bool(self.sat.hid.latching_values[section])
        except (IndexError, AttributeError):
            return False

    # -----------------------------------------------------------------------
    # Maze generation
    # -----------------------------------------------------------------------

    def _generate_maze(self, num_junctions):
        """Generate a solvable pipe maze.

        Returns:
            (junctions, start_section) where *junctions* is a list of dicts:
              - 'row'          : int  – matrix row where the junction occurs
              - 'section'      : int  – fluid section (0-7) at that row
              - 'correct_right': bool – True if toggle ON routes correctly
        """
        junctions = []
        section = random.randint(2, 5)   # Start near the centre
        start_section = section

        if num_junctions == 0:
            return junctions, start_section

        # Space junctions evenly, leaving two rows of margin at top and bottom
        usable_rows = _MATRIX_H - 4
        spacing = max(usable_rows // (num_junctions + 1), 1)

        for i in range(num_junctions):
            row = 2 + (i + 1) * spacing
            if row >= _MATRIX_H - 2:
                break

            # Decide direction, respecting matrix boundaries
            if section == 0:
                go_right = True
            elif section == _NUM_SECTIONS - 1:
                go_right = False
            else:
                go_right = random.choice([True, False])

            junctions.append({
                'row': row,
                'section': section,
                'correct_right': go_right,
            })

            section = max(0, min(
                _NUM_SECTIONS - 1,
                section + (1 if go_right else -1)
            ))

        return junctions, start_section

    def _compute_path_segments(self, start_section):
        """Pre-compute the vertical pipe segments that make up the solution.

        Each segment covers a run of rows in a single column section.
        """
        segments = []
        section = start_section
        prev_row = 0

        for junc in self.junctions:
            segments.append({
                'section': section,
                'row_start': prev_row,
                'row_end': junc['row'],
            })
            prev_row = junc['row']
            section = max(0, min(
                _NUM_SECTIONS - 1,
                junc['section'] + (1 if junc['correct_right'] else -1)
            ))

        # Final segment from the last junction to the bottom
        segments.append({
            'section': section,
            'row_start': prev_row,
            'row_end': _MATRIX_H,
        })
        return segments

    # -----------------------------------------------------------------------
    # Main game loop
    # -----------------------------------------------------------------------

    async def run(self):
        """Outer game loop: manage levels until GAME OVER."""
        self._init_satellite()
        if not self.sat:
            self.core.display.update_status("PIPELINE OVERLOAD", "SAT OFFLINE - ABORT")
            await asyncio.sleep(2)
            return "FAILURE"

        self.difficulty = self.core.data.get_setting(
            "PIPELINE_OVERLOAD", "difficulty", "NORMAL"
        )
        params = _DIFF_PARAMS.get(self.difficulty, _DIFF_PARAMS["NORMAL"])
        self.variant = self.difficulty
        self.base_speed = params["speed"]

        self.score = 0
        self.level = 1

        self.core.display.use_standard_layout()
        self.core.display.update_status("PIPELINE OVERLOAD", "ROUTE THE FLUID!")
        self.core.display.update_footer("DIAL: SPEED BOOST")
        asyncio.create_task(
            self.core.synth.play_sequence(tones.POWER_UP, patch="SCANNER")
        )
        await asyncio.sleep(2.0)

        self.core.hid.reset_encoder(_ENC_SPEED)

        while True:
            # Build this level's maze (more junctions as level increases)
            num_junctions = min(
                params["junctions"] + (self.level - 1),
                _NUM_SECTIONS - 1
            )
            self.junctions, start_section = self._generate_maze(num_junctions)
            self.path_segments = self._compute_path_segments(start_section)

            self.fluid_y = 0.0
            self.fluid_section = start_section
            self.next_junc_idx = 0

            result = await self._run_level()

            if result == "GAME_OVER":
                return await self.game_over()

            # Level cleared
            self.score += _POINTS_LEVEL_CLEAR * self.level
            self.level += 1
            self.core.display.update_status("PIPE CLEARED!", f"SCORE: {self.score}")
            asyncio.create_task(
                self.core.synth.play_sequence(tones.NOTIFY_INBOX, patch="SUCCESS")
            )
            await asyncio.sleep(1.5)

    async def _run_level(self):
        """Run a single level.  Returns ``'GAME_OVER'`` or ``'LEVEL_COMPLETE'``."""
        last_tick = ticks_ms()

        while True:
            now = ticks_ms()
            delta_ms = ticks_diff(now, last_tick)

            if delta_ms >= 16:  # ~60 FPS target
               # NEW: Clamp hardware tracking to prevent wind-up debt
                max_enc = int((_MAX_SPEED - self.base_speed) / _ENC_SPEED_STEP)
                current_enc = self.core.hid.encoder_positions[_ENC_SPEED]

                if current_enc > max_enc:
                    self.core.hid.encoder_positions[_ENC_SPEED] = max_enc
                    current_enc = max_enc
                elif current_enc < 0:
                    self.core.hid.encoder_positions[_ENC_SPEED] = 0
                    current_enc = 0

                self.speed = self.base_speed + current_enc * _ENC_SPEED_STEP

                # Advance fluid
                self.fluid_y += (delta_ms / 1000.0) * self.speed

                # Check whether the fluid has crossed the next junction row
                if self.next_junc_idx < len(self.junctions):
                    junc = self.junctions[self.next_junc_idx]
                    if self.fluid_y >= junc['row']:
                        toggle_on = self._toggle_state(junc['section'])
                        correct = (toggle_on == junc['correct_right'])

                        if correct:
                            speed_mult = 1.0 + enc_pos * 0.1
                            pts = int(_POINTS_PER_JUNCTION * speed_mult)
                            self.score += pts
                            # Route fluid to the next section
                            self.fluid_section = max(0, min(
                                _NUM_SECTIONS - 1,
                                junc['section'] + (1 if junc['correct_right'] else -1)
                            ))
                            self.next_junc_idx += 1
                            self.core.synth.play_note(880.0, "UI_SELECT", duration=0.05)
                        else:
                            # Wrong toggle – fluid spills
                            self.core.matrix.fill(Palette.RED)

                            asyncio.create_task(
                                self.core.synth.play_sequence(tones.GAME_OVER)
                            )
                            await asyncio.sleep(1.0)
                            return "GAME_OVER"

                # Fluid has exited the bottom of the matrix
                if self.fluid_y >= _MATRIX_H:
                    return "LEVEL_COMPLETE"

                # Update HUD
                self.core.display.update_status(
                    f"SCORE: {self.score}",
                    f"LVL:{self.level} SPD:{self.speed:.1f}"
                )

                # Track the fluid path for continuous trail rendering
                current_head = (self.fluid_section * _SECTION_W, int(self.fluid_y))
                if not self._trail_history or self._trail_history[0] != current_head:
                    self._trail_history.insert(0, current_head)
                    if len(self._trail_history) > 3: # Keep head + 2 trail steps
                        self._trail_history.pop()

                # Draw frame
                self._render(now)
                last_tick = now

            await asyncio.sleep(0.01)

    # -----------------------------------------------------------------------
    # Rendering
    # -----------------------------------------------------------------------

    def _render(self, now):
        """Draw the pipe maze, junction states, and the descending fluid blob."""
        self.core.matrix.clear()
        pulse = (now % 500) > 250

        # --- Background: dim vertical pipe for every section ---
        for s in range(_NUM_SECTIONS):
            c = s * _SECTION_W
            for r in range(_MATRIX_H):
                self.core.matrix.draw_pixel(c,     r, Palette.NAVY)
                self.core.matrix.draw_pixel(c + 1, r, Palette.NAVY)

        # --- Correct solution path (TEAL vertical segments) ---
        for seg in self.path_segments:
            s = seg['section']
            c = s * _SECTION_W
            for r in range(seg['row_start'], min(seg['row_end'], _MATRIX_H)):
                self.core.matrix.draw_pixel(c,     r, Palette.TEAL)
                self.core.matrix.draw_pixel(c + 1, r, Palette.TEAL)

        # --- Junction connectors (coloured by toggle correctness) ---
        fluid_row = int(self.fluid_y)

        for i, junc in enumerate(self.junctions):
            jsec  = junc['section']
            jrow  = junc['row']
            go_right = junc['correct_right']

            toggle_on = self._toggle_state(jsec)
            correct   = (toggle_on == go_right)

            # Choose indicator colour
            if i == self.next_junc_idx:
                # Active upcoming junction – warn/confirm based on toggle state
                approaching = (fluid_row >= jrow - 4)
                if approaching:
                    color = (Palette.LIME if pulse else Palette.GREEN) if correct \
                            else (Palette.ORANGE if pulse else Palette.RED)
                else:
                    color = Palette.CYAN if correct else Palette.ORANGE
            elif i < self.next_junc_idx:
                color = Palette.TEAL   # Already cleared
            else:
                color = Palette.TEAL   # Future junction

            # Draw horizontal connector in the direction the toggle currently routes
            target_sec = max(0, min(
                _NUM_SECTIONS - 1,
                jsec + (1 if toggle_on else -1)
            ))
            min_sec = min(jsec, target_sec)
            max_sec = max(jsec, target_sec)
            for sc in range(min_sec, max_sec + 1):
                c = sc * _SECTION_W
                self.core.matrix.draw_pixel(c,     jrow, color)
                self.core.matrix.draw_pixel(c + 1, jrow, color)

            # Draw one row of exit pipe below the junction
            if jrow + 1 < _MATRIX_H:
                tc = target_sec * _SECTION_W
                self.core.matrix.draw_pixel(tc,     jrow + 1, color)
                self.core.matrix.draw_pixel(tc + 1, jrow + 1, color)

        # --- Fluid blob and trailing path ---
        for i, (f_col, f_row) in enumerate(self._trail_history):
            if 0 <= f_row < _MATRIX_H:
                if i == 0: # The Head
                    fluid_color = Palette.WHITE if pulse else Palette.GOLD
                else:      # The Trail
                    fluid_color = Palette.ORANGE

                self.core.matrix.draw_pixel(f_col,     f_row, fluid_color)
                self.core.matrix.draw_pixel(f_col + 1, f_row, fluid_color)



    # -----------------------------------------------------------------------
    # Tutorial
    # -----------------------------------------------------------------------

    async def run_tutorial(self):
        """Guided demonstration of Pipeline Overload mechanics.

        Voiceover script (audio/tutes/pipeline_tute.wav) ~30 seconds:
            [0:00] "Welcome to Pipeline Overload."
            [0:03] "Volatile fluid is falling through the pipe maze on the
                    screen."
            [0:07] "Each of the eight latching toggles controls one column
                    section of the matrix."
            [0:12] "When the fluid reaches a junction, the toggle for that
                    section determines whether it bends left or right."
            [0:18] "If the junction is set incorrectly the fluid will spill –
                    game over."
            [0:22] "Watch for the flashing junction indicator.  Green means
                    the toggle is correct; orange means you need to flip it."
            [0:27] "Turn the dial to speed up the flow for a score multiplier
                    – if you're feeling brave!"
            [0:30] (End of file)
        """
        await self.core.clean_slate()
        self.game_state = "TUTORIAL"

        self.core.audio.play(
            "audio/tutes/pipeline_tute.wav",
            bus_id=self.core.audio.CH_VOICE,
        )

        self._init_satellite()

        # Hardcode a simple three-junction demo maze
        self.junctions = [
            {'row': 4,  'section': 4, 'correct_right': False},
            {'row': 8,  'section': 3, 'correct_right': True},
            {'row': 12, 'section': 4, 'correct_right': False},
        ]
        start_section = 4
        self.path_segments = self._compute_path_segments(start_section)
        self.fluid_y = 0.0
        self.fluid_section = start_section
        self.next_junc_idx = 0
        self.speed = 2.5

        # [0:00 – 0:07] Introduction: show the static maze
        self.core.display.update_status("PIPELINE OVERLOAD", "ROUTE THE FLUID!")
        self._render(ticks_ms())
        await asyncio.sleep(7.0)

        # [0:07 – 0:12] Scroll fluid down toward first junction
        self.core.display.update_status("FLUID DESCENDS", "DOWN THE PIPE!")
        for _ in range(150):
            self.fluid_y = min(self.fluid_y + 0.025, 3.0)
            self._render(ticks_ms())
            await asyncio.sleep(0.016)

        # [0:12 – 0:18] Flash all four CORE LEDs to draw attention to the toggles
        self.core.display.update_status("JUNCTION AHEAD!", "FLIP THE TOGGLE!")
        for i in range(4):
            self.core.leds.flash_led(i, Palette.CYAN, duration=0.4)
        await asyncio.sleep(4.0)

        # [0:18 – 0:22] Show a "wrong toggle" flash (matrix red)
        self.core.display.update_status("WRONG TOGGLE!", "FLUID SPILLS!")
        self.core.matrix.fill(Palette.RED)

        asyncio.create_task(self.core.buzzer.play_sequence(tones.UI_ERROR))
        await asyncio.sleep(2.0)

        # Restore maze display
        self.fluid_y = 1.0
        self._render(ticks_ms())

        # [0:22 – 0:27] Explain colour coding
        self.core.display.update_status("GREEN = CORRECT", "ORANGE = FLIP IT!")
        await asyncio.sleep(4.0)

        # [0:27 – 0:30] Speed dial hint
        self.core.display.update_status("SPEED DIAL", "TURN FOR BONUS!")
        await asyncio.sleep(3.0)

        await self.core.clean_slate()
        return "TUTORIAL_COMPLETE"
