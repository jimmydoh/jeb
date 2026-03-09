"""Maglev Express Game Mode – High-Speed Transit Simulator."""

import asyncio
import random

from adafruit_ticks import ticks_ms, ticks_diff

from utilities.palette import Palette
from utilities import tones
from utilities import matrix_animations

from .game_mode import GameMode

# ---------------------------------------------------------------------------
# Train States
# ---------------------------------------------------------------------------
STATE_COLD_BOOT      = "COLD_BOOT"    # Waiting for key + guarded toggle startup
STATE_RUNNING        = "RUNNING"      # Main driving loop
STATE_EMERGENCY      = "EMERGENCY"    # E-brake engaged; must disarm and restart
STATE_SIDING         = "SIDING"       # Entered wrong branch; reversing out
STATE_STATION_COAST  = "STATION_COAST"# Precision approach to platform

# ---------------------------------------------------------------------------
# Fault state
# ---------------------------------------------------------------------------
FAULT_NONE    = "NONE"     # No active fault
FAULT_PENDING = "PENDING"  # Fault displayed; waiting for toggle response
FAULT_RESOLVE = "RESOLVE"  # Correct toggle flipped; cooldown before next

# ---------------------------------------------------------------------------
# Waypoint types
# ---------------------------------------------------------------------------
WP_STATION = "STATION"
WP_BRANCH  = "BRANCH"

# ---------------------------------------------------------------------------
# Hardware indices on the Industrial Satellite
# ---------------------------------------------------------------------------
_SW_KEY          = 9    # Key Switch           (latching index 9)
_SW_GUARD        = 8    # Guarded Toggle        (latching index 8)
_MT_REVERSE      = 0    # Momentary toggle (reverse polarity in siding)
_BTN_EBRAKE      = 0    # Giant Red Arcade Button = emergency brake

# Core encoder index (throttle / brake)
_ENC_THROTTLE    = 0

# Satellite encoder index (track switch steering)
_ENC_SWITCH      = 0

# Latching toggle range for fault management
_FAULT_TOGGLE_START = 0
_FAULT_TOGGLE_END   = 7   # inclusive (8 toggles)

# ---------------------------------------------------------------------------
# Physics constants
# ---------------------------------------------------------------------------
MAX_VELOCITY      = 10.0    # max speed units / second
THROTTLE_STEP     = 0.5     # velocity units per encoder click
ACCEL_RATE        = 1.2     # velocity units / second² (acceleration)
DECEL_RATE        = 2.0     # velocity units / second² (braking)
EBRAKE_RATE       = 8.0     # velocity units / second² (emergency brake)
SIDING_SPEED      = 1.5     # max reverse speed in siding

# ---------------------------------------------------------------------------
# Heat / fault constants
# ---------------------------------------------------------------------------
HEAT_RISE_RATE    = 3.0     # heat units / second at MAX_VELOCITY (proportional)
HEAT_DECAY_RATE   = 2.0     # heat units / second when fault toggle correct
HEAT_MAX          = 100.0
FAULT_THRESHOLD   = 70.0    # heat must exceed this before a fault fires
FAULT_TIMEOUT     = 12.0    # seconds to resolve a fault before auto-brake
FAULT_COOLDOWN    = 8.0     # seconds between fault events after resolution

# ---------------------------------------------------------------------------
# Score constants (wages in CR)
# ---------------------------------------------------------------------------
SCORE_PERFECT_STOP    =  500   # velocity < 0.3 at 0 m mark
SCORE_GOOD_STOP       =  200   # velocity < 1.5 at station
SCORE_OVERSHOOT       = -400   # missed station (speed too high to stop)
SCORE_WRONG_BRANCH    = -300   # entered siding
SCORE_FAULT_UNRESOLVED= -150   # fault auto-brake penalty
SCORE_PER_SECOND      =    5   # passive wage for running time

# ---------------------------------------------------------------------------
# Branch switching
# ---------------------------------------------------------------------------
SWITCH_WINDOW_M   = 500     # metres before junction to begin watching encoder
SWITCH_THRESHOLD  = 3       # encoder delta needed to confirm switch direction

# ---------------------------------------------------------------------------
# Station approach
# ---------------------------------------------------------------------------
STATION_COAST_M   = 600     # metres before station to enter coast mode
PERFECT_STOP_VEL  = 0.3
GOOD_STOP_VEL     = 1.5

