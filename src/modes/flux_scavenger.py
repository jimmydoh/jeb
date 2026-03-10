"""Flux Scavenger – Dial-Scrubbing Puzzle Platformer.

A precision puzzle-platformer where the player "scrubs" through levels using
the physical hardware as a hacker's toolkit.  One encoder click moves the
character exactly one pixel, giving microscopic, hyper-precise edge-walking.

Hardware (CORE + INDUSTRIAL Satellite):
    Core:
        - 16×16 Matrix:   Level display (1 pixel = 1 game unit)
        - OLED:           Level info, gravity mode, toggle state
        - Rotary Encoder: Lateral scrubbing (1 click = 1 pixel)
        - Button 0:       Jump / push-off (direction follows gravity)

    Industrial Satellite (SAT-01):
        - 8× Latching Toggles (0-7): Circuit-breaker environment hacks
            Even indices  (0, 2, 4, 6) → activate solid platforms
            Odd indices   (1, 3, 5, 7) → activate hazard fields
        - 3-Position Rotary Switch (latch indices 10 / 11): Gravity mode
            Neither active  → NORMAL   (floor gravity, pulls down)
            Latch-10 only   → ZERO_G   (near-weightless slow float)
            Latch-11 (or both) → CEILING (inverted gravity, pulls up)
        - Momentary Toggle 0 direction UP: Time Rewind
            Hold to scrub backward through the last ~3 s of state
"""

import asyncio
import math

from adafruit_ticks import ticks_ms, ticks_diff

from utilities.palette import Palette
from utilities import tones

from .game_mode import GameMode

# ---------------------------------------------------------------------------
# Hardware indices (Industrial Satellite SAT-01)
# ---------------------------------------------------------------------------
_SW_ROTARY_A = 10    # 3-pos rotary: index A
_SW_ROTARY_B = 11    # 3-pos rotary: index B
_MT_REWIND   = 0     # Momentary toggle index (UP = rewind)
_BTN_JUMP    = 0     # Core button 0 = Jump
_ENC_MOVE    = 0     # Core encoder 0 = lateral movement

# ---------------------------------------------------------------------------
# Gravity mode identifiers
# ---------------------------------------------------------------------------
GRAV_NORMAL  = "NORMAL"    # rot neither → floor gravity (vy increases down)
GRAV_ZERO_G  = "ZERO_G"    # rot-A only  → near-weightless
GRAV_CEILING = "CEILING"   # rot-B (or both) → ceiling gravity (vy increases up)

# ---------------------------------------------------------------------------
# Tile type constants  (stored in 256-element level tuples)
# ---------------------------------------------------------------------------
T_EMPTY   = 0    # Open air
T_SOLID   = 1    # Static gray platform / wall
T_CYN_SOL = 2    # Toggle-0 activated solid   (Cyan bridge)
T_RED_HAZ = 3    # Toggle-1 activated hazard  (Red laser field)
T_BLU_SOL = 4    # Toggle-2 activated solid   (Blue platform)
T_ORG_HAZ = 5    # Toggle-3 activated hazard  (Orange fire floor)
T_GRN_SOL = 6    # Toggle-4 activated solid   (Green scaffold)
T_YEL_HAZ = 7    # Toggle-5 activated hazard  (Yellow voltage spike)
T_MAG_SOL = 8    # Toggle-6 activated solid   (Magenta barrier)
T_WHT_HAZ = 9    # Toggle-7 activated hazard  (White electricity)
T_GOAL    = 10   # Exit / goal pixel

# Tile → (toggle_index, is_hazard)
_TILE_TOGGLE_MAP = {
    T_CYN_SOL: (0, False),
    T_RED_HAZ: (1, True),
    T_BLU_SOL: (2, False),
    T_ORG_HAZ: (3, True),
    T_GRN_SOL: (4, False),
    T_YEL_HAZ: (5, True),
    T_MAG_SOL: (6, False),
    T_WHT_HAZ: (7, True),
}

# Tile → display colour (Color objects from Palette)
_TILE_COLOR = {
    T_EMPTY:   Palette.OFF,
    T_SOLID:   Palette.GRAY,
    T_CYN_SOL: Palette.CYAN,
    T_RED_HAZ: Palette.LASER,
    T_BLU_SOL: Palette.BLUE,
    T_ORG_HAZ: Palette.ORANGE,
    T_GRN_SOL: Palette.GREEN,
    T_YEL_HAZ: Palette.YELLOW,
    T_MAG_SOL: Palette.MAGENTA,
    T_WHT_HAZ: Palette.WHITE,
    T_GOAL:    Palette.GOLD,
}

