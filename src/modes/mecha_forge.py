# File: src/modes/mecha_forge.py
"""Mecha Forge – Pixel-art robot customizer sandbox toy.

A zero-stress creative sandbox where players build and customize a 16x16
pixel-art robot using all of the available hardware controls. Aimed at
younger audiences who want to interact with the satisfying clicky hardware
without any score pressure.

Hardware:
    Core:
        - 16x16 Matrix: Live pixel-art robot display
        - OLED: Current variant names, active accessories, and input hint
        - Encoder (index 0): Cycle through Head/Torso variants (4 options)
        - Encoder long-press (2 s): Return to menu

    Industrial Satellite (SAT-01) – optional, features enabled when present:
        - Satellite Encoder (index 0): Cycle through Leg/Tread variants
        - 8x Latching Toggles (0-7): Attach/detach robot accessories
        - 9-Digit Keypad: Type a 3-digit RGB code (e.g. 9-0-0 for red) to
          repaint the mech body
        - Momentary Toggle index 0, direction UP held ≥ 500 ms:
          Trigger Attack animation (lasers firing from the matrix)
        - Big Red Button (button index 0): Trigger Launch animation
          (mech blasts off the top of the screen)
"""

import asyncio
import gc

from adafruit_ticks import ticks_ms, ticks_diff

from .base import BaseMode
from utilities import tones

# ---------------------------------------------------------------------------
# Hardware indices (SAT-01 INDUSTRIAL mirror)
# ---------------------------------------------------------------------------
_MT_ATTACK       = 0   # Momentary toggle index: UP direction = attack
_BTN_LAUNCH      = 0   # Big button (buttons_values index): launch
_ENC_SAT         = 0   # Satellite encoder index
_ENC_CORE        = 0   # Core encoder index
_ACC_COUNT       = 8   # Number of accessory latching toggles (0-7)

# ---------------------------------------------------------------------------
# Robot head/torso templates  –  12 rows × 16 cols  (192 bytes each)
# Pixel values:  0 = empty  |  1 = body  |  2 = detail  |  4 = eye/white
# ---------------------------------------------------------------------------
#
#  Variant 0 – CLASSIC  (square boxy head, single antenna)
_HT0 = bytes([
    0, 0, 0, 0, 0, 0, 0, 1, 1, 0, 0, 0, 0, 0, 0, 0,  # row 0  antenna
    0, 0, 0, 0, 0, 0, 0, 1, 1, 0, 0, 0, 0, 0, 0, 0,  # row 1
    0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0,  # row 2  head top
    0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0,  # row 3  head
    0, 0, 0, 0, 0, 1, 4, 1, 1, 4, 1, 0, 0, 0, 0, 0,  # row 4  eyes
    0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0,  # row 5  face
    0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0,  # row 6  chin
    0, 0, 0, 0, 0, 0, 0, 1, 1, 0, 0, 0, 0, 0, 0, 0,  # row 7  neck
    0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0,  # row 8  shoulder
    0, 0, 0, 0, 1, 1, 2, 1, 1, 2, 1, 1, 0, 0, 0, 0,  # row 9  chest
    0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0,  # row 10
    0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0,  # row 11 waist
])

#  Variant 1 – DOME  (rounded dome head, wide visor)
_HT1 = bytes([
    0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0,  # row 0  dome top
    0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0,  # row 1
    0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0,  # row 2  dome wide
    0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0,  # row 3
    0, 0, 0, 0, 1, 4, 1, 1, 1, 1, 4, 1, 0, 0, 0, 0,  # row 4  eyes
    0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0,  # row 5  visor
    0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0,  # row 6  chin
    0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0,  # row 7  neck
    0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0,  # row 8  shoulder
    0, 0, 0, 0, 1, 1, 2, 1, 1, 2, 1, 1, 0, 0, 0, 0,  # row 9  chest
    0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0,  # row 10
    0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0,  # row 11 waist
])

