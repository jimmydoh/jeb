# File: src/modes/magnetic_containment.py
"""Magnetic Containment – Dual-Encoder Physics Juggling Game.

The player must keep a volatile plasma ball centered on the 16×16 matrix by
adjusting two magnetic poles via the rotary encoders. The plasma ball naturally
wants to drift and accelerate toward the edges; the player must dial both
encoders simultaneously (Etch-A-Sketch style) to counteract the particle's
momentum and drag it back to center.

Hardware Mapping
----------------
Core:
    - 16×16 Matrix: Plasma particle + containment field visualization
    - OLED: Containment Integrity, score, stasis status
    - Rotary Encoder: X-axis magnetic force (CW = pull right, CCW = pull left)

Industrial Satellite (SAT-01):
    - Rotary Encoder (index 0): Y-axis magnetic force
    - 14-Segment Display: Containment Integrity as "INTG  XXX"
    - Guarded Toggle (index 8): Arm the Stasis Field
    - Momentary Toggle (index 0) UP: Trigger Stasis Field (freeze 2 s)

Gameplay
--------
The plasma ball starts at center with zero velocity. Random "chaos kicks" are
periodically applied to push the particle in unpredictable directions. The
player must use the dual encoders to apply counteracting magnetic forces.

Containment Integrity drains faster the closer the ball gets to the edge.
Reaching 0% triggers GAME OVER.

Emergency Stasis Field: Arm the guarded toggle and flick the momentary switch
UP to freeze the plasma for 2 seconds, allowing the player to re-centre their
encoder positions. A recharge cooldown applies before it can be used again.
"""

import asyncio
import math
import random

from adafruit_ticks import ticks_ms, ticks_diff

from utilities.palette import Palette
from utilities import tones

from .game_mode import GameMode

# ---------------------------------------------------------------------------
# Hardware indices (mirror sat_01_driver layout)
# ---------------------------------------------------------------------------
_ENC_CORE   = 0   # Core rotary encoder index
_ENC_SAT    = 0   # Satellite rotary encoder index
_SW_ARM     = 8   # Guarded toggle (Master Arm / Stasis Arm)
_MT_STASIS  = 0   # Momentary toggle index for stasis trigger

# ---------------------------------------------------------------------------
# Physics constants
# ---------------------------------------------------------------------------
_MATRIX_W   = 16
_MATRIX_H   = 16
_CENTER_X   = (_MATRIX_W - 1) / 2.0   # 7.5
_CENTER_Y   = (_MATRIX_H - 1) / 2.0   # 7.5

# Force applied per encoder tick
_FORCE_PER_TICK     = 0.07
# Maximum magnetic force magnitude (clamps encoder pull)
_MAX_FORCE          = 0.30
# Natural damping applied each frame (slight drag to prevent infinite drift)
_DAMPING            = 0.985
# Maximum speed cap per axis
_MAX_VELOCITY       = 1.2
# Bounce damping when hitting a wall
_BOUNCE_DAMPING     = 0.55

# ---------------------------------------------------------------------------
# Chaos kick settings
# ---------------------------------------------------------------------------
_CHAOS_STRENGTH_BASE   = 0.25   # Magnitude of random kick impulse
_CHAOS_INTERVAL_BASE   = 3.0    # Seconds between chaos kicks (base)

# ---------------------------------------------------------------------------
# Health / integrity
# ---------------------------------------------------------------------------
_MAX_INTEGRITY          = 100
# Drain rate multiplier: integrity lost per second at maximum edge distance
_DRAIN_RATE_BASE        = 8.0   # at the outermost boundary
# Safe zone radius – no drain while particle is within this distance from center
_SAFE_RADIUS            = 3.5   # pixels from center
# Maximum drain distance (particle at edge = full drain)
_MAX_DRAIN_DIST         = math.sqrt(_CENTER_X ** 2 + _CENTER_Y ** 2)   # ~10.6