# Toggle index → display colour (derived from _TILE_TOGGLE_MAP + _TILE_COLOR)
_TOGGLE_LED_COLOR = {
    toggle_idx: _TILE_COLOR[tile_type]
    for tile_type, (toggle_idx, _) in _TILE_TOGGLE_MAP.items()
}

# ---------------------------------------------------------------------------
# Physics constants  (units: pixels, frames at ~30 fps)
# ---------------------------------------------------------------------------
_GRAV_NORMAL   =  0.18   # px / frame² – pulls downward (increasing y)
_GRAV_ZERO_G   =  0.02   # px / frame² – near-weightless drift
_GRAV_CEILING  = -0.18   # px / frame² – pulls upward (decreasing y)

_JUMP_FLOOR    = -1.6    # vy impulse when jumping from a floor surface
_JUMP_CEILING  =  1.6    # vy impulse when pushing off from a ceiling surface
_JUMP_ZERO_G   = -0.9    # vy impulse in zero-G mode (gentle upward nudge)

_MAX_FALL_SPEED = 2.5    # maximum |vy| in px / frame

# ---------------------------------------------------------------------------
# Time-rewind history buffer
# ---------------------------------------------------------------------------
_HISTORY_LEN = 90   # ~3 s of history at 30 fps; each entry = [px, py, vy]

# ---------------------------------------------------------------------------
# Level data – 3 puzzles, each a 256-element tuple (row-major, 16 × 16)
# ---------------------------------------------------------------------------
#
# Tile legend:
#   0 = empty    1 = static solid    2 = cyan-platform (toggle 0)
#   3 = red-haz  4 = blue-platform   5 = orange-haz    6 = green-platform
#   7 = yellow   8 = magenta-wall    9 = white-haz     10 = goal
#
# ── Level 1 ─── "WIRE TAP" ──────────────────────────────────────────────────
#
# Intro puzzle: encoder walk + one toggle (cyan bridge) + red laser avoidance.
# Player starts at (1, 14).  Goal at (13, 1).
#
# Puzzle solution:
#   • Toggle-0 ON  → cyan bridge at row 6, cols 1-9 appears (safe crossing)
#   • Toggle-1 OFF → red laser field at row 4, cols 7-9 stays dormant
#   • Walk right using the encoder to reach the ascending staircase, climb to
#     platform at row 2, then reach the goal.
#
_LV1 = (
    # x: 0  1  2  3  4  5  6  7  8  9 10 11 12 13 14 15
       1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,  # y=0  ceiling
       1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,10, 0, 1,  # y=1  goal@13
       1, 0, 0, 0, 0, 0, 0, 1, 1, 0, 0, 0, 1, 1, 0, 1,  # y=2  platforms@7-8,12-13
       1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1,  # y=3
       1, 0, 0, 0, 0, 0, 0, 3, 3, 3, 0, 0, 0, 0, 0, 1,  # y=4  red-haz@7-9 [t1]
       1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1,  # y=5
       1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 0, 0, 0, 0, 0, 1,  # y=6  cyan bridge@1-9 [t0]
       1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 1,  # y=7  step@12
       1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1,  # y=8
       1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 0, 0, 1,  # y=9  step@11-12
       1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1,  # y=10
       1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 0, 0, 0, 1,  # y=11 step@10-11
       1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1,  # y=12
       1, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 0, 0, 0, 0, 1,  # y=13 step@9-10
       1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1,  # y=14 player starts here
       1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,  # y=15 floor
)
_LV1_START = (1, 14)