#  Variant 2 – ANGULAR  (twin antennae, split jaw, very wide shoulders)
_HT2 = bytes([
    0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0,  # row 0  twin antennae
    0, 0, 0, 0, 1, 1, 0, 0, 0, 0, 1, 1, 0, 0, 0, 0,  # row 1
    0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0,  # row 2  angular head
    0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0,  # row 3
    0, 0, 0, 0, 1, 4, 1, 1, 1, 1, 4, 1, 0, 0, 0, 0,  # row 4  eyes
    0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0,  # row 5  face
    0, 0, 0, 0, 1, 1, 0, 0, 0, 0, 1, 1, 0, 0, 0, 0,  # row 6  split jaw
    0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0,  # row 7  neck
    0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0,  # row 8  very wide shoulder
    0, 0, 0, 1, 1, 1, 2, 1, 1, 2, 1, 1, 1, 0, 0, 0,  # row 9  wider chest
    0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0,  # row 10
    0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0,  # row 11 waist
])

#  Variant 3 – HEAVY  (sensor horns, massive frame)
_HT3 = bytes([
    0, 0, 0, 0, 1, 1, 0, 0, 0, 0, 1, 1, 0, 0, 0, 0,  # row 0  sensor horns
    0, 0, 0, 0, 1, 1, 0, 0, 0, 0, 1, 1, 0, 0, 0, 0,  # row 1
    0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0,  # row 2  wide head
    0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0,  # row 3
    0, 0, 0, 1, 1, 4, 1, 1, 1, 1, 4, 1, 1, 0, 0, 0,  # row 4  eyes
    0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0,  # row 5  thick face
    0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0,  # row 6
    0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0,  # row 7  neck
    0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0,  # row 8  massive shoulder
    0, 0, 1, 1, 1, 1, 2, 1, 1, 2, 1, 1, 1, 1, 0, 0,  # row 9  thick chest
    0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0,  # row 10
    0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0,  # row 11 wide waist
])

# All head/torso variants in order
_HT = (_HT0, _HT1, _HT2, _HT3)
_HT_NAMES = ("CLASSIC", "DOME", "ANGULAR", "HEAVY")

# ---------------------------------------------------------------------------
# Leg/tread templates  –  4 rows × 16 cols  (64 bytes each)
# Same pixel value convention as above.
# ---------------------------------------------------------------------------

#  Variant 0 – LEGS  (bipedal stance)
_LG0 = bytes([
    0, 0, 0, 0, 0, 1, 1, 0, 0, 1, 1, 0, 0, 0, 0, 0,  # row 12 hips
    0, 0, 0, 0, 0, 1, 1, 0, 0, 1, 1, 0, 0, 0, 0, 0,  # row 13 thighs
    0, 0, 0, 0, 0, 1, 1, 0, 0, 1, 1, 0, 0, 0, 0, 0,  # row 14 lower legs
    0, 0, 0, 0, 1, 1, 1, 0, 0, 1, 1, 1, 0, 0, 0, 0,  # row 15 feet
])

#  Variant 1 – TREADS  (tank tread platform)
_LG1 = bytes([
    0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0,  # row 12 tread connector
    0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0,  # row 13 tread top
    0, 0, 0, 1, 2, 1, 2, 1, 1, 2, 1, 2, 1, 0, 0, 0,  # row 14 tread (wheel marks)
    0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0,  # row 15 tread bottom
])

#  Variant 2 – SPIDER  (sprawling arachnid legs)
_LG2 = bytes([
    0, 0, 0, 1, 1, 0, 0, 0, 0, 0, 0, 1, 1, 0, 0, 0,  # row 12 hip joints
    0, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 0,  # row 13 spread wide
    1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1,  # row 14 more spread
    1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1,  # row 15 feet tips
])

#  Variant 3 – JETS  (hover thruster platform)
_LG3 = bytes([
    0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0,  # row 12 hover plate
    0, 0, 0, 0, 1, 1, 0, 0, 0, 0, 1, 1, 0, 0, 0, 0,  # row 13 dual jets
    0, 0, 0, 0, 2, 2, 0, 0, 0, 0, 2, 2, 0, 0, 0, 0,  # row 14 jet flame
    0, 0, 0, 0, 0, 2, 0, 0, 0, 0, 2, 0, 0, 0, 0, 0,  # row 15 flame tip
])

# All leg variants in order
_LG = (_LG0, _LG1, _LG2, _LG3)
_LG_NAMES = ("LEGS", "TREADS", "SPIDER", "JETS")