# Safe zone ring visual thickness (pixels from the safe radius boundary)
_SAFE_RING_THICKNESS = 0.7

# ---------------------------------------------------------------------------
# Stasis field
# ---------------------------------------------------------------------------
_STASIS_DURATION    = 2.0    # Seconds the stasis field holds
_STASIS_COOLDOWN    = 12.0   # Recharge seconds before next use

# ---------------------------------------------------------------------------
# Score
# ---------------------------------------------------------------------------
_SCORE_PER_SECOND       = 10    # Score gained per second of survival
_SCORE_CENTER_BONUS     = 5     # Extra score per second while inside safe radius

# ---------------------------------------------------------------------------
# Difficulty tuning
# ---------------------------------------------------------------------------
_DIFF_PARAMS = {
    "NORMAL": {
        "chaos_strength":   _CHAOS_STRENGTH_BASE,
        "chaos_interval":   _CHAOS_INTERVAL_BASE,
        "drain_rate":       _DRAIN_RATE_BASE,
        "max_velocity":     _MAX_VELOCITY,
    },
    "HARD": {
        "chaos_strength":   _CHAOS_STRENGTH_BASE * 1.5,
        "chaos_interval":   _CHAOS_INTERVAL_BASE * 0.7,
        "drain_rate":       _DRAIN_RATE_BASE * 1.5,
        "max_velocity":     _MAX_VELOCITY * 1.3,
    },
    "INSANE": {
        "chaos_strength":   _CHAOS_STRENGTH_BASE * 2.2,
        "chaos_interval":   _CHAOS_INTERVAL_BASE * 0.45,
        "drain_rate":       _DRAIN_RATE_BASE * 2.5,
        "max_velocity":     _MAX_VELOCITY * 1.7,
    },
}


