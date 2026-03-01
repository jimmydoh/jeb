"""DEFCON Commander Game Mode - Tactical Intercept Protocol."""

import asyncio
import random

from adafruit_ticks import ticks_ms, ticks_diff

from utilities.palette import Palette
from utilities import tones

from .game_mode import GameMode

# ---------------------------------------------------------------------------
# Silo States
# ---------------------------------------------------------------------------
SILO_IDLE      = "IDLE"       # No order – dark
SILO_ORDERED   = "ORDERED"    # Launch order issued – Yellow
SILO_AUTH      = "AUTH"       # Auth code verified + key ON – Cyan
SILO_ARMING    = "ARMING"     # Guarded toggle UP, charging – flashing Orange
SILO_OPEN      = "OPEN"       # Door opening (hold momentary toggle)
SILO_PREP      = "PREP"       # Fault toggle step
SILO_READY     = "READY"      # Solid Orange – fire with Big Red Button
SILO_LAUNCHED  = "LAUNCHED"   # Missile away – White→Blue fade

# ---------------------------------------------------------------------------
# Hardware indices on the Industrial Satellite
# ---------------------------------------------------------------------------
_SW_KEY          = 9    # Key Switch       (Expander 2, latching index 1)
_SW_ARM          = 8    # Guarded Toggle   (Expander 2, latching index 0)
_MT_DOOR         = 0    # Momentary toggle (door open rail)
_BTN_LAUNCH      = 0    # Giant Red Arcade Button

# Fault-toggle indices (latching toggles 0-7)
_FAULT_TOGGLE_START = 0
_FAULT_TOGGLE_END   = 7   # inclusive

# Encoder index for silo browsing
_ENC_SILO        = 0

# ---------------------------------------------------------------------------
# Auth result constants
# ---------------------------------------------------------------------------
_AUTH_PENDING  = "PENDING"   # not enough digits yet
_AUTH_WRONG    = "WRONG"     # wrong code entered
_AUTH_OK       = "OK"        # correct code

# ---------------------------------------------------------------------------
# Timing / gameplay constants
# ---------------------------------------------------------------------------
_NUM_SILOS        = 10
_ORDER_INTERVAL   = 12.0   # seconds between new launch orders
_CHARGE_TIME      = 4.0    # seconds to charge up after arming
_DOOR_OPEN_HOLD   = 2.0    # seconds to hold momentary toggle for door open
_PENALTY_TIME     = 5.0    # time penalty (s) for a fault action

# Probability that a PREP fault is generated (increases with score)
_PREP_FAULT_BASE  = 0.3    # 30% at mission start
_PREP_FAULT_SCALE = 0.05   # +5% per successfully launched silo

# Number of digits in the auth code
_AUTH_CODE_LEN    = 4

# Matrix dimensions
_MATRIX_SIZE      = 16

# Silo field occupies the left portion of the matrix (columns 0-6)
_FIELD_COLS       = 7
# Side-on schematic occupies the right portion (columns 8-15)
_SCHEMATIC_X      = 8
_SCHEMATIC_W      = 8


