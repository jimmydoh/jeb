"""Artillery Command Game Mode – Steampunk Giant Artillery Simulator.

The player operates a massive steampunk cannon receiving orders from the
Fire Direction Centre. Each mission requires strict adherence to the correct
loading, aiming, and firing protocol using the full Industrial Satellite
hardware loadout.

Gameplay phases per Fire Mission:
    1. ORDER RECEIVED  – Read the incoming target: bearing, distance, shell type
    2. LOAD DISTANCE   – Type the target distance on the 9-digit keypad
    3. SELECT SHELL    – Rotate the 3-position rotary switch to the correct type
    4. CHARGE BAGS     – Flip latching toggles to load minimum powder charges;
                         segment/audio indicates minimum required; LEDs show bag status
    5. AIM             – Dial in calculated elevation (satellite encoder) and
                         bearing (core encoder); momentary toggle sets speed mode
    6. RAM HOME        – Engage guarded toggle and hold momentary UP to lock round
    7. FIRE            – Press the Big Red Button
    8. RESET           – Return elevation to 0°, clear charge toggles, disarm arm
"""

import asyncio
import random
import math

from adafruit_ticks import ticks_ms, ticks_diff

from utilities.palette import Palette
from utilities import tones

from .game_mode import GameMode

# ---------------------------------------------------------------------------
# Hardware indices (mirror sat_01_driver layout)
# ---------------------------------------------------------------------------
_CHARGE_TOGGLE_COUNT = 8    # Latching toggles 0-7 are charge bag slots
_SW_ARM              = 8    # Guarded latching toggle / Master Arm (index 8)
_SW_KEY              = 9    # Key switch (safe/active – index 9)
_SW_ROTARY_A         = 10   # 3-Position rotary switch: Position A (index 10)
_SW_ROTARY_B         = 11   # 3-Position rotary switch: Position B (index 11)
_MT_SPEED            = 0    # Momentary toggle: UP=fast, DOWN=fine (index 0)
_BTN_FIRE            = 0    # Large momentary button – FIRE (index 0)
_ENC_ELEVATION       = 0    # Satellite encoder: elevation (index 0)
_ENC_BEARING         = 0    # Core encoder: bearing/rotation (index 0)
_KP_DISTANCE         = 0    # Matrix keypad index 0 for distance entry

# ---------------------------------------------------------------------------
# Shell types
# ---------------------------------------------------------------------------
SHELL_HE        = "HE"         # High Explosive  – standard weight
SHELL_AP        = "AP"         # Armour Piercing – heavy, high velocity
SHELL_STARSHELL = "STARSHELL"  # Illumination    – light, high arc

# Rotary switch decoding (indices 10-11)
#   A=ON , B=OFF → HE
#   A=OFF, B=ON  → AP
#   A=ON , B=ON  → STARSHELL
#   A=OFF, B=OFF → HE (default / centre rest)
_SHELL_NAMES = {
    SHELL_HE:        "HE",
    SHELL_AP:        "AP",
    SHELL_STARSHELL: "STAR",
}

# ---------------------------------------------------------------------------
# Ballistic model constants
# ---------------------------------------------------------------------------
_GRAVITY              = 9.81    # m/s²
_BASE_VELOCITY        = 300.0   # m/s – muzzle velocity with zero charge bags
_VELOCITY_PER_CHARGE  = 50.0    # m/s added per active charge bag

# Weight factor – adjusts effective range for shell type
# Higher value → heavier projectile → needs more elevation for same range
_SHELL_WEIGHT_FACTOR = {
    SHELL_HE:        1.00,
    SHELL_AP:        1.20,
    SHELL_STARSHELL: 0.70,
}

# ---------------------------------------------------------------------------
# Phase identifiers
# ---------------------------------------------------------------------------
_PHASE_ORDER    = "ORDER"
_PHASE_DISTANCE = "DISTANCE"
_PHASE_SHELL    = "SHELL"
_PHASE_CHARGES  = "CHARGES"
_PHASE_AIM      = "AIM"
_PHASE_RAM      = "RAM"
_PHASE_FIRE     = "FIRE"
_PHASE_RESET    = "RESET"

# ---------------------------------------------------------------------------
# Timing constants
# ---------------------------------------------------------------------------
_GLOBAL_TIME   = 180.0   # 3-minute total game timer (seconds)
_BONUS_TIME    = 15.0    # Bonus seconds added per completed fire mission
_ORDER_PAUSE   = 2.5     # Seconds to display the order before auto-advancing
_RAM_HOLD_TIME = 2.0     # Seconds to hold momentary toggle UP to confirm ram

# ---------------------------------------------------------------------------
# Encoder movement speed multipliers
# ---------------------------------------------------------------------------
_ENCODER_STEP_FAST   = 3    # degrees per encoder tick in FAST mode
_ENCODER_STEP_NORMAL = 1    # degrees per encoder tick in NORMAL mode