class MagneticContainment(GameMode):
    """Magnetic Containment – dual-encoder physics juggling game.

    Hardware:
        Core:
            - 16×16 Matrix: plasma particle + containment field lines
            - OLED: status line with integrity and stasis state
            - Rotary Encoder: X-axis magnetic force

        Industrial Satellite (SAT-01):
            - Rotary Encoder (index 0): Y-axis magnetic force
            - 14-Segment Display: Containment Integrity
            - Guarded Toggle (index 8): Arm Stasis Field
            - Momentary Toggle (index 0) UP: Trigger Stasis Field
    """

    def __init__(self, core):
        super().__init__(core, "MAG CONTAINMENT", "Plasma Juggling Physics")
        self.sat = None
        for sat in self.core.satellites.values():
            if sat.sat_type_name == "INDUSTRIAL":
                self.sat = sat
                break

        # Plasma ball state
        self._ball_x = float(_CENTER_X)
        self._ball_y = float(_CENTER_Y)
        self._vel_x  = 0.0
        self._vel_y  = 0.0

        # Encoder tracking
        self._last_core_enc = 0
        self._last_sat_enc  = 0

        # Integrity / health
        self._integrity = float(_MAX_INTEGRITY)

        # Chaos kick timer
        self._chaos_timer = 0.0

        # Stasis state
        self._stasis_armed    = False
        self._stasis_active   = False
        self._stasis_timer    = 0.0
        self._stasis_cooldown = 0.0

        # Difficulty parameters (populated in run())
        self._chaos_strength   = _CHAOS_STRENGTH_BASE
        self._chaos_interval   = _CHAOS_INTERVAL_BASE
        self._drain_rate       = _DRAIN_RATE_BASE
        self._max_vel          = _MAX_VELOCITY

        # Last LED update for segment throttle
        self._last_segment_integrity = -1

        # Score accumulator for fractional seconds
        self._score_accumulator = 0.0

        # Pre-compute safe zone ring pixels to save CPU in the render loop
        self._safe_ring_pixels = []
        for x in range(_MATRIX_W):
            for y in range(_MATRIX_H):
                dist = math.sqrt((x - _CENTER_X) ** 2 + (y - _CENTER_Y) ** 2)
                if abs(dist - _SAFE_RADIUS) < _SAFE_RING_THICKNESS:
                    self._safe_ring_pixels.append((x, y))

    # ------------------------------------------------------------------
    # Satellite helpers
    # ------------------------------------------------------------------

    def _sat_encoder(self):
        """Return current satellite encoder position."""
        if not self.sat:
            return 0
        try:
            return self.sat.hid.encoder_positions[_ENC_SAT]
        except (IndexError, AttributeError):
            return 0

    def _sat_arm(self):
        """Return True when the guarded toggle (Stasis Arm) is engaged."""
        if not self.sat:
            return False
        try:
            return bool(self.sat.hid.latching_values[_SW_ARM])
        except (IndexError, AttributeError):
            return False

    def _sat_momentary_up(self):
        """Return True while the momentary toggle is held UP."""
        if not self.sat:
            return False
        try:
            return self.sat.hid.is_momentary_toggled(_MT_STASIS, direction="U")
        except (IndexError, AttributeError):
            return False

    def _send_segment(self, text):
        """Send text to the satellite 14-segment display (8-char max)."""
        if self.sat:
            try:
                self.sat.send("DSP", text[:8])
            except Exception:
                pass

    def _play_encoder_click(self):
        """Play a short tactile click tone for encoder input feedback (throttled)."""
        now = ticks_ms()
        if ticks_diff(now, getattr(self, '_last_click_ms', 0)) > 50:
            self.core.synth.play_note(880.0, "UI_SELECT", duration=0.01)
            self._last_click_ms = now

    def _update_segment_display(self):
        """Send Containment Integrity to the 14-segment display (throttled)."""
        integrity_int = int(self._integrity)
        if integrity_int == self._last_segment_integrity:
            return
        self._last_segment_integrity = integrity_int
        label = "STASIS" if self._stasis_active else f"INTG {integrity_int:3d}%"
        self._send_segment(label)

    # ------------------------------------------------------------------
    # Physics helpers
    # ------------------------------------------------------------------

    def _apply_damping(self):
        """Apply slight velocity damping each frame."""
        self._vel_x *= _DAMPING
        self._vel_y *= _DAMPING

    def _clamp_velocity(self):
        """Clamp velocity to maximum speed."""
        self._vel_x = max(-self._max_vel, min(self._max_vel, self._vel_x))
        self._vel_y = max(-self._max_vel, min(self._max_vel, self._vel_y))

    def _integrate_position(self):
        """Integrate position from velocity."""
        self._ball_x += self._vel_x
        self._ball_y += self._vel_y

    def _wall_bounce(self):
        """Bounce the plasma ball off the matrix walls."""
        # Left wall
        if self._ball_x < 0:
            self._ball_x = 0.0
            self._vel_x  = abs(self._vel_x) * _BOUNCE_DAMPING

        # Right wall
        if self._ball_x >= _MATRIX_W:
            self._ball_x = float(_MATRIX_W - 1)
            self._vel_x  = -abs(self._vel_x) * _BOUNCE_DAMPING

        # Top wall
        if self._ball_y < 0:
            self._ball_y = 0.0
            self._vel_y  = abs(self._vel_y) * _BOUNCE_DAMPING

        # Bottom wall
        if self._ball_y >= _MATRIX_H:
            self._ball_y = float(_MATRIX_H - 1)
            self._vel_y  = -abs(self._vel_y) * _BOUNCE_DAMPING

    def _distance_from_center(self):
        """Return the plasma ball's Euclidean distance from the matrix centre."""
        dx = self._ball_x - _CENTER_X
        dy = self._ball_y - _CENTER_Y
        return math.sqrt(dx * dx + dy * dy)

    def _chaos_kick(self):
        """Apply a random impulse to the plasma ball."""
        angle = random.uniform(0, 2 * math.pi)
        strength = random.uniform(
            self._chaos_strength * 0.5,
            self._chaos_strength
        )
        self._vel_x += math.cos(angle) * strength
        self._vel_y += math.sin(angle) * strength

    # ------------------------------------------------------------------
    # Integrity drain
    # ------------------------------------------------------------------

    def _update_integrity(self, delta_s):
        """Drain containment integrity based on plasma ball's distance from centre."""
        dist = self._distance_from_center()
        if dist <= _SAFE_RADIUS:
            return  # No drain inside the safe zone

        # Fraction of maximum edge distance (0 = safe edge, 1 = absolute corner)
        edge_fraction = min(1.0, (dist - _SAFE_RADIUS) / (_MAX_DRAIN_DIST - _SAFE_RADIUS))

        drain = self._drain_rate * edge_fraction * delta_s
        self._integrity = max(0.0, self._integrity - drain)

    # ------------------------------------------------------------------
    # Score update
    # ------------------------------------------------------------------

    def _update_score(self, delta_s):
        """Accumulate score based on survival and centre proximity."""
        self._score_accumulator += _SCORE_PER_SECOND * delta_s
        if self._distance_from_center() <= _SAFE_RADIUS:
            self._score_accumulator += _SCORE_CENTER_BONUS * delta_s
        earned = int(self._score_accumulator)
        if earned > 0:
            self.score += earned
            self._score_accumulator -= earned

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _render(self, frame_count):
        """Render the plasma ball and magnetic containment field on the matrix."""
        self.core.matrix.clear()

        # ---- Magnetic field lines (dim cyan cross) ----
        cx = int(round(_CENTER_X))
        cy = int(round(_CENTER_Y))
        for x in range(_MATRIX_W):
            self.core.matrix.draw_pixel(x, cy, Palette.CYAN, brightness=0.08)
        for y in range(_MATRIX_H):
            self.core.matrix.draw_pixel(cx, y, Palette.CYAN, brightness=0.08)

        # ---- Safe zone corners (dim blue) ----
        for px, py in self._safe_ring_pixels:
            self.core.matrix.draw_pixel(px, py, Palette.BLUE, brightness=0.12)

        # ---- Stasis field effect (blue pulse overlay when active) ----
        if self._stasis_active:
            for x in range(_MATRIX_W):
                self.core.matrix.draw_pixel(x, 0,  Palette.CYAN, brightness=0.5, anim_mode="PULSE", speed=4.0)
                self.core.matrix.draw_pixel(x, 15, Palette.CYAN, brightness=0.5, anim_mode="PULSE", speed=4.0)
            for y in range(1, _MATRIX_H - 1):
                self.core.matrix.draw_pixel(0,  y, Palette.CYAN, brightness=0.5, anim_mode="PULSE", speed=4.0)
                self.core.matrix.draw_pixel(15, y, Palette.CYAN, brightness=0.5, anim_mode="PULSE", speed=4.0)

        # ---- Plasma ball ----
        bx = int(round(self._ball_x))
        by = int(round(self._ball_y))
        bx = max(0, min(_MATRIX_W - 1, bx))
        by = max(0, min(_MATRIX_H - 1, by))

        # Colour shifts from green (safe) to red (danger) based on distance
        dist = self._distance_from_center()
        if dist <= _SAFE_RADIUS:
            ball_color = Palette.GREEN
        elif dist <= _SAFE_RADIUS * 1.8:
            ball_color = Palette.YELLOW
        elif dist <= _SAFE_RADIUS * 2.5:
            ball_color = Palette.ORANGE
        else:
            ball_color = Palette.RED

        if self._stasis_active:
            ball_color = Palette.CYAN

        self.core.matrix.draw_pixel(bx, by, ball_color, brightness=1.0, anim_mode="PULSE", speed=3.0)

        # Glow: draw dim neighbours
        for nx, ny in [(bx-1, by), (bx+1, by), (bx, by-1), (bx, by+1)]:
            if 0 <= nx < _MATRIX_W and 0 <= ny < _MATRIX_H:
                self.core.matrix.draw_pixel(nx, ny, ball_color, brightness=0.25)

        self.core.matrix.show_frame()

    # ------------------------------------------------------------------
    # Tutorial
    # ------------------------------------------------------------------

    async def run_tutorial(self):
        """
        Guided demonstration of Magnetic Containment.

        The Voiceover Script (audio/tutes/mag_tute.wav) ~ 32 seconds:
            [0:00] "Welcome to Magnetic Containment. Keep the plasma ball centered at all costs."
            [0:06] "The plasma ball will constantly drift and accelerate toward the edges."
            [0:12] "Use the base dial to control the X-axis magnetic force."
            [0:17] "Use the satellite dial to control the Y-axis magnetic force."
            [0:22] "If the plasma escapes the safe zone, Containment Integrity will drain."
            [0:27] "In an emergency, arm the guard and flick the switch to trigger Stasis."
            [0:32] (End of file)
        """
        await self.core.clean_slate()

        if not self.sat or not self.sat.is_active:
            self.core.display.update_status("MAG CONTAINMENT", "SAT OFFLINE - ABORT")
            await asyncio.sleep(2)
            return "TUTORIAL_FAILED"

        self.game_state = "TUTORIAL"

        self.core.audio.play(
            "audio/tutes/mag_tute.wav",
            bus_id=self.core.audio.CH_VOICE
        )

        # [0:00 - 0:06] Welcome
        self.core.display.update_status("MAG CONTAINMENT", "KEEP IT CENTRED")
        self.core.matrix.show_icon("MAGNETIC_CONTAINMENT", clear=True)
        self.core.buzzer.play_sequence(tones.POWER_UP)
        await asyncio.sleep(6.0)

        # [0:06 - 0:12] Drift demo: place ball near edge
        self._ball_x = 13.0
        self._ball_y = 8.0
        self._vel_x  = 0.2
        self._vel_y  = 0.0
        self._integrity = 100.0
        self._stasis_active = False
        self._send_segment("INTG 100%")
        self.core.display.update_status("PLASMA DRIFTING", "INTEGRITY DRAINING")
        for _ in range(40):
            self._wall_bounce()
            self._integrate_position()
            self._render(0)
            await asyncio.sleep(0.05)

        # [0:12 - 0:17] X-axis demo: pull ball back to center
        self.core.display.update_status("X-AXIS CONTROL", "BASE DIAL → X FORCE")
        self.core.leds.solid_led(0, Palette.CYAN)
        for _ in range(40):
            # Simulate encoder force toward center
            self._vel_x -= 0.05
            self._wall_bounce()
            self._apply_damping()
            self._integrate_position()
            self._render(0)
            await asyncio.sleep(0.05)
        self.core.leds.off_led(0)

        # [0:17 - 0:22] Y-axis demo
        self._ball_x = 8.0
        self._ball_y = 13.0
        self._vel_x  = 0.0
        self._vel_y  = 0.2
        self.core.display.update_status("Y-AXIS CONTROL", "SAT DIAL → Y FORCE")
        for _ in range(40):
            self._vel_y -= 0.06
            self._wall_bounce()
            self._apply_damping()
            self._integrate_position()
            self._render(0)
            await asyncio.sleep(0.05)

        # [0:22 - 0:27] Safe zone drain
        self._ball_x = 14.0
        self._ball_y = 14.0
        self._vel_x  = 0.0
        self._vel_y  = 0.0
        self._integrity = 60.0
        self.core.display.update_status("SAFE ZONE BREACH", "INTEGRITY DRAINING")
        for step in range(30):
            fake_drain = 1.0
            self._integrity = max(0.0, self._integrity - fake_drain)
            self._send_segment(f"INTG {int(self._integrity):3d}%")
            self._render(0)
            await asyncio.sleep(0.06)

        # [0:27 - 0:32] Stasis field demo
        self._stasis_active = True
        self._ball_x = _CENTER_X
        self._ball_y = _CENTER_Y
        self._vel_x  = 0.0
        self._vel_y  = 0.0
        self._integrity = 60.0
        self.core.display.update_status("STASIS FIELD!", "PLASMA FROZEN")
        self._send_segment("STASIS  ")
        for _ in range(40):
            self._render(0)
            await asyncio.sleep(0.05)
        self._stasis_active = False

        await self.core.clean_slate()
        return "TUTORIAL_COMPLETE"

    # ------------------------------------------------------------------
    # Main game loop
    # ------------------------------------------------------------------

    async def run(self):
        """Main Magnetic Containment game loop."""
        self.difficulty = self.core.data.get_setting(
            "MAGNETIC_CONTAINMENT", "difficulty", "NORMAL"
        )
        self.variant = self.difficulty

        params = _DIFF_PARAMS.get(self.difficulty, _DIFF_PARAMS["NORMAL"])
        self._chaos_strength = params["chaos_strength"]
        self._chaos_interval = params["chaos_interval"]
        self._drain_rate     = params["drain_rate"]
        self._max_vel        = params["max_velocity"]

        # Satellite check
        if not self.sat or not self.sat.is_active:
            self.core.display.update_status("MAG CONTAINMENT", "SAT OFFLINE - ABORT")
            await asyncio.sleep(2)
            return "FAILURE"

        # ---- Initialise game state ----
        self._ball_x = float(_CENTER_X)
        self._ball_y = float(_CENTER_Y)
        self._vel_x  = 0.0
        self._vel_y  = 0.0
        self._integrity = float(_MAX_INTEGRITY)
        self.score  = 0
        self._score_accumulator = 0.0

        self._chaos_timer      = self._chaos_interval
        self._stasis_armed     = False
        self._stasis_active    = False
        self._stasis_timer     = 0.0
        self._stasis_cooldown  = 0.0
        self._last_segment_integrity = -1

        # Reset encoders
        self.core.hid.reset_encoder(value=0, index=_ENC_CORE)
        self._last_core_enc = self.core.hid.encoder_positions[_ENC_CORE]
        if self.sat:
            try:
                self.sat.hid.reset_encoder(value=0, index=_ENC_SAT)
            except Exception:
                pass
        self._last_sat_enc = self._sat_encoder()

        # Intro animation
        self.core.display.use_standard_layout()
        self.core.display.update_status("MAG CONTAINMENT", "INITIALIZING...")
        self.core.matrix.show_icon("MAGNETIC_CONTAINMENT", clear=True)
        asyncio.create_task(
            self.core.synth.play_sequence(tones.POWER_UP, patch="SCANNER")
        )
        self._send_segment("INIT    ")
        await asyncio.sleep(2.0)

        # Brief countdown
        for count_val in [3, 2, 1]:
            self.core.display.update_status("MAG CONTAINMENT", f"STARTING IN {count_val}...")
            self._send_segment(f"READY {count_val} ")
            self.core.buzzer.play_sequence(tones.BEEP)
            await asyncio.sleep(0.7)

        self.core.display.update_status("CONTAINMENT ACTIVE", "KEEP IT CENTRED!")
        self._send_segment(f"INTG 100%")

        last_tick_ms  = ticks_ms()
        frame_count   = 0

        # ---- Main loop ----
        while True:
            now      = ticks_ms()
            delta_ms = ticks_diff(now, last_tick_ms)

            # Only advance physics at ~50 FPS (20 ms per tick)
            if delta_ms < 20:
                await asyncio.sleep(0.005)
                continue

            delta_s = delta_ms / 1000.0
            last_tick_ms = now
            frame_count += 1

            # ---- 1. Read encoders → apply magnetic force ----
            if not self._stasis_active:
                curr_core = self.core.hid.encoder_positions[_ENC_CORE]
                dx_enc    = curr_core - self._last_core_enc
                if dx_enc != 0:
                    force_x = max(-_MAX_FORCE, min(_MAX_FORCE, dx_enc * _FORCE_PER_TICK))
                    self._vel_x += force_x
                    self._last_core_enc = curr_core
                    self._play_encoder_click()

                curr_sat = self._sat_encoder()
                dy_enc   = curr_sat - self._last_sat_enc
                if dy_enc != 0:
                    force_y = max(-_MAX_FORCE, min(_MAX_FORCE, dy_enc * _FORCE_PER_TICK))
                    self._vel_y += force_y
                    self._last_sat_enc = curr_sat
                    self._play_encoder_click()

            # ---- 2. Chaos kick ----
            if not self._stasis_active:
                self._chaos_timer -= delta_s
                if self._chaos_timer <= 0:
                    self._chaos_kick()
                    self._chaos_timer = self._chaos_interval * random.uniform(0.7, 1.3)
                    asyncio.create_task(
                        self.core.synth.play_sequence(tones.DANGER, patch="ALARM")
                    )

            # ---- 3. Physics integration ----
            if not self._stasis_active:
                self._apply_damping()
                self._clamp_velocity()
                self._integrate_position()
                self._wall_bounce()

            # ---- 4. Stasis field management ----
            arm_now = self._sat_arm()
            mot_now = self._sat_momentary_up()

            # Edge detection for the momentary switch
            mot_rising = mot_now and not getattr(self, '_last_mot_state', False)
            self._last_mot_state = mot_now

            if self._stasis_active:
                self._stasis_timer -= delta_s
                if self._stasis_timer <= 0:
                    # Stasis expired
                    self._stasis_active   = False
                    self._stasis_cooldown = _STASIS_COOLDOWN
                    self._stasis_timer    = 0.0
                    asyncio.create_task(
                        self.core.synth.play_sequence(tones.POWER_FAIL, patch="ALARM")
                    )
            else:
                # Count down cooldown
                if self._stasis_cooldown > 0:
                    self._stasis_cooldown = max(0.0, self._stasis_cooldown - delta_s)

                # Trigger stasis: armed + momentary up, no cooldown
                if arm_now and mot_rising and self._stasis_cooldown <= 0:
                    self._stasis_active = True
                    self._stasis_timer  = _STASIS_DURATION
                    asyncio.create_task(
                        self.core.synth.play_sequence(tones.CHARGING, patch="SCANNER")
                    )

            self._stasis_armed = arm_now

            # ---- 5. Integrity drain ----
            if not self._stasis_active:
                self._update_integrity(delta_s)

            # ---- 6. Score ----
            self._update_score(delta_s)

            # ---- 7. Integrity-based alarm tone (dim buzzer at low integrity) ----
            if self._integrity < 30 and frame_count % 25 == 0:
                self.core.buzzer.play_sequence(tones.ALARM)

            # ---- 8. OLED status ----
            if frame_count % 5 == 0:
                cd_str = ""
                if self._stasis_cooldown > 0:
                    cd_str = f" CD:{self._stasis_cooldown:.0f}s"
                if self._stasis_active:
                    status = f"STASIS {self._stasis_timer:.1f}s"
                elif arm_now:
                    cd_note = " READY" if self._stasis_cooldown <= 0 else cd_str
                    status = f"ARMED{cd_note}"
                else:
                    status = f"INTG:{int(self._integrity)}% SCR:{self.score}"
                self.core.display.update_status("MAG CONTAINMENT", status)

            # ---- 9. Segment display ----
            self._update_segment_display()

            # ---- 10. Render matrix ----
            self._render(frame_count)

            # ---- 11. Game over check ----
            if self._integrity <= 0:
                break

        # ---- Game Over ----
        self._send_segment("ESCAPED ")
        asyncio.create_task(
            self.core.synth.play_sequence(tones.GAME_OVER, patch="ALARM")
        )
        return await self.game_over()