# ── Level 2 ─── "FLUX INVERSION" ────────────────────────────────────────────
#
# Introduces ceiling gravity and two interacting toggles.
# Player starts at (1, 14).  Goal at (14, 2).
#
# Puzzle solution:
#   • Toggle-3 OFF  → orange fire floor at row 6 stays dormant
#   • Switch to CEILING gravity → player "falls" upward to ceiling (row 0)
#   • Toggle-2 ON   → blue platforms at row 3 cols 1-5 and row 4 cols 12-14
#   • Walk along ceiling to above the goal, switch back to NORMAL, drop down
#   • Land on blue platform at row 4 cols 12-14, reach goal at (14, 2)
#
_LV2 = (
    # x: 0  1  2  3  4  5  6  7  8  9 10 11 12 13 14 15
       1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,  # y=0  ceiling
       1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1,  # y=1
       1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,10, 1,  # y=2  goal@14
       1, 4, 4, 4, 4, 4, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1,  # y=3  blue-platform@1-5 [t2]
       1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 4, 4, 4, 1,  # y=4  blue-platform@12-14 [t2]
       1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1,  # y=5
       1, 5, 5, 5, 5, 5, 5, 5, 5, 0, 0, 0, 0, 0, 0, 1,  # y=6  orange-haz@1-8 [t3]
       1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1,  # y=7
       1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 1,  # y=8  step@13
       1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 0, 0, 1,  # y=9  step@11-12
       1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1,  # y=10
       1, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 0, 0, 0, 0, 1,  # y=11 step@9-10
       1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1,  # y=12
       1, 0, 0, 0, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 1,  # y=13 platform@4-7
       1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1,  # y=14 player starts here
       1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,  # y=15 floor
)
_LV2_START = (1, 14)

# ── Level 3 ─── "CIRCUIT ZERO" ──────────────────────────────────────────────
#
# Full challenge: all 8 toggles, all 3 gravity modes, zero-G traversal.
# Player starts at (1, 14).  Goal at (14, 2).
#
# Puzzle solution hint:
#   • Toggle-0 ON  → cyan bridge at row 6, cols 1-5
#   • Toggle-1 OFF → red laser at row 4, cols 7-9 stays dormant
#   • Toggle-6 ON  → magenta wall at row 8, cols 10-11 blocks right path
#     (must use ZERO_G to float over it)
#   • Toggle-7 OFF → white electricity at row 7, cols 7-9 off
#   • Toggle-2 ON  → blue scaffold at row 7, cols 12-14 appears
#   • Toggle-4 ON  → green scaffold at row 3, cols 13-14 gives foothold to goal
#   • Toggle-3 OFF / Toggle-5 OFF → orange and yellow hazards dormant
#
_LV3 = (
    # x: 0  1  2  3  4  5  6  7  8  9 10 11 12 13 14 15
       1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,  # y=0  ceiling
       1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1,  # y=1
       1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,10, 1,  # y=2  goal@14
       1, 0, 7, 7, 0, 0, 0, 0, 0, 0, 0, 0, 0, 6, 6, 1,  # y=3  yellow@2-3[t5] green@13-14[t4]
       1, 0, 0, 0, 0, 0, 0, 3, 3, 3, 0, 0, 0, 0, 0, 1,  # y=4  red-haz@7-9 [t1]
       1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1,  # y=5
       1, 2, 2, 2, 2, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1,  # y=6  cyan@1-5 [t0]
       1, 0, 0, 0, 0, 0, 0, 9, 9, 9, 0, 0, 4, 4, 4, 1,  # y=7  white@7-9[t7] blue@12-14[t2]
       1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 8, 8, 0, 0, 0, 1,  # y=8  magenta@10-11 [t6]
       1, 0, 0, 0, 0, 0, 5, 5, 5, 0, 0, 0, 0, 0, 0, 1,  # y=9  orange@6-8 [t3]
       1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1,  # y=10
       1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 0, 0, 0, 1,  # y=11 static@10-11
       1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1,  # y=12
       1, 0, 0, 0, 0, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 1,  # y=13 static@5-7
       1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1,  # y=14 player starts here
       1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,  # y=15 floor
)
_LV3_START = (1, 14)

# ---------------------------------------------------------------------------
# Level catalogue
# ---------------------------------------------------------------------------
_LEVELS = (_LV1, _LV2, _LV3)
_STARTS = (_LV1_START, _LV2_START, _LV3_START)
_LEVEL_NAMES = ("WIRE TAP", "FLUX INVERSION", "CIRCUIT ZERO")


