"""Iron Canopy Game Mode - Tactical SAM Battery Defense."""

import asyncio
import random
import math

from adafruit_ticks import ticks_ms, ticks_diff

from utilities.palette import Palette
from utilities import matrix_animations
from utilities import tones

from .game_mode import GameMode

# ---------------------------------------------------------------------------
# Tube States
# ---------------------------------------------------------------------------
TUBE_READY      = "READY"
TUBE_ARMED      = "ARMED"
TUBE_FIRED      = "FIRED"
TUBE_RELOADING  = "RELOADING"

# ---------------------------------------------------------------------------
# Power Routing Modes
# ---------------------------------------------------------------------------
POWER_ACTIVE_RADAR = "ACTIVE_RADAR"   # POS 1: fast radar, reload paused
POWER_AUTO_LOADER  = "AUTO_LOADER"    # POS 2: slow radar, fast reload
POWER_ECM_JAMMING  = "ECM_JAMMING"    # POS 3: radar blind, weapons locked

# Rotary switch latching toggle indices on the Industrial Satellite
_SW_ROTARY_A = 10   # Position A (Exp2 pin 4)
_SW_ROTARY_B = 11   # Position B (Exp2 pin 5)

# Latching toggle indices for missile tubes 1-8
_TUBE_TOGGLE_START = 0
_TUBE_TOGGLE_END   = 7   # inclusive

# Guarded toggle (Master Arm) index
_SW_ARM  = 8

# Momentary toggle index (firing rail)
_MT_FIRE = 0

# Large button index (CIWS panic)
_BTN_CIWS = 0

# Encoder index for threat list
_ENC_THREAT = 0

# Matrix dimensions
_MATRIX_SIZE = 16

# Base health
_BASE_HEALTH_MAX   = 100
_CIWS_HEALTH_DRAIN = 25

# Reload durations (seconds)
_RELOAD_TIME_FAST  = 4.0
_RELOAD_TIME_SLOW  = 12.0

# Bogey speed range (normalized units per second)
_BOGEY_SPEED_MIN = 0.02
_BOGEY_SPEED_MAX = 0.06

# CIWS blast radius (normalized, clears this radius from center)
_CIWS_RADIUS = 0.3

# Decryption code length
_DECRYPT_CODE_LEN = 3


