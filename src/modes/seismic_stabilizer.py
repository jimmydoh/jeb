# File: src/modes/seismic_stabilizer.py
"""Seismic Stabilizer – Continuous Physics Balancing Game.

The player controls an inverted pendulum (reactor core rod) that is
constantly trying to topple under gravity and random seismic shocks.
Two tension cables (Core encoder and Satellite encoder) must be
continuously tweaked to maintain equilibrium.

Hardware Mapping
----------------
Core:
    - 16×16 Matrix: Animated inverted pendulum rod, coloured by danger level.
    - Rotary Encoder (index 0): Left tension cable.

Industrial Satellite (SAT-01):
    - Rotary Encoder (index 0): Right tension cable.
    - 8× Latching Toggles (indices 0–7): Coolant rods. Inserting rods
      slows the physics engine (easier) but reduces the score multiplier
      by 10 % per active rod (minimum 10 %).
    - Momentary Toggle (index 0, direction UP): Emergency pressure vent.
      Rapidly re-centres the rod, but accumulates overheat. Reaching
      100 % overheat triggers a game over.
    - 14-Segment Display: Live rod angle / overheat readout.

Gameplay
--------
* Gravity and seismic shocks constantly try to topple the rod.
* The rod falls and the game ends when |angle| ≥ FALL_ANGLE (~69 °).
* Score accumulates each second, scaled by the current multiplier.
* Seismic shocks increase in frequency and magnitude as the level rises.
  The level increases every LEVEL_UP_INTERVAL seconds of survival.
"""

import asyncio
import math
import random

from adafruit_ticks import ticks_ms, ticks_diff

from utilities.palette import Palette
from utilities import tones

from .game_mode import GameMode


# ---------------------------------------------------------------------------
# Hardware indices
# ---------------------------------------------------------------------------
_ENC_CORE        = 0    # Core rotary encoder → left cable
_ENC_SAT         = 0    # Satellite encoder index → right cable
_COOLANT_START   = 0    # First coolant-rod latching toggle index
_COOLANT_COUNT   = 8    # Number of coolant rods
_MT_VENT         = 0    # Momentary toggle index for emergency vent

# ---------------------------------------------------------------------------
# Physics constants
# ---------------------------------------------------------------------------
_GRAVITY_FACTOR  = 1.8    # Destabilising torque coefficient (rad/s² per rad)
_CABLE_STEP      = 0.10   # Cable tension change per encoder detent (rad/s²)
_CABLE_MAX       = 4.0    # Max cable tension magnitude
_CABLE_FORCE     = 1.0    # Torque applied per unit of net cable tension (rad/s²)
_DAMPING         = 0.5    # Angular-velocity damping per second
_FALL_ANGLE      = 1.2    # Rod fall threshold in radians (~69 °)
_WARN_ANGLE      = 0.65   # Warning zone threshold (~37 °)
_SAFE_ANGLE      = 0.20   # Safe zone threshold (~11 °)

# ---------------------------------------------------------------------------
# Seismic shocks
# ---------------------------------------------------------------------------
_SHOCK_INTERVAL_BASE = 5.0    # Seconds between shocks at level 0
_SHOCK_INTERVAL_MIN  = 1.5    # Minimum interval between shocks
_SHOCK_MAGNITUDE     = 0.40   # Base shock angular impulse (rad/s)
_SHOCK_SCALE_PER_LVL = 0.06   # Extra impulse magnitude per level

# ---------------------------------------------------------------------------
# Coolant rods
# ---------------------------------------------------------------------------
_COOLANT_SLOW_FACTOR  = 0.12   # Physics-speed reduction per active rod (fraction)
_COOLANT_MULT_PENALTY = 0.10   # Score-multiplier penalty per active rod
_COOLANT_MULT_MIN     = 0.10   # Minimum score multiplier

