# File: src/modes/orbital_docking.py
"""Orbital Docking Simulator – Zero-G 6-DOF Physics Game Mode.

A tense, high-precision physics simulator where the player manually aligns
and docks a spacecraft with a rotating space station using RCS thrusters.
True Newtonian mechanics: there is no friction in space, so every thrust
impulse accumulates as permanent momentum until counter-thrust is applied.

Hardware (Core + Industrial Satellite):
    Core:
        - 16x16 Matrix: Targeting viewport – crosshair at centre, docking
          ring that expands as Z-distance closes and shifts off-screen when
          X/Y alignment drifts.
        - OLED: Flight-computer telemetry – Z-Distance, Z-Velocity,
          X/Y Alignment Error, and RCS Fuel remaining.
        - Rotary Encoder: X-axis RCS translation. Each click *applies an
          impulse* (no friction – momentum persists until counter-thrust).
        - Button 0 (hold): Stability Augmentation System – reaction wheels
          attempt to arrest X/Y translation. Uses RCS fuel.

    Industrial Satellite (SAT-01):
        - Rotary Encoder (index 0): Y-axis RCS translation impulse.
        - Momentary Toggle (index 0) UP: OMS engine forward (approach).
        - Momentary Toggle (index 0) DOWN: Retro-rockets (braking).
        - 8× Latching Toggles (0-7): Magnetic clamps – once distance
          < 10 m and alignment is within tolerance, the OLED prompts the
          player to engage 4 specific clamps in a displayed sequence.
        - Guarded Toggle (index 8): Hard Capture – when distance reaches 0 m
          and approach speed is ≤ SAFE_DOCK_SPEED, flipping the guarded
          toggle triggers the hard capture and wins the mission.
        - 14-Segment Display: Real-time approach telemetry.

Gameplay:
    The player starts 200 m from the station.  Every encoder click applies
    lateral thrust; repeated clicks in the same direction build momentum
    that must be reversed before docking.  The OMS toggle controls approach
    speed along the Z-axis.  At < 10 m the clamp sequence initiates; at 0 m
    the guarded toggle triggers hard capture.

Difficulty Modifiers:
    EASY:   Station stationary, generous fuel (150%), wide alignment window.
    NORMAL: Station stationary, 100% fuel, standard window.
    HARD:   Station slow lateral drift, 75% fuel, tighter window.
    INSANE: Station fast lateral drift, 50% fuel, tight window.
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
_ENC_CORE       = 0    # Core rotary encoder → X translation
_ENC_SAT        = 0    # Satellite rotary encoder → Y translation
_BTN_SAS        = 0    # Core button 0 → SAS (hold)
_MT_OMS         = 0    # Satellite momentary toggle → Z-axis OMS
_SW_GUARD       = 8    # Satellite guarded toggle → hard capture
_TOGGLE_COUNT   = 8    # Latching toggles for magnetic clamps
_CLAMP_COUNT    = 4    # Number of clamps required in the docking sequence

# ---------------------------------------------------------------------------
# Physics constants
# ---------------------------------------------------------------------------
_INITIAL_DISTANCE   = 200.0   # metres to station at mission start
_SAFE_DOCK_SPEED    = 0.5     # m/s max approach speed for hard capture
_CLAMP_DISTANCE     = 10.0    # metres: start clamp-sequence phase
_CRASH_SPEED        = 3.0     # m/s: collision speed causes mission failure

_RCS_IMPULSE        = 0.04    # m/s per encoder tick (lateral)
_OMS_THRUST         = 0.06    # m/s per physics tick (z-axis thrust)
_SAS_DECAY          = 0.85    # velocity multiplier per frame when SAS active
_MAX_LAT_VELOCITY   = 1.5     # m/s: cap on X/Y velocity
_MAX_Z_VELOCITY     = 2.5     # m/s: cap on Z approach velocity

_FUEL_COST_RCS      = 1.0     # fuel units per encoder tick
_FUEL_COST_OMS      = 0.4     # fuel units per physics tick (OMS)
_FUEL_COST_SAS      = 0.5     # fuel units per physics tick (SAS)

# Station lateral drift (units per tick) for HARD/INSANE
_DRIFT_SLOW         = 0.008
_DRIFT_FAST         = 0.018

# ---------------------------------------------------------------------------
# Matrix rendering constants
# ---------------------------------------------------------------------------
_MATRIX_SIZE        = 16
_RING_MAX_RADIUS    = 7       # pixels at z=0
_CENTRE             = 8       # matrix centre pixel

# ---------------------------------------------------------------------------
# Phases
# ---------------------------------------------------------------------------
_PHASE_APPROACH     = "APPROACH"
_PHASE_CLAMP_SEQ    = "CLAMP_SEQ"
_PHASE_HARD_CAPTURE = "HARD_CAPTURE"

# ---------------------------------------------------------------------------
# Difficulty tables
# ---------------------------------------------------------------------------
_DIFF_PARAMS = {
    "EASY":   {"fuel_mult": 1.5, "drift": False, "align_tol": 2.5},
    "NORMAL": {"fuel_mult": 1.0, "drift": False, "align_tol": 1.5},
    "HARD":   {"fuel_mult": 0.75, "drift": True,  "align_tol": 1.0, "drift_speed": _DRIFT_SLOW},
    "INSANE": {"fuel_mult": 0.5,  "drift": True,  "align_tol": 0.6, "drift_speed": _DRIFT_FAST},
}

_BASE_FUEL          = 100.0   # maximum RCS fuel units


class OrbitalDocking(GameMode):
    """Orbital Docking Simulator – zero-gravity 6-DOF docking game.

    Hardware:
        Core:
            - 16×16 Matrix: Targeting viewport (crosshair + docking ring)
            - OLED: Flight-computer telemetry
            - Rotary Encoder (index 0): X-axis RCS thrust
            - Button 0 (hold): SAS – stability augmentation

        Industrial Satellite (SAT-01):
            - Rotary Encoder (index 0): Y-axis RCS thrust
            - Momentary Toggle (index 0) UP: OMS forward thrust (approach)
            - Momentary Toggle (index 0) DOWN: Retro-rockets (braking)
            - 8× Latching Toggles (0-7): Magnetic clamps
            - Guarded Toggle (index 8): Hard Capture trigger
            - 14-Segment Display: Approach telemetry
    """

    def __init__(self, core):
        super().__init__(core, "ORBITAL DOCKING", "Zero-G Docking Simulator")
        self.sat = None
        for sat in self.core.satellites.values():
            if sat.sat_type_name == "INDUSTRIAL":
                self.sat = sat
                break

        # Physics state
        self._z_dist    = _INITIAL_DISTANCE
        self._vel_x     = 0.0
        self._vel_y     = 0.0
        self._vel_z     = 0.0   # positive = approaching
        self._align_x   = 0.0   # lateral offset, metres equivalent
        self._align_y   = 0.0

        # Resources
        self._fuel      = _BASE_FUEL

        # Difficulty
        self._fuel_mult = 1.0
        self._drift     = False
        self._drift_speed = _DRIFT_SLOW
        self._align_tol = 1.5

        # Station drift state
        self._drift_dir_x = 1.0
        self._drift_dir_y = 0.5

        # Phase / sequence
        self._phase             = _PHASE_APPROACH
        self._clamp_sequence    = []   # list of 4 toggle indices to engage
        self._clamp_progress    = 0    # clamps correctly engaged so far
        self._prev_latching     = [False] * _TOGGLE_COUNT
        self._last_segment_text = ""

        # Encoder tracking (delta-based)
        self._last_core_enc = 0
        self._last_sat_enc  = 0

        # Frame counter for animations
        self._frame = 0

    # ------------------------------------------------------------------
    # Satellite HID helpers (safe wrappers)
    # ------------------------------------------------------------------

    def _sat_latching(self, idx):
        """Return the state of a satellite latching toggle (0-7)."""
        if not self.sat:
            return False
        try:
            return bool(self.sat.hid.latching_values[idx])
        except (IndexError, AttributeError):
            return False

    def _sat_guard(self):
        """Return True if the guarded toggle (hard capture) is engaged."""
        if not self.sat:
            return False
        try:
            return bool(self.sat.hid.latching_values[_SW_GUARD])
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

    def _sat_momentary_up(self):
        """Return True if the satellite OMS momentary toggle is held UP."""
        if not self.sat:
            return False
        try:
            return self.sat.hid.is_momentary_toggled(_MT_OMS, direction="U")
        except (IndexError, AttributeError):
            return False

    def _sat_momentary_down(self):
        """Return True if the satellite OMS momentary toggle is held DOWN."""
        if not self.sat:
            return False
        try:
            return self.sat.hid.is_momentary_toggled(_MT_OMS, direction="D")
        except (IndexError, AttributeError):
            return False

    def _send_segment(self, text):
        """Send text to the satellite 14-segment display (max 8 chars)."""
        safe_text = text[:8]
        if self.sat and self._last_segment_text != safe_text:
            try:
                self.sat.send("DSP", safe_text)
                self._last_segment_text = safe_text
            except Exception:
                pass

    def _set_led(self, idx, color):
        """Set a satellite LED colour."""
        if self.sat:
            try:
                self.sat.send("LED", f"{idx},{color.index},0.0,1.0,2")
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Physics
    # ------------------------------------------------------------------

    def _apply_rcs_x(self, delta):
        """Apply an X-axis RCS impulse from an encoder delta."""
        if delta == 0:
            return
        fuel_needed = abs(delta) * _FUEL_COST_RCS
        if self._fuel <= 0:
            return
        fuel_used = min(fuel_needed, self._fuel)
        scale = fuel_used / fuel_needed if fuel_needed > 0 else 0.0
        self._vel_x += delta * _RCS_IMPULSE * scale
        self._vel_x = max(-_MAX_LAT_VELOCITY, min(_MAX_LAT_VELOCITY, self._vel_x))
        self._fuel = max(0.0, self._fuel - fuel_used)

    def _apply_rcs_y(self, delta):
        """Apply a Y-axis RCS impulse from an encoder delta."""
        if delta == 0:
            return
        fuel_needed = abs(delta) * _FUEL_COST_RCS
        if self._fuel <= 0:
            return
        fuel_used = min(fuel_needed, self._fuel)
        scale = fuel_used / fuel_needed if fuel_needed > 0 else 0.0
        self._vel_y += delta * _RCS_IMPULSE * scale
        self._vel_y = max(-_MAX_LAT_VELOCITY, min(_MAX_LAT_VELOCITY, self._vel_y))
        self._fuel = max(0.0, self._fuel - fuel_used)

    def _apply_sas(self):
        """Stability Augmentation System: decay X/Y velocity toward zero."""
        if self._fuel <= 0:
            return
        self._vel_x *= _SAS_DECAY
        self._vel_y *= _SAS_DECAY
        self._fuel = max(0.0, self._fuel - _FUEL_COST_SAS)

    def _update_physics(self, oms_forward, oms_brake, sas_active):
        """Integrate velocities and positions for one physics tick."""
        # Z-axis (approach / braking)
        if oms_forward and self._fuel > 0:
            self._vel_z += _OMS_THRUST
            self._vel_z = min(_MAX_Z_VELOCITY, self._vel_z)
            self._fuel = max(0.0, self._fuel - _FUEL_COST_OMS)
        if oms_brake and self._fuel > 0:
            self._vel_z -= _OMS_THRUST
            self._vel_z = max(-_MAX_Z_VELOCITY, self._vel_z)
            self._fuel = max(0.0, self._fuel - _FUEL_COST_OMS)

        # SAS (lateral stabilisation)
        if sas_active:
            self._apply_sas()

        # Station drift (HARD / INSANE difficulty)
        if self._drift:
            self._align_x += self._drift_dir_x * self._drift_speed
            self._align_y += self._drift_dir_y * self._drift_speed
            # Bounce station drift direction at edges
            if abs(self._align_x) > 8.0:
                self._drift_dir_x = -self._drift_dir_x
            if abs(self._align_y) > 8.0:
                self._drift_dir_y = -self._drift_dir_y

        # Integrate X/Y lateral position
        self._align_x += self._vel_x
        self._align_y += self._vel_y

        # Integrate Z
        self._z_dist -= self._vel_z
        self._z_dist = max(0.0, self._z_dist)

        self._frame += 1

    def _approach_speed(self):
        """Return the magnitude of the total velocity vector."""
        return math.sqrt(self._vel_x ** 2 + self._vel_y ** 2 + self._vel_z ** 2)

    def _is_aligned(self):
        """Return True when X/Y error is within the docking tolerance."""
        return (abs(self._align_x) <= self._align_tol and
                abs(self._align_y) <= self._align_tol)

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _draw_ring(self, cx, cy, radius, color):
        """Draw a circle outline on the 16×16 matrix (Bresenham)."""
        r = int(round(radius))
        if r <= 0:
            # At radius 0 just mark the centre point
            if 0 <= cx < _MATRIX_SIZE and 0 <= cy < _MATRIX_SIZE:
                self.core.matrix.draw_pixel(cx, cy, color)
            return
        x, y = 0, r
        d = 3 - 2 * r
        while x <= y:
            for px, py in [
                (cx + x, cy + y), (cx - x, cy + y),
                (cx + x, cy - y), (cx - x, cy - y),
                (cx + y, cy + x), (cx - y, cy + x),
                (cx + y, cy - x), (cx - y, cy - x),
            ]:
                if 0 <= px < _MATRIX_SIZE and 0 <= py < _MATRIX_SIZE:
                    self.core.matrix.draw_pixel(px, py, color)
            if d <= 0:
                d += 4 * x + 6
            else:
                d += 4 * (x - y) + 10
                y -= 1
            x += 1

    def _render(self):
        """Render the current docking state onto the LED matrix."""
        self.core.matrix.clear()

        # --- Docking ring ---
        # Radius grows from 0 to _RING_MAX_RADIUS as distance closes.
        progress = 1.0 - (self._z_dist / _INITIAL_DISTANCE)
        progress = max(0.0, min(1.0, progress))
        ring_r = progress * _RING_MAX_RADIUS

        # Ring centre shifts with alignment error (clamped to matrix)
        ring_cx = int(round(_CENTRE - self._align_x))
        ring_cy = int(round(_CENTRE - self._align_y))

        # Ring colour: green when aligned, orange when drifted
        if self._is_aligned():
            ring_color = Palette.GREEN
        else:
            ring_color = Palette.ORANGE

        # Flash ring when in CLAMP_SEQ or HARD_CAPTURE phase
        if self._phase in (_PHASE_CLAMP_SEQ, _PHASE_HARD_CAPTURE):
            if (self._frame // 4) % 2 == 0:
                ring_color = Palette.CYAN

        self._draw_ring(ring_cx, ring_cy, ring_r, ring_color)

        # --- Crosshair (player centre) ---
        cx, cy = _CENTRE, _CENTRE
        # Horizontal arms
        for dx in (-3, -2, -1, 1, 2, 3):
            if 0 <= cx + dx < _MATRIX_SIZE:
                self.core.matrix.draw_pixel(cx + dx, cy, Palette.GRAY)
        # Vertical arms
        for dy in (-3, -2, -1, 1, 2, 3):
            if 0 <= cy + dy < _MATRIX_SIZE:
                self.core.matrix.draw_pixel(cx, cy + dy, Palette.GRAY)
        # Centre dot (bright)
        self.core.matrix.draw_pixel(cx, cy, Palette.WHITE)

        # --- Velocity vector indicator ---
        if abs(self._vel_x) > 0.1 or abs(self._vel_y) > 0.1:
            vx = cx + int(self._vel_x * 2.0)
            vy = cy + int(self._vel_y * 2.0)
            vx = max(0, min(_MATRIX_SIZE - 1, vx))
            vy = max(0, min(_MATRIX_SIZE - 1, vy))
            self.core.matrix.draw_pixel(vx, vy, Palette.RED)

        self.core.matrix.show_frame()

    def _render_telemetry(self, phase_hint=""):
        """Update Core OLED with current flight-computer data."""
        fuel_pct = int(self._fuel / (_BASE_FUEL * self._fuel_mult) * 100)
        fuel_pct = max(0, min(100, fuel_pct))
        vz_sign = "+" if self._vel_z >= 0 else ""
        self.core.display.update_header(
            f"Z:{self._z_dist:.0f}m  VZ:{vz_sign}{self._vel_z:.2f}"
        )
        ax_sign = "+" if self._align_x >= 0 else ""
        ay_sign = "+" if self._align_y >= 0 else ""
        self.core.display.update_status(
            f"X:{ax_sign}{self._align_x:.1f} Y:{ay_sign}{self._align_y:.1f}",
            f"FUEL:{fuel_pct}%  {phase_hint}"
        )

    # ------------------------------------------------------------------
    # Clamp sequence helpers
    # ------------------------------------------------------------------

    def _generate_clamp_sequence(self):
        """Pick 4 distinct toggle indices as the required clamp sequence."""
        indices = list(range(_TOGGLE_COUNT))
        random.shuffle(indices)
        self._clamp_sequence = indices[:_CLAMP_COUNT]
        self._clamp_progress = 0

    def _check_clamp_progress(self):
        """Detect new toggle activations and advance clamp sequence."""
        for i in range(_TOGGLE_COUNT):
            now = self._sat_latching(i)
            was = self._prev_latching[i]
            if now and not was:
                # A toggle was just flipped ON
                expected = self._clamp_sequence[self._clamp_progress]
                if i == expected:
                    self._clamp_progress += 1
                    self._set_led(i, Palette.GREEN)
                    asyncio.create_task(
                        self.core.synth.play_note(440.0 + self._clamp_progress * 110.0,
                                                  "BLIP", duration=0.08)
                    )
                else:
                    # Wrong toggle – reset sequence
                    self._clamp_progress = 0
                    self._set_led(i, Palette.RED)
                    asyncio.create_task(
                        self.core.synth.play_sequence(tones.FAIL_BEEP)
                    )
            self._prev_latching[i] = now

    # ------------------------------------------------------------------
    # Tutorial
    # ------------------------------------------------------------------

    async def run_tutorial(self):
        """
        A guided, non-interactive demonstration of the Orbital Docking mission.

        Voiceover Script (audio/tutes/orbital_docking_tute.wav) ~ 45 seconds:
            [0:00] "Welcome to Orbital Docking Simulator. True Newtonian physics."
            [0:05] "You are 200 metres from the station. The docking ring will expand as you approach."
            [0:11] "Use the base dial for X-axis thrust, and the satellite dial for Y-axis thrust."
            [0:17] "There is no friction in space. Each click builds momentum you must reverse."
            [0:23] "Push the momentary toggle UP to fire the OMS engine and approach the station."
            [0:29] "Push DOWN for retro-rockets to slow your approach. Watch your speed."
            [0:34] "Hold the big button to activate the Stability Augmentation System."
            [0:38] "Within 10 metres, engage the 4 magnetic clamps in the displayed sequence."
            [0:43] "Then flip the guarded toggle to execute hard capture. Good luck."
            [0:47] (End of file)
        """
        await self.core.clean_slate()

        if not self.sat or not self.sat.is_active:
            self.core.display.update_status("ORBITAL DOCKING", "SAT OFFLINE - ABORT")
            await asyncio.sleep(2)
            return "TUTORIAL_FAILED"

        self.game_state = "TUTORIAL"

        # Start voiceover
        tute_audio = asyncio.create_task(
            self.core.audio.play(
                "audio/tutes/orbital_docking_tute.wav",
                bus_id=self.core.audio.CH_VOICE
            )
        )

        # [0:00 - 0:05] "Welcome to Orbital Docking Simulator..."
        self.core.display.update_header("ORBITAL DOCKING")
        self.core.display.update_status("ZERO-G PHYSICS", "STAND BY")
        self.core.matrix.show_icon("ORBITAL_DOCKING", clear=True)
        self.core.buzzer.play_sequence(tones.POWER_UP)
        await asyncio.sleep(5.0)

        # [0:05 - 0:11] "You are 200 metres from the station..."
        self.core.display.update_header("Z:200m  VZ:+0.00")
        self.core.display.update_status("APPROACHING", "RING EXPANDS ON CLOSE")
        # Animate ring growing
        self._z_dist = _INITIAL_DISTANCE
        self._align_x = 0.0
        self._align_y = 0.0
        self._vel_z = 0.5
        for _ in range(60):
            self._z_dist = max(80.0, self._z_dist - 2.0)
            self._render()
            await asyncio.sleep(0.05)
        await asyncio.sleep(0.5)

        # [0:11 - 0:17] "Use the base dial for X-axis thrust..."
        self.core.display.update_status("DIAL=X THRUST", "SAT DIAL=Y THRUST")
        self._align_x = 0.0
        for _ in range(50):
            self._align_x += 0.12
            if self._align_x > 3.0:
                self._align_x = 3.0
            self._render()
            await asyncio.sleep(0.05)
        # Counter-thrust
        for _ in range(50):
            self._align_x -= 0.12
            if self._align_x < 0.0:
                self._align_x = 0.0
            self._render()
            await asyncio.sleep(0.05)
        await asyncio.sleep(0.5)

        # [0:17 - 0:23] "There is no friction in space..."
        self.core.display.update_status("NO FRICTION!", "MOMENTUM PERSISTS")
        # Simulate drifting off-centre
        self._vel_x = 0.15
        for _ in range(60):
            self._align_x += self._vel_x
            self._render()
            await asyncio.sleep(0.05)
        # Counter-thrust to stop
        self._vel_x = -0.10
        for _ in range(40):
            self._align_x += self._vel_x
            if self._align_x <= 0.0:
                self._align_x = 0.0
                self._vel_x = 0.0
                break
            self._render()
            await asyncio.sleep(0.05)
        self._vel_x = 0.0
        await asyncio.sleep(1.0)

        # [0:23 - 0:29] "Push the momentary toggle UP to approach..."
        self.core.display.update_status("MT UP=APPROACH", "MT DOWN=RETRO")
        self._vel_z = 0.3
        for _ in range(60):
            self._z_dist = max(30.0, self._z_dist - 1.5)
            self._render()
            await asyncio.sleep(0.05)
        await asyncio.sleep(0.5)

        # [0:29 - 0:34] "Push DOWN for retro-rockets..."
        self.core.display.update_status("RETRO BURN!", "WATCH YOUR SPEED")
        self._vel_z = 0.0
        self._z_dist = 30.0
        for _ in range(40):
            self._render()
            await asyncio.sleep(0.05)
        await asyncio.sleep(0.5)

        # [0:34 - 0:38] "Hold the big button to activate SAS..."
        self.core.display.update_status("SAS ACTIVE", "HOLD B0 TO HOLD")
        self._align_x = 2.0
        self._vel_x = 0.08
        for _ in range(50):
            # SAS decay demo
            self._vel_x *= _SAS_DECAY
            self._align_x += self._vel_x
            self._render()
            await asyncio.sleep(0.05)
        self._vel_x = 0.0
        self._align_x = 0.0
        await asyncio.sleep(0.5)

        # [0:38 - 0:43] "Within 10 metres, engage the 4 magnetic clamps..."
        self.core.display.update_status("CLAMP SEQUENCE", "ENGAGE IN ORDER!")
        self._z_dist = 8.0
        self._generate_clamp_sequence()
        seq_str = " ".join(str(i + 1) for i in self._clamp_sequence)
        self.core.display.update_footer(f"SEQ: {seq_str}")
        self._send_segment(f"CLM {self._clamp_sequence[0] + 1}")
        for _ in range(60):
            self._render()
            await asyncio.sleep(0.05)
        await asyncio.sleep(0.5)

        # [0:43 - 0:47] "Then flip the guarded toggle..."
        self.core.display.update_status("HARD CAPTURE", "FLIP GUARD TOGGLE")
        self._z_dist = 0.0
        self._send_segment("DOCK RDY")
        for _ in range(40):
            self._render()
            await asyncio.sleep(0.05)
        self.core.matrix.fill(Palette.CYAN, show=True)
        self.core.buzzer.play_sequence(tones.SUCCESS)
        await asyncio.sleep(1.0)

        # Wait for audio to finish
        if hasattr(self.core.audio, 'wait_for_bus'):
            await self.core.audio.wait_for_bus(self.core.audio.CH_VOICE)
        else:
            await asyncio.sleep(3.0)

        await self.core.clean_slate()
        return "TUTORIAL_COMPLETE"

    # ------------------------------------------------------------------
    # Main game loop
    # ------------------------------------------------------------------

    async def run(self):
        """Main game loop for Orbital Docking Simulator."""
        self.difficulty = self.core.data.get_setting(
            "ORBITAL_DOCKING", "difficulty", "NORMAL"
        )
        self.variant = self.difficulty

        diff_cfg = _DIFF_PARAMS.get(self.difficulty, _DIFF_PARAMS["NORMAL"])
        self._fuel_mult  = diff_cfg["fuel_mult"]
        self._drift      = diff_cfg["drift"]
        self._align_tol  = diff_cfg["align_tol"]
        self._drift_speed = diff_cfg.get("drift_speed", _DRIFT_SLOW)

        # Initialise state
        self._z_dist    = _INITIAL_DISTANCE
        self._vel_x     = 0.0
        self._vel_y     = 0.0
        self._vel_z     = 0.0
        self._align_x   = 0.0
        self._align_y   = 0.0
        self._fuel      = _BASE_FUEL * self._fuel_mult
        self._phase     = _PHASE_APPROACH
        self._frame     = 0
        self._last_segment_text = ""

        # Initialise encoder baseline
        self._last_core_enc = self.core.hid.encoder_positions[_ENC_CORE]
        self._last_sat_enc  = self._sat_encoder()
        self.core.hid.reset_encoder(index=_ENC_CORE)
        if self.sat:
            try:
                self.sat.hid.reset_encoder(value=0, index=_ENC_SAT)
            except Exception:
                pass
        self._last_core_enc = 0
        self._last_sat_enc  = 0

        # Initialise toggle snapshot
        self._prev_latching = [self._sat_latching(i) for i in range(_TOGGLE_COUNT)]

        # Display setup
        self.core.display.use_standard_layout()
        self.core.display.update_header("ORBITAL DOCKING")
        self.core.display.update_status("SYSTEMS NOMINAL", "APPROACH STATION")
        self.core.display.update_footer("ENC:X  SAT:Y  MT:Z")
        self._send_segment("APPR 200")
        asyncio.create_task(self.core.synth.play_sequence(tones.POWER_UP, patch="SCANNER"))
        await asyncio.sleep(2.0)

        last_tick = ticks_ms()

        while True:
            now = ticks_ms()
            delta_ms = ticks_diff(now, last_tick)

            if delta_ms < 33:  # ~30 FPS
                await asyncio.sleep(0.005)
                continue

            last_tick = now

            # --- Read controls ---
            curr_core_enc = self.core.hid.encoder_positions[_ENC_CORE]
            enc_dx = curr_core_enc - self._last_core_enc
            self._last_core_enc = curr_core_enc

            curr_sat_enc = self._sat_encoder()
            enc_dy = curr_sat_enc - self._last_sat_enc
            self._last_sat_enc = curr_sat_enc

            oms_forward = self._sat_momentary_up()
            oms_brake   = self._sat_momentary_down()
            sas_active  = self.core.hid.is_button_pressed(_BTN_SAS)

            # --- Apply lateral RCS impulses (encoder deltas) ---
            if enc_dx != 0:
                self._apply_rcs_x(enc_dx)
            if enc_dy != 0:
                self._apply_rcs_y(enc_dy)

            # --- Physics tick ---
            self._update_physics(oms_forward, oms_brake, sas_active)

            # --- Crash check: too fast Z collision ---
            if self._z_dist <= 0.0:
                total_speed = self._approach_speed()
                if total_speed > _SAFE_DOCK_SPEED and self._phase != _PHASE_HARD_CAPTURE:
                    # Crashed
                    self.core.matrix.fill(Palette.RED, show=True)
                    asyncio.create_task(self.core.synth.play_sequence(tones.GAME_OVER))
                    self.core.display.update_status("COLLISION!", f"SPD:{total_speed:.2f}m/s")
                    self._send_segment("CRASH!!!")
                    await asyncio.sleep(0.5)
                    return await self.game_over()

            # --- Crash check: excessive lateral velocity at close range ---
            if (self._z_dist < _CLAMP_DISTANCE and
                    (abs(self._vel_x) > _CRASH_SPEED or abs(self._vel_y) > _CRASH_SPEED)):
                self.core.matrix.fill(Palette.RED, show=True)
                asyncio.create_task(self.core.synth.play_sequence(tones.GAME_OVER))
                self.core.display.update_status("LATERAL CRASH!", "REDUCE SPEED")
                self._send_segment("CRASH!!!")
                await asyncio.sleep(0.5)
                return await self.game_over()

            # --- Phase transitions ---
            if self._phase == _PHASE_APPROACH:
                if (self._z_dist <= _CLAMP_DISTANCE and self._is_aligned()):
                    self._phase = _PHASE_CLAMP_SEQ
                    self._generate_clamp_sequence()
                    seq_str = " ".join(str(i + 1) for i in self._clamp_sequence)
                    self.core.display.update_footer(f"CLAMP SEQ: {seq_str}")
                    next_clamp = self._clamp_sequence[0] + 1
                    self._send_segment(f"CLM {next_clamp}")
                    asyncio.create_task(
                        self.core.synth.play_sequence(tones.UI_CONFIRM)
                    )

            elif self._phase == _PHASE_CLAMP_SEQ:
                # Check if alignment drifted out again
                if not self._is_aligned() and self._z_dist > 1.0:
                    self._phase = _PHASE_APPROACH
                    self._clamp_progress = 0
                    self.core.display.update_footer("MAINTAIN ALIGNMENT!")
                    self._send_segment("RE-ALIGN")

                # Check clamp sequence progress
                self._check_clamp_progress()

                # Show next expected clamp
                if self._clamp_progress < _CLAMP_COUNT:
                    next_clamp = self._clamp_sequence[self._clamp_progress] + 1
                    self._send_segment(f"CLM {next_clamp}")

                # All 4 clamps engaged → move to hard capture
                if self._clamp_progress >= _CLAMP_COUNT:
                    self._phase = _PHASE_HARD_CAPTURE
                    self.core.display.update_footer("FLIP GUARD: HARD CAPTURE")
                    self._send_segment("DOCK RDY")
                    asyncio.create_task(
                        self.core.synth.play_sequence(tones.SUCCESS)
                    )

            elif self._phase == _PHASE_HARD_CAPTURE:
                total_speed = self._approach_speed()
                if self._sat_guard():
                    if total_speed <= _SAFE_DOCK_SPEED and self._z_dist <= 0.5:
                        # Successful docking!
                        self.score = max(
                            100,
                            int(1000 * (1.0 - total_speed / _SAFE_DOCK_SPEED)
                                + self._fuel * 5)
                        )
                        self.core.matrix.fill(Palette.CYAN, show=True)
                        self._send_segment("DOCKED!!")
                        asyncio.create_task(
                            self.core.audio.play(
                                "audio/general/win.wav",
                                self.core.audio.CH_SFX,
                                level=1.0,
                                interrupt=True
                            )
                        )
                        self.core.display.update_status(
                            "HARD CAPTURE OK!",
                            f"SCORE: {self.score}"
                        )
                        await asyncio.sleep(2.0)
                        return await self.victory()
                    elif total_speed > _SAFE_DOCK_SPEED:
                        # Guard flipped but too fast
                        self.core.display.update_footer(
                            f"TOO FAST: {total_speed:.2f}m/s!"
                        )

            # --- OMS engine sound ---
            if oms_forward or oms_brake:
                now_ms = ticks_ms()
                if now_ms - getattr(self, '_last_oms_audio', 0) > 150:
                    freq = 80.0 + abs(self._vel_z) * 40.0
                    self.core.synth.play_note(freq, "ENGINE_HUM", duration=0.15)
                    self._last_oms_audio = now_ms

            # --- RCS click sounds ---
            if enc_dx != 0 or enc_dy != 0:
                now_ms = ticks_ms()
                if now_ms - getattr(self, '_last_rcs_audio', 0) > 80:
                    self.core.synth.play_note(520.0, "BLIP", duration=0.04)
                    self._last_rcs_audio = now_ms

            # --- Low fuel warning ---
            if self._fuel <= 10.0 and (self._frame % 30) == 0:
                asyncio.create_task(
                    self.core.synth.play_sequence(tones.FAIL_BEEP)
                )

            # --- Render ---
            self._render()
            self._render_telemetry(self._phase)

            # Update satellite segment display periodically
            if self._frame % 10 == 0:
                if self._phase == _PHASE_APPROACH:
                    self._send_segment(f"Z {self._z_dist:.0f}m")
                elif self._phase == _PHASE_HARD_CAPTURE:
                    self._send_segment("DOCK RDY")

            await asyncio.sleep(0.005)