# ---------------------------------------------------------------------------
# Arch scroll
# ---------------------------------------------------------------------------
ARCH_SPEED_SCALE  = 0.07    # arch_offset advance per unit velocity per second

# Velocity to distance scaling: 1 unit/s = VELOCITY_TO_METRES metres/second
VELOCITY_TO_METRES = 100.0

# Distance the train must reverse to clear a siding
SIDING_REVERSE_DISTANCE = 400.0

# ---------------------------------------------------------------------------
# Pre-defined route: list of waypoints in order
# ---------------------------------------------------------------------------
ROUTE = [
    {"type": WP_STATION, "name": "ALPHA PLEX",  "distance": 2000},
    {"type": WP_BRANCH,  "name": "EAST DELTA",  "distance": 1500, "direction": "RIGHT"},
    {"type": WP_STATION, "name": "CORE CENTRAL","distance": 2500},
    {"type": WP_BRANCH,  "name": "NORTH LOOP",  "distance": 1000, "direction": "LEFT"},
    {"type": WP_STATION, "name": "TERMINUS X",  "distance": 3000},
]


class MaglevExpress(GameMode):
    """Maglev Express – High-Speed Transit Simulator.

    The player pilots a futuristic maglev train through a multi-station route,
    managing throttle/braking, heat faults, and track-switch decisions while
    the 16×16 LED matrix renders a first-person 3D vanishing-point windshield.

    Hardware:
        Core:
            - 16×16 Matrix: 3D vanishing-point windshield (speed-driven)
            - OLED:          Speed, distance to next waypoint, upcoming instruction
            - Rotary Encoder (index 0):  Throttle / brake target speed

        Industrial Satellite (SAT-01):
            - 14-Segment Display:        Live speed readout + heat level
            - Key Switch  (latching 9):  Cold-boot step 1 (unlock drive)
            - Guarded Toggle (latching 8): Cold-boot step 2 (engage drive)
            - 8× Latching Toggles (0–7): Fault management (coolant/power routing)
            - Satellite Encoder (index 0): Track-switch direction during branches
            - Momentary Toggle (index 0):  Reverse polarity in siding (hold UP)
            - Giant Red Button (index 0):  Emergency brake
    """

    def __init__(self, core):
        super().__init__(core, "MAGLEV EXPRESS", "High-Speed Transit Simulator")
        self.sat = None
        for sat in self.core.satellites.values():
            if sat.sat_type_name == "INDUSTRIAL":
                self.sat = sat
                break

        # ── Physics state ──
        self.velocity        = 0.0    # actual speed (units/s)
        self.target_velocity = 0.0    # player-commanded speed
        self.distance_m      = 0.0    # metres travelled since last waypoint

        # ── Route tracking ──
        self._route          = list(ROUTE)
        self._wp_idx         = 0      # index into _route for next waypoint

        # ── Heat and fault ──
        self.heat            = 0.0
        self.fault_state     = FAULT_NONE
        self._fault_toggle   = -1     # which toggle has the active fault
        self._fault_want_on  = False  # the state the toggle must be set to
        self._fault_timer    = 0.0    # seconds since fault fired
        self._fault_cooldown = 0.0    # seconds until next fault can fire

        # ── Branch switch ──
        self._switch_enc_snapshot = 0  # satellite encoder value at branch approach
        self._switch_active       = False
        self._switch_direction    = ""  # "LEFT" or "RIGHT"

        # ── Score / time ──
        self._run_time       = 0.0    # seconds driven
        self._stations_done  = 0

        # ── Rendering ──
        self._arch_offset    = 0.0    # vanishing-point arch scroll phase
        self._fault_flash    = False  # red border on matrix

        # ── Encoder tracking ──
        self._last_enc_pos   = 0      # core encoder position snapshot
        self._last_sat_enc   = 0      # satellite encoder position snapshot

        # ── Tick timing ──
        self._last_tick_ms   = 0

        # ── Difficulty scaling (set in run()) ──
        self._fault_rate_scale  = 1.0
        self._switch_threshold  = SWITCH_THRESHOLD

    # =========================================================================
    # Tutorial
    # =========================================================================

    async def run_tutorial(self):
        """
        A guided, non-interactive demonstration of Maglev Express.

        Voiceover Script (audio/tutes/maglev_tute.wav) ~ 38 seconds:
            [0:00] "Welcome to Maglev Express. You are the pilot of a futuristic
                    high-speed transit train."
            [0:05] "To cold-boot the train, turn the key switch, then engage the
                    guarded drive toggle."
            [0:11] "Turn the core dial clockwise to increase your throttle, and
                    counter-clockwise to brake. The train is heavy – give yourself
                    plenty of time to slow down."
            [0:19] "High speeds generate engine heat. When a fault code flashes,
                    flip the corresponding toggle before the timer expires."
            [0:26] "At track branch junctions, crank the satellite encoder in the
                    indicated direction to set the switch in time."
            [0:32] "Hit the big red button for an emergency stop – but you will
                    need to fully disarm and restart the train afterwards."
            [0:38] (End of file)
        """
        await self.core.clean_slate()

        if not self.sat or not self.sat.is_active:
            self.core.display.update_status("MAGLEV EXPRESS", "SAT OFFLINE - ABORT")
            await asyncio.sleep(2)
            return "TUTORIAL_FAILED"

        self.game_state = "TUTORIAL"

        tute_audio = asyncio.create_task(
            self.core.audio.play("audio/tutes/maglev_tute.wav", bus_id=self.core.audio.CH_VOICE)
        )

        # Reset display state
        self.velocity        = 0.0
        self._arch_offset    = 0.0
        self._fault_flash    = False
        self.heat            = 0.0

        # [0:00 – 0:05]  Show cold-boot screen
        self.core.display.update_status("MAGLEV EXPRESS", "SYSTEM OFFLINE")
        matrix_animations.animate_vanishing_point(
            self.core.matrix, self._arch_offset, speed_fraction=0.0
        )
        self.core.matrix.show_frame()
        await asyncio.sleep(5.0)

        # [0:05 – 0:11]  Demonstrate key + guarded toggle startup
        self.core.display.update_status("COLD BOOT", "TURN KEY → ENGAGE DRIVE")
        asyncio.create_task(self.core.synth.play_sequence(tones.SYSTEM_BOOT))
        await asyncio.sleep(6.0)

        # [0:11 – 0:19]  Animate acceleration
        self.core.display.update_status("THROTTLE UP", "DIAL = TARGET SPEED")
        for step in range(40):
            self.velocity = step / 40.0 * MAX_VELOCITY * 0.6
            self._arch_offset = (self._arch_offset + self.velocity * ARCH_SPEED_SCALE * 0.2) % 1.0
            matrix_animations.animate_vanishing_point(
                self.core.matrix, self._arch_offset, speed_fraction=self.velocity / MAX_VELOCITY
            )
            self.core.matrix.show_frame()
            self._update_segment_display()
            await asyncio.sleep(0.2)

        # [0:19 – 0:26]  Demonstrate fault
        self.core.display.update_status("FAULT: T3 COOLANT", "FLIP TOGGLE 3!")
        self._fault_flash = True
        asyncio.create_task(self.core.synth.play_sequence(tones.MAGLEV_FAULT))
        try:
            self.sat.send("LEDFLASH", f"3,{Palette.RED.index},0.0,1.0,3,0.2,0.2")
        except Exception:
            pass
        for step in range(35):
            self._arch_offset = (self._arch_offset + self.velocity * ARCH_SPEED_SCALE * 0.2) % 1.0
            matrix_animations.animate_vanishing_point(
                self.core.matrix, self._arch_offset,
                speed_fraction=self.velocity / MAX_VELOCITY,
                fault_flash=self._fault_flash
            )
            self.core.matrix.show_frame()
            await asyncio.sleep(0.2)

        # Fault resolved
        self._fault_flash = False
        self.core.display.update_status("FAULT CLEARED", "SYSTEM NOMINAL")
        try:
            self.sat.send("LED", f"3,{Palette.GREEN.index},0.0,1.0,2")
        except Exception:
            pass
        asyncio.create_task(self.core.synth.play_sequence(tones.SUCCESS))
        await asyncio.sleep(2.0)

        # [0:26 – 0:32]  Branch demonstration
        self.core.display.update_status("BRANCH: 500M", "SAT ENC → RIGHT")
        await asyncio.sleep(6.0)

        # [0:32 – 0:38]  E-brake demonstration
        self.core.display.update_status("EMERGENCY BRAKE", "BIG RED BUTTON")
        asyncio.create_task(self.core.synth.play_sequence(tones.MAGLEV_BRAKE))
        for step in range(30):
            self.velocity = max(0.0, self.velocity - EBRAKE_RATE * 0.2)
            self._arch_offset = (self._arch_offset + self.velocity * ARCH_SPEED_SCALE * 0.2) % 1.0
            matrix_animations.animate_vanishing_point(
                self.core.matrix, self._arch_offset, speed_fraction=self.velocity / MAX_VELOCITY
            )
            self.core.matrix.show_frame()
            await asyncio.sleep(0.2)

        await tute_audio
        await self.core.clean_slate()
        return "TUTORIAL_COMPLETE"

    # =========================================================================
    # Satellite hardware accessors
    # =========================================================================

    def _key_is_on(self):
        """Return True if the Key Switch is turned ON."""
        if not self.sat:
            return False
        try:
            return bool(self.sat.hid.latching_values[_SW_KEY])
        except (IndexError, AttributeError):
            return False

    def _guard_is_up(self):
        """Return True if the Guarded Toggle is raised (drive engaged)."""
        if not self.sat:
            return False
        try:
            return bool(self.sat.hid.latching_values[_SW_GUARD])
        except (IndexError, AttributeError):
            return False

    def _ebrake_pressed(self):
        """Return True if the Giant Red Arcade Button is currently pressed."""
        if not self.sat:
            return False
        try:
            return bool(self.sat.hid.buttons_values[_BTN_EBRAKE])
        except (IndexError, AttributeError):
            return False

    def _reverse_held(self):
        """Return True while the Momentary Toggle is held UP (reverse polarity)."""
        if not self.sat:
            return False
        try:
            return self.sat.hid.is_momentary_toggled(_MT_REVERSE, direction="U")
        except (IndexError, AttributeError):
            return False

    def _toggle_state(self, idx):
        """Return bool state of latching toggle at idx."""
        if not self.sat:
            return False
        try:
            return bool(self.sat.hid.latching_values[idx])
        except (IndexError, AttributeError):
            return False

    def _sat_encoder_pos(self):
        """Return satellite encoder position (index 0)."""
        if not self.sat:
            return 0
        try:
            return self.sat.hid.encoder_positions[_ENC_SWITCH]
        except (IndexError, AttributeError):
            return 0

    # =========================================================================
    # Core encoder (throttle)
    # =========================================================================

    def _read_throttle_encoder(self):
        """Return delta from core encoder and update snapshot."""
        try:
            pos = self.core.hid.encoder_positions[_ENC_THROTTLE]
        except (IndexError, AttributeError):
            return 0
        delta = pos - self._last_enc_pos
        self._last_enc_pos = pos
        return delta

    # =========================================================================
    # Physics update
    # =========================================================================

    def _update_physics(self, dt):
        """Advance velocity toward target_velocity with inertia."""
        if self.velocity < self.target_velocity:
            self.velocity = min(self.target_velocity, self.velocity + ACCEL_RATE * dt)
        elif self.velocity > self.target_velocity:
            self.velocity = max(self.target_velocity, self.velocity - DECEL_RATE * dt)

        # Advance distance
        self.distance_m += self.velocity * dt * VELOCITY_TO_METRES

        # Update arch scroll
        self._arch_offset = (self._arch_offset + self.velocity * ARCH_SPEED_SCALE * dt) % 1.0

        # Update heat
        heat_rise = (self.velocity / MAX_VELOCITY) * HEAT_RISE_RATE * dt * self._fault_rate_scale
        self.heat = min(HEAT_MAX, self.heat + heat_rise)

        # Passive score (wage)
        self.score += int(SCORE_PER_SECOND * dt)
        self._run_time += dt

    # =========================================================================
    # Fault management
    # =========================================================================

    def _tick_faults(self, dt):
        """Manage heat-driven fault events and toggle resolution."""
        if self.fault_state == FAULT_NONE:
            # Cooldown between faults
            if self._fault_cooldown > 0:
                self._fault_cooldown -= dt
                return
            # Trigger new fault if heat is high enough
            if self.heat >= FAULT_THRESHOLD and self.velocity > 1.0:
                self._trigger_fault()

        elif self.fault_state == FAULT_PENDING:
            self._fault_timer += dt
            self._fault_flash = (int(self._fault_timer * 4) % 2 == 0)
            # Check if player flipped the required toggle
            if self._fault_toggle >= 0:
                current = self._toggle_state(self._fault_toggle)
                if current == self._fault_want_on:
                    # Fault resolved
                    self.fault_state   = FAULT_RESOLVE
                    self._fault_flash  = False
                    self.heat         -= 20.0
                    self.heat          = max(0.0, self.heat)
                    self._fault_timer  = 0.0
                    self._fault_cooldown = FAULT_COOLDOWN
                    asyncio.create_task(
                        self.core.synth.play_sequence(tones.SUCCESS)
                    )
                    self.core.display.update_status("FAULT CLEARED", "SYSTEM NOMINAL")
                    try:
                        self.sat.send("LED", f"{self._fault_toggle},{Palette.GREEN.index},0.0,1.0,2")
                    except Exception:
                        pass
            # Timeout → emergency auto-brake
            if self._fault_timer >= FAULT_TIMEOUT:
                self.score += SCORE_FAULT_UNRESOLVED
                self.fault_state  = FAULT_NONE
                self._fault_flash = False
                self._fault_timer = 0.0
                # Trigger emergency stop
                self.target_velocity = 0.0
                return "EMERGENCY"

        elif self.fault_state == FAULT_RESOLVE:
            # Brief settle period before clearing
            self._fault_timer += dt
            # Decay heat faster while resolved
            self.heat = max(0.0, self.heat - HEAT_DECAY_RATE * dt)
            if self._fault_timer >= 2.0:
                self.fault_state  = FAULT_NONE
                self._fault_timer = 0.0

        return None

    def _trigger_fault(self):
        """Select a random latching toggle and assign it a fault."""
        self._fault_toggle   = random.randint(_FAULT_TOGGLE_START, _FAULT_TOGGLE_END)
        # Require the *opposite* of the toggle's current state
        self._fault_want_on  = not self._toggle_state(self._fault_toggle)
        self.fault_state     = FAULT_PENDING
        self._fault_timer    = 0.0
        self._fault_flash    = True

        # Flash the hardware LED on the satellite
        try:
            self.sat.send(
                "LEDFLASH",
                f"{self._fault_toggle},{Palette.RED.index},0.0,1.0,3,0.2,0.2"
            )
        except Exception:
            pass

        asyncio.create_task(self.core.synth.play_sequence(tones.MAGLEV_FAULT))
        direction = "ON" if self._fault_want_on else "OFF"
        self.core.display.update_status(
            f"FAULT: T{self._fault_toggle} {'COOL' if self._fault_toggle < 4 else 'PWR'}",
            f"TOGGLE {self._fault_toggle} → {direction}"
        )

    # =========================================================================
    # Waypoint / route management
    # =========================================================================

    def _next_waypoint(self):
        """Return the next waypoint dict, or None if route is complete."""
        if self._wp_idx < len(self._route):
            return self._route[self._wp_idx]
        return None

    def _advance_waypoint(self):
        """Move to the next route entry and reset distance counter."""
        self.distance_m = 0.0
        self._wp_idx += 1
        self._switch_active = False
        self._last_sat_enc  = self._sat_encoder_pos()

    # =========================================================================
    # Branch switch handling
    # =========================================================================

    def _check_branch(self, wp):
        """Activate the switch window when approaching a branch waypoint."""
        if wp["type"] != WP_BRANCH:
            return
        dist_remaining = wp["distance"] - self.distance_m
        if dist_remaining <= SWITCH_WINDOW_M and not self._switch_active:
            self._switch_active    = True
            self._switch_direction = wp["direction"]
            self._last_sat_enc     = self._sat_encoder_pos()
            direction_str = "← LEFT" if self._switch_direction == "LEFT" else "RIGHT →"
            self.core.display.update_status(
                f"BRANCH IN {int(dist_remaining)}M",
                f"SAT ENC {direction_str}"
            )
            asyncio.create_task(self.core.synth.play_sequence(tones.NOTIFY_INBOX))

    def _read_switch_encoder(self):
        """Return delta from the satellite encoder relative to snapshot."""
        pos = self._sat_encoder_pos()
        return pos - self._last_sat_enc

    def _resolve_branch(self, wp):
        """
        Called when distance_m >= wp distance.
        Returns True if switch was thrown correctly, False for siding.
        """
        if not self._switch_active:
            # No switch needed – treat as straight-through
            return True
        delta = self._read_switch_encoder()
        if self._switch_direction == "LEFT"  and delta <= -self._switch_threshold:
            return True
        if self._switch_direction == "RIGHT" and delta >=  self._switch_threshold:
            return True
        return False

    # =========================================================================
    # Station approach
    # =========================================================================

    def _check_station_coast(self, wp):
        """Enter coast-mode warning when close to a station."""
        if wp["type"] != WP_STATION:
            return
        dist_remaining = wp["distance"] - self.distance_m
        if dist_remaining <= STATION_COAST_M:
            self.core.display.update_status(
                f"STATION: {wp['name']}",
                f"COAST   {int(dist_remaining):4d}M  {self.velocity:.1f}u/s"
            )

    def _score_station_stop(self):
        """Award or penalise based on arrival speed."""
        if self.velocity <= PERFECT_STOP_VEL:
            self.score += SCORE_PERFECT_STOP
            asyncio.create_task(self.core.synth.play_sequence(tones.ONE_UP))
            self.core.display.update_status("PERFECT STOP!", f"+{SCORE_PERFECT_STOP} CR")
            self._stations_done += 1
        elif self.velocity <= GOOD_STOP_VEL:
            self.score += SCORE_GOOD_STOP
            asyncio.create_task(self.core.synth.play_sequence(tones.SUCCESS))
            self.core.display.update_status("GOOD STOP", f"+{SCORE_GOOD_STOP} CR")
            self._stations_done += 1
        else:
            # Too fast – bypass / overshoot
            self.score += SCORE_OVERSHOOT
            asyncio.create_task(self.core.synth.play_sequence(tones.DANGER))
            self.core.display.update_status(
                "OVERSHOOT!", f"MISSED STOP  {SCORE_OVERSHOOT} CR"
            )

    # =========================================================================
    # Rendering helpers
    # =========================================================================

    def _render_windshield(self):
        """Draw the vanishing-point windshield on the matrix."""
        matrix_animations.animate_vanishing_point(
            self.core.matrix,
            self._arch_offset,
            speed_fraction=self.velocity / MAX_VELOCITY,
            fault_flash=self._fault_flash
        )

    def _update_oled_running(self, wp):
        """Update OLED display during normal running."""
        if wp is None:
            self.core.display.update_status(
                f"SPEED {self.velocity:.1f}",
                f"SCORE {self.score} CR"
            )
            return
        dist_remaining = max(0, wp["distance"] - self.distance_m)
        if wp["type"] == WP_STATION:
            label = f"STA {wp['name'][:6]} {int(dist_remaining)}M"
        else:
            direction_str = "L" if wp["direction"] == "LEFT" else "R"
            label = f"BRANCH {direction_str}  {int(dist_remaining)}M"
        self.core.display.update_status(
            f"SPD {self.velocity:4.1f}u/s  HEAT {int(self.heat)}%",
            label
        )

    def _update_segment_display(self):
        """Push speed + heat to the satellite 14-segment display."""
        if not self.sat:
            return
        try:
            self.sat.send("DSP", f"S{self.velocity:4.1f}H{int(self.heat):3d}")
        except Exception:
            pass

    # =========================================================================
    # Cold-boot sequence
    # =========================================================================

    async def _run_cold_boot(self):
        """
        Wait for the player to complete the physical startup sequence:
            1. Key Switch ON  (latching index 9)
            2. Guarded Toggle ON  (latching index 8)
        Returns "RUNNING" on success or "ABORT" if mode exit is triggered.
        """
        self.core.display.update_status("SYSTEM OFFLINE", "TURN KEY TO START")

        # Phase 1: Wait for Key Switch
        while not self._key_is_on():
            self._render_windshield()
            self.core.matrix.show_frame()
            await asyncio.sleep(0.1)
            if getattr(self, "_exit_requested", False):
                return "ABORT"

        asyncio.create_task(self.core.synth.play_sequence(tones.UI_TICK))
        self.core.display.update_status("KEY ON", "ENGAGE DRIVE TOGGLE")

        # Phase 2: Wait for Guarded Toggle
        while not self._guard_is_up():
            self._render_windshield()
            self.core.matrix.show_frame()
            await asyncio.sleep(0.1)
            if getattr(self, "_exit_requested", False):
                return "ABORT"

        asyncio.create_task(self.core.synth.play_sequence(tones.SYSTEM_BOOT))
        self.core.display.update_status("DRIVE ENGAGED", "THROTTLE UP")
        await asyncio.sleep(2.0)
        return "RUNNING"

    # =========================================================================
    # Emergency-brake disarm sequence
    # =========================================================================

    async def _run_emergency_disarm(self):
        """
        After an emergency stop the player must fully disarm before restarting:
            1. Drop Guarded Toggle to OFF
            2. Turn Key Switch to OFF
        Returns "COLD_BOOT".
        """
        self.core.display.update_status("EMERGENCY STOP", "LOWER DRIVE TOGGLE")
        asyncio.create_task(self.core.synth.play_sequence(tones.MAGLEV_BRAKE))

        # Brake the train to zero
        while self.velocity > 0.0:
            self.velocity = max(0.0, self.velocity - EBRAKE_RATE * 0.1)
            self._arch_offset = (self._arch_offset + self.velocity * ARCH_SPEED_SCALE * 0.1) % 1.0
            self._render_windshield()
            self.core.matrix.show_frame()
            self._update_segment_display()
            await asyncio.sleep(0.1)

        self.target_velocity = 0.0

        # Wait for guard down
        while self._guard_is_up():
            await asyncio.sleep(0.1)
            if getattr(self, "_exit_requested", False):
                return "ABORT"

        asyncio.create_task(self.core.synth.play_sequence(tones.UI_TICK))
        self.core.display.update_status("DRIVE LOWERED", "TURN KEY OFF")

        # Wait for key off
        while self._key_is_on():
            await asyncio.sleep(0.1)
            if getattr(self, "_exit_requested", False):
                return "ABORT"

        asyncio.create_task(self.core.synth.play_sequence(tones.UI_TICK))
        self.core.display.update_status("SYSTEM DISARMED", "RESTART WHEN READY")
        await asyncio.sleep(1.5)
        return "COLD_BOOT"

    # =========================================================================
    # Siding reverse-out sequence
    # =========================================================================

    async def _run_siding(self, siding_name):
        """
        Player entered a dead-end siding.  They must hold the Momentary Toggle
        UP to reverse the engine polarity, then back out slowly.
        Returns "RUNNING" to resume the main route.
        """
        self.score += SCORE_WRONG_BRANCH
        asyncio.create_task(self.core.synth.play_sequence(tones.DANGER))
        self.core.display.update_status(
            f"SIDING: {siding_name[:8]}",
            f"HOLD MT UP TO REVERSE  {SCORE_WRONG_BRANCH} CR"
        )

        # Brake to 0
        while self.velocity > 0.0:
            self.velocity = max(0.0, self.velocity - DECEL_RATE * 0.1)
            self.target_velocity = 0.0
            self._arch_offset = (self._arch_offset + self.velocity * ARCH_SPEED_SCALE * 0.1) % 1.0
            self._render_windshield()
            self.core.matrix.show_frame()
            await asyncio.sleep(0.1)

        self.core.display.update_status("STOPPED IN SIDING", "HOLD MT UP → REVERSE")

        # Wait for momentary toggle to be held
        while not self._reverse_held():
            await asyncio.sleep(0.05)
            if getattr(self, "_exit_requested", False):
                return "ABORT"

        asyncio.create_task(self.core.synth.play_sequence(tones.MAGLEV_HORN))
        self.core.display.update_status("REVERSING", "BACK TO MAIN LINE...")

        # Reverse out at slow speed while toggle held
        reverse_dist = 0.0
        required_reverse = SIDING_REVERSE_DISTANCE
        while reverse_dist < required_reverse:
            if self._reverse_held():
                self.velocity = SIDING_SPEED
            else:
                self.velocity = max(0.0, self.velocity - DECEL_RATE * 0.1)
            reverse_dist += self.velocity * VELOCITY_TO_METRES * 0.1
            self._arch_offset = (self._arch_offset - self.velocity * ARCH_SPEED_SCALE * 0.1) % 1.0
            self._render_windshield()
            self.core.matrix.show_frame()
            await asyncio.sleep(0.1)

        self.velocity = 0.0
        self.target_velocity = 0.0
        asyncio.create_task(self.core.synth.play_sequence(tones.SUCCESS))
        self.core.display.update_status("MAIN LINE CLEAR", "THROTTLE TO PROCEED")
        await asyncio.sleep(2.0)
        return "RUNNING"

    # =========================================================================
    # Main run loop
    # =========================================================================

    async def run(self):
        """Main game loop for Maglev Express."""
        await self.core.clean_slate()

        # ── Load settings ──
        difficulty = self.core.data.get_setting("MAGLEV_EXPRESS", "difficulty") or "NORMAL"
        self.difficulty = difficulty
        if difficulty == "HARD":
            self._fault_rate_scale   = 1.5
            self._switch_threshold   = 4
        elif difficulty == "INSANE":
            self._fault_rate_scale   = 2.5
            self._switch_threshold   = 5

        # ── Reset game state ──
        self.score           = 0
        self.velocity        = 0.0
        self.target_velocity = 0.0
        self.distance_m      = 0.0
        self.heat            = 0.0
        self.fault_state     = FAULT_NONE
        self._fault_toggle   = -1
        self._fault_flash    = False
        self._fault_timer    = 0.0
        self._fault_cooldown = FAULT_COOLDOWN
        self._arch_offset    = 0.0
        self._run_time       = 0.0
        self._stations_done  = 0
        self._wp_idx         = 0
        self._route          = list(ROUTE)
        self._switch_active  = False
        self._last_tick_ms   = ticks_ms()

        # Snapshot encoders
        try:
            self._last_enc_pos = self.core.hid.encoder_positions[_ENC_THROTTLE]
        except (IndexError, AttributeError):
            self._last_enc_pos = 0
        self._last_sat_enc = self._sat_encoder_pos()

        # ── Start horn ──
        asyncio.create_task(self.core.synth.play_sequence(tones.MAGLEV_HORN))

        game_state = STATE_COLD_BOOT

        while True:
            # ── Compute dt ──
            now = ticks_ms()
            dt = ticks_diff(now, self._last_tick_ms) / 1000.0
            dt = min(dt, 0.1)   # cap to avoid spiral if loop stalls
            self._last_tick_ms = now

            # ──────────────────────────────────────────────────────────────
            if game_state == STATE_COLD_BOOT:
                result = await self._run_cold_boot()
                if result == "ABORT":
                    break
                game_state = STATE_RUNNING
                self._last_tick_ms = ticks_ms()   # reset timer after blocking wait

            # ──────────────────────────────────────────────────────────────
            elif game_state == STATE_RUNNING:
                # -- Throttle encoder --
                enc_delta = self._read_throttle_encoder()
                if enc_delta != 0:
                    self.target_velocity = max(
                        0.0, min(MAX_VELOCITY, self.target_velocity + enc_delta * THROTTLE_STEP)
                    )

                # -- Emergency brake button --
                if self._ebrake_pressed():
                    asyncio.create_task(self.core.synth.play_sequence(tones.MAGLEV_BRAKE))
                    game_state = STATE_EMERGENCY
                    continue

                # -- Physics --
                self._update_physics(dt)

                # -- Fault management --
                fault_result = self._tick_faults(dt)
                if fault_result == "EMERGENCY":
                    game_state = STATE_EMERGENCY
                    continue

                # -- Waypoint logic --
                wp = self._next_waypoint()
                if wp is not None:
                    self._check_branch(wp)
                    self._check_station_coast(wp)

                    if self.distance_m >= wp["distance"]:
                        if wp["type"] == WP_BRANCH:
                            switched_ok = self._resolve_branch(wp)
                            if switched_ok:
                                self._advance_waypoint()
                            else:
                                siding_name = wp.get("name", "SIDING")
                                self._advance_waypoint()
                                result = await self._run_siding(siding_name)
                                if result == "ABORT":
                                    break
                                game_state = STATE_RUNNING
                                self._last_tick_ms = ticks_ms()

                        elif wp["type"] == WP_STATION:
                            self._score_station_stop()
                            self._advance_waypoint()
                            # Brief station dwell
                            self.core.display.update_header(
                                f"DEP {wp['name'][:8].upper()}"
                            )
                            asyncio.create_task(self.core.synth.play_sequence(tones.MAGLEV_HORN))
                            await asyncio.sleep(2.0)
                            self._last_tick_ms = ticks_ms()

                else:
                    # Route complete – final station reached
                    self.core.display.update_status(
                        "ROUTE COMPLETE!", f"TOTAL WAGE: {self.score} CR"
                    )
                    break

                # -- Render --
                self._render_windshield()
                self.core.matrix.show_frame()
                self._update_oled_running(wp)
                self._update_segment_display()

            # ──────────────────────────────────────────────────────────────
            elif game_state == STATE_EMERGENCY:
                result = await self._run_emergency_disarm()
                if result == "ABORT":
                    break
                game_state = STATE_COLD_BOOT
                self._last_tick_ms = ticks_ms()

            await asyncio.sleep(0.02)   # ~50 fps target

        # ── End of run ──
        self._update_segment_display()
        return await self.game_over()