# ---------------------------------------------------------------------------
# Pressure vent
# ---------------------------------------------------------------------------
_VENT_DAMP_RATE    = 4.0     # Vent damping strength (applied to angle + vel)
_OVERHEAT_RATE     = 35.0    # Overheat accumulation rate (% per second held)
_OVERHEAT_COOL     = 10.0    # Overheat dissipation rate (% per second off)
_OVERHEAT_LIMIT    = 100.0   # Game-over overheat threshold

# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------
_BASE_SCORE_RATE  = 10.0    # Points per second at ×1.0 multiplier

# ---------------------------------------------------------------------------
# Level progression
# ---------------------------------------------------------------------------
_LEVEL_UP_INTERVAL = 30.0   # Seconds of survival before level increases

# ---------------------------------------------------------------------------
# Difficulty table
# ---------------------------------------------------------------------------
_DIFF_PARAMS = {
    "NORMAL": {"gravity_mult": 1.0, "shock_mult": 1.0},
    "HARD":   {"gravity_mult": 1.4, "shock_mult": 1.4},
    "INSANE": {"gravity_mult": 2.0, "shock_mult": 2.0},
}

# ---------------------------------------------------------------------------
# Matrix layout
# ---------------------------------------------------------------------------
_MATRIX_W   = 16
_MATRIX_H   = 16
_PIVOT_X    = 8     # rod base column (centre of 16-wide grid)
_PIVOT_Y    = 14    # rod base row (second-from-bottom)
_ROD_LENGTH = 12    # pixels from pivot to tip

# Coolant indicator column positions (row 15) for 8 rods
_COOLANT_COLS = (0, 2, 4, 6, 9, 11, 13, 15)