class DefconCommander(GameMode):
    """DEFCON Commander – Tactical Intercept Protocol.

    The player acts as the last operator in a subterranean Cold War bunker,
    managing a 10-silo ICBM complex through a strict physical launch protocol.

    Hardware (Industrial Satellite SAT-01):
        Core:
            - 16x16 Matrix: Silo field (left) + side-on schematic (right)
            - OLED: Teletype Emergency Action Messages
            - Rotary Encoder: Browse/focus silos

        Industrial Satellite:
            - Key Switch       (latching index 9): Unlock firing circuit
            - Guarded Toggle   (latching index 8): Arm payload
            - Momentary Toggle (index 0):          Open silo door (hold)
            - Giant Red Button (button index 0):   Execute launch
            - 8x Latching Toggles (0-7):           Fault/preparation switches
            - 9-Digit Keypad:                      Auth code entry
    """

    METADATA = {
        "id": "DEFCON_COMMANDER",
        "name": "DEFCON CMDR",
        "icon": "DEFCON_COMMANDER",
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
        super().__init__(core, "DEFCON COMMANDER", "Tactical Intercept Protocol")
        self.sat = None
        for sat in self.core.satellites.values():
            if sat.sat_type_name == "INDUSTRIAL":
                self.sat = sat
                break

        # --- Silo state machine ---
        self.silo_states = [SILO_IDLE] * _NUM_SILOS
        self.silo_auth_codes = [""] * _NUM_SILOS     # 4-digit auth codes
        self.silo_orders = [False] * _NUM_SILOS       # True = order pending

        # --- Active operation tracking ---
        self.active_silo       = -1     # silo currently being processed
        self.focused_silo      = 0      # silo highlighted/viewed in schematic
        self._charge_timer     = 0.0    # seconds of charging elapsed
        self._door_hold_timer  = 0.0    # seconds momentary toggle held
        self._door_open_frac   = 0.0    # 0.0 = closed, 1.0 = fully open
        self._fault_toggle_idx = -1     # which toggle has the fault
        self._fault_toggle_was = False  # the state the toggle was *before* fault

        # --- Keypad input ---
        self._keypad_buf      = ""      # accumulated keypad digits
        self._last_keypad_buf = ""

        # --- Order scheduling ---
        self._order_timer    = _ORDER_INTERVAL * 0.5   # faster first order
        self._order_interval = _ORDER_INTERVAL          # may be scaled by difficulty
        self._launched_count = 0                        # silos successfully launched

        # --- Penalty / result tracking ---
        self._penalty_timer   = 0.0
        self._total_time      = 0.0     # time elapsed (score = -total_time)
        self._reset_needed    = False   # player must reset key + arm before new op

        # --- Tick timing ---
        self._last_tick_ms = 0

    # ------------------------------------------------------------------
    # Satellite hardware accessors
    # ------------------------------------------------------------------

    def _key_is_on(self):
        """Return True if the Key Switch is turned ON."""
        if not self.sat:
            return False
        try:
            return bool(self.sat.hid.latching_values[_SW_KEY])
        except (IndexError, AttributeError):
            return False

    def _arm_is_up(self):
        """Return True if the Guarded Toggle is in the UP (Armed) position."""
        if not self.sat:
            return False
        try:
            return bool(self.sat.hid.latching_values[_SW_ARM])
        except (IndexError, AttributeError):
            return False

    def _door_held(self):
        """Return True while the momentary toggle is held UP (door rail)."""
        if not self.sat:
            return False
        try:
            return self.sat.hid.is_momentary_toggled(_MT_DOOR, direction="U")
        except (IndexError, AttributeError):
            return False

    def _launch_pressed(self):
        """Return True if the Giant Red Arcade Button is pressed."""
        if not self.sat:
            return False
        try:
            return bool(self.sat.hid.buttons_values[_BTN_LAUNCH])
        except (IndexError, AttributeError):
            return False

    def _fault_toggle_state(self, idx):
        """Return the current state of latching toggle idx."""
        if not self.sat:
            return False
        try:
            return bool(self.sat.hid.latching_values[idx])
        except (IndexError, AttributeError):
            return False

    # ------------------------------------------------------------------
    # Keypad input
    # ------------------------------------------------------------------

    def _poll_keypad(self):
        """Poll the satellite keypad and append new digits to the buffer."""
        if not self.sat:
            return
        try:
            keypads = self.sat.hid.keypad_values
            if not keypads:
                return
            current = "".join(
                str(k) for k in keypads[0] if k is not None and str(k).isdigit()
            )
        except (IndexError, AttributeError):
            return

        if current != self._last_keypad_buf:
            # Append only new characters since last poll
            new_chars = current[len(self._last_keypad_buf):]
            self._keypad_buf += new_chars
            self._last_keypad_buf = current

    def _clear_keypad_buf(self):
        """Flush the keypad buffer and reset snapshot."""
        self._keypad_buf = ""
        self._last_keypad_buf = ""

    # ------------------------------------------------------------------
    # Order management
    # ------------------------------------------------------------------

    def _issue_order(self):
        """Issue a launch order for a random IDLE silo."""
        idle_silos = [i for i in range(_NUM_SILOS) if self.silo_states[i] == SILO_IDLE]
        if not idle_silos:
            return

        target = random.choice(idle_silos)
        auth_code = "".join([str(random.randint(0, 9)) for _ in range(_AUTH_CODE_LEN)])

        self.silo_states[target]     = SILO_ORDERED
        self.silo_auth_codes[target] = auth_code
        self.silo_orders[target]     = True

        self.focused_silo = target
        self.core.display.update_status(
            f"ICBM LAUNCH ORDER | SILO {target + 1:02d}",
            f"AUTH: {auth_code} | KEY+ARM+FIRE"
        )
        asyncio.create_task(
            self.core.synth.play_sequence(tones.ALARM, patch="ALARM")
        )

    # ------------------------------------------------------------------
    # Protocol steps
    # ------------------------------------------------------------------

    def _try_auth(self, silo_idx):
        """Check keypad buffer for silo selection + auth code.

        Returns _AUTH_PENDING, _AUTH_WRONG, or _AUTH_OK.
        """
        if not self.silo_orders[silo_idx]:
            return _AUTH_PENDING

        # Expect the player to have typed the auth code (last _AUTH_CODE_LEN digits)
        if len(self._keypad_buf) < _AUTH_CODE_LEN:
            return _AUTH_PENDING

        entered = self._keypad_buf[-_AUTH_CODE_LEN:]
        expected = self.silo_auth_codes[silo_idx]

        if entered != expected:
            return _AUTH_WRONG
        return _AUTH_OK

    def _trigger_fault(self, silo_idx):
        """Assign a random fault toggle for the PREP phase."""
        self._fault_toggle_idx = random.randint(_FAULT_TOGGLE_START, _FAULT_TOGGLE_END)
        self._fault_toggle_was = self._fault_toggle_state(self._fault_toggle_idx)
        self.core.display.update_status(
            f"SILO {silo_idx + 1:02d} FAULT",
            f"TOGGLE SW-{self._fault_toggle_idx + 1:02d} TO CLEAR"
        )
        asyncio.create_task(
            self.core.synth.play_sequence(tones.DANGER, patch="ALARM")
        )

    def _fault_cleared(self):
        """Return True if the fault toggle has been flipped to the opposite state."""
        if self._fault_toggle_idx < 0:
            return True
        current = self._fault_toggle_state(self._fault_toggle_idx)
        return current != self._fault_toggle_was

    def _apply_penalty(self):
        """Record a time penalty and flash the matrix red."""
        self._penalty_timer = _PENALTY_TIME
        asyncio.create_task(
            self.core.synth.play_sequence(tones.ERROR, patch="ALARM")
        )

    # ------------------------------------------------------------------
    # State machine tick
    # ------------------------------------------------------------------

    def _tick_active_silo(self, delta_s):
        """Drive the protocol state machine for the active silo."""
        if self.active_silo < 0:
            return

        si = self.active_silo
        state = self.silo_states[si]

        # ---- ORDERED: waiting for auth code + key switch ON ----
        if state == SILO_ORDERED:
            self._poll_keypad()
            result = self._try_auth(si)

            if result == _AUTH_WRONG:
                self._clear_keypad_buf()
                self._apply_penalty()
                self.core.display.update_status("AUTH FAILED", "WRONG CODE")
            elif result == _AUTH_OK:
                if self._key_is_on():
                    # Auth OK + key on → advance to ARMING
                    self.silo_states[si] = SILO_AUTH
                    self._clear_keypad_buf()
                    self.core.display.update_status(
                        f"SILO {si + 1:02d} AUTHORIZED",
                        "RAISE ARM TOGGLE"
                    )
                    asyncio.create_task(
                        self.core.synth.play_sequence(tones.SUCCESS, patch="UI_SELECT")
                    )
                else:
                    self.core.display.update_status(
                        f"SILO {si + 1:02d} AUTH OK",
                        "TURN KEY TO UNLOCK"
                    )

        # ---- AUTH: waiting for guarded toggle UP ----
        elif state == SILO_AUTH:
            if not self._key_is_on():
                # Key turned off – abort
                self.silo_states[si] = SILO_ORDERED
                self.core.display.update_status("KEY REMOVED", "RE-AUTHENTICATE")
            elif self._arm_is_up():
                self.silo_states[si] = SILO_ARMING
                self._charge_timer = 0.0
                self.core.display.update_status(
                    f"SILO {si + 1:02d} ARMING",
                    "HOLD FOR DOOR OPEN"
                )
                asyncio.create_task(
                    self.core.synth.play_sequence(tones.CHARGING, patch="SCANNER")
                )

        # ---- ARMING: charging – advance timer ----
        elif state == SILO_ARMING:
            if not self._arm_is_up():
                # Toggle dropped – abort arming
                self.silo_states[si] = SILO_AUTH
                self._charge_timer = 0.0
                self.core.display.update_status("ARM ABORTED", "RAISE ARM AGAIN")
                return

            self._charge_timer += delta_s
            charge_pct = int((self._charge_timer / _CHARGE_TIME) * 100)
            self.core.display.update_status(
                f"SILO {si + 1:02d} CHARGING {charge_pct}%",
                "HOLD DOOR TOGGLE"
            )

            if self._charge_timer >= _CHARGE_TIME:
                # Charged – transition to OPEN phase
                self.silo_states[si] = SILO_OPEN
                self._door_hold_timer = 0.0
                self._door_open_frac  = 0.0
                self.core.display.update_status(
                    f"SILO {si + 1:02d} CHARGED",
                    "HOLD DOOR TOGGLE TO OPEN"
                )

        # ---- OPEN: hold momentary toggle until door opens ----
        elif state == SILO_OPEN:
            if self._door_held():
                self._door_hold_timer += delta_s
                self._door_open_frac = min(1.0, self._door_hold_timer / _DOOR_OPEN_HOLD)

                if self._door_hold_timer >= _DOOR_OPEN_HOLD:
                    # Door fully open – check for prep fault
                    fault_prob = min(
                        0.9,
                        _PREP_FAULT_BASE + self._launched_count * _PREP_FAULT_SCALE
                    )
                    if random.random() < fault_prob:
                        self.silo_states[si] = SILO_PREP
                        self._trigger_fault(si)
                    else:
                        self.silo_states[si] = SILO_READY
                        self.core.display.update_status(
                            f"SILO {si + 1:02d} READY",
                            "PRESS RED BUTTON"
                        )
                        asyncio.create_task(
                            self.core.synth.play_sequence(tones.POWER_UP, patch="SCANNER")
                        )
            else:
                # Toggle released – timer does not reset but doesn't advance
                pass

        # ---- PREP: clear random fault toggle ----
        elif state == SILO_PREP:
            if self._fault_cleared():
                self._fault_toggle_idx = -1
                self.silo_states[si] = SILO_READY
                self.core.display.update_status(
                    f"SILO {si + 1:02d} FAULT CLEAR",
                    "PRESS RED BUTTON"
                )
                asyncio.create_task(
                    self.core.synth.play_sequence(tones.SUCCESS, patch="UI_SELECT")
                )

        # ---- READY: waiting for Giant Red Button ----
        elif state == SILO_READY:
            if self._launch_pressed():
                self.silo_states[si] = SILO_LAUNCHED
                self._launched_count += 1
                self._reset_needed = True
                self.score += 1000
                self.core.display.update_status(
                    f"SILO {si + 1:02d} LAUNCH!",
                    f"SILOS LAUNCHED: {self._launched_count}/{_NUM_SILOS}"
                )
                asyncio.create_task(
                    self.core.synth.play_sequence(tones.LAUNCH, patch="SCANNER")
                )
                # Schedule reset requirement after brief delay
                asyncio.create_task(self._post_launch_display(si))

        # ---- LAUNCHED: record done – wait for reset ----
        elif state == SILO_LAUNCHED:
            if self._reset_needed:
                if not self._arm_is_up() and not self._key_is_on():
                    self._reset_needed = False
                    self.active_silo = -1
                    self.core.display.update_status(
                        "PROTOCOL RESET",
                        f"STANDBY | LAUNCHED: {self._launched_count}/{_NUM_SILOS}"
                    )
                    asyncio.create_task(
                        self.core.synth.play_sequence(tones.UI_CONFIRM, patch="UI_SELECT")
                    )

    async def _post_launch_display(self, si):
        """Show a brief launch animation then remind player to reset."""
        await asyncio.sleep(1.5)
        self.core.display.update_status(
            "MISSILE AWAY",
            "DISARM: KEY OFF + ARM DOWN"
        )

    # ------------------------------------------------------------------
    # Order scheduler
    # ------------------------------------------------------------------

    def _update_orders(self, delta_s):
        """Issue new orders on a timer when silos are idle."""
        if self._launched_count >= _NUM_SILOS:
            return   # all silos launched

        # Only issue a new order if no order is currently being processed
        pending = [i for i in range(_NUM_SILOS) if self.silo_states[i] == SILO_ORDERED]
        if self.active_silo >= 0 or pending:
            return

        self._order_timer -= delta_s
        if self._order_timer <= 0.0:
            self._issue_order()
            self._order_timer = self._order_interval

            # Auto-activate the silo that was just ordered
            ordered_silos = [
                i for i in range(_NUM_SILOS) if self.silo_states[i] == SILO_ORDERED
            ]
            if ordered_silos:
                self.active_silo = ordered_silos[0]
                self.focused_silo = self.active_silo

    # ------------------------------------------------------------------
    # Matrix rendering
    # ------------------------------------------------------------------

    def _silo_pixel_pos(self, silo_idx):
        """Return the (x, y) top-left pixel of silo_idx in the silo field."""
        row = silo_idx // 2
        col = silo_idx % 2
        px = 1 + col * 3
        py = 1 + row * 3
        return px, py

    def _silo_color(self, silo_idx):
        """Return the display color for a silo based on its state."""
        state = self.silo_states[silo_idx]
        if state == SILO_IDLE:
            return Palette.OFF
        if state == SILO_ORDERED:
            return Palette.YELLOW
        if state == SILO_AUTH:
            return Palette.CYAN
        if state in (SILO_ARMING, SILO_OPEN, SILO_PREP):
            return Palette.ORANGE
        if state == SILO_READY:
            return Palette.ORANGE
        if state == SILO_LAUNCHED:
            return Palette.GREEN
        return Palette.OFF

    def _silo_anim(self, silo_idx):
        """Return the animation mode for a silo."""
        state = self.silo_states[silo_idx]
        if state in (SILO_ARMING, SILO_PREP):
            return "BLINK"
        return None

    def _render_silo_field(self):
        """Draw all 10 silos on the left portion of the matrix."""
        for i in range(_NUM_SILOS):
            px, py = self._silo_pixel_pos(i)
            color  = self._silo_color(i)
            anim   = self._silo_anim(i)

            for dx in range(2):
                for dy in range(2):
                    self.core.matrix.draw_pixel(
                        px + dx, py + dy, color,
                        show=False,
                        anim_mode=anim,
                        speed=3.0
                    )

        # Focus indicator: border pixel around active silo
        if self.focused_silo >= 0:
            fx, fy = self._silo_pixel_pos(self.focused_silo)
            focus_col = Palette.WHITE
            self.core.matrix.draw_pixel(fx - 1, fy - 1, focus_col, show=False)

    def _render_schematic(self):
        """Draw the side-on silo schematic for the focused silo."""
        si = self.focused_silo
        state = self.silo_states[si] if 0 <= si < _NUM_SILOS else SILO_IDLE

        x0 = _SCHEMATIC_X      # left wall of schematic tube
        x1 = _SCHEMATIC_X + 5  # right wall (tube is 4px wide, walls at edges)
        tube_x0 = x0 + 1       # inner left of tube
        tube_x1 = x0 + 4       # inner right of tube (4 px wide)

        # Silo walls (vertical lines, full height)
        wall_color = Palette.GRAY
        for y in range(0, 14):
            self.core.matrix.draw_pixel(x0,  y, wall_color, show=False)
            self.core.matrix.draw_pixel(x1,  y, wall_color, show=False)

        # Base (bottom 2 rows)
        base_color = Palette.GRAY
        for bx in range(x0, x1 + 1):
            self.core.matrix.draw_pixel(bx, 14, base_color, show=False)
            self.core.matrix.draw_pixel(bx, 15, base_color, show=False)

        # Door/cover – slides up as door opens
        door_rows = 2
        if state in (SILO_IDLE, SILO_ORDERED, SILO_AUTH, SILO_ARMING):
            door_y = 0   # door closed
        elif state == SILO_OPEN:
            # Door slides off as player holds toggle
            door_y = -int(self._door_open_frac * (door_rows + 1))
        else:
            door_y = -(door_rows + 1)   # fully open (off-screen above)

        door_color = Palette.SILVER
        for dy in range(door_rows):
            ry = door_y + dy
            if 0 <= ry < _MATRIX_SIZE:
                for tx in range(tube_x0, tube_x1 + 1):
                    self.core.matrix.draw_pixel(tx, ry, door_color, show=False)

        # Missile body (rows 2-12 inside tube)
        if state == SILO_LAUNCHED:
            # Show missile rising above the door
            missile_bottom = max(-1, 12 - int(self._door_open_frac * 14))
        else:
            missile_bottom = 12

        nose_color   = Palette.WHITE
        body_color   = Palette.SILVER
        exhaust_color = Palette.ORANGE if state in (SILO_READY, SILO_LAUNCHED) else Palette.OFF

        for row in range(2, missile_bottom + 1):
            if row < 0 or row >= _MATRIX_SIZE:
                continue
            col = nose_color if row == 2 else body_color
            for tx in range(tube_x0, tube_x1 + 1):
                self.core.matrix.draw_pixel(tx, row, col, show=False)

        # Exhaust glow at the base when ready/launched
        if state in (SILO_READY, SILO_LAUNCHED):
            for tx in range(tube_x0, tube_x1 + 1):
                if missile_bottom + 1 < 14:
                    self.core.matrix.draw_pixel(
                        tx, missile_bottom + 1, exhaust_color, show=False,
                        anim_mode="BLINK", speed=4.0
                    )

        # Fault indicator (flash the fault toggle position on schematic)
        if state == SILO_PREP and self._fault_toggle_idx >= 0:
            fi_y = 4 + self._fault_toggle_idx
            if 0 <= fi_y < _MATRIX_SIZE:
                self.core.matrix.draw_pixel(
                    x0 - 1, fi_y, Palette.RED, show=False,
                    anim_mode="BLINK", speed=5.0
                )

    def _render_matrix(self):
        """Full matrix render: clear, draw field, draw schematic."""
        self.core.matrix.fill(Palette.OFF, show=False)
        self._render_silo_field()
        self._render_schematic()

    # ------------------------------------------------------------------
    # Satellite LED feedback
    # ------------------------------------------------------------------

    def _update_sat_leds(self):
        """Update satellite toggle LEDs to reflect fault and launch states."""
        if not self.sat:
            return

        for i in range(_FAULT_TOGGLE_START, _FAULT_TOGGLE_END + 1):
            if self._fault_toggle_idx == i:
                cmd_type = "LEDFLASH"
                led_cmd  = f"{i},{Palette.RED.index},0.0,1.0,3,0.2,0.2"
            elif i < _NUM_SILOS and self.silo_states[i] == SILO_LAUNCHED:
                cmd_type = "LED"
                led_cmd  = f"{i},{Palette.GREEN.index},0.0,1.0,2"
            else:
                cmd_type = "LED"
                led_cmd  = f"{i},{Palette.OFF.index},0.0,0.0,2"
            try:
                self.sat.send(cmd_type, led_cmd)
            except (AttributeError, OSError):
                pass

    # ------------------------------------------------------------------
    # Main game loop
    # ------------------------------------------------------------------

    async def run(self):
        """Main DEFCON Commander game loop."""
        self.difficulty = self.core.data.get_setting(
            "DEFCON_COMMANDER", "difficulty", "NORMAL"
        )
        self.variant = self.difficulty

        # Difficulty scaling
        if self.difficulty == "HARD":
            self._order_interval = 9.0
        elif self.difficulty == "INSANE":
            self._order_interval = 6.0

        # Satellite check
        if not self.sat or not self.sat.is_active:
            self.core.display.update_status("DEFCON CMDR", "SAT OFFLINE – ABORT")
            await asyncio.sleep(2)
            return "FAILURE"

        # Startup teletype intro
        self.core.display.use_standard_layout()
        self.core.display.update_status("DEFCON COMMANDER", "SYSTEMS ONLINE...")
        asyncio.create_task(
            self.core.synth.play_sequence(tones.POWER_UP, patch="SCANNER")
        )
        await asyncio.sleep(2.0)
        self.core.display.update_status(
            "LAUNCH AUTHORITY GRANTED",
            "AWAIT ORDERS..."
        )
        await asyncio.sleep(1.5)

        # Reset state
        self.silo_states      = [SILO_IDLE] * _NUM_SILOS
        self.silo_auth_codes  = [""] * _NUM_SILOS
        self.silo_orders      = [False] * _NUM_SILOS
        self.active_silo      = -1
        self.focused_silo     = 0
        self._charge_timer    = 0.0
        self._door_hold_timer = 0.0
        self._door_open_frac  = 0.0
        self._fault_toggle_idx = -1
        self._launched_count  = 0
        self._order_timer     = self._order_interval * 0.5
        self._reset_needed    = False
        self._penalty_timer   = 0.0
        self._total_time      = 0.0
        self.score            = 0

        self._clear_keypad_buf()
        self.core.hid.reset_encoder(_ENC_SILO)
        self._last_tick_ms = ticks_ms()

        while True:
            now       = ticks_ms()
            delta_ms  = ticks_diff(now, self._last_tick_ms)

            if delta_ms >= 33:   # ~30 FPS
                delta_s = delta_ms / 1000.0
                self._last_tick_ms = now

                # Accumulate total time (score penalises time)
                if self._launched_count < _NUM_SILOS:
                    self._total_time += delta_s
                    self.score = max(0, 10000 - int(self._total_time * 10))

                # Penalty flash timer
                if self._penalty_timer > 0:
                    self._penalty_timer -= delta_s
                    self.core.matrix.fill(Palette.RED, show=True, anim_mode=None)
                    await asyncio.sleep(0.01)
                    continue

                # Issue orders / update order timer
                self._update_orders(delta_s)

                # Encoder: browse silos
                try:
                    enc = self.core.hid.encoder_positions[_ENC_SILO]
                    self.focused_silo = enc % _NUM_SILOS
                except (IndexError, AttributeError):
                    pass

                # Reset guard: prevent starting a new op without resetting
                if self._reset_needed:
                    self.core.display.update_status(
                        "RESET REQUIRED",
                        "KEY OFF + ARM DOWN"
                    )
                    if not self._arm_is_up() and not self._key_is_on():
                        self._reset_needed = False
                        self.active_silo = -1
                else:
                    # Drive the active silo's protocol
                    self._tick_active_silo(delta_s)

                # Render
                self._render_matrix()
                self._update_sat_leds()

                # Victory condition: all 10 silos launched
                if self._launched_count >= _NUM_SILOS:
                    self.core.display.update_status(
                        "ALL SILOS LAUNCHED",
                        f"TIME: {int(self._total_time)}s | SCORE: {self.score}"
                    )
                    asyncio.create_task(
                        self.core.synth.play_sequence(tones.POWER_UP, patch="SCANNER")
                    )
                    await asyncio.sleep(3.0)
                    return await self.victory()

            await asyncio.sleep(0.01)