class IronCanopy(GameMode):
    """Iron Canopy Game Mode.

    Tactical SAM battery defense game using the full Industrial Satellite
    hardware loadout. The player must juggle power routing, target locking,
    payload allocation, and strict firing protocols while defending a base.

    Hardware:
        Core:
            - 16x16 Matrix: Radial radar sweep (center = base, red = bogeys, blue = interceptors)
            - OLED: Threat board telemetry
            - Rotary Encoder + Push: Scroll/lock threat list

        Industrial Satellite (SAT-01):
            - 14-Segment Display: Base integrity / power mode
            - 8x Latching Toggles: Missile tube allocation (0-7)
            - 3-Position Rotary Switch: Power routing (indices 10-11)
            - Guarded Toggle: Master Arm (index 8)
            - Momentary Toggle: Firing rail (pair 0)
            - 9-Digit Keypad: Decrypt jammed signals
            - Big Button: CIWS panic (index 0)
    """

    METADATA = {
        "id": "IRON_CANOPY",
        "name": "IRON CANOPY",
        "icon": "IRON_CANOPY",
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
        super().__init__(core, "IRON CANOPY", "Tactical SAM Battery Defense")
        self.sat = None
        for sat in self.core.satellites.values():
            if sat.sat_type_name == "INDUSTRIAL":
                self.sat = sat
                break

        # Missile tube state machine: 8 tubes
        self.tube_states = [TUBE_READY] * 8
        self.tube_reload_timers = [0.0] * 8   # seconds remaining for reload

        # Bogey entity list: each is a dict with x, y, speed, jammed, id
        self.bogeys = []
        self._bogey_id_counter = 0

        # Interceptors in flight: each is a dict with x, y, target_id
        self.interceptors = []

        # Locked target index into self.bogeys (-1 = none)
        self.locked_idx = 0

        # Base health (0-100)
        self.base_health = _BASE_HEALTH_MAX

        # Radar sweep state
        self._sweep_angle = 0.0
        self._sweep_speed_normal = 90.0   # degrees/second in ACTIVE_RADAR mode
        self._sweep_speed_slow   = 18.0   # degrees/second in AUTO_LOADER mode

        # Decryption state: pending code for jammed bogey
        self._decrypt_target_id  = None
        self._decrypt_code       = ""
        self._decrypt_answer     = ""

        # Keypad buffer snapshot for detecting new input
        self._last_keypad_buf    = ""

        # Tick timing
        self._last_tick_ms = 0

        # Spawn timing
        self._spawn_interval     = 6.0    # seconds between spawns
        self._spawn_timer        = 0.0

        # Difficulty parameters (set in run())
        self._max_bogeys         = 6
        self._bogey_speed_scale  = 1.0

    # ------------------------------------------------------------------
    # Power routing helpers
    # ------------------------------------------------------------------

    def _get_power_mode(self):
        """Read the 3-position rotary switch from the satellite and return a power mode string."""
        if not self.sat:
            return POWER_ACTIVE_RADAR
        try:
            rot_a = self.sat.hid.latching_values[_SW_ROTARY_A]
            rot_b = self.sat.hid.latching_values[_SW_ROTARY_B]
        except (IndexError, AttributeError):
            return POWER_ACTIVE_RADAR

        if rot_a and not rot_b:
            return POWER_ACTIVE_RADAR
        if not rot_a and rot_b:
            return POWER_AUTO_LOADER
        if rot_a and rot_b:
            return POWER_ECM_JAMMING
        return POWER_ACTIVE_RADAR   # default center = POS 1

    # ------------------------------------------------------------------
    # Tube helpers
    # ------------------------------------------------------------------

    def _get_armed_tubes(self):
        """Return list of tube indices whose latching toggle is UP (armed)."""
        armed = []
        if not self.sat:
            return armed
        try:
            for i in range(_TUBE_TOGGLE_START, _TUBE_TOGGLE_END + 1):
                if self.sat.hid.latching_values[i]:
                    armed.append(i)
        except (IndexError, AttributeError):
            pass
        return armed

    def _is_arm_engaged(self):
        """Return True if the guarded Master Arm toggle is engaged."""
        if not self.sat:
            return False
        try:
            return bool(self.sat.hid.latching_values[_SW_ARM])
        except (IndexError, AttributeError):
            return False

    def _is_fire_rail_hot(self):
        """Return True if the momentary firing toggle is held UP."""
        if not self.sat:
            return False
        try:
            return self.sat.hid.is_momentary_toggled(_MT_FIRE, direction="U")
        except (IndexError, AttributeError):
            return False

    def _is_ciws_pressed(self):
        """Return True if the big CIWS button is pressed."""
        if not self.sat:
            return False
        try:
            return bool(self.sat.hid.buttons_values[_BTN_CIWS])
        except (IndexError, AttributeError):
            return False

    # ------------------------------------------------------------------
    # Bogey helpers
    # ------------------------------------------------------------------

    def _spawn_bogey(self):
        """Spawn a new bogey at a random edge of the radar field."""
        edge = random.randint(0, 3)
        if edge == 0:   # top
            x = random.random()
            y = 0.0
        elif edge == 1:  # right
            x = 1.0
            y = random.random()
        elif edge == 2:  # bottom
            x = random.random()
            y = 1.0
        else:           # left
            x = 0.0
            y = random.random()

        speed = random.uniform(_BOGEY_SPEED_MIN, _BOGEY_SPEED_MAX) * self._bogey_speed_scale
        jammed = random.random() < 0.25  # 25% chance of jammed signal

        bogey = {
            "id":     self._bogey_id_counter,
            "x":      x,
            "y":      y,
            "speed":  speed,
            "jammed": jammed,
        }
        if jammed:
            bogey["code"] = "".join([str(random.randint(0, 9)) for _ in range(_DECRYPT_CODE_LEN)])

        self._bogey_id_counter += 1
        self.bogeys.append(bogey)

    def _update_bogeys(self, delta_s, power_mode):
        """Move bogeys toward the center. ECM jamming slows them."""
        cx = 0.5
        cy = 0.5

        speed_mult = 0.4 if power_mode == POWER_ECM_JAMMING else 1.0

        bogeys_to_remove = []
        for bogey in self.bogeys:
            dx = cx - bogey['x']
            dy = cy - bogey['y']
            dist = math.sqrt(dx * dx + dy * dy)
            if dist < 0.05:
                # Bogey reached the base – deal damage
                bogeys_to_remove.append(bogey)
                self.base_health -= 10
                asyncio.create_task(
                    self.core.synth.play_sequence(tones.DANGER, patch="ALARM")
                )
                continue

            # Normalise direction and advance
            step = bogey['speed'] * delta_s * speed_mult
            bogey['x'] += (dx / dist) * step
            bogey['y'] += (dy / dist) * step

        for b in bogeys_to_remove:
            self.bogeys.remove(b)

    def _update_interceptors(self, delta_s):
        """Move interceptors toward their target bogey; remove on intercept."""
        interceptors_to_remove = []
        for interceptor in self.interceptors:
            target = next((b for b in self.bogeys if b['id'] == interceptor['target_id']), None)
            if target is None:
                interceptors_to_remove.append(interceptor)
                continue

            dx = target['x'] - interceptor['x']
            dy = target['y'] - interceptor['y']
            dist = math.sqrt(dx * dx + dy * dy)

            if dist < 0.07:
                # Intercept!
                interceptors_to_remove.append(interceptor)
                self.bogeys.remove(target)
                self.score += 100
                self.core.synth.play_note(1200.0, "UI_SELECT", duration=0.05)
                continue

            step = 0.18 * delta_s   # interceptor travel speed
            interceptor['x'] += (dx / dist) * step
            interceptor['y'] += (dy / dist) * step

        for i in interceptors_to_remove:
            self.interceptors.remove(i)

    # ------------------------------------------------------------------
    # Reload logic
    # ------------------------------------------------------------------

    def _update_reload(self, delta_s, power_mode):
        """Advance reload timers for tubes in RELOADING state."""
        if power_mode == POWER_ACTIVE_RADAR:
            return  # reload paused in ACTIVE_RADAR mode

        reload_time = _RELOAD_TIME_FAST if power_mode == POWER_AUTO_LOADER else _RELOAD_TIME_SLOW

        for i in range(8):
            if self.tube_states[i] == TUBE_RELOADING:
                self.tube_reload_timers[i] -= delta_s
                if self.tube_reload_timers[i] <= 0.0:
                    self.tube_states[i] = TUBE_READY
                    self.tube_reload_timers[i] = 0.0
                    self.core.synth.play_note(660.0, "UI_SELECT", duration=0.04)

    # ------------------------------------------------------------------
    # Tube state sync with physical toggles
    # ------------------------------------------------------------------

    def _sync_tube_armed_states(self):
        """Arm READY tubes whose physical toggle is UP; disarm if back down."""
        for i in range(8):
            toggle_up = (self.sat is not None and
                         len(self.sat.hid.latching_values) > i and
                         self.sat.hid.latching_values[i])

            if toggle_up and self.tube_states[i] == TUBE_READY:
                self.tube_states[i] = TUBE_ARMED
            elif not toggle_up and self.tube_states[i] == TUBE_ARMED:
                self.tube_states[i] = TUBE_READY

    def _check_reset_for_reload(self):
        """Move FIRED tubes into RELOADING when their toggle is flipped back DOWN."""
        for i in range(8):
            if self.tube_states[i] == TUBE_FIRED:
                toggle_down = (self.sat is None or
                               not self.sat.hid.latching_values[i])
                if toggle_down:
                    self.tube_states[i] = TUBE_RELOADING
                    self.tube_reload_timers[i] = _RELOAD_TIME_SLOW

    # ------------------------------------------------------------------
    # Firing protocol
    # ------------------------------------------------------------------

    def _attempt_fire(self):
        """Execute the firing protocol if all conditions are met."""
        # Require Master Arm engaged
        if not self._is_arm_engaged():
            return

        # Require fire rail hot (momentary toggle held UP)
        if not self._is_fire_rail_hot():
            return

        # Need a locked target
        if not self.bogeys or self.locked_idx >= len(self.bogeys):
            return

        target = self.bogeys[self.locked_idx]

        # Jammed bogeys require decryption before they can be engaged
        if target.get('jammed') and self._decrypt_target_id != target['id']:
            return

        # Collect ARMED tubes and launch one interceptor per tube
        launched = 0
        for i in range(8):
            if self.tube_states[i] == TUBE_ARMED:
                self.tube_states[i] = TUBE_FIRED
                self.interceptors.append({
                    'x':         0.5,   # launch from base (center)
                    'y':         0.5,
                    'target_id': target['id'],
                })
                launched += 1

        if launched > 0:
            # Heavy launch transient
            asyncio.create_task(
                self.core.synth.play_sequence(tones.LAUNCH, patch="SCANNER")
            )
            self.core.display.update_status(
                f"LAUNCH x{launched}",
                f"TGT:{target['id']:03d}"
            )

    # ------------------------------------------------------------------
    # CIWS panic button
    # ------------------------------------------------------------------

    def _check_ciws(self):
        """CIWS clears bogeys near the base at the cost of base health."""
        if not self._is_ciws_pressed():
            return
        bogeys_cleared = 0
        bogeys_to_remove = []
        for bogey in self.bogeys:
            dx = 0.5 - bogey['x']
            dy = 0.5 - bogey['y']
            dist = math.sqrt(dx * dx + dy * dy)
            if dist < _CIWS_RADIUS:
                bogeys_to_remove.append(bogey)
                bogeys_cleared += 1

        for b in bogeys_to_remove:
            self.bogeys.remove(b)

        if bogeys_cleared > 0:
            self.base_health = max(0, self.base_health - _CIWS_HEALTH_DRAIN)
            self.score += bogeys_cleared * 25
            asyncio.create_task(
                self.core.synth.play_sequence(tones.POWER_UP, patch="BUZZ")
            )

    # ------------------------------------------------------------------
    # Decryption via keypad
    # ------------------------------------------------------------------

    def _check_decryption(self):
        """Check the satellite keypad buffer for a 3-digit override code."""
        if not self.sat:
            return
        try:
            keypads = self.sat.hid.keypad_values
            if not keypads:
                return
            # Collect recently pressed digits from the first keypad buffer
            current = "".join(str(k) for k in keypads[0] if k is not None and str(k).isdigit())
        except (IndexError, AttributeError):
            return

        if len(current) < _DECRYPT_CODE_LEN:
            return

        # Only take the last 3 characters entered
        entered = current[-_DECRYPT_CODE_LEN:]

        # Find first jammed bogey without a solved decryption
        jammed = next(
            (b for b in self.bogeys if b.get('jammed') and b['id'] != self._decrypt_target_id),
            None
        )
        if jammed and entered == jammed.get('code', ''):
            jammed['jammed'] = False
            self._decrypt_target_id = jammed['id']
            self._decrypt_answer = ''
            self.score += 50
            self.core.display.update_status("SIGNAL DECRYPTED", f"TGT {jammed['id']:03d} CLEAR")
            asyncio.create_task(
                self.core.synth.play_sequence(tones.SUCCESS, patch="UI_SELECT")
            )

    # ------------------------------------------------------------------
    # Encoder scroll / lock
    # ------------------------------------------------------------------

    def _update_lock(self):
        """Scroll threat list via encoder and lock on encoder push."""
        if not self.bogeys:
            self.locked_idx = 0
            return

        try:
            enc_pos = self.core.hid.encoder_positions[_ENC_THREAT]
            self.locked_idx = enc_pos % len(self.bogeys)
        except (IndexError, AttributeError):
            pass

    # ------------------------------------------------------------------
    # Satellite LED feedback
    # ------------------------------------------------------------------

    def _update_tube_leds(self):
        """Send LED state commands to the satellite for all 8 tube indicators."""
        if not self.sat:
            return
        for i in range(8):
            state = self.tube_states[i]
            if state == TUBE_READY:
                cmd_type = "LED"
                led_cmd = f"{i},{Palette.GREEN.index},0.0,1.0,2"
            elif state == TUBE_ARMED:
                # Amber flashing = armed/assigned
                cmd_type = "LEDFLASH"
                led_cmd = f"{i},{Palette.ORANGE.index},0.0,0.5,3,0.3,0.3"
            elif state == TUBE_FIRED:
                cmd_type = "LED"
                led_cmd = f"{i},{Palette.RED.index},0.0,1.0,2"
            else:  # RELOADING – slow red flash
                cmd_type = "LEDFLASH"
                led_cmd = f"{i},{Palette.RED.index},0.0,0.3,3,0.8,0.8"
            self.sat.send(cmd_type, led_cmd)

    # ------------------------------------------------------------------
    # Satellite segment display
    # ------------------------------------------------------------------

    def _update_segment_display(self, power_mode):
        """Send base integrity and power mode to satellite 14-segment display."""
        if not self.sat:
            return
        if power_mode == POWER_ACTIVE_RADAR:
            mode_str = "RDAR"
        elif power_mode == POWER_AUTO_LOADER:
            mode_str = "LOAD"
        else:
            mode_str = "ECM "
        self.sat.send("DSP", f"DEF {self.base_health:3d}%")

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _render_radar(self, power_mode):
        """Render the current radar sweep frame onto the matrix."""
        if power_mode == POWER_ECM_JAMMING:
            # Static noise during ECM
            self.core.matrix.fill(Palette.OFF, show=False)
            for _ in range(20):
                x = random.randint(0, _MATRIX_SIZE - 1)
                y = random.randint(0, _MATRIX_SIZE - 1)
                noise = (random.randint(0, 80), random.randint(0, 80), 0)
                self.core.matrix.draw_pixel(x, y, noise, brightness=1.0)
            return

        matrix_animations.animate_radar_sweep(
            self.core.matrix,
            self._sweep_angle,
            # In AUTO_LOADER mode the sweep is slow; blank bogeys on alternate 30° half-cycles
            # to simulate intermittent radar snapshots as the sweep moves slowly across sectors.
            bogeys=self.bogeys if power_mode != POWER_AUTO_LOADER or (self._sweep_angle % 60) < 30 else [],
            interceptors=self.interceptors,
            trail_steps=4
        )

    def _render_threat_board(self, power_mode):
        """Update the OLED with the current threat board telemetry."""
        if not self.bogeys:
            self.core.display.update_status(
                f"IRON CANOPY | DEF:{self.base_health}%",
                f"{power_mode[:4]} | NO CONTACTS"
            )
            return

        # Clamp locked index
        if self.locked_idx >= len(self.bogeys):
            self.locked_idx = 0

        bogey = self.bogeys[self.locked_idx]

        # Range = distance from base center (0.5, 0.5)
        dx = 0.5 - bogey['x']
        dy = 0.5 - bogey['y']
        rng = int(math.sqrt(dx * dx + dy * dy) * 16)

        spd_label = "HI" if bogey['speed'] > 0.04 else "LO"
        jammed_label = "JAM" if bogey.get('jammed') else "CLR"

        self.core.display.update_status(
            f"TRK:{self.locked_idx:02d} | RNG:{rng:02d} | SPD:{spd_label}",
            f"{jammed_label} | {power_mode[:4]} | DEF:{self.base_health}%"
        )

    # ------------------------------------------------------------------
    # Main game loop
    # ------------------------------------------------------------------

    async def run(self):
        """Main Iron Canopy game loop."""
        self.difficulty = self.core.data.get_setting("IRON_CANOPY", "difficulty", "NORMAL")
        self.variant = self.difficulty

        # Apply difficulty scaling
        if self.difficulty == "HARD":
            self._max_bogeys = 8
            self._bogey_speed_scale = 1.4
            self._spawn_interval = 4.5
        elif self.difficulty == "INSANE":
            self._max_bogeys = 10
            self._bogey_speed_scale = 2.0
            self._spawn_interval = 3.0

        # Satellite check
        if not self.sat or not self.sat.is_active:
            self.core.display.update_status("IRON CANOPY", "SAT OFFLINE - ABORT")
            await asyncio.sleep(2)
            return "FAILURE"

        # Setup
        self.core.display.use_standard_layout()
        self.core.display.update_status("IRON CANOPY", "SYSTEMS ONLINE...")
        asyncio.create_task(self.core.synth.play_sequence(tones.POWER_UP, patch="SCANNER"))
        await asyncio.sleep(2.0)

        self.core.hid.reset_encoder(_ENC_THREAT)
        self._last_tick_ms  = ticks_ms()
        self._spawn_timer   = self._spawn_interval
        self.score          = 0
        self.base_health    = _BASE_HEALTH_MAX

        # Initial spawn
        self._spawn_bogey()

        game_running = True

        while game_running:
            now = ticks_ms()
            delta_ms = ticks_diff(now, self._last_tick_ms)

            if delta_ms >= 33:   # ~30 FPS target
                delta_s = delta_ms / 1000.0
                self._last_tick_ms = now

                power_mode = self._get_power_mode()

                # --- Sweep angle update ---
                sweep_speed = (self._sweep_speed_slow
                               if power_mode == POWER_AUTO_LOADER
                               else self._sweep_speed_normal)
                if power_mode != POWER_ECM_JAMMING:
                    self._sweep_angle = (self._sweep_angle + sweep_speed * delta_s) % 360.0

                # --- Entity updates ---
                self._update_bogeys(delta_s, power_mode)
                self._update_interceptors(delta_s)

                # --- Tube state machine ---
                self._sync_tube_armed_states()
                self._check_reset_for_reload()
                self._update_reload(delta_s, power_mode)

                # --- Spawn logic ---
                self._spawn_timer -= delta_s
                if self._spawn_timer <= 0.0 and len(self.bogeys) < self._max_bogeys:
                    self._spawn_bogey()
                    self._spawn_timer = self._spawn_interval

                # --- Player inputs ---
                self._update_lock()
                self._check_decryption()
                if power_mode != POWER_ECM_JAMMING:
                    self._attempt_fire()
                self._check_ciws()

                # --- Score from time survived ---
                self.score += 1

                # --- Rendering ---
                self._render_radar(power_mode)
                self._render_threat_board(power_mode)
                self._update_tube_leds()
                self._update_segment_display(power_mode)

                # --- Win/loss conditions ---
                if self.base_health <= 0:
                    self.core.matrix.fill(Palette.RED)
                    asyncio.create_task(
                        self.core.synth.play_sequence(tones.GAME_OVER, patch="ALARM")
                    )
                    await asyncio.sleep(0.2)
                    return await self.game_over()

                if self.score >= 9000:
                    return await self.victory()

            await asyncio.sleep(0.01)