class SeismicStabilizer(GameMode):
    """Seismic Stabilizer – continuous inverted-pendulum physics game.

    Requires both Core and Industrial Satellite hardware.
    """

    METADATA = {
        "id": "SEISMIC_STABILIZER",
        "name": "SEISMIC STAB",
        "requires": ["CORE", "INDUSTRIAL"],
    }

    def __init__(self, core):
        super().__init__(core, "SEISMIC STAB", "Physics Balancing Game")

        # Find the first Industrial satellite
        self.sat = None
        for sat in self.core.satellites.values():
            if sat.sat_type_name == "INDUSTRIAL":
                self.sat = sat
                break

        # Physics state
        self._angle = 0.0
        self._angular_velocity = 0.0

        # Vent / overheat state
        self._overheat_pct = 0.0

        # Shock timer
        self._shock_timer = 0.0

        # Level / score accumulators
        self._level_timer = 0.0
        self._score_accum = 0.0

        # Satellite encoder calibration offset
        self._sat_enc_offset = 0

        # Segment display cache
        self._last_segment_text = ""

        # Difficulty multipliers (set in run())
        self._gravity_mult = 1.0
        self._shock_mult = 1.0

    # ------------------------------------------------------------------
    # Private helpers – hardware access
    # ------------------------------------------------------------------

    def _sat_encoder_raw(self):
        """Return the raw satellite encoder position (0 if no satellite)."""
        if not self.sat:
            return 0
        try:
            return self.sat.hid.encoder_positions[_ENC_SAT]
        except (IndexError, AttributeError):
            return 0

    def _count_coolant_rods(self):
        """Return the number of active (inserted) coolant-rod toggles (0–8)."""
        if not self.sat:
            return 0
        count = 0
        try:
            for i in range(_COOLANT_START, _COOLANT_START + _COOLANT_COUNT):
                if self.sat.hid.latching_values[i]:
                    count += 1
        except (IndexError, AttributeError):
            pass
        return count

    def _is_vent_held(self):
        """Return True if the momentary vent toggle is currently held UP."""
        if not self.sat:
            return False
        try:
            return self.sat.hid.is_momentary_toggled(_MT_VENT, direction="U")
        except (IndexError, AttributeError):
            return False

    def _get_cable_tensions(self):
        """Return (left_tension, right_tension) from the encoder positions."""
        core_pos = self.core.hid.encoder_positions[_ENC_CORE]
        sat_pos  = self._sat_encoder_raw() - self._sat_enc_offset

        left  = max(-_CABLE_MAX, min(_CABLE_MAX, core_pos * _CABLE_STEP))
        right = max(-_CABLE_MAX, min(_CABLE_MAX, sat_pos  * _CABLE_STEP))
        return left, right

    def _get_multiplier(self, coolant_count):
        """Return the current score multiplier based on active coolant rods."""
        mult = 1.0 - coolant_count * _COOLANT_MULT_PENALTY
        return max(_COOLANT_MULT_MIN, mult)

    # ------------------------------------------------------------------
    # Private helpers – physics
    # ------------------------------------------------------------------

    def _update_physics(self, dt, left_tension, right_tension, vent_held):
        """Advance the physics simulation by *dt* seconds."""
        gravity = _GRAVITY_FACTOR * self._gravity_mult

        # Gravity destabilises the rod: torque is proportional to sin(angle),
        # which is zero at perfect vertical (angle=0) and grows as the rod tilts.
        grav_torque = gravity * math.sin(self._angle)

        # Net cable tension: positive → pulls top of rod LEFT (restoring if angle > 0)
        net_control = (left_tension - right_tension) * _CABLE_FORCE

        self._angular_velocity += (grav_torque - net_control) * dt

        # Natural damping
        decay_factor = math.exp(-_DAMPING * dt)
        self._angular_velocity *= decay_factor

        # Vent: rapidly damp both angle and velocity toward zero
        if vent_held:
            decay_factor = math.exp(-_VENT_DAMP_RATE * dt)
            self._angular_velocity *= decay_factor
            self._angle            *= decay_factor

        # Integrate
        self._angle += self._angular_velocity * dt

    def _trigger_seismic_shock(self):
        """Apply a random seismic impulse to angular velocity."""
        magnitude = (_SHOCK_MAGNITUDE + self.level * _SHOCK_SCALE_PER_LVL) * self._shock_mult
        impulse = random.choice([-1, 1]) * magnitude * random.uniform(0.7, 1.3)
        self._angular_velocity += impulse
        asyncio.create_task(
            self.core.synth.play_sequence(tones.ALARM, patch="ALARM")
        )

    # ------------------------------------------------------------------
    # Private helpers – rendering
    # ------------------------------------------------------------------

    def _rod_color(self):
        """Return a Palette colour for the rod based on the current angle."""
        abs_angle = abs(self._angle)
        if abs_angle < _SAFE_ANGLE:
            return Palette.GREEN
        if abs_angle < _WARN_ANGLE:
            return Palette.YELLOW
        return Palette.RED

    def _render(self, frame_count, vent_held, coolant_count):
        """Render the current game state onto the LED matrix."""
        self.core.matrix.clear()

        # --- Coolant rod indicators (bottom row) ---
        for i in range(_COOLANT_COUNT):
            col = _COOLANT_COLS[i]
            try:
                if self.sat and self.sat.hid.latching_values[_COOLANT_START + i]:
                    self.core.matrix.draw_pixel(col, _MATRIX_H - 1, Palette.CYAN,
                                                brightness=0.8, show=False)
                else:
                    self.core.matrix.draw_pixel(col, _MATRIX_H - 1, Palette.BLUE,
                                                brightness=0.1, show=False)
            except (IndexError, AttributeError):
                pass

        # --- Pivot pixel ---
        self.core.matrix.draw_pixel(_PIVOT_X, _PIVOT_Y, Palette.WHITE,
                                    brightness=0.9, show=False)

        # --- Rod line: parametric samples from pivot to tip ---
        rod_color = self._rod_color()
        for t in range(1, _ROD_LENGTH + 1):
            frac = t / _ROD_LENGTH
            px = int(round(_PIVOT_X + frac * _ROD_LENGTH * math.sin(self._angle)))
            py = int(round(_PIVOT_Y - frac * _ROD_LENGTH * math.cos(self._angle)))
            if 0 <= px < _MATRIX_W and 0 <= py < _MATRIX_H:
                brightness = 1.0 if t == _ROD_LENGTH else 0.7
                self.core.matrix.draw_pixel(px, py, rod_color,
                                            brightness=brightness, show=False)

        # --- Overheat flicker when vent is active ---
        if vent_held and self._overheat_pct > 50.0:
            if (frame_count // 3) % 2 == 0:
                # Dim orange flash on the pivot area
                for dx in range(-1, 2):
                    px = _PIVOT_X + dx
                    if 0 <= px < _MATRIX_W:
                        self.core.matrix.draw_pixel(px, _PIVOT_Y, Palette.ORANGE,
                                                    brightness=0.4, show=False)



    def _send_segment(self, text):
        """Send a string to the satellite 14-segment display (cached)."""
        safe_text = text[:8]
        if self.sat and self._last_segment_text != safe_text:
            try:
                self.sat.send("DSP", safe_text)
            except Exception:
                pass
            self._last_segment_text = safe_text

    # ------------------------------------------------------------------
    # Tutorial
    # ------------------------------------------------------------------

    async def run_tutorial(self):
        """
        A guided, non-interactive demonstration of Seismic Stabilizer.

        Voiceover Script (audio/tutes/seismic_tute.wav) ~ 38 seconds:
            [0:00] "Welcome to Seismic Stabilizer. Keep the reactor rod upright against
                   gravity and seismic shocks."
            [0:07] "The core dial adjusts the left tension cable. The satellite dial
                   adjusts the right cable."
            [0:14] "Turn both dials to maintain balance. Watch the rod colour: green
                   is safe, yellow is risky, red is critical."
            [0:22] "Inserting coolant rods slows the physics and makes it easier,
                   but reduces your score multiplier."
            [0:30] "In an emergency, hold the vent switch to re-centre the rod.
                   But do not overheat the reactor!"
            [0:38] (End of file)
        """
        await self.core.clean_slate()

        if not self.sat or not self.sat.is_active:
            self.core.display.update_status("SEISMIC STAB", "SAT OFFLINE - ABORT")
            await asyncio.sleep(2)
            return "TUTORIAL_FAILED"

        self.game_state = "TUTORIAL"

        # Start voiceover
        self.core.audio.play("audio/tutes/seismic_tute.wav",
                                bus_id=self.core.audio.CH_VOICE)

        # [0:00 - 0:07] Welcome
        self.core.display.update_header("SEISMIC STAB")
        self.core.display.update_status("REACTOR ONLINE", "STAND BY")
        self.core.matrix.show_icon("SEISMIC_STABILIZER", clear=True)
        self._angle = 0.0
        self._angular_velocity = 0.0
        self._overheat_pct = 0.0
        self._send_segment("ANG   0d")
        await asyncio.sleep(7.0)

        # [0:07 - 0:14] Show gravity pulling rod and encoders correcting it
        self.core.display.update_status("LEFT CABLE", "CORE DIAL")
        self._angle = 0.0
        self._angular_velocity = 0.3  # Small initial tilt
        for _ in range(40):
            self._update_physics(0.033, 0.0, 0.0, False)
            self._render(int(ticks_ms() / 33), False, 0)
            angle_deg = int(math.degrees(self._angle))
            self._send_segment(f"ANG {angle_deg:4d}d")
            await asyncio.sleep(0.033)

        # [0:07 - 0:14] Demonstrate left cable correction
        for _ in range(50):
            self._update_physics(0.033, 1.5, 0.0, False)
            self._render(int(ticks_ms() / 33), False, 0)
            angle_deg = int(math.degrees(self._angle))
            self._send_segment(f"ANG {angle_deg:4d}d")
            await asyncio.sleep(0.033)

        # [0:14 - 0:22] Both cables holding the rod steady
        self.core.display.update_status("BOTH CABLES", "DIAL BALANCE")
        self._angle = 0.05
        self._angular_velocity = 0.0
        for _ in range(80):
            self._update_physics(0.033, 0.9, 0.8, False)
            self._render(int(ticks_ms() / 33), False, 0)
            angle_deg = int(math.degrees(self._angle))
            self._send_segment(f"ANG {angle_deg:4d}d")
            await asyncio.sleep(0.033)

        # [0:22 - 0:30] Coolant rods inserted (simulate 4 rods active)
        self.core.display.update_status("COOLANT RODS", "SLOW PHYSICS")
        simulated_rods = 4  # number of coolant rods to demonstrate
        for _ in range(100):
            # physics_dt is slowed by factor 1 / (1 + simulated_rods * _COOLANT_SLOW_FACTOR)
            physics_dt = 0.033 / (1.0 + simulated_rods * _COOLANT_SLOW_FACTOR)
            self._update_physics(physics_dt, 0.4, 0.4, False)
            self._render(int(ticks_ms() / 33), False, simulated_rods)
            self._send_segment("COOL 0.6x")
            await asyncio.sleep(0.033)

        # [0:30 - 0:38] Vent demonstration
        self.core.display.update_status("VENT SWITCH", "RE-CENTRES ROD")
        self._angle = 0.4
        self._angular_velocity = 0.5
        self._overheat_pct = 0.0
        for step in range(80):
            self._overheat_pct = min(_OVERHEAT_LIMIT,
                                     self._overheat_pct + _OVERHEAT_RATE * 0.033)
            self._update_physics(0.033, 0.0, 0.0, True)
            self._render(int(ticks_ms() / 33), True, 0)
            self._send_segment(f"VNT {int(self._overheat_pct):3d}%")
            if self._overheat_pct > 60 and step == 60:
                self.core.display.update_status("CAUTION!", "OVERHEAT RISK")
            await asyncio.sleep(0.033)

        await self.core.clean_slate()
        return "TUTORIAL_COMPLETE"

    # ------------------------------------------------------------------
    # Main game loop
    # ------------------------------------------------------------------

    async def run(self):
        """Main game loop."""
        # --- Settings ---
        self.difficulty = self.core.data.get_setting(
            "SEISMIC_STABILIZER", "difficulty", "NORMAL"
        )
        self.variant = self.difficulty

        diff_cfg = _DIFF_PARAMS.get(self.difficulty, _DIFF_PARAMS["NORMAL"])
        self._gravity_mult = diff_cfg["gravity_mult"]
        self._shock_mult   = diff_cfg["shock_mult"]

        # --- Satellite check ---
        if not self.sat or not self.sat.is_active:
            self.core.display.update_status("SEISMIC STAB", "SAT OFFLINE - ABORT")
            await asyncio.sleep(2.0)
            return "SAT_OFFLINE"

        # --- Display intro ---
        self.core.display.use_standard_layout()
        self.core.display.update_status("SEISMIC STAB", "HOLD THE LINE")
        self.core.display.update_footer("L-ENC:LEFT  R-ENC:RIGHT")
        asyncio.create_task(
            self.core.synth.play_sequence(tones.WARP_CORE_IDLE, patch="ENGINE_HUM")
        )
        await asyncio.sleep(2.0)

        # --- Reset state ---
        self.score = 0
        self.level = 0  # 0-indexed internally; displayed as level + 1 to the player
        self._angle = 0.0
        self._angular_velocity = 0.0
        self._overheat_pct = 0.0
        self._shock_timer = _SHOCK_INTERVAL_BASE
        self._level_timer = 0.0
        self._score_accum = 0.0
        self._last_segment_text = ""

        # --- Calibrate encoder origins ---
        self.core.hid.reset_encoder(0)
        self._sat_enc_offset = self._sat_encoder_raw()

        last_tick = ticks_ms()
        frame_count = 0
        game_running = True

        while game_running:
            now = ticks_ms()
            delta_ms = ticks_diff(now, last_tick)

            if delta_ms >= 33:  # ~30 FPS
                last_tick = now
                dt = min(delta_ms / 1000.0, 0.1)  # cap to avoid physics explosion
                frame_count += 1

                # --- Read inputs ---
                coolant_count = self._count_coolant_rods()
                vent_held     = self._is_vent_held()

                # NEW: Clamp encoder positions to prevent "wind-up" debt
                max_ticks = int(_CABLE_MAX / _CABLE_STEP)

                # Clamp Core
                core_enc = self.core.hid.encoder_positions[_ENC_CORE]
                if core_enc > max_ticks:
                    self.core.hid.encoder_positions[_ENC_CORE] = max_ticks
                elif core_enc < -max_ticks:
                    self.core.hid.encoder_positions[_ENC_CORE] = -max_ticks

                # Clamp Satellite
                if self.sat:
                    sat_enc = self.sat.hid.encoder_positions[_ENC_SAT]
                    target_sat_max = self._sat_enc_offset + max_ticks
                    target_sat_min = self._sat_enc_offset - max_ticks

                    if sat_enc > target_sat_max:
                        self.sat.hid.encoder_positions[_ENC_SAT] = target_sat_max
                    elif sat_enc < target_sat_min:
                        self.sat.hid.encoder_positions[_ENC_SAT] = target_sat_min

                left_tension, right_tension = self._get_cable_tensions()

                # --- Overheat management ---
                if vent_held:
                    self._overheat_pct = min(
                        _OVERHEAT_LIMIT,
                        self._overheat_pct + _OVERHEAT_RATE * dt
                    )
                    if self._overheat_pct >= _OVERHEAT_LIMIT:
                        self.core.matrix.fill(Palette.ORANGE, show=True)
                        asyncio.create_task(
                            self.core.synth.play_sequence(tones.GAME_OVER)
                        )
                        self._send_segment("OVERHEAT")
                        await asyncio.sleep(0.5)
                        return await self.game_over()
                else:
                    self._overheat_pct = max(
                        0.0,
                        self._overheat_pct - _OVERHEAT_COOL * dt
                    )

                # --- Physics update (slowed by coolant rods) ---
                physics_dt = dt / (1.0 + coolant_count * _COOLANT_SLOW_FACTOR)
                self._update_physics(physics_dt, left_tension, right_tension, vent_held)

                # --- Fall check ---
                if abs(self._angle) >= _FALL_ANGLE:
                    self.core.matrix.fill(Palette.RED, show=True)
                    asyncio.create_task(
                        self.core.synth.play_sequence(tones.GAME_OVER)
                    )
                    self._send_segment("CRITICAL")
                    await asyncio.sleep(0.5)
                    return await self.game_over()

                # --- Seismic shocks ---
                self._shock_timer -= dt
                if self._shock_timer <= 0.0:
                    self._trigger_seismic_shock()
                    interval = max(
                        _SHOCK_INTERVAL_MIN,
                        _SHOCK_INTERVAL_BASE - self.level * 0.5
                    )
                    self._shock_timer = interval * random.uniform(0.7, 1.3)

                # --- Level progression ---
                self._level_timer += dt
                if self._level_timer >= _LEVEL_UP_INTERVAL:
                    self.level += 1
                    self._level_timer = 0.0
                    self.core.buzzer.play_sequence(tones.UI_CONFIRM)
                    self.core.display.update_status(
                        f"LEVEL {self.level + 1}!",
                        "SHOCKS INCREASING"
                    )
                    await asyncio.sleep(0.8)

                # --- Score accumulation ---
                multiplier = self._get_multiplier(coolant_count)
                self._score_accum += _BASE_SCORE_RATE * multiplier * dt
                self.score = int(self._score_accum)

                # --- HUD update ---
                angle_deg = int(math.degrees(self._angle))
                if vent_held:
                    status_b = f"VENT {int(self._overheat_pct):3d}%  {multiplier:.1f}x"
                else:
                    status_b = f"ANG:{angle_deg:+4d} {multiplier:.1f}x"
                self.core.display.update_status(
                    f"SCORE: {self.score}  LV:{self.level + 1}",
                    status_b
                )

                # --- Satellite segment display ---
                if vent_held:
                    self._send_segment(f"VNT {int(self._overheat_pct):3d}%")
                else:
                    self._send_segment(f"ANG {angle_deg:+4d}d")

                # --- Render ---
                self._render(frame_count, vent_held, coolant_count)

            await asyncio.sleep(0.01)