# ---------------------------------------------------------------------------
# Difficulty tuning tables
# ---------------------------------------------------------------------------
_DIFF_PARAMS = {
    "NORMAL": {"dist_digits": 4, "min_charges": 2, "elev_tol": 3, "bearing_tol": 5},
    "HARD":   {"dist_digits": 5, "min_charges": 3, "elev_tol": 2, "bearing_tol": 3},
    "INSANE": {"dist_digits": 5, "min_charges": 4, "elev_tol": 1, "bearing_tol": 2},
}

# Target distance range in metres
_DIST_MIN = 1000
_DIST_MAX = 8000

# ---------------------------------------------------------------------------
# Matrix dimensions
# ---------------------------------------------------------------------------
_MATRIX_SIZE = 16


class ArtilleryCommand(GameMode):
    """Steampunk Giant Artillery Simulator.

    The player receives fire orders and must operate a giant cannon through a
    strict multi-phase protocol: verify distance, select ammunition, load
    powder charges, dial in elevation and bearing, ram the round home, and fire.

    Hardware:
        Core:
            - 16x16 Matrix: Target map (bearing pointer), ballistic arc, fire animation
            - OLED: Mission orders, phase instructions, status
            - Rotary Encoder (index 0): Bearing / azimuth adjustment

        Industrial Satellite (SAT-01):
            - 9-Digit Keypad (index 0): Target distance entry
            - 3-Position Rotary Switch (indices 10-11): Shell type selection
            - 8x Latching Toggles (0-7): Powder charge bags
            - Guarded Toggle (index 8): Master Arm / Ram lock
            - Momentary Toggle (index 0): Speed mode (UP=FAST / DOWN=FINE)
            - Large Button (index 0): FIRE
            - 14-Segment Display: Phase readout / elevation / bearing
    """

    METADATA = {
        "id": "ARTILLERY_COMMAND",
        "name": "ARTY COMMAND",
        "icon": "ARTILLERY_COMMAND",
        "requires": ["CORE", "INDUSTRIAL"],
        "settings": [
            {
                "key": "difficulty",
                "label": "DIFF",
                "options": ["NORMAL", "HARD", "INSANE"],
                "default": "NORMAL"
            }
        ]
    }

    def __init__(self, core):
        super().__init__(core, "ARTY COMMAND", "Steampunk Artillery Simulator")

        # Find the Industrial Satellite
        self.sat = None
        for sat in self.core.satellites.values():
            if sat.sat_type_name == "INDUSTRIAL":
                self.sat = sat
                break

        # Current fire order
        self._order_bearing  = 0    # Degrees (0–359)
        self._order_distance = 0    # Metres
        self._order_shell    = SHELL_HE

        # Required values calculated from the order + loaded charges
        self._req_elevation  = 0    # Degrees (calculated, 1–89)
        self._req_bearing    = 0    # = _order_bearing (mirrored for clarity)
        self._min_charges    = 2    # Minimum charge bags from difficulty

        # Player-dialled values
        self._player_elevation = 0  # Degrees
        self._player_bearing   = 0  # Degrees

        # Phase tracking
        self._phase         = _PHASE_ORDER
        self._mission_count = 0
        self._time_remaining = _GLOBAL_TIME
        self._last_tick_ms  = 0

        # Keypad / distance entry
        self._dist_entered    = ""
        self._last_kp_snapshot = ""

        # Ram-home state
        self._ram_hold_start  = 0.0
        self._ram_held        = False

        # Encoder tracking
        self._last_enc_elevation = 0
        self._last_enc_bearing   = 0
        self._fine_accum_elev    = 0.0  # sub-step accumulator for FINE mode

        # Difficulty parameters (populated in run())
        self._dist_digits = 4
        self._elev_tol    = 3
        self._bearing_tol = 5

        # LED state cache to avoid flooding UART
        self._last_led_states = [None] * _CHARGE_TOGGLE_COUNT

    # ------------------------------------------------------------------
    # Satellite HID helpers
    # ------------------------------------------------------------------

    def _sat_latching(self, idx):
        """Return the state of a satellite latching toggle (safe)."""
        if not self.sat:
            return False
        try:
            return bool(self.sat.hid.latching_values[idx])
        except (IndexError, AttributeError):
            return False

    def _sat_button(self, idx=0):
        """Return True if the satellite large button is pressed."""
        if not self.sat:
            return False
        try:
            return bool(self.sat.hid.buttons_values[idx])
        except (IndexError, AttributeError):
            return False

    def _sat_encoder(self):
        """Return current satellite encoder position."""
        if not self.sat:
            return 0
        try:
            return self.sat.hid.encoder_positions[_ENC_ELEVATION]
        except (IndexError, AttributeError):
            return 0

    def _sat_momentary_up(self):
        """Return True if the satellite momentary toggle is held UP."""
        if not self.sat:
            return False
        try:
            return self.sat.hid.is_momentary_toggled(_MT_SPEED, direction="U")
        except (IndexError, AttributeError):
            return False

    def _sat_momentary_down(self):
        """Return True if the satellite momentary toggle is held DOWN."""
        if not self.sat:
            return False
        try:
            return self.sat.hid.is_momentary_toggled(_MT_SPEED, direction="D")
        except (IndexError, AttributeError):
            return False

    def _send_segment(self, text):
        """Send text string to the satellite 14-segment display (max 8 chars)."""
        if self.sat:
            try:
                self.sat.send("DSP", text[:8])
            except Exception:
                pass

    def _set_sat_led(self, idx, color):
        """Set a satellite NeoPixel LED colour (palette Color object)."""
        if self.sat:
            try:
                self.sat.send("LED", f"{idx},{color.index},0.0,1.0,2")
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Shell-type helper
    # ------------------------------------------------------------------

    def _get_shell_type(self):
        """Read the 3-position rotary switch and return a SHELL_* constant."""
        rot_a = self._sat_latching(_SW_ROTARY_A)
        rot_b = self._sat_latching(_SW_ROTARY_B)
        if rot_a and not rot_b:
            return SHELL_HE
        if not rot_a and rot_b:
            return SHELL_AP
        if rot_a and rot_b:
            return SHELL_STARSHELL
        return SHELL_HE  # default centre position

    # ------------------------------------------------------------------
    # Charge-bag helpers
    # ------------------------------------------------------------------

    def _count_active_charges(self):
        """Count how many of the 8 charge-bag toggles are currently ON."""
        count = 0
        for i in range(_CHARGE_TOGGLE_COUNT):
            if self._sat_latching(i):
                count += 1
        return count

    def _sync_charge_leds(self, min_charges):
        """Update satellite LEDs to reflect current charge bag states.

        - Toggles ON  (charge loaded): ORANGE – awaiting firing
        - Toggles OFF (charge absent): GREEN  – slot available
        - First ``min_charges`` slots that are still OFF: blink RED
        """
        active = self._count_active_charges()
        for i in range(_CHARGE_TOGGLE_COUNT):
            state = self._sat_latching(i)
            if state:
                desired = "ORANGE"
            elif i < min_charges and active < min_charges:
                desired = "RED"
            else:
                desired = "GREEN"

            if self._last_led_states[i] != desired:
                if desired == "ORANGE":
                    self._set_sat_led(i, Palette.ORANGE)
                elif desired == "RED":
                    self._set_sat_led(i, Palette.RED)
                else:
                    self._set_sat_led(i, Palette.GREEN)
                self._last_led_states[i] = desired

    # ------------------------------------------------------------------
    # Ballistic calculation
    # ------------------------------------------------------------------

    def _calculate_elevation(self, distance, shell_type, num_charges):
        """Return required elevation in whole degrees (1–89).

        Uses the simplified flat-Earth ballistic formula:
            sin(2θ) = g × d × weight_factor / v²
        where v = base velocity + num_charges × velocity per charge.
        """
        v = _BASE_VELOCITY + max(1, num_charges) * _VELOCITY_PER_CHARGE
        wf = _SHELL_WEIGHT_FACTOR.get(shell_type, 1.0)
        sin_2theta = (_GRAVITY * distance * wf) / (v * v)
        # Clamp to valid arcsin domain
        sin_2theta = max(-1.0, min(1.0, sin_2theta))
        elevation = math.degrees(math.asin(sin_2theta)) / 2.0
        return max(1, min(89, round(elevation)))

    # ------------------------------------------------------------------
    # Mission generation
    # ------------------------------------------------------------------

    def _new_order(self):
        """Generate a new fire order (bearing, distance, shell type)."""
        self._order_bearing  = random.randint(0, 359)
        # Round distance to nearest 100m for clean keypad entry
        dist_units = random.randint(_DIST_MIN // 100, _DIST_MAX // 100)
        self._order_distance = dist_units * 100
        self._order_dist_str = str(self._order_distance)

        # Shell type is part of the order; rotary switch must be dialled to match
        self._order_shell = random.choice([SHELL_HE, SHELL_AP, SHELL_STARSHELL])

        # Bearing that the player must aim at
        self._req_bearing = self._order_bearing

        # Reset distance entry buffer
        self._dist_entered     = ""
        self._last_kp_snapshot = ""

        # Reset LED state cache
        for i in range(_CHARGE_TOGGLE_COUNT):
            self._last_led_states[i] = None

    # ------------------------------------------------------------------
    # Matrix renders
    # ------------------------------------------------------------------

    def _render_target_map(self):
        """Draw a top-down target map showing bearing and range ring."""
        self.core.matrix.clear()
        w = _MATRIX_SIZE
        h = _MATRIX_SIZE
        cx = w // 2
        cy = h // 2

        # Outer range ring (cyan)
        r = 7
        for angle in range(0, 360, 5):
            rad = math.radians(angle)
            x = int(cx + r * math.sin(rad))
            y = int(cy - r * math.cos(rad))
            if 0 <= x < w and 0 <= y < h:
                self.core.matrix.draw_pixel(x, y, Palette.TEAL, brightness=0.4)

        # Bearing line (green arrow from centre toward target)
        bear_rad = math.radians(self._order_bearing)
        for step in range(1, r):
            x = int(cx + step * math.sin(bear_rad))
            y = int(cy - step * math.cos(bear_rad))
            if 0 <= x < w and 0 <= y < h:
                self.core.matrix.draw_pixel(x, y, Palette.GREEN, brightness=0.8)

        # Target dot (red, blinking) at bearing extremity
        tx = int(cx + r * math.sin(bear_rad))
        ty = int(cy - r * math.cos(bear_rad))
        tx = max(0, min(w - 1, tx))
        ty = max(0, min(h - 1, ty))
        self.core.matrix.draw_pixel(tx, ty, Palette.RED, brightness=1.0,
                                    anim_mode="BLINK", speed=3.0)

        # Gun position at centre (white)
        self.core.matrix.draw_pixel(cx, cy, Palette.WHITE, brightness=1.0)

    def _render_ballistic_arc(self):
        """Draw an arc showing the current barrel trajectory.

        The arc height scales with current elevation; bearing sets direction.
        """
        self.core.matrix.clear()
        w = _MATRIX_SIZE
        h = _MATRIX_SIZE
        cx = w // 2
        cy = h // 2

        bear_rad = math.radians(self._player_bearing)
        elev_frac = self._player_elevation / 90.0

        # Draw dotted arc (parabola projected to 2-D overhead view is a line,
        # but we draw an elevation-dependent curve along the bearing direction)
        max_reach = 7
        steps = 14
        for i in range(steps + 1):
            t = i / steps                               # 0 → 1
            r = max_reach * t                           # horizontal distance
            # Parabolic height component (peaks at t=0.5)
            arc_offset = int(3 * elev_frac * (1 - (2 * t - 1) ** 2))
            # Project to matrix: use bearing for direction
            px = int(cx + r * math.sin(bear_rad))
            py = int(cy - r * math.cos(bear_rad) - arc_offset)
            if 0 <= px < w and 0 <= py < h:
                color = Palette.GOLD if i < steps else Palette.RED
                bright = 1.0 if i == steps else 0.6
                self.core.matrix.draw_pixel(px, py, color, brightness=bright)

        # Target crosshair direction indicator
        tx = int(cx + max_reach * math.sin(math.radians(self._req_bearing)))
        ty = int(cy - max_reach * math.cos(math.radians(self._req_bearing)))
        tx = max(0, min(w - 1, tx))
        ty = max(0, min(h - 1, ty))
        self.core.matrix.draw_pixel(tx, ty, Palette.CYAN,
                                    brightness=1.0, anim_mode="BLINK", speed=2.0)

        # Gun base
        self.core.matrix.draw_pixel(cx, cy, Palette.WHITE, brightness=1.0)

    async def _animate_fire(self):
        """Expanding shell-impact explosion at the target location."""
        w = _MATRIX_SIZE
        h = _MATRIX_SIZE

        # Compute impact pixel from bearing
        bear_rad = math.radians(self._order_bearing)
        cx = w // 2
        cy = h // 2
        r = 7
        tx = max(0, min(w - 1, int(cx + r * math.sin(bear_rad))))
        ty = max(0, min(h - 1, int(cy - r * math.cos(bear_rad))))

        # Muzzle flash at gun base
        self.core.matrix.clear()
        self.core.matrix.draw_pixel(cx, cy, Palette.GOLD, brightness=1.0)
        await asyncio.sleep(0.08)

        # Expanding ring at impact
        max_radius = 6
        for radius in range(1, max_radius + 1):
            self.core.matrix.clear()
            for angle in range(0, 360, 10):
                rad = math.radians(angle)
                px = tx + int(radius * math.cos(rad))
                py = ty + int(radius * math.sin(rad))
                if 0 <= px < w and 0 <= py < h:
                    if radius <= 2:
                        col = Palette.GOLD
                    elif radius <= 4:
                        col = Palette.ORANGE
                    else:
                        col = Palette.RED
                    self.core.matrix.draw_pixel(px, py, col, brightness=1.0)
            await asyncio.sleep(0.05)

        self.core.matrix.clear()

    # ------------------------------------------------------------------
    # Phase: ORDER RECEIVED
    # ------------------------------------------------------------------

    async def _run_phase_order(self):
        """Phase 1 – Display the incoming fire order."""
        shell_name = _SHELL_NAMES.get(self._order_shell, self._order_shell)
        self.core.display.update_status(
            f"FIRE ORDER #{self._mission_count + 1}",
            f"BRG:{self._order_bearing:03d} D:{self._order_distance}m {shell_name}"
        )
        self._send_segment("INCOMNG ")
        asyncio.create_task(
            self.core.synth.play_sequence(tones.NOTIFY_INBOX, patch="BEEP")
        )
        self._render_target_map()

        # Brief hold so the player can read the order
        await asyncio.sleep(_ORDER_PAUSE)
        return True

    # ------------------------------------------------------------------
    # Phase: LOAD DISTANCE
    # ------------------------------------------------------------------

    async def _run_phase_distance(self):
        """Phase 2 – Player types the target distance on the keypad."""
        dist_str = self._order_dist_str
        self.core.display.update_status(
            f"LOAD DISTANCE",
            f"TYPE: {dist_str}m"
        )
        self._send_segment("        ")
        self._render_target_map()

        while True:
            # Read keypad buffer from satellite
            current = ""
            if self.sat:
                try:
                    keypads = self.sat.hid.keypad_values
                    if keypads:
                        current = "".join(
                            str(k) for k in keypads[0]
                            if k is not None and str(k).isdigit()
                        )
                except (IndexError, AttributeError):
                    pass

            # Detect new key presses
            if len(current) > len(self._last_kp_snapshot):
                new_chars = current[len(self._last_kp_snapshot):]
                self._dist_entered += new_chars
                self._last_kp_snapshot = current

                # Trim to expected length
                max_len = len(dist_str)
                if len(self._dist_entered) > max_len:
                    self._dist_entered = self._dist_entered[-max_len:]

                self._send_segment(self._dist_entered.ljust(max_len))
                self.core.display.update_status(
                    f"TYPE: {dist_str}m",
                    f"ENTERED: {self._dist_entered}"
                )
                self.core.synth.play_note(880.0, "BEEP", duration=0.05)

            # Check for correct entry
            if len(self._dist_entered) >= len(dist_str):
                if self._dist_entered[-len(dist_str):] == dist_str:
                    self.core.synth.play_note(1200.0, "SUCCESS", duration=0.1)
                    return True
                else:
                    # Wrong – reset with error feedback
                    self._dist_entered    = ""
                    self._last_kp_snapshot = current
                    self._send_segment("ERR     ")
                    self.core.display.update_status(
                        "DISTANCE ERROR",
                        f"RE-ENTER: {dist_str}m"
                    )
                    asyncio.create_task(
                        self.core.synth.play_sequence(tones.ERROR, patch="ERROR")
                    )
                    await asyncio.sleep(0.8)
                    self._send_segment("        ")
                    self.core.display.update_status(
                        f"TYPE: {dist_str}m",
                        "RE-ENTER DISTANCE"
                    )

            await asyncio.sleep(0.05)

    # ------------------------------------------------------------------
    # Phase: SELECT SHELL
    # ------------------------------------------------------------------

    async def _run_phase_shell(self):
        """Phase 3 – Player rotates the 3-position switch to the ordered shell type."""
        required = self._order_shell
        req_name = _SHELL_NAMES.get(required, required)
        self.core.display.update_status(
            "SELECT SHELL TYPE",
            f"REQUIRED: {req_name}"
        )
        self._send_segment(f"SHL:{req_name[:4]} ")

        while True:
            current = self._get_shell_type()
            cur_name = _SHELL_NAMES.get(current, current)
            self.core.display.update_status(
                f"REQUIRED: {req_name}",
                f"SELECTED: {cur_name}"
            )

            if current == required:
                self.core.synth.play_note(1000.0, "SUCCESS", duration=0.1)
                self._send_segment(f"SHL:{req_name[:4]}OK")
                return True

            await asyncio.sleep(0.08)

    # ------------------------------------------------------------------
    # Phase: CHARGE BAGS
    # ------------------------------------------------------------------

    async def _run_phase_charges(self):
        """Phase 4 – Player loads at least min_charges powder charge bags.

        LEDs:
            ON  (loaded)  → ORANGE – charge bag seated
            OFF (empty)   → GREEN  – bay available
            First unloaded slots when below minimum → RED (urgent)

        The segment display shows "MIN:X   " then "CHG:Y   " once enough.
        """
        min_c = self._min_charges
        self._send_segment(f"MIN:{min_c}   ")
        self.core.display.update_status(
            "LOAD CHARGE BAGS",
            f"MINIMUM: {min_c} BAGS"
        )
        asyncio.create_task(
            self.core.synth.play_sequence(tones.UI_TICK, patch="CLICK")
        )

        # Reset LED cache
        for i in range(_CHARGE_TOGGLE_COUNT):
            self._last_led_states[i] = None

        while True:
            active = self._count_active_charges()
            self._sync_charge_leds(min_c)

            # Update segment: show current count
            seg = f"CHG:{active}   " if active < min_c else f"CHG:{active}RDY"
            self._send_segment(seg)
            self.core.display.update_status(
                f"BAGS: {active}/{_CHARGE_TOGGLE_COUNT}",
                f"MIN {min_c} TO CONTINUE"
            )

            if active >= min_c:
                self.core.synth.play_note(1100.0, "SUCCESS", duration=0.1)
                await asyncio.sleep(0.3)  # brief confirmation pause
                return True

            await asyncio.sleep(0.08)

    # ------------------------------------------------------------------
    # Phase: AIM (elevation + bearing)
    # ------------------------------------------------------------------

    async def _run_phase_aim(self):
        """Phase 5 – Player dials in elevation (sat encoder) and bearing (core encoder).

        Momentary toggle sets movement speed:
            UP   → FAST  (×3 degrees per tick)
            DOWN → FINE  (fractions – sub-step accumulator)
            OFF  → NORMAL (×1 degree per tick)
        """
        # Calculate required elevation from the actual loaded charges
        num_charges = self._count_active_charges()
        self._req_elevation = self._calculate_elevation(
            self._order_distance, self._order_shell, num_charges
        )
        self._req_bearing = self._order_bearing

        self.core.display.update_status(
            "AIM CANNON",
            f"ELV:{self._req_elevation:02d}  BRG:{self._req_bearing:03d}"
        )
        self._send_segment(
            f"E{self._req_elevation:02d}B{self._req_bearing:03d} "
        )
        asyncio.create_task(
            self.core.synth.play_sequence(tones.POWER_UP, patch="SCANNER")
        )

        # Initialise encoder references
        self._last_enc_elevation = self._sat_encoder()
        self._last_enc_bearing   = self.core.hid.encoder_positions[_ENC_BEARING]
        self._fine_accum_elev    = 0.0
        self._player_elevation   = 0
        self._player_bearing     = 0

        elev_tol   = self._elev_tol
        bear_tol   = self._bearing_tol

        while True:
            # --- Speed mode from momentary toggle ---
            if self._sat_momentary_up():
                enc_step = _ENCODER_STEP_FAST
                fine_mode = False
            elif self._sat_momentary_down():
                enc_step = 1
                fine_mode = True
            else:
                enc_step = _ENCODER_STEP_NORMAL
                fine_mode = False

            # --- Satellite encoder → elevation ---
            curr_elev_enc = self._sat_encoder()
            delta_e = curr_elev_enc - self._last_enc_elevation
            if delta_e != 0:
                self._last_enc_elevation = curr_elev_enc
                if fine_mode:
                    self._fine_accum_elev += delta_e * 0.33
                    if abs(self._fine_accum_elev) >= 1.0:
                        step = int(self._fine_accum_elev)
                        self._player_elevation = max(0, min(89, self._player_elevation + step))
                        self._fine_accum_elev -= step
                else:
                    self._player_elevation = max(
                        0, min(89, self._player_elevation + delta_e * enc_step)
                    )
                self.core.synth.play_note(660.0, "CLICK", duration=0.03)

            # --- Core encoder → bearing ---
            curr_bear_enc = self.core.hid.encoder_positions[_ENC_BEARING]
            delta_b = curr_bear_enc - self._last_enc_bearing
            if delta_b != 0:
                self._last_enc_bearing = curr_bear_enc
                self._player_bearing = (self._player_bearing + delta_b * enc_step) % 360
                self.core.synth.play_note(660.0, "CLICK", duration=0.03)

            # --- Render ballistic arc ---
            self._render_ballistic_arc()

            # --- Update displays ---
            spd_str = "FAST" if enc_step == _ENCODER_STEP_FAST else (
                "FINE" if fine_mode else "NORM"
            )
            elev_diff  = abs(self._player_elevation - self._req_elevation)
            bear_diff  = abs(self._player_bearing   - self._req_bearing)
            # Account for bearing wrap-around
            bear_diff  = min(bear_diff, 360 - bear_diff)

            self.core.display.update_status(
                f"ELV:{self._player_elevation:02d}° [{self._req_elevation:02d}°]"
                f"  BRG:{self._player_bearing:03d}°",
                f"ERR E:{elev_diff:02d} B:{bear_diff:03d} SPD:{spd_str}"
            )
            self._send_segment(
                f"E{self._player_elevation:02d}B{self._player_bearing:03d}"
            )

            # --- Check lock-on ---
            if elev_diff <= elev_tol and bear_diff <= bear_tol:
                self.core.synth.play_note(1200.0, "SUCCESS", duration=0.15)
                self._send_segment("AIM LOCK")
                return True

            await asyncio.sleep(0.05)

    # ------------------------------------------------------------------
    # Phase: RAM HOME
    # ------------------------------------------------------------------

    async def _run_phase_ram(self):
        """Phase 6 – Player arms the guarded toggle and holds the momentary toggle
        UP for RAM_HOLD_TIME seconds to simulate ramming the round home."""
        self.core.display.update_status(
            "RAM HOME & LOCK",
            "ARM GUARD + HOLD UP"
        )
        self._send_segment("RAM HME ")
        asyncio.create_task(
            self.core.synth.play_sequence(tones.ALARM, patch="ALARM")
        )

        # Turn all charge-bag LEDs cyan (round loaded / awaiting fire)
        for i in range(_CHARGE_TOGGLE_COUNT):
            if self._sat_latching(i):
                self._set_sat_led(i, Palette.CYAN)
                self._last_led_states[i] = "CYAN"

        hold_start = None

        while True:
            arm_on    = self._sat_latching(_SW_ARM)
            mt_up     = self._sat_momentary_up()

            if arm_on and mt_up:
                if hold_start is None:
                    hold_start = ticks_ms()
                held_ms = ticks_diff(ticks_ms(), hold_start)
                held_s  = held_ms / 1000.0
                pct     = min(100, int(held_s / _RAM_HOLD_TIME * 100))
                self._send_segment(f"RAM:{pct:3d}%")
                self.core.display.update_status(
                    "RAMMING HOME...",
                    f"HOLD: {held_s:.1f}s / {_RAM_HOLD_TIME:.0f}s  ({pct}%)"
                )
                if held_s >= _RAM_HOLD_TIME:
                    self.core.synth.play_note(1200.0, "SUCCESS", duration=0.15)
                    self._send_segment("LOCKED! ")
                    return True
            else:
                hold_start = None
                arm_str = "ARM:ON " if arm_on else "ARM:OFF"
                mt_str  = "MT:UP  " if mt_up  else "MT:OFF "
                self.core.display.update_status(
                    "ARM GUARD + HOLD MT UP",
                    f"{arm_str}  {mt_str}"
                )
                self._send_segment("NOTLCKD ")

            await asyncio.sleep(0.05)

    # ------------------------------------------------------------------
    # Phase: FIRE
    # ------------------------------------------------------------------

    async def _run_phase_fire(self):
        """Phase 7 – Player presses the Big Red Button to fire."""
        self.core.display.update_status(
            "READY TO FIRE",
            "PRESS BIG RED BUTTON"
        )
        self._send_segment("FIRE!!! ")
        asyncio.create_task(
            self.core.synth.play_sequence(tones.ALARM, patch="ALARM")
        )
        self._render_ballistic_arc()

        while True:
            if self._sat_button(_BTN_FIRE):
                return True
            await asyncio.sleep(0.05)

    # ------------------------------------------------------------------
    # Phase: RESET
    # ------------------------------------------------------------------

    async def _run_phase_reset(self):
        """Phase 8 – Player returns hardware to safe state before next round.

        Requires:
            - All 8 charge-bag toggles flipped OFF
            - Guarded arm toggle disengaged
        Elevation encoder is not reset by hardware; the game resets the
        internal tracking value automatically.
        """
        self.core.display.update_status(
            "RESET HARDWARE",
            "CLEAR BAGS + ARM"
        )
        self._send_segment("RESET   ")

        # Reset LED cache so sync runs fresh
        for i in range(_CHARGE_TOGGLE_COUNT):
            self._last_led_states[i] = None

        while True:
            all_clear = True

            # Check charge-bag toggles
            for i in range(_CHARGE_TOGGLE_COUNT):
                state = self._sat_latching(i)
                if state:
                    all_clear = False
                    if self._last_led_states[i] != "RED":
                        self._set_sat_led(i, Palette.RED)
                        self._last_led_states[i] = "RED"
                else:
                    if self._last_led_states[i] != "GREEN":
                        self._set_sat_led(i, Palette.GREEN)
                        self._last_led_states[i] = "GREEN"

            # Check guarded arm toggle
            if self._sat_latching(_SW_ARM):
                all_clear = False

            tog_str = "".join(
                ["X" if self._sat_latching(i) else "_" for i in range(_CHARGE_TOGGLE_COUNT)]
            )
            arm_str = "ARM:CLR" if not self._sat_latching(_SW_ARM) else "ARM:ON!"
            self.core.display.update_status(
                f"BAGS: {tog_str}",
                arm_str
            )

            if all_clear:
                self.core.synth.play_note(800.0, "SUCCESS", duration=0.1)
                # Reset player aim for fresh start
                self._player_elevation = 0
                self._player_bearing   = 0
                return True

            await asyncio.sleep(0.08)

    # ------------------------------------------------------------------
    # Timed phase wrapper
    # ------------------------------------------------------------------

    async def _timed_phase(self, phase_coro):
        """Run a phase coroutine; returns False if global time runs out first."""
        task = asyncio.create_task(phase_coro())
        try:
            while not task.done():
                now = ticks_ms()
                elapsed_ms = ticks_diff(now, self._last_tick_ms)
                if elapsed_ms >= 100:
                    self._time_remaining -= elapsed_ms / 1000.0
                    self._last_tick_ms = now

                if self._time_remaining <= 0:
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                    return False

                await asyncio.sleep(0.05)

            return await task

        except asyncio.CancelledError:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            raise

    # ------------------------------------------------------------------
    # Main game loop
    # ------------------------------------------------------------------

    async def run(self):
        """Main Artillery Command game loop."""
        self.difficulty = self.core.data.get_setting(
            "ARTILLERY_COMMAND", "difficulty", "NORMAL"
        )
        self.variant = self.difficulty

        params = _DIFF_PARAMS.get(self.difficulty, _DIFF_PARAMS["NORMAL"])
        self._dist_digits = params["dist_digits"]
        self._min_charges = params["min_charges"]
        self._elev_tol    = params["elev_tol"]
        self._bearing_tol = params["bearing_tol"]

        # Require the Industrial Satellite
        if not self.sat or not self.sat.is_active:
            self.core.display.update_status(
                "ARTY COMMAND", "SAT OFFLINE - ABORT"
            )
            await asyncio.sleep(2)
            return "FAILURE"

        # Intro sequence
        self.core.display.use_standard_layout()
        self.core.display.update_status(
            "ARTY COMMAND",
            "CANNON READY..."
        )
        self.core.matrix.show_icon("ARTILLERY_COMMAND", clear=True)
        asyncio.create_task(
            self.core.synth.play_sequence(tones.POWER_UP, patch="SCANNER")
        )
        await asyncio.sleep(2.0)

        # Reset encoders
        self.core.hid.reset_encoder(value=0, index=_ENC_BEARING)
        if self.sat:
            try:
                self.sat.hid.reset_encoder(value=0, index=_ENC_ELEVATION)
            except Exception:
                pass

        self._time_remaining = _GLOBAL_TIME
        self._mission_count  = 0
        self.score           = 0
        self._last_tick_ms   = ticks_ms()

        while True:
            # Tick the global timer
            now = ticks_ms()
            elapsed_ms = ticks_diff(now, self._last_tick_ms)
            if elapsed_ms >= 100:
                self._time_remaining -= elapsed_ms / 1000.0
                self._last_tick_ms = now

            if self._time_remaining <= 0:
                break

            # Generate a new fire order
            self._new_order()
            mission_start_time = self._time_remaining

            # ----------------------------------------------------------
            # Phase 1: Order received
            # ----------------------------------------------------------
            self._phase = _PHASE_ORDER
            done = await self._timed_phase(self._run_phase_order)
            if not done:
                break

            self._tick_timer()
            if self._time_remaining <= 0:
                break

            # ----------------------------------------------------------
            # Phase 2: Load distance
            # ----------------------------------------------------------
            self._phase = _PHASE_DISTANCE
            done = await self._timed_phase(self._run_phase_distance)
            if not done:
                break

            self._tick_timer()
            if self._time_remaining <= 0:
                break

            # ----------------------------------------------------------
            # Phase 3: Select shell type
            # ----------------------------------------------------------
            self._phase = _PHASE_SHELL
            done = await self._timed_phase(self._run_phase_shell)
            if not done:
                break

            self._tick_timer()
            if self._time_remaining <= 0:
                break

            # ----------------------------------------------------------
            # Phase 4: Load charge bags
            # ----------------------------------------------------------
            self._phase = _PHASE_CHARGES
            done = await self._timed_phase(self._run_phase_charges)
            if not done:
                break

            self._tick_timer()
            if self._time_remaining <= 0:
                break

            # ----------------------------------------------------------
            # Phase 5: Aim (elevation + bearing)
            # ----------------------------------------------------------
            self._phase = _PHASE_AIM
            done = await self._timed_phase(self._run_phase_aim)
            if not done:
                break

            self._tick_timer()
            if self._time_remaining <= 0:
                break

            # ----------------------------------------------------------
            # Phase 6: Ram home
            # ----------------------------------------------------------
            self._phase = _PHASE_RAM
            done = await self._timed_phase(self._run_phase_ram)
            if not done:
                break

            self._tick_timer()
            if self._time_remaining <= 0:
                break

            # ----------------------------------------------------------
            # Phase 7: Fire!
            # ----------------------------------------------------------
            self._phase = _PHASE_FIRE
            done = await self._timed_phase(self._run_phase_fire)
            if not done:
                break

            # Fire animation
            asyncio.create_task(
                self.core.synth.play_sequence(tones.FIREBALL, patch="ALARM")
            )
            await self._animate_fire()

            # ----------------------------------------------------------
            # Mission complete – tally score
            # ----------------------------------------------------------
            mission_time = mission_start_time - self._time_remaining
            speed_bonus  = max(0, int(60 - mission_time) * 5)
            self.score  += 100 + speed_bonus
            self._time_remaining = min(
                _GLOBAL_TIME, self._time_remaining + _BONUS_TIME
            )
            self._mission_count += 1

            self.core.display.update_status(
                "ROUND FIRED!",
                f"+{100 + speed_bonus} PTS  T:{self._time_remaining:.0f}s"
            )
            self._send_segment("FIRED!! ")
            await asyncio.sleep(1.0)

            # ----------------------------------------------------------
            # Phase 8: Reset
            # ----------------------------------------------------------
            self._phase = _PHASE_RESET
            done = await self._timed_phase(self._run_phase_reset)
            if not done:
                break

            self._tick_timer()
            if self._time_remaining <= 0:
                break

            # Brief inter-mission pause
            self.core.display.update_status(
                f"MISSION {self._mission_count} COMPLETE",
                f"SCORE: {self.score}  T:{self._time_remaining:.0f}s"
            )
            await asyncio.sleep(1.0)

        # Time's up
        self._send_segment("TIME UP ")
        return await self.game_over()

    def _tick_timer(self):
        """Snap the global timer to the latest tick."""
        now = ticks_ms()
        elapsed_ms = ticks_diff(now, self._last_tick_ms)
        self._time_remaining -= elapsed_ms / 1000.0
        self._last_tick_ms = now