# ---------------------------------------------------------------------------
# Accessories  –  8 items, one per latching toggle (0-7)
# Each entry:  ( tuple-of-(x,y) , (R,G,B) )
# Accessories are overlaid on top of the base robot after body+legs are drawn.
# ---------------------------------------------------------------------------
_ACCESSORIES = (
    # 0: Shoulder Cannon  –  right side, orange
    (((12, 7), (13, 7), (14, 7), (15, 7),
      (12, 8), (13, 8), (14, 8), (15, 8),
      (12, 9)),
     (255, 130, 0)),

    # 1: Radar Dish  –  top centre, gold
    (((5, 0), (6, 0), (9, 0), (10, 0),
      (6, 1), (7, 1), (8, 1), (9, 1)),
     (255, 215, 0)),

    # 2: Jetpack  –  rear right, green
    (((13, 7), (14, 7),
      (13, 8), (14, 8), (15, 8),
      (13, 9), (14, 9), (15, 9),
      (14, 10), (14, 11)),
     (0, 200, 50)),

    # 3: Laser Blade  –  right arm, laser red
    (((13, 8), (14, 8), (15, 8),
      (15, 9), (15, 10), (15, 11),
      (14, 11)),
     (255, 50, 50)),

    # 4: Rocket Pod  –  left shoulder, red
    (((0, 8), (1, 8), (2, 8),
      (0, 9), (1, 9), (2, 9),
      (1, 10), (0, 10)),
     (220, 0, 0)),

    # 5: Energy Shield  –  front left, cyan
    (((3, 9), (3, 10), (4, 10),
      (3, 11), (4, 11), (3, 12),
      (4, 12), (5, 12)),
     (0, 210, 210)),

    # 6: Energy Wings  –  both sides, magenta
    (((0, 7), (0, 8), (0, 9), (0, 10),
      (15, 7), (15, 8), (15, 9), (15, 10)),
     (220, 0, 220)),

    # 7: Victory Crest  –  top centre, yellow (overlays antenna)
    (((6, 0), (7, 0), (8, 0), (9, 0),
      (7, 1), (8, 1)),
     (255, 255, 0)),
)

_ACC_NAMES = (
    "CANNON", "RADAR", "JETPACK", "LASER",
    "ROCKET", "SHIELD", "WINGS", "CREST",
)

# Default body colour (CYAN-ish as RGB)
_DEFAULT_COLOR = (0, 200, 200)
_EYE_COLOR     = (255, 255, 255)  # white
_DETAIL_COLOR  = (0, 100, 180)    # darker blue for vent/tread details
_FLAME_COLOR   = (255, 100, 0)    # orange flame for jets leg detail