class FluxScavenger(GameMode):
    """Flux Scavenger – Dial-Scrubbing Puzzle Platformer.

    Hardware:
        Core:
            - 16×16 Matrix: Level viewport (1 pixel = 1 game unit)
            - OLED: Level info, gravity mode, toggle bitmask
            - Rotary Encoder: Lateral pixel-scrubbing (1 click = 1 pixel)
            - Button 0: Jump / push-off (direction follows active gravity)

        Industrial Satellite (SAT-01):
            - 8× Latching Toggles (0-7): Environment circuit-breakers
            - 3-Position Rotary Switch (latch 10/11): Gravity mode selector
            - Momentary Toggle 0, direction UP: Time Rewind
    """

    METADATA = {
        "id": "FLUX_SCAVENGER",
        "name": "FLUX SCAVENGER",
        "icon": "FLUX_SCAVENGER",
        "requires": ["CORE", "INDUSTRIAL"],
        "settings": [
            {
                "key": "difficulty",
                "label": "DIFF",
                "options": ["NORMAL", "HARD"],
                "default": "NORMAL",
            }
        ],
    }

    def __init__(self, core):
        super().__init__(core, "FLUX SCAVENGER", "Dial-Scrubbing Puzzle Platformer")
        self.sat = None
        for sat in self.core.satellites.values():
            if sat.sat_type_name == "INDUSTRIAL":
                self.sat = sat
                break

        # Player physics state
        self._px = 1.0    # float x position
        self._py = 14.0   # float y position
        self._vy = 0.0    # vertical velocity (px/frame)

        # Button edge-detection
        self._btn_jump_prev = False

        # Encoder tracking
        self._last_enc = 0

        # Rewind history: list of [px, py, vy], newest at index -1
        self._history = []

        # Blink counter for hazard tiles
        self._tick = 0

    # ------------------------------------------------------------------
    # Tutorial
    # ------------------------------------------------------------------

    async def run_tutorial(self):
        """
        Guided, animated demonstration of Flux Scavenger mechanics.

        The Voiceover Script (audio/tutes/flux_tute.wav) ~34 seconds:
            [0:00] "Welcome to Flux Scavenger. You must reach the golden pixel to escape."
            [0:05] "Turn the core dial to scrub your character left and right. Press button zero to jump."
            [0:12] "The eight toggle switches hack the environment. Flip them to solidify platforms or disable hazards."
            [0:19] "The rotary switch controls gravity. You can walk on the ceiling, or float in zero-G."
            [0:25] "If you make a fatal mistake, hold the momentary switch UP to rewind time."
            [0:31] "Good luck, Scavenger."
            [0:34] (End of file)
        """
        await self.core.clean_slate()

        if not self.sat or not self.sat.is_active:
            self.core.display.update_status("FLUX SCAVENGER", "SAT OFFLINE - ABORT")
            await asyncio.sleep(2)
            return "TUTORIAL_FAILED"

        self.game_state = "TUTORIAL"

        tute_audio = asyncio.create_task(
            self.core.audio.play("audio/tutes/flux_tute.wav", bus_id=self.core.audio.CH_VOICE)
        )

        # Setup mock state using Level 1
        level = _LV1
        self._px = float(_LV1_START[0])
        self._py = float(_LV1_START[1])
        self._vy = 0.0
        toggles = [False] * 8
        grav_mode = GRAV_NORMAL

        self.core.display.use_standard_layout()

        def _refresh(rewinding=False):
            self._render(level, toggles)
            self.core.matrix.show_frame()
            self._update_oled(0, grav_mode, toggles, rewinding)

        # --- [0:00 - 0:05] Welcome ---
        self.core.display.update_status("FLUX SCAVENGER", "REACH THE GOLD PIXEL")
        _refresh()
        await asyncio.sleep(5.0)

        # --- [0:05 - 0:12] Move and Jump ---
        self.core.display.update_status("DIAL = SCRUB", "BUTTON 0 = JUMP")

        # Simulate encoder scrubbing
        for _ in range(8):
            self._px += 0.5
            _refresh()
            self.core.synth.play_note(440.0, "CLICK", duration=0.01)
            await asyncio.sleep(0.15)

        # Simulate jump
        self.core.synth.play_note(660.0, "UI_SELECT", duration=0.05)
        self._vy = _JUMP_FLOOR
        for _ in range(16):
            self._px += 0.2
            self._vy += _GRAV_NORMAL
            self._py += self._vy
            # Floor collision
            if self._py >= 14.0:
                self._py = 14.0
                self._vy = 0.0
            _refresh()
            await asyncio.sleep(0.04)

        await asyncio.sleep(2.0)

        # --- [0:12 - 0:19] Toggles (Hack Environment) ---
        self.core.display.update_status("8 TOGGLES", "HACK ENVIRONMENT")
        await asyncio.sleep(1.0)

        # Flip toggle 0 to activate the Cyan bridge
        toggles[0] = True
        self.core.buzzer.play_sequence(tones.COIN)
        self._update_sat_leds(toggles, True)
        _refresh()
        await asyncio.sleep(5.0)

        # --- [0:19 - 0:25] Gravity Shift ---
        self.core.display.update_status("ROTARY SWITCH", "SHIFT GRAVITY")
        await asyncio.sleep(1.0)

        # Switch to ceiling gravity
        grav_mode = GRAV_CEILING
        self.core.buzzer.play_sequence(tones.UI_TICK)
        self._update_sat_display(0, grav_mode)

        # Simulate falling UP to the ceiling
        self._vy = 0.0
        for _ in range(25):
            self._vy += _GRAV_CEILING
            self._py += self._vy
            # Ceiling collision
            if self._py <= 1.0:
                self._py = 1.0
                self._vy = 0.0
            _refresh()
            await asyncio.sleep(0.04)

        await asyncio.sleep(3.0)

        # --- [0:25 - 0:31] Time Rewind ---
        self.core.display.update_status("MOMENTARY UP", "REWIND TIME!")
        await asyncio.sleep(1.0)

        # Simulate scrubbing backward
        for _ in range(30):
            self._py += 0.43 # Smoothly interpolate back to the floor
            if self._py >= 14.0:
                self._py = 14.0
            _refresh(rewinding=True)
            self.core.synth.play_note(300.0, "UI_SELECT", duration=0.02)
            await asyncio.sleep(0.04)

        grav_mode = GRAV_NORMAL
        _refresh(rewinding=False)
        self._update_sat_display(0, grav_mode)

        # --- [0:31 - 0:34] Outro ---
        self.core.display.update_status("GOOD LUCK", "SCAVENGER")

        if hasattr(self.core.audio, 'wait_for_bus'):
            await self.core.audio.wait_for_bus(self.core.audio.CH_VOICE)
        else:
            await asyncio.sleep(3.0)

        await self.core.clean_slate()
        return "TUTORIAL_COMPLETE"

    # ------------------------------------------------------------------
    # Satellite helpers
    # ------------------------------------------------------------------

    def _read_toggles(self):
        """Return a tuple of 8 booleans for latching toggles 0-7."""
        if not self.sat:
            return (False,) * 8
        try:
            lv = self.sat.hid.latching_values
            return tuple(bool(lv[i]) if i < len(lv) else False for i in range(8))
        except (IndexError, AttributeError):
            return (False,) * 8

    def _get_gravity_mode(self):
        """Read the 3-position rotary switch and return a gravity mode string."""
        if not self.sat:
            return GRAV_NORMAL
        try:
            lv = self.sat.hid.latching_values
            rot_a = bool(lv[_SW_ROTARY_A]) if _SW_ROTARY_A < len(lv) else False
            rot_b = bool(lv[_SW_ROTARY_B]) if _SW_ROTARY_B < len(lv) else False
        except (IndexError, AttributeError):
            return GRAV_NORMAL

        if rot_b:
            return GRAV_CEILING   # latch-11 (or both) → inverted
        if rot_a:
            return GRAV_ZERO_G    # latch-10 only → zero-G
        return GRAV_NORMAL        # neither → normal floor gravity

    def _is_rewinding(self):
        """Return True if the momentary toggle is held UP (time-rewind)."""
        if not self.sat:
            return False
        try:
            return self.sat.hid.is_momentary_toggled(_MT_REWIND, direction="U")
        except (IndexError, AttributeError):
            return False

    # ------------------------------------------------------------------
    # Tile helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_tile(level, x, y):
        """Return tile type at grid position (x, y); out-of-bounds = solid."""
        if 0 <= x <= 15 and 0 <= y <= 15:
            return level[y * 16 + x]
        return T_SOLID

    @staticmethod
    def _tile_is_solid(tile, toggles):
        """Return True if this tile currently blocks movement."""
        if tile == T_SOLID:
            return True
        if tile == T_GOAL:
            return False
        if tile in _TILE_TOGGLE_MAP:
            idx, is_hazard = _TILE_TOGGLE_MAP[tile]
            if is_hazard:
                return False   # hazards don't block – they kill
            return toggles[idx]  # solid only when toggle is ON
        return False

    @staticmethod
    def _tile_is_hazard(tile, toggles):
        """Return True if this tile is lethal when stood on."""
        if tile in _TILE_TOGGLE_MAP:
            idx, is_hazard = _TILE_TOGGLE_MAP[tile]
            if is_hazard:
                return toggles[idx]  # lethal only when toggle is ON
        return False

    # ------------------------------------------------------------------
    # Physics
    # ------------------------------------------------------------------

    def _step_physics(self, level, toggles, grav_mode):
        """Advance one frame of physics.  Updates _px, _py, _vy in-place.

        Returns:
            (on_surface, hit_hazard, hit_goal)
        """
        # --- Gravity ---
        if grav_mode == GRAV_NORMAL:
            self._vy += _GRAV_NORMAL
        elif grav_mode == GRAV_ZERO_G:
            self._vy += _GRAV_ZERO_G
        else:  # CEILING
            self._vy += _GRAV_CEILING

        # Clamp velocity
        if self._vy > _MAX_FALL_SPEED:
            self._vy = _MAX_FALL_SPEED
        elif self._vy < -_MAX_FALL_SPEED:
            self._vy = -_MAX_FALL_SPEED

        # --- Vertical movement with collision ---
        new_py = self._py + self._vy
        ipy     = int(self._py)
        inew_py = int(new_py)
        ipx     = int(self._px)

        on_surface = False

        if self._vy > 0 and inew_py > ipy:
            # Moving downward – check each new row
            for row in range(ipy + 1, min(inew_py + 2, 17)):
                if self._tile_is_solid(self._get_tile(level, ipx, row), toggles):
                    new_py = float(row - 1)
                    self._vy = 0.0
                    on_surface = True
                    break
        elif self._vy < 0 and inew_py < ipy:
            # Moving upward – check each new row
            for row in range(ipy - 1, max(inew_py - 2, -1), -1):
                if self._tile_is_solid(self._get_tile(level, ipx, row), toggles):
                    new_py = float(row + 1)
                    self._vy = 0.0
                    on_surface = True
                    break

        self._py = new_py

        # --- Ground / ceiling check for jump eligibility ---
        if grav_mode == GRAV_NORMAL or grav_mode == GRAV_ZERO_G:
            on_surface = on_surface or self._tile_is_solid(
                self._get_tile(level, ipx, int(self._py) + 1), toggles)
        if grav_mode == GRAV_CEILING:
            on_surface = on_surface or self._tile_is_solid(
                self._get_tile(level, ipx, int(self._py) - 1), toggles)

        # --- Tile under player (hazard / goal checks) ---
        tile_here = self._get_tile(level, int(self._px), int(self._py))
        hit_hazard = self._tile_is_hazard(tile_here, toggles)
        hit_goal   = (tile_here == T_GOAL)

        return on_surface, hit_hazard, hit_goal

    def _move_x(self, level, toggles, dx):
        """Move player dx pixels laterally (one pixel per encoder click)."""
        if dx == 0:
            return

        steps = int(dx)
        if steps == 0:
            steps = 1 if dx > 0 else -1

        direction = 1 if steps > 0 else -1
        for _ in range(abs(steps)):
            new_x = int(self._px) + direction
            new_x = max(0, min(15, new_x))

            # Check both the floor-row and ceil-row to prevent corner clipping!
            py_floor = int(self._py)
            py_ceil = int(math.ceil(self._py))

            floor_solid = self._tile_is_solid(self._get_tile(level, new_x, py_floor), toggles)
            ceil_solid = self._tile_is_solid(self._get_tile(level, new_x, py_ceil), toggles)

            if not floor_solid and not ceil_solid:
                self._px = float(new_x)
            else:
                break  # Blocked by wall; stop

    # ------------------------------------------------------------------
    # History (time-rewind)
    # ------------------------------------------------------------------

    def _push_history(self):
        """Snapshot current player state into the rewind buffer."""
        if len(self._history) >= _HISTORY_LEN:
            del self._history[0]
        self._history.append([self._px, self._py, self._vy])

    def _pop_history(self):
        """Restore most-recent snapshot; returns False if buffer is empty."""
        if not self._history:
            return False
        snap = self._history.pop()
        self._px, self._py, self._vy = snap[0], snap[1], snap[2]
        return True

    # ------------------------------------------------------------------
    # Satellite feedback
    # ------------------------------------------------------------------

    def _update_sat_leds(self, toggles, blink_on):
        """Light the 8 satellite LEDs to mirror each toggle's live state."""
        if not self.sat:
            return
        for i, on in enumerate(toggles):
            if on:
                color = _TOGGLE_LED_COLOR.get(i, Palette.WHITE)

                # Check if this toggle is mapped to a hazard
                is_hazard = any(v[0] == i and v[1] for v in _TILE_TOGGLE_MAP.values())

                if is_hazard and not blink_on:
                    # Dim the LED during the off-blink
                    self.sat.send("LED", f"{i},{color.index},0.0,0.1,2")
                else:
                    self.sat.send("LED", f"{i},{color.index},0.0,1.0,2")
            else:
                self.sat.send("LED", f"{i},{Palette.CHARCOAL.index},0.0,0.3,2")

    def _update_sat_display(self, level_num, grav_mode):
        """Send level + gravity info to the satellite 14-segment display."""
        if not self.sat:
            return
        grav_short = grav_mode[:3]
        self.sat.send("DSP", f"L{level_num+1} {grav_short}")

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _render(self, level, toggles):
        """Draw the current level state + player to the matrix."""
        self.core.matrix.clear()
        blink_on = (self._tick % 6) < 3   # hazard blink at ~5 Hz

        for y in range(16):
            for x in range(16):
                tile = level[y * 16 + x]
                if tile == T_EMPTY:
                    continue

                color = _TILE_COLOR.get(tile, Palette.OFF)

                if tile in _TILE_TOGGLE_MAP:
                    idx, is_hazard = _TILE_TOGGLE_MAP[tile]
                    active = toggles[idx]
                    if not active:
                        # Inactive toggled tiles shown dimly
                        color = Palette.CHARCOAL
                    elif is_hazard and not blink_on:
                        # Hazards blink
                        continue

                self.core.matrix.draw_pixel(x, y, color)

        # Goal pixel – pulse gold
        goal_color = Palette.GOLD if (self._tick % 8) < 5 else Palette.ORANGE
        for y in range(16):
            for x in range(16):
                if level[y * 16 + x] == T_GOAL:
                    self.core.matrix.draw_pixel(x, y, goal_color)
                    break

        # Player – white dot
        px_i = max(0, min(15, int(self._px)))
        py_i = max(0, min(15, int(self._py)))
        self.core.matrix.draw_pixel(px_i, py_i, Palette.WHITE)

    # ------------------------------------------------------------------
    # OLED display
    # ------------------------------------------------------------------

    def _update_oled(self, level_num, grav_mode, toggles, rewinding):
        """Push current status to the Core OLED."""
        toggle_str = "".join("1" if t else "0" for t in toggles)
        grav_label = {"NORMAL": "NRM", "ZERO_G": "0-G", "CEILING": "CEL"}.get(
            grav_mode, "NRM")
        rw_marker = "<RW>" if rewinding else "    "
        line1 = f"LV{level_num+1} {_LEVEL_NAMES[level_num]} {rw_marker}"
        line2 = f"G:{grav_label} T:{toggle_str}"
        self.core.display.update_status(line1, line2)

    # ------------------------------------------------------------------
    # Main game loop
    # ------------------------------------------------------------------

    async def run(self):
        """Main Flux Scavenger game loop."""
        self.difficulty = self.core.data.get_setting(
            "FLUX_SCAVENGER", "difficulty", "NORMAL")
        self.variant = self.difficulty

        # Satellite check
        if not self.sat or not self.sat.is_active:
            self.core.display.update_status("FLUX SCAVENGER", "SAT OFFLINE")
            await asyncio.sleep(2)
            return "FAILURE"

        self.core.display.use_standard_layout()

        total_levels = len(_LEVELS)
        level_idx = 0

        # Score per level = 1000 points for first, 750 for rewind usage
        self.score = 0

        while level_idx < total_levels:
            # ── per-level initialisation ─────────────────────────────
            level = _LEVELS[level_idx]
            sx, sy = _STARTS[level_idx]

            self._px = float(sx)
            self._py = float(sy)
            self._vy = 0.0
            self._history = []
            self._last_enc = self.core.hid.encoder_positions[_ENC_MOVE]
            self._btn_jump_prev = False
            self._tick = 0

            self.core.display.update_status(
                f"FLUX SCAVENGER", f"LEVEL {level_idx+1}: {_LEVEL_NAMES[level_idx]}")
            asyncio.create_task(
                self.core.synth.play_sequence(tones.POWER_UP, patch="SCANNER"))
            await asyncio.sleep(1.5)

            last_frame_ms = ticks_ms()
            level_complete = False
            level_failed   = False
            _rewind_used   = False

            # ── per-level game loop ───────────────────────────────────
            while not level_complete and not level_failed:
                now = ticks_ms()
                if ticks_diff(now, last_frame_ms) < 33:
                    await asyncio.sleep(0.005)
                    continue
                last_frame_ms = now
                self._tick += 1

                # 1. Read environment state
                toggles   = self._read_toggles()
                grav_mode = self._get_gravity_mode()
                rewinding = self._is_rewinding()

                # 2. Time-rewind
                if rewinding:
                    if self._pop_history():
                        _rewind_used = True
                        self.core.synth.play_note(300.0, "UI_SELECT", duration=0.02)
                    self._render(level, toggles)
                    self._update_oled(level_idx, grav_mode, toggles, rewinding)
                    continue   # Skip normal physics while rewinding

                # 3. Save state snapshot (before this frame's changes)
                self._push_history()

                # 4. Encoder lateral movement
                enc_now = self.core.hid.encoder_positions[_ENC_MOVE]
                enc_delta = enc_now - self._last_enc
                self._last_enc = enc_now
                if enc_delta != 0:
                    self._move_x(level, toggles, enc_delta)
                    self.core.synth.play_note(
                        440.0 + abs(enc_delta) * 30, "CLICK", duration=0.01)

                # 5. Jump input (rising-edge detection)
                btn_now = self.core.hid.is_button_pressed(_BTN_JUMP)
                if btn_now and not self._btn_jump_prev:
                    if grav_mode == GRAV_NORMAL:
                        # Only jump if on ground
                        if self._tile_is_solid(
                                self._get_tile(level, int(self._px), int(self._py) + 1),
                                toggles):
                            self._vy = _JUMP_FLOOR
                            self.core.synth.play_note(660.0, "UI_SELECT", duration=0.05)
                    elif grav_mode == GRAV_CEILING:
                        # Push away from ceiling
                        if self._tile_is_solid(
                                self._get_tile(level, int(self._px), int(self._py) - 1),
                                toggles):
                            self._vy = _JUMP_CEILING
                            self.core.synth.play_note(440.0, "UI_SELECT", duration=0.05)
                    else:
                        # Zero-G: gentle nudge upward always allowed
                        self._vy = _JUMP_ZERO_G
                        self.core.synth.play_note(550.0, "UI_SELECT", duration=0.05)
                self._btn_jump_prev = btn_now

                # 6. Physics step
                on_surface, hit_hazard, hit_goal = self._step_physics(
                    level, toggles, grav_mode)

                # 7. Win / lose checks
                if hit_goal:
                    level_complete = True
                    base_pts = 1000 if self.difficulty == "NORMAL" else 1500
                    self.score += base_pts - (500 if _rewind_used else 0)
                    continue

                if hit_hazard:
                    level_failed = True
                    continue

                # 8. Satellite feedback (every 3 frames to reduce chatter)
                if self._tick % 3 == 0:
                    blink_on = (self._tick % 6) < 3 # compute blink state
                    self._update_sat_leds(toggles, blink_on) # pass it
                    self._update_sat_display(level_idx, grav_mode)

                # 9. Render and OLED
                self._render(level, toggles)
                self._update_oled(level_idx, grav_mode, toggles, rewinding)

            # ── level outcome ─────────────────────────────────────────
            if level_failed:
                self.core.matrix.fill(Palette.RED)
                asyncio.create_task(
                    self.core.synth.play_sequence(tones.CRITICAL_STOP, patch="ALARM"))
                self.core.display.update_status("HAZARD!", "USE REWIND OR RETRY")
                await asyncio.sleep(1.5)
                # Do NOT advance level – retry same level
                _rewind_used = False

            elif level_complete:
                self.core.matrix.fill(Palette.GOLD)
                asyncio.create_task(
                    self.core.synth.play_sequence(tones.SUCCESS, patch="SELECT"))
                self.core.display.update_status(
                    f"LEVEL {level_idx+1} CLEAR!", f"SCORE: {self.score}")
                await asyncio.sleep(2.0)
                level_idx += 1

        # ── all levels complete → victory ─────────────────────────────
        return await self.victory()
