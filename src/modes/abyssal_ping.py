# File: src/modes/abyssal_ping.py
"""Abyssal Ping – Audio-Driven Submarine Hunt Game Mode.

The player hunts a rogue submarine almost entirely by ear using two rotary
encoders to isolate the target's acoustic signature, then configures a depth
charge payload and fires before the sub slips away.

Hardware mapping
----------------
Core:
    - 16x16 Matrix: pitch-black sweep line (cosmetic), single red pixel on lock
    - OLED: encrypted acoustic telemetry, payload requirements, mission timer
    - Rotary Encoder: tunes Sonar Frequency (Y-axis target matching)

Industrial Satellite (SAT-01):
    - Rotary Encoder (index 0): pans Hydrophone Azimuth (X-axis target matching)
    - 14-Segment Display: current signal strength
    - 8x Latching Toggles (0-7): Depth & Yield binary configuration
    - Guarded Toggle (index 8): Master Arm
    - Giant Red Button (index 0): Fire Depth Charge

Gameplay phases
---------------
1. HUNT    – match both encoders to the hidden (target_freq, target_azimuth)
2. PAYLOAD – match 8 latching toggles to the displayed binary yield pattern
3. EXECUTE – arm the guarded toggle, then press the big red button
"""

import asyncio
import random

from adafruit_ticks import ticks_ms, ticks_diff

from utilities.palette import Palette
from utilities.synth_registry import Patches

from .game_mode import GameMode

# ---------------------------------------------------------------------------
# Hardware indices (mirror sat_01_driver layout)
# ---------------------------------------------------------------------------
_TOGGLE_COUNT   = 8      # Small latching toggles (indices 0-7)
_SW_ARM         = 8      # Guarded toggle / Master Arm
_BTN_FIRE       = 0      # Giant red button
_ENC_SAT        = 0      # Satellite encoder index → Azimuth (X-axis)
_ENC_CORE       = 0      # Core encoder index → Frequency (Y-axis)

# ---------------------------------------------------------------------------
# Timing constants (seconds)
# ---------------------------------------------------------------------------
_GLOBAL_TIME    = 120.0   # 2-minute global game timer
_BONUS_TIME     = 10.0    # Bonus seconds per successful depth charge
_LOCK_FLASH_MS  = 33      # Duration of red-pixel lock flash (~1 frame at 30 fps)

# ---------------------------------------------------------------------------
# Proximity model
# ---------------------------------------------------------------------------
_MAX_DELTA              = 20.0   # Encoder delta beyond which proximity = 0
_LOCK_THRESHOLD_NORMAL  = 0.90   # Both axes must exceed this to achieve lock
_LOCK_THRESHOLD_HARD    = 0.95   # Stricter threshold for HARD / INSANE

# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------
_BASE_SCORE     = 500
_SPEED_BONUS    = 200

# ---------------------------------------------------------------------------
# Difficulty tuning table
# ---------------------------------------------------------------------------
_DIFF_PARAMS = {
    "NORMAL": {"drift": False, "lock_threshold": _LOCK_THRESHOLD_NORMAL},
    "HARD":   {"drift": True,  "lock_threshold": _LOCK_THRESHOLD_HARD},
    "INSANE": {"drift": True,  "lock_threshold": _LOCK_THRESHOLD_HARD},
}

# Phase identifiers
_PHASE_HUNT    = "HUNT"
_PHASE_PAYLOAD = "PAYLOAD"
_PHASE_EXECUTE = "EXECUTE"