class MechaForge(BaseMode):
    """Mecha Forge – tactile pixel-art robot customizer.

    Zero-stress sandbox toy:  build a robot by turning knobs, flipping
    toggles, and hammering buttons – no score, no timer, just creativity.
    """

    def __init__(self, core):
        super().__init__(core, "MECHA FORGE", "Robot Builder Toy")

        # Locate industrial satellite (optional)
        self.sat = None
        for sat in self.core.satellites.values():
            if sat.sat_type_name == "INDUSTRIAL":
                self.sat = sat
                break

        # Robot configuration state
        self._ht_idx = 0               # Head/torso variant index (0-3)
        self._lg_idx = 0               # Leg variant index (0-3)
        self._acc = [False] * _ACC_COUNT  # Active accessories per toggle

        # Body colour (R, G, B), modified by keypad input
        self._body_color = _DEFAULT_COLOR

        # Keypad digit buffer: accumulate 3 digits for an RGB code
        self._kp_buf = []

        # Prevent re-triggering launch/attack while animating
        self._animating = False

        # Redraw flag: set True whenever robot state changes
        self._dirty = True

    async def run_tutorial(self):
        """
        A guided demonstration of the Mecha Forge sandbox.

        The Voiceover Script (audio/tutes/mecha_tute.wav) ~31 seconds:
            [0:00] "Welcome to Mecha Forge! Time to build your ultimate robot."
            [0:05] "Turn the core dial to change the head and torso."
            [0:09] "Turn the satellite dial to change the legs."
            [0:13] "Flip the eight toggle switches to equip different weapons and accessories."
            [0:18] "Type a three-digit code on the keypad to paint your mech."
            [0:23] "Hold the momentary switch UP to fire your lasers!"
            [0:27] "And press the Big Red Button to launch! Have fun!"
            [0:31] (End of file)
        """
        await self.core.clean_slate()
        self.game_state = "TUTORIAL"

        self.core.audio.play("audio/tutes/mecha_tute.wav", bus_id=self.core.audio.CH_VOICE)

        # Reset to a blank slate for the demo
        self._ht_idx = 0
        self._lg_idx = 0
        self._acc = [False] * _ACC_COUNT
        self._body_color = _DEFAULT_COLOR
        self._kp_buf = []

        # Helper to force a frame draw during the tutorial
        def _refresh():
            self.core.matrix.clear()
            self._draw_robot()


        # [0:00 - 0:05] "Welcome to Mecha Forge..."
        self.core.display.update_status("MECHA FORGE", "ROBOT BUILDER")
        _refresh()
        await asyncio.sleep(5.0)

        # [0:05 - 0:09] "Turn the core dial to change the head and torso."
        self.core.display.update_status("CORE DIAL", "CHANGE HEAD/TORSO")
        for _ in range(3):
            self._ht_idx = (self._ht_idx + 1) % len(_HT)
            _refresh()
            self.core.buzzer.play_sequence(tones.UI_TICK)
            await asyncio.sleep(1.3)

        # [0:09 - 0:13] "Turn the satellite dial to change the legs."
        self.core.display.update_status("SATELLITE DIAL", "CHANGE LEGS")
        for _ in range(3):
            self._lg_idx = (self._lg_idx + 1) % len(_LG)
            _refresh()
            self.core.buzzer.play_sequence(tones.UI_TICK)
            await asyncio.sleep(1.3)

        # [0:13 - 0:18] "Flip the eight toggle switches to equip..."
        self.core.display.update_status("TOGGLE SWITCHES", "EQUIP ACCESSORIES")
        for toggle_idx in [0, 6, 1]:  # Cannon, Wings, Radar
            self._acc[toggle_idx] = True
            _refresh()
            self.core.buzzer.play_sequence(tones.COIN)
            await asyncio.sleep(1.6)

        # [0:18 - 0:23] "Type a three-digit code on the keypad to paint..."
        self.core.display.update_status("9-DIGIT KEYPAD", "PAINT YOUR MECH")
        # Simulate typing 9-1-1 for a bright red
        for digit in ["9", "1", "1"]:
            self._kp_buf.append(int(digit))
            self.core.buzzer.play_sequence(tones.UI_TICK)
            await asyncio.sleep(0.8)

        self._body_color = (255, 20, 20)  # Apply the red paint
        self._kp_buf = []
        _refresh()
        self.core.buzzer.play_sequence(tones.UI_CONFIRM)
        await asyncio.sleep(2.6)

        # [0:23 - 0:27] "Hold the momentary switch UP to fire your lasers!"
        self.core.display.update_status("MOMENTARY UP", "LASER ATTACK!")
        await self._attack_animation()
        await asyncio.sleep(1.5)

        # [0:27 - 0:31] "And press the Big Red Button to launch! Have fun!"
        self.core.display.update_status("BIG RED BUTTON", "LAUNCH!")
        await self._launch_animation()

        # Wait for the audio track to finish naturally
        if hasattr(self.core.audio, 'wait_for_bus'):
            await self.core.audio.wait_for_bus(self.core.audio.CH_VOICE)
        else:
            await asyncio.sleep(2.0)

        await self.core.clean_slate()
        return "TUTORIAL_COMPLETE"

    # ------------------------------------------------------------------
    # Satellite helpers
    # ------------------------------------------------------------------

    def _sat_latching(self, idx):
        """Return current state of satellite latching toggle *idx* (safe)."""
        if not self.sat:
            return False
        try:
            return bool(self.sat.hid.latching_values[idx])
        except (IndexError, AttributeError):
            return False

    def _sat_button(self, idx=_BTN_LAUNCH):
        """Return True if the satellite big button at *idx* is pressed."""
        if not self.sat:
            return False
        try:
            return bool(self.sat.hid.buttons_values[idx])
        except (IndexError, AttributeError):
            return False

    def _sat_encoder(self):
        """Return the current satellite encoder position integer."""
        if not self.sat:
            return 0
        try:
            return self.sat.hid.encoder_positions[_ENC_SAT]
        except (IndexError, AttributeError):
            return 0

    def _sat_momentary_up(self):
        """Return True if satellite momentary toggle 0 is held UP."""
        if not self.sat:
            return False
        try:
            return self.sat.hid.is_momentary_toggled(
                _MT_ATTACK, direction="U", long=True, duration=500
            )
        except (IndexError, AttributeError):
            return False

    # ------------------------------------------------------------------
    # Robot rendering
    # ------------------------------------------------------------------

    def _draw_robot(self, y_offset=0):
        """Draw the current robot configuration onto the matrix.

        Args:
            y_offset: Vertical shift applied to all pixels (for animations).
                      Positive values shift the robot down; negative up.
        """
        bc = self._body_color    # body colour
        ec = _EYE_COLOR          # eye colour
        dc = _DETAIL_COLOR       # vent / detail colour
        fc = _FLAME_COLOR        # flame colour for jets

        # ---- Head/torso  (rows 0-11) ----
        ht = _HT[self._ht_idx]
        for row in range(12):
            draw_y = row + y_offset
            if draw_y < 0 or draw_y > 15:
                continue
            row_start = row * 16
            for col in range(16):
                val = ht[row_start + col]
                if val == 0:
                    continue
                color = bc if val == 1 else (ec if val == 4 else dc)
                self.core.matrix.draw_pixel(col, draw_y, color)

        # ---- Legs  (rows 12-15) ----
        lg = _LG[self._lg_idx]
        for row in range(4):
            draw_y = row + 12 + y_offset
            if draw_y < 0 or draw_y > 15:
                continue
            row_start = row * 16
            for col in range(16):
                val = lg[row_start + col]
                if val == 0:
                    continue
                # Jets use flame colour for detail pixels
                color = bc if val == 1 else (fc if self._lg_idx == 3 else dc)
                self.core.matrix.draw_pixel(col, draw_y, color)

        # ---- Accessories ----
        for i in range(_ACC_COUNT):
            if not self._acc[i]:
                continue
            pixels, acc_color = _ACCESSORIES[i]
            for (px, py) in pixels:
                draw_y = py + y_offset
                if 0 <= draw_y <= 15:
                    self.core.matrix.draw_pixel(px, draw_y, acc_color)

    def _update_display(self):
        """Refresh OLED with current robot configuration info."""
        ht_name = _HT_NAMES[self._ht_idx]
        lg_name = _LG_NAMES[self._lg_idx]
        acc_on = [_ACC_NAMES[i] for i in range(_ACC_COUNT) if self._acc[i]]
        acc_str = ",".join(acc_on[:3]) if acc_on else "NONE"

        r, g, b = self._body_color
        color_code = f"{r // 28}{g // 28}{b // 28}"

        self.core.display.update_status(
            f"{ht_name}+{lg_name}",
            f"ACC:{acc_str[:8]} C:{color_code}",
        )

    # ------------------------------------------------------------------
    # Animations
    # ------------------------------------------------------------------

    async def _attack_animation(self):
        """Laser beams shoot outward from the robot's torso."""
        self._animating = True
        self.core.buzzer.play_sequence(tones.FIREBALL)

        laser = (255, 60, 60)   # bright red laser
        boost = (255, 200, 0)   # yellow muzzle flash

        # Extend lasers outward over several frames
        for length in range(1, 9):
            self.core.matrix.clear()
            self._draw_robot()

            # Left laser  (shoot left from col 3)
            for x in range(max(0, 4 - length), 4):
                self.core.matrix.draw_pixel(x, 8, laser)
                self.core.matrix.draw_pixel(x, 9, laser)

            # Right laser  (shoot right from col 12)
            for x in range(12, min(16, 12 + length)):
                self.core.matrix.draw_pixel(x, 8, laser)
                self.core.matrix.draw_pixel(x, 9, laser)

            await asyncio.sleep(0.05)

        # Full-width flash
        self.core.matrix.clear()
        for x in range(16):
            self.core.matrix.draw_pixel(x, 8, boost)
            self.core.matrix.draw_pixel(x, 9, boost)
        await asyncio.sleep(0.15)

        self._animating = False
        self._dirty = True

    async def _launch_animation(self):
        """Rocket boost: jet exhaust flickers, then mech scrolls off the top."""
        self._animating = True
        self.core.buzzer.play_sequence(tones.LAUNCH)

        exhaust = (255, 165, 0)   # orange exhaust

        # Pre-launch flicker
        for _ in range(4):
            self.core.matrix.clear()
            self._draw_robot()
            for col in range(5, 11):
                self.core.matrix.draw_pixel(col, 15, exhaust)
            await asyncio.sleep(0.07)
            self.core.matrix.clear()
            self._draw_robot()
            await asyncio.sleep(0.05)

        # Scroll upward until off-screen
        for offset in range(0, 17):
            self.core.matrix.clear()
            self._draw_robot(y_offset=-offset)
            # Leave an exhaust trail at the bottom
            trail_y = 15 - offset + 2
            if 0 <= trail_y < 16:
                for col in range(5, 11):
                    self.core.matrix.draw_pixel(col, trail_y, exhaust)
            await asyncio.sleep(0.05)

        self.core.matrix.clear()
        await asyncio.sleep(0.3)

        self._animating = False
        self._dirty = True

    # ------------------------------------------------------------------
    # Main run loop
    # ------------------------------------------------------------------

    async def run(self):
        """Main Mecha Forge event loop."""
        # ---- Setup ----
        self.core.display.use_standard_layout()
        self.core.display.update_header("MECHA FORGE")
        self.core.display.update_footer("TURN:HEAD  BTN:EXIT")

        self.core.hid.flush()
        self.core.hid.reset_encoder(value=0, index=_ENC_CORE)
        last_core_enc = self.core.hid.encoder_positions[_ENC_CORE]

        if self.sat:
            try:
                self.sat.hid.reset_encoder(value=0, index=_ENC_SAT)
                self.sat.hid.flush_keypad_queue(0)
            except (AttributeError, IndexError):
                pass

        last_sat_enc = self._sat_encoder()

        while True:
            # ---- Core encoder: cycle head/torso ----
            curr_core_enc = self.core.hid.encoder_positions[_ENC_CORE]
            if curr_core_enc != last_core_enc:
                delta = 1 if curr_core_enc > last_core_enc else -1
                self._ht_idx = (self._ht_idx + delta) % len(_HT)
                last_core_enc = curr_core_enc
                self._dirty = True
                self.core.buzzer.play_sequence(tones.UI_TICK)

            # ---- Satellite encoder: cycle legs ----
            curr_sat_enc = self._sat_encoder()
            if curr_sat_enc != last_sat_enc:
                delta = 1 if curr_sat_enc > last_sat_enc else -1
                self._lg_idx = (self._lg_idx + delta) % len(_LG)
                last_sat_enc = curr_sat_enc
                self._dirty = True
                self.core.buzzer.play_sequence(tones.UI_TICK)

            # ---- Latching toggles: accessories ----
            if self.sat:
                for i in range(_ACC_COUNT):
                    new_state = self._sat_latching(i)
                    if new_state != self._acc[i]:
                        self._acc[i] = new_state
                        self._dirty = True
                        self.core.buzzer.play_sequence(tones.COIN)

            # ---- Keypad: 3-digit RGB paint code ----
            if self.sat:
                try:
                    key = self.sat.hid.get_keypad_next_key(0)
                except (AttributeError, IndexError):
                    key = None
                if key is not None and str(key).isdigit():
                    self._kp_buf.append(int(str(key)))
                    self.core.buzzer.play_sequence(tones.UI_TICK)
                    if len(self._kp_buf) >= 3:
                        r = min(9, self._kp_buf[0]) * 28
                        g = min(9, self._kp_buf[1]) * 28
                        b = min(9, self._kp_buf[2]) * 28
                        # Ensure body isn't totally black (min brightness 20)
                        if r == 0 and g == 0 and b == 0:
                            r, g, b = 20, 20, 20
                        self._body_color = (r, g, b)
                        self._kp_buf = []
                        self._dirty = True
                        self.core.buzzer.play_sequence(tones.UI_CONFIRM)

            # ---- Momentary toggle: attack animation ----
            if not self._animating and self._sat_momentary_up():
                await self._attack_animation()

            # ---- Big red button: launch animation ----
            if not self._animating and self._sat_button():
                await self._launch_animation()

            # ---- Core encoder long-press: exit ----
            if self.core.hid.is_encoder_button_pressed(long=True, duration=2000):
                gc.collect()
                return "SUCCESS"
            elif self.core.hid.is_encoder_button_pressed(action="tap"):
                self.core.display.update_status("HOLD TO EXIT", "PRESS FOR 2s")
                self.core.buzzer.play_sequence(tones.ERROR)

            # ---- Redraw only when state changed ----
            if self._dirty and not self._animating:
                self.core.matrix.clear()
                self._draw_robot()
                self._update_display()
                self._dirty = False

            await asyncio.sleep(0.04)