class AbyssalPing(GameMode):
    """Abyssal Ping – hunt a rogue submarine by ear.

    Gameplay
    --------
    Phase 1 – HUNT:
        A submarine hides at (target_freq, target_azimuth).  The player
        turns the Core Encoder to sweep a sonar frequency; a secondary sine
        pitch tracks the encoder position.  Turning the Satellite Encoder
        pans the hydrophone; random static fades as azimuth converges.
        Perfect alignment triggers a sharp SONAR_PING and a one-frame red
        pixel flash on the matrix.

    Phase 2 – PAYLOAD:
        The OLED displays the target's depth-hull signature as an 8-bit
        binary string.  The player scrambles to match the 8 satellite
        latching toggles to that pattern.

    Phase 3 – EXECUTE:
        Flip the guarded Master Arm toggle UP, then press the big red
        button.  If the payload is still correct the depth charge detonates
        (explosion sound + white matrix flash).  If the toggles have shifted,
        a dull splash plays and the sub warps to a new location.

    Difficulty
    ----------
    HARD / INSANE: the submarine slowly drifts, requiring constant
    encoder adjustment.  The lock threshold is also tightened.
    """

    # Frequency-axis encoder sweep parameters
    FREQ_MIN  = 50.0
    FREQ_MAX  = 150.0
    FREQ_STEP = 0.5          # Hz per encoder detent

    # Azimuth-axis encoder sweep parameters
    AZ_MIN    = 0.0
    AZ_MAX    = 100.0
    AZ_STEP   = 0.5          # Units per encoder detent

    # Submarine drift speed (units per second, HARD / INSANE only)
    DRIFT_SPEED = 0.2

    def __init__(self, core):
        super().__init__(core, "ABYSSAL PING", "Submarine Acoustic Hunt")

        # Find the first Industrial satellite
        self.sat = None
        for sat in self.core.satellites.values():
            if sat.sat_type_name == "INDUSTRIAL":
                self.sat = sat
                break

        # Hunt-phase state
        self._player_freq    = 100.0
        self._player_az      = 50.0
        self._target_freq    = 100.0
        self._target_az      = 50.0
        self._drift_freq     = 0.0
        self._drift_az       = 0.0
        self._running        = False
        self._drift_enabled  = False
        self._lock_threshold = _LOCK_THRESHOLD_NORMAL

        # Payload state
        self._yield_pattern  = []   # 8 booleans (required toggle states)

        # Global timer state
        self._time_remaining     = _GLOBAL_TIME
        self._last_tick_ms       = 0
        self._depth_charges_fired = 0

    # ------------------------------------------------------------------
    # Satellite helpers
    # ------------------------------------------------------------------

    def _sat_latching(self, idx):
        """Return the state of a satellite latching toggle (safe fallback)."""
        if not self.sat:
            return False
        try:
            return bool(self.sat.hid.latching_values[idx])
        except (IndexError, AttributeError):
            return False

    def _sat_button(self, idx=_BTN_FIRE):
        """Return True if the satellite big button at *idx* is pressed."""
        if not self.sat:
            return False
        try:
            return bool(self.sat.hid.buttons_values[idx])
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

    def _send_segment(self, text):
        """Send a string to the satellite 14-segment display.

        Caches the last value sent so the UART bus is only written when
        the displayed text actually changes.
        """
        if not hasattr(self, "_last_segment_text"):
            self._last_segment_text = ""

        safe_text = text[:8]
        if self.sat and self._last_segment_text != safe_text:
            self.sat.send("DSP", safe_text)
            self._last_segment_text = safe_text

    # ------------------------------------------------------------------
    # Matrix rendering
    # ------------------------------------------------------------------

    def _render_sweep(self, sweep_col):
        """Draw a dim green sweep line at *sweep_col*; rest of the matrix black."""
        self.core.matrix.fill(Palette.OFF, show=False)
        h = self.core.matrix.height
        for y in range(h):
            self.core.matrix.draw_pixel(sweep_col, y, Palette.GREEN, brightness=0.1, show=False)

    def _render_lock_flash(self):
        """Flash a single red pixel at the matrix centre for acoustic lock."""
        self.core.matrix.fill(Palette.OFF, show=False)
        cx = self.core.matrix.width  // 2
        cy = self.core.matrix.height // 2
        self.core.matrix.draw_pixel(cx, cy, Palette.RED, brightness=1.0, show=False)

    def _render_explosion(self):
        """Fill the matrix white to indicate depth-charge detonation."""
        self.core.matrix.fill(Palette.WHITE)

    # ------------------------------------------------------------------
    # Hunt phase audio (background task)
    # ------------------------------------------------------------------

    async def _ocean_audio_loop(self):
        """Background audio task for the Hunt phase.

        - Continuous low ocean drone (ENGINE_HUM).
        - Secondary sine pitch tracks the Core Encoder position (player_freq).
        - Sporadic noise bursts decrease as azimuth converges on the target.
        """
        # Start the background drone – holds open until we release it
        drone_note = self.core.synth.play_note(55.0, Patches.ENGINE_HUM)
        try:
            while self._running:
                # --- Secondary sine: pitch tracks player frequency ---
                # Map player_freq (FREQ_MIN…FREQ_MAX) → audible range (200…800 Hz)
                freq_range = self.FREQ_MAX - self.FREQ_MIN
                scan_pitch = 200.0 + (
                    (self._player_freq - self.FREQ_MIN) / freq_range
                ) * 600.0
                self.core.synth.play_note(scan_pitch, Patches.SONAR, duration=0.15)

                # --- Noise: volume decreases as azimuth converges ---
                az_delta = abs(self._player_az - self._target_az)
                az_prox  = max(0.0, 1.0 - (az_delta / _MAX_DELTA))

                if az_prox < 0.9:
                    # Play noise with probability proportional to distance
                    noise_prob = 1.0 - az_prox
                    if random.random() < noise_prob:
                        self.core.synth.play_note(400.0, Patches.get_noise_patch(), duration=0.05)

                await asyncio.sleep(0.2)

        except asyncio.CancelledError:
            self.core.synth.stop_note(drone_note)
            self.core.synth.release_all()
            raise

    # ------------------------------------------------------------------
    # Phase 1: Hunt
    # ------------------------------------------------------------------

    async def _run_phase_hunt(self):
        """Phase 1 – align both encoders to achieve acoustic lock.

        Returns 'LOCKED' when combined proximity >= lock_threshold,
        or 'TIMEOUT' when the global timer runs out.
        """
        # Reset encoder baselines
        self.core.hid.reset_encoder(value=0, index=_ENC_CORE)
        if self.sat:
            try:
                self.sat.hid.reset_encoder(value=0, index=_ENC_SAT)
            except Exception:
                pass

        last_core_enc = self.core.hid.encoder_positions[_ENC_CORE]
        last_sat_enc  = self._sat_encoder()

        # Start both axes at the midpoint so the player always has room to go
        self._player_freq = (self.FREQ_MIN + self.FREQ_MAX) / 2.0
        self._player_az   = (self.AZ_MIN   + self.AZ_MAX)   / 2.0
        self._running     = True

        audio_task = asyncio.create_task(self._ocean_audio_loop())
        sweep_col  = 0
        sweep_tick = 0
        result     = "TIMEOUT"

        try:
            while True:
                # --- Global timer tick ---
                now        = ticks_ms()
                elapsed_ms = ticks_diff(now, self._last_tick_ms)
                if elapsed_ms >= 100:
                    self._time_remaining -= elapsed_ms / 1000.0
                    self._last_tick_ms    = now

                if self._time_remaining <= 0:
                    break

                # --- Core encoder → Frequency ---
                curr_core   = self.core.hid.encoder_positions[_ENC_CORE]
                delta_core  = curr_core - last_core_enc
                if delta_core != 0:
                    self._player_freq += delta_core * self.FREQ_STEP
                    self._player_freq  = max(self.FREQ_MIN,
                                             min(self.FREQ_MAX, self._player_freq))
                    last_core_enc = curr_core

                # --- Satellite encoder → Azimuth ---
                curr_sat  = self._sat_encoder()
                delta_sat = curr_sat - last_sat_enc
                if delta_sat != 0:
                    self._player_az += delta_sat * self.AZ_STEP
                    self._player_az  = max(self.AZ_MIN,
                                           min(self.AZ_MAX, self._player_az))
                    last_sat_enc = curr_sat

                # --- Submarine drift (HARD / INSANE) ---
                if self._drift_enabled:
                    self._target_freq += self._drift_freq * 0.04
                    self._target_az   += self._drift_az   * 0.04

                    # Bounce at soft boundaries
                    if self._target_freq >= self.FREQ_MAX - 5.0:
                        self._target_freq = self.FREQ_MAX - 5.0
                        self._drift_freq  = -abs(self._drift_freq)
                    elif self._target_freq <= self.FREQ_MIN + 5.0:
                        self._target_freq = self.FREQ_MIN + 5.0
                        self._drift_freq  =  abs(self._drift_freq)

                    if self._target_az >= self.AZ_MAX - 5.0:
                        self._target_az = self.AZ_MAX - 5.0
                        self._drift_az  = -abs(self._drift_az)
                    elif self._target_az <= self.AZ_MIN + 5.0:
                        self._target_az = self.AZ_MIN + 5.0
                        self._drift_az  =  abs(self._drift_az)

                # --- Proximity calculation ---
                freq_delta     = abs(self._player_freq - self._target_freq)
                az_delta       = abs(self._player_az   - self._target_az)
                freq_prox      = max(0.0, 1.0 - (freq_delta / _MAX_DELTA))
                az_prox        = max(0.0, 1.0 - (az_delta   / _MAX_DELTA))
                combined_prox  = freq_prox * az_prox

                # --- OLED telemetry ---
                sig_bars = int(combined_prox * 8)
                self.core.display.update_header(
                    f"SONAR  T:{self._time_remaining:.0f}s"
                )
                self.core.display.update_status(
                    f"F:{self._player_freq:.1f} AZ:{self._player_az:.1f}",
                    f"SIG: {'|' * sig_bars}{'-' * (8 - sig_bars)}"
                )

                # --- 14-segment: signal strength percentage ---
                strength_pct = int(combined_prox * 100)
                self._send_segment(f"SIG {strength_pct:3d}%")

                # --- Matrix: dim green sweep line (cosmetic only) ---
                sweep_tick += 1
                if sweep_tick >= 2:
                    sweep_tick = 0
                    sweep_col  = (sweep_col + 1) % self.core.matrix.width
                self._render_sweep(sweep_col)

                # --- Lock check ---
                if combined_prox >= self._lock_threshold:
                    result = "LOCKED"
                    break

                await asyncio.sleep(0.04)

        finally:
            self._running = False
            audio_task.cancel()
            try:
                await audio_task
            except asyncio.CancelledError:
                pass

        if result == "LOCKED":
            # Acoustic lock achieved: sharp ping + one-frame red pixel flash
            self.core.synth.play_note(1760.0, Patches.SONAR, duration=0.4)
            self._render_lock_flash()
            await asyncio.sleep(_LOCK_FLASH_MS / 1000.0)
            self.core.matrix.clear()

        return result

    # ------------------------------------------------------------------
    # Phase 2: Payload configuration
    # ------------------------------------------------------------------

    async def _run_phase_payload(self):
        """Phase 2 – match 8 latching toggles to the displayed yield pattern.

        Returns True when all 8 toggles match; False on global timeout.
        """
        pat_str = "".join(["1" if b else "0" for b in self._yield_pattern])
        self.core.display.update_status("DEPTH CHARGE CFG", f"YIELD: {pat_str}")
        self._send_segment("YIELD   ")

        last_led_states = [None] * _TOGGLE_COUNT

        while True:
            # --- Global timer tick ---
            now        = ticks_ms()
            elapsed_ms = ticks_diff(now, self._last_tick_ms)
            if elapsed_ms >= 100:
                self._time_remaining -= elapsed_ms / 1000.0
                self._last_tick_ms    = now

            if self._time_remaining <= 0:
                return False

            all_match = True
            for i in range(_TOGGLE_COUNT):
                state    = self._sat_latching(i)
                expected = self._yield_pattern[i]
                if state == expected:
                    if last_led_states[i] != "GREEN":
                        if self.sat:
                            try:
                                self.sat.send("LED", f"{i},{Palette.GREEN.index},0.0,1.0,2")
                            except Exception:
                                pass
                        last_led_states[i] = "GREEN"
                else:
                    all_match = False
                    if last_led_states[i] != "ORANGE":
                        if self.sat:
                            try:
                                self.sat.send("LED", f"{i},{Palette.ORANGE.index},0.0,1.0,2")
                            except Exception:
                                pass
                        last_led_states[i] = "ORANGE"

            cur_str = "".join(["1" if self._sat_latching(i) else "0"
                                for i in range(_TOGGLE_COUNT)])
            self.core.display.update_status(
                f"YIELD: {pat_str}",
                f"HAVE:  {cur_str}"
            )
            self._send_segment(f"Y{pat_str}")

            if all_match:
                self.core.synth.play_note(1000.0, Patches.SUCCESS, duration=0.1)
                return True

            await asyncio.sleep(0.08)

    # ------------------------------------------------------------------
    # Phase 3: Execute
    # ------------------------------------------------------------------

    async def _run_phase_execute(self):
        """Phase 3 – arm the guarded toggle and press the big red button.

        Returns True when Master Arm is UP and button is pressed.
        Returns False on global timeout.
        """
        self.core.display.update_status("ARM + FIRE", "TOGGLE ARM, PRESS BTN")
        self._send_segment("FIRE    ")

        while True:
            # --- Global timer tick ---
            now        = ticks_ms()
            elapsed_ms = ticks_diff(now, self._last_tick_ms)
            if elapsed_ms >= 100:
                self._time_remaining -= elapsed_ms / 1000.0
                self._last_tick_ms    = now

            if self._time_remaining <= 0:
                return False

            arm_engaged = self._sat_latching(_SW_ARM)
            btn_pressed = self._sat_button(_BTN_FIRE)

            arm_str = "ARM:ON " if arm_engaged else "ARM:OFF"
            btn_str = "BTN:ON"  if btn_pressed  else "BTN:OFF"
            self.core.display.update_status(
                "ARM + FIRE",
                f"{arm_str} | {btn_str}"
            )
            self._send_segment("ARMED   " if arm_engaged else "SAFE    ")

            if arm_engaged and btn_pressed:
                return True

            await asyncio.sleep(0.05)

    # ------------------------------------------------------------------
    # Submarine spawning
    # ------------------------------------------------------------------

    def _spawn_submarine(self):
        """Spawn a submarine at a fresh random (target_freq, target_azimuth)
        and generate a random 8-bit yield pattern for the depth charge."""
        margin = 10.0
        self._target_freq = round(
            random.uniform(self.FREQ_MIN + margin, self.FREQ_MAX - margin), 2
        )
        self._target_az = round(
            random.uniform(self.AZ_MIN + margin, self.AZ_MAX - margin), 2
        )
        # Random 8-bit depth-charge yield requirement
        self._yield_pattern = [random.choice([True, False])
                                for _ in range(_TOGGLE_COUNT)]

        # Assign drift for HARD / INSANE difficulties
        if self._drift_enabled:
            self._drift_freq = random.uniform(-self.DRIFT_SPEED, self.DRIFT_SPEED)
            self._drift_az   = random.uniform(-self.DRIFT_SPEED, self.DRIFT_SPEED)
            # Ensure non-zero drift so the target always moves
            if abs(self._drift_freq) < 0.05:
                self._drift_freq = 0.1
            if abs(self._drift_az) < 0.05:
                self._drift_az = 0.1
        else:
            self._drift_freq = 0.0
            self._drift_az   = 0.0

    # ------------------------------------------------------------------
    # Main game loop
    # ------------------------------------------------------------------

    async def run(self):
        """Main Abyssal Ping game loop."""
        self.difficulty = self.core.data.get_setting(
            "ABYSSAL_PING", "difficulty", "NORMAL"
        )
        self.variant = self.difficulty

        params = _DIFF_PARAMS.get(self.difficulty, _DIFF_PARAMS["NORMAL"])
        self._drift_enabled  = params["drift"]
        self._lock_threshold = params["lock_threshold"]

        # Satellite sanity check
        if not self.sat or not self.sat.is_active:
            self.core.display.update_status("ABYSSAL PING", "SAT OFFLINE - ABORT")
            await asyncio.sleep(2)
            return "FAILURE"

        # Intro splash
        self.core.display.use_standard_layout()
        self.core.display.update_status("ABYSSAL PING", "SONAR SYSTEMS ONLINE")
        self.core.matrix.show_icon("ABYSSAL_PING", clear=True)
        self.core.synth.play_note(110.0, Patches.ENGINE_HUM, duration=2.0)
        await asyncio.sleep(2.0)

        # Reset both encoders to a known zero position
        self.core.hid.reset_encoder(value=0, index=_ENC_CORE)
        if self.sat:
            try:
                self.sat.hid.reset_encoder(value=0, index=_ENC_SAT)
            except Exception:
                pass

        self._time_remaining      = _GLOBAL_TIME
        self._last_tick_ms        = ticks_ms()
        self._depth_charges_fired = 0
        self.score                = 0

        while self._time_remaining > 0:
            # Spawn (or re-spawn) the submarine
            self._spawn_submarine()

            # ---- Phase 1: Hunt ----------------------------------------
            hunt_result = await self._run_phase_hunt()
            if hunt_result != "LOCKED":
                break  # Global timer expired

            # ---- Phase 2: Payload config --------------------------------
            payload_ok = await self._run_phase_payload()
            if not payload_ok:
                break  # Global timer expired

            # ---- Phase 3: Execute --------------------------------------
            execute_ok = await self._run_phase_execute()
            if not execute_ok:
                break  # Global timer expired

            # ---- Detonation judgement ----------------------------------
            # Validate the payload is still correct at the moment of firing
            pattern_valid = all(
                self._sat_latching(i) == self._yield_pattern[i]
                for i in range(_TOGGLE_COUNT)
            )

            if pattern_valid:
                # Direct hit – submarine destroyed
                self._depth_charges_fired += 1
                self.score += _BASE_SCORE

                self._render_explosion()
                self.core.synth.play_note(80.0,  Patches.PUNCH, duration=0.5)
                await asyncio.sleep(0.1)
                self.core.synth.play_note(55.0,  Patches.ALARM, duration=0.3)
                self.core.display.update_status(
                    "DEPTH CHARGE HIT!",
                    f"KILLS: {self._depth_charges_fired}"
                )
                self._send_segment("BOOM    ")
                self._time_remaining = min(
                    _GLOBAL_TIME, self._time_remaining + _BONUS_TIME
                )
                await asyncio.sleep(1.0)
                self.core.matrix.clear()
            else:
                # Toggles changed after aiming – dull splash, sub warps away
                self.core.synth.play_note(220.0, Patches.get_noise_patch(), duration=0.3)
                self.core.display.update_status("SPLASH!", "SUB SPOOKED – WARPING")
                self._send_segment("SPLASH  ")
                await asyncio.sleep(1.0)

            # Brief inter-round display
            self.core.display.update_status(
                f"KILLS: {self._depth_charges_fired}",
                f"T:{self._time_remaining:.0f}s  SC:{self.score}"
            )
            await asyncio.sleep(0.8)

        # Time's up
        self._send_segment("T-O END ")
        return await self.game_over()
