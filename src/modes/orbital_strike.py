# File: src/modes/orbital_strike.py
"""Orbital Strike - Tactical Fire Control Game Mode.

The player is a weapons officer processing rapid-fire artillery requests.
Uses the full Industrial Satellite hardware loadout:
    - Numeric keypad + satellite 14-segment display for target grid entry
    - 8x latching toggles for payload configuration
    - Core encoder (X-axis) + satellite encoder (Y-axis) for fine targeting
    - Guarded toggle (Master Arm) + big button to execute the strike

Gameplay phases per Fire Mission:
    1. TARGET GRID    – enter a numeric code on the keypad
    2. PAYLOAD CONFIG – match 8 toggle states to a random pattern
    3. FINE TARGETING – move crosshair onto a red dot with dual encoders
    4. EXECUTE        – arm the guarded toggle and press the big button
    5. RESET          – return toggles/guarded arm to safe before next mission
"""

import asyncio
import random

from adafruit_ticks import ticks_ms, ticks_diff

from utilities.palette import Palette
from utilities import tones

from .game_mode import GameMode

# ---------------------------------------------------------------------------
# Hardware indices (mirror sat_01_driver layout)
# ---------------------------------------------------------------------------
_TOGGLE_COUNT   = 8      # Small latching toggles (indices 0-7)
_SW_ARM         = 8      # Guarded toggle / Master Arm
_BTN_EXECUTE    = 0      # Large momentary button
_ENC_SAT        = 0      # Satellite rotary encoder index
_ENC_CORE       = 0      # Core rotary encoder index

# ---------------------------------------------------------------------------
# Timing constants (seconds)
# ---------------------------------------------------------------------------
_GLOBAL_TIME        = 120.0   # 2-minute global timer
_BONUS_TIME         = 5.0     # Bonus seconds per completed mission
_PANNING_DURATION   = 0.8     # Matrix pan animation after grid entry
_LOCK_THRESHOLD     = 1       # Crosshair must be within this many cells

# ---------------------------------------------------------------------------
# Difficulty tuning tables
# ---------------------------------------------------------------------------
_DIFF_PARAMS = {
    "NORMAL": {"code_len": 4, "drift": False},
    "HARD":   {"code_len": 6, "drift": True},
    "INSANE": {"code_len": 8, "drift": True},
}

# Phase identifiers
_PHASE_GRID     = "GRID"
_PHASE_PAYLOAD  = "PAYLOAD"
_PHASE_TARGET   = "TARGET"
_PHASE_EXECUTE  = "EXECUTE"
_PHASE_RESET    = "RESET"

# Payload configuration names for UI flavour
_PAYLOAD_NAMES = [
    ["SABOT", "HE", "EMP", "FRAG", "THERM", "AP", "AERO", "WP"],
    ["ILLUM", "SMK", "GAS", "INCND", "ICM", "LAZE", "SASER", "BUZZ"],
]


class OrbitalStrike(GameMode):
    """Orbital Strike – Tactical Fire Control game mode.

    Hardware:
        Core:
            - 16x16 Matrix: targeting reticle, crosshair, target dot
            - OLED: mission state and instructions
            - Rotary Encoder: X-axis crosshair panning

        Industrial Satellite (SAT-01):
            - 14-Segment Display: target grid input echo
            - Numeric Keypad: grid code entry
            - 8x Latching Toggles: payload configuration
            - Guarded Toggle (index 8): Master Arm
            - Large Button (index 0): Execute strike
            - Rotary Encoder (index 0): Y-axis crosshair panning
    """

    METADATA = {
        "id": "ORBITAL_STRIKE",
        "name": "ORBITAL STRIKE",
        "icon": "ORBITAL_STRIKE",
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
        super().__init__(core, "ORBITAL STRIKE", "Tactical Fire Control")
        self.sat = None
        for sat in self.core.satellites.values():
            if sat.sat_type_name == "INDUSTRIAL":
                self.sat = sat
                break

        self._phase = _PHASE_GRID
        self._mission_count = 0
        self._time_remaining = _GLOBAL_TIME
        self._last_tick_ms = 0

        # Phase-specific state
        self._grid_code = ""          # Required keypad code this mission
        self._grid_entered = ""       # What the player has typed so far
        self._last_keypad_snapshot = ""

        self._payload_pattern = []    # Required toggle states (list of bool)
        self._payload_names = []      # Descriptive names for OLED

        self._target_x = 0           # Red dot position on matrix
        self._target_y = 0
        self._crosshair_x = 0        # Crosshair position
        self._crosshair_y = 0
        self._last_core_enc = 0
        self._last_sat_enc = 0

        self._drift_dx = 0           # Per-tick drift for HARD/INSANE target
        self._drift_dy = 0

        self._code_len = 4
        self._drift_enabled = False

    # ------------------------------------------------------------------
    # Satellite helpers
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
            return self.sat.hid.encoder_positions[_ENC_SAT]
        except (IndexError, AttributeError):
            return 0

    def _send_segment(self, text):
        """Send text string to the satellite 14-segment display."""
        if self.sat:
            self.sat.send("DSP", text[:8])

    def _set_sat_led(self, idx, color_idx, anim="SOLID", speed=1.0):
        """Set a satellite NeoPixel LED."""
        if self.sat:
            self.sat.send("LED", f"{idx},{color_idx},0.0,1.0,2")

    # ------------------------------------------------------------------
    # Matrix rendering
    # ------------------------------------------------------------------

    def _render_targeting(self):
        """Draw the targeting reticle, crosshair and target dot."""
        self.core.matrix.clear()

        w = self.core.matrix.width
        h = self.core.matrix.height
        cx = self._crosshair_x
        cy = self._crosshair_y

        # Draw crosshair arms (green), leave 2-cell hollow centre
        gap = 2
        for x in range(w):
            if abs(x - cx) > gap:
                self.core.matrix.draw_pixel(x, cy, Palette.GREEN, brightness=0.6)
        for y in range(h):
            if abs(y - cy) > gap:
                self.core.matrix.draw_pixel(cx, y, Palette.GREEN, brightness=0.6)

        # Draw red target dot
        self.core.matrix.draw_pixel(
            self._target_x, self._target_y,
            Palette.RED,
            brightness=1.0,
            anim_mode="BLINK",
            speed=2.0
        )

    def _render_locked(self):
        """Draw the 'solution locked' frame: cyan crosshair, red pulse border."""
        self.core.matrix.clear()
        w = self.core.matrix.width
        h = self.core.matrix.height

        # Border pulse (red)
        for x in range(w):
            self.core.matrix.draw_pixel(x, 0, Palette.RED, brightness=1.0, anim_mode="PULSE", speed=3.0)
            self.core.matrix.draw_pixel(x, h - 1, Palette.RED, brightness=1.0, anim_mode="PULSE", speed=3.0)
        for y in range(1, h - 1):
            self.core.matrix.draw_pixel(0, y, Palette.RED, brightness=1.0, anim_mode="PULSE", speed=3.0)
            self.core.matrix.draw_pixel(w - 1, y, Palette.RED, brightness=1.0, anim_mode="PULSE", speed=3.0)

        # Crosshair (cyan)
        cx, cy = self._crosshair_x, self._crosshair_y
        gap = 2
        for x in range(w):
            if abs(x - cx) > gap:
                self.core.matrix.draw_pixel(x, cy, Palette.CYAN, brightness=1.0)
        for y in range(h):
            if abs(y - cy) > gap:
                self.core.matrix.draw_pixel(cx, y, Palette.CYAN, brightness=1.0)

    async def _animate_panning(self):
        """Quick panning animation on the matrix to simulate terrain slew."""
        w = self.core.matrix.width
        h = self.core.matrix.height
        steps = 8
        for step in range(steps):
            self.core.matrix.clear()
            frac = step / steps
            # Draw a sweeping green line that scrolls across
            line_x = int(frac * w)
            for y in range(h):
                self.core.matrix.draw_pixel(line_x, y, Palette.GREEN, brightness=0.4)
            await asyncio.sleep(_PANNING_DURATION / steps)
        self.core.matrix.clear()

    async def _animate_explosion(self):
        """Expanding explosion rings on the matrix at the target location."""
        tx, ty = self._target_x, self._target_y
        w = self.core.matrix.width
        h = self.core.matrix.height
        max_radius = max(w, h)

        for radius in range(1, max_radius):
            self.core.matrix.clear()
            for dx in range(-radius, radius + 1):
                for dy in range(-radius, radius + 1):
                    dist = (dx * dx + dy * dy) ** 0.5
                    if abs(dist - radius) < 1.5:
                        px = tx + dx
                        py = ty + dy
                        if 0 <= px < w and 0 <= py < h:
                            # Gradient: orange -> red -> dim
                            if radius < max_radius // 3:
                                color = Palette.ORANGE
                            elif radius < 2 * max_radius // 3:
                                color = Palette.RED
                            else:
                                color = (40, 0, 0)
                            self.core.matrix.draw_pixel(px, py, color, brightness=1.0)
            await asyncio.sleep(0.04)
        self.core.matrix.clear()

    # ------------------------------------------------------------------
    # Mission generation
    # ------------------------------------------------------------------

    def _new_mission(self):
        """Generate a fresh fire mission."""
        # Grid code
        self._grid_code = "".join([str(random.randint(0, 9)) for _ in range(self._code_len)])
        self._grid_entered = ""
        self._last_keypad_snapshot = ""

        # Payload pattern (random ON/OFF for 8 toggles)
        self._payload_pattern = [random.choice([True, False]) for _ in range(_TOGGLE_COUNT)]
        name_set = random.choice(_PAYLOAD_NAMES)
        self._payload_names = [name_set[i] for i in range(_TOGGLE_COUNT) if self._payload_pattern[i]]

        # Target position (avoid edges and crosshair start)
        margin = 2
        w = self.core.matrix.width
        h = self.core.matrix.height
        self._target_x = random.randint(margin, w - 1 - margin)
        self._target_y = random.randint(margin, h - 1 - margin)

        # Target drift for harder difficulties
        if self._drift_enabled:
            self._drift_dx = random.choice([-1, 0, 1])
            self._drift_dy = random.choice([-1, 0, 1])
        else:
            self._drift_dx = 0
            self._drift_dy = 0

    # ------------------------------------------------------------------
    # Phase: Target Grid
    # ------------------------------------------------------------------

    async def _run_phase_grid(self):
        """Phase 1 – Player types the grid code on the satellite keypad."""
        self.core.display.update_status(
            f"MISSION RECV #{self._mission_count + 1}",
            f"GRID: {self._grid_code}"
        )
        self._send_segment("        ")
        asyncio.create_task(
            self.core.synth.play_sequence(tones.BEEP, patch="BEEP")
        )
        self.core.matrix.show_icon("ORBITAL_STRIKE", clear=True)
        self._last_keypad_snapshot = ""

        while True:
            # Read keypad from satellite
            if self.sat:
                try:
                    keypads = self.sat.hid.keypad_values
                    if keypads:
                        current = "".join(
                            str(k) for k in keypads[0] if k is not None and str(k).isdigit()
                        )
                    else:
                        current = ""
                except (IndexError, AttributeError):
                    current = ""
            else:
                current = ""

            # Detect new keypresses
            if len(current) > len(self._last_keypad_snapshot):
                new_chars = current[len(self._last_keypad_snapshot):]
                self._grid_entered += new_chars
                self._last_keypad_snapshot = current

                # Trim to code length
                if len(self._grid_entered) > self._code_len:
                    self._grid_entered = self._grid_entered[-self._code_len:]

                self._send_segment(self._grid_entered.ljust(self._code_len))
                self.core.display.update_status(
                    f"GRID: {self._grid_code}",
                    f"ENTERED: {self._grid_entered}"
                )
                self.core.synth.play_note(880.0, "BEEP", duration=0.05)

            # Check for correct code
            if len(self._grid_entered) >= self._code_len:
                if self._grid_entered[-self._code_len:] == self._grid_code:
                    self.core.synth.play_note(1200.0, "SUCCESS", duration=0.1)
                    return True
                else:
                    # Wrong code – reset entry silently
                    self._grid_entered = ""
                    self._last_keypad_snapshot = current
                    self._send_segment("ERR     ")
                    self.core.display.update_status("GRID ERROR", f"RE-ENTER: {self._grid_code}")
                    asyncio.create_task(
                        self.core.synth.play_sequence(tones.ERROR, patch="ERROR")
                    )
                    await asyncio.sleep(0.8)
                    self._send_segment("        ")
                    self.core.display.update_status(
                        f"GRID: {self._grid_code}", "RE-ENTER CODE"
                    )

            # Global timeout check handled by caller
            await asyncio.sleep(0.05)

    # ------------------------------------------------------------------
    # Phase: Payload Configuration
    # ------------------------------------------------------------------

    async def _run_phase_payload(self):
        """Phase 2 – Player matches 8 latching toggles to the pattern."""
        names_str = "/".join(self._payload_names[:4]) if self._payload_names else "ALL OFF"
        self.core.display.update_status("CONFIG PAYLOAD", names_str[:20])
        self._send_segment("PAYLOAD ")
        asyncio.create_task(
            self.core.synth.play_sequence(tones.UI_TICK, patch="CLICK")
        )

        # Track last color sent per LED to avoid blasting the UART on every poll
        last_led_states = [None] * _TOGGLE_COUNT

        while True:
            all_match = True
            for i in range(_TOGGLE_COUNT):
                state = self._sat_latching(i)
                expected = self._payload_pattern[i]
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

            # Build pattern display for OLED
            pat = "".join(["X" if self._payload_pattern[i] else "_" for i in range(_TOGGLE_COUNT)])
            cur = "".join(["X" if self._sat_latching(i) else "_" for i in range(_TOGGLE_COUNT)])
            self.core.display.update_status(f"NEED: {pat}", f"HAVE: {cur}")

            if all_match:
                self.core.synth.play_note(1000.0, "SUCCESS", duration=0.1)
                return True

            await asyncio.sleep(0.08)

    # ------------------------------------------------------------------
    # Phase: Fine Targeting
    # ------------------------------------------------------------------

    async def _run_phase_target(self):
        """Phase 3 – Player aligns crosshair onto target using dual encoders."""
        w = self.core.matrix.width
        h = self.core.matrix.height

        # Center the crosshair
        self._crosshair_x = w // 2
        self._crosshair_y = h // 2
        self._last_core_enc = self.core.hid.encoder_positions[_ENC_CORE]
        self._last_sat_enc = self._sat_encoder()

        self.core.display.update_status("FINE TARGETING", "USE BOTH ENCODERS")
        self._send_segment("TGT     ")

        # Brief panning animation first
        await self._animate_panning()

        tick_counter = 0
        while True:
            # --- Core encoder → X-axis ---
            curr_core = self.core.hid.encoder_positions[_ENC_CORE]
            dx = curr_core - self._last_core_enc
            if dx != 0:
                self._crosshair_x = max(0, min(w - 1, self._crosshair_x + dx))
                self._last_core_enc = curr_core
                self.core.synth.play_note(660.0, "CLICK", duration=0.03)

            # --- Satellite encoder → Y-axis ---
            curr_sat = self._sat_encoder()
            dy = curr_sat - self._last_sat_enc
            if dy != 0:
                self._crosshair_y = max(0, min(h - 1, self._crosshair_y + dy))
                self._last_sat_enc = curr_sat
                self.core.synth.play_note(660.0, "CLICK", duration=0.03)

            # --- Target drift (hard/insane) ---
            if self._drift_enabled:
                tick_counter += 1
                if tick_counter >= 15:   # drift every ~0.75 s
                    tick_counter = 0
                    self._target_x = max(1, min(w - 2, self._target_x + self._drift_dx))
                    self._target_y = max(1, min(h - 2, self._target_y + self._drift_dy))

            # --- Render ---
            self._render_targeting()

            # --- Distance check ---
            dist = max(abs(self._crosshair_x - self._target_x),
                       abs(self._crosshair_y - self._target_y))

            self.core.display.update_status(
                f"TGT ({self._target_x},{self._target_y})",
                f"CHX ({self._crosshair_x},{self._crosshair_y}) D={dist}"
            )

            if dist <= _LOCK_THRESHOLD:
                return True

            await asyncio.sleep(0.05)

    # ------------------------------------------------------------------
    # Phase: Execute
    # ------------------------------------------------------------------

    async def _run_phase_execute(self):
        """Phase 4 – Player arms the guarded toggle and presses the big button."""
        # Show locked state
        self._render_locked()
        self.core.display.update_status("SOLUTION LOCKED", "ARM + PRESS BUTTON")
        self._send_segment("LOCKED  ")
        asyncio.create_task(
            self.core.synth.play_sequence(tones.ALARM, patch="ALARM")
        )

        while True:
            arm_engaged = self._sat_latching(_SW_ARM)
            btn_pressed = self._sat_button(_BTN_EXECUTE)

            if arm_engaged and btn_pressed:
                return True

            # Pulse the OLED to show arm/button status
            arm_str = "ARM:ON " if arm_engaged else "ARM:OFF"
            btn_str = "BTN:ON" if btn_pressed else "BTN:OFF"
            self.core.display.update_status(f"ARM+BTN TO FIRE", f"{arm_str} | {btn_str}")

            await asyncio.sleep(0.05)

    # ------------------------------------------------------------------
    # Phase: Reset
    # ------------------------------------------------------------------

    async def _run_phase_reset(self):
        """Phase 5 – Player resets all toggles and disarms guarded toggle."""
        self.core.display.update_status("RESET HARDWARE", "CLEAR TOGGLES + ARM")
        self._send_segment("RESET   ")

        # Track last color sent per LED to avoid blasting the UART on every poll
        last_led_states = [None] * _TOGGLE_COUNT

        while True:
            all_clear = True

            # All 8 payload toggles must be DOWN
            for i in range(_TOGGLE_COUNT):
                state = self._sat_latching(i)
                if state:
                    all_clear = False
                    if last_led_states[i] != "RED":
                        if self.sat:
                            try:
                                self.sat.send("LED", f"{i},{Palette.RED.index},0.0,1.0,2")
                            except Exception:
                                pass
                        last_led_states[i] = "RED"
                else:
                    if last_led_states[i] != "GREEN":
                        if self.sat:
                            try:
                                self.sat.send("LED", f"{i},{Palette.GREEN.index},0.0,0.3,2")
                            except Exception:
                                pass
                        last_led_states[i] = "GREEN"

            # Guarded toggle must be DOWN
            if self._sat_latching(_SW_ARM):
                all_clear = False

            tog_str = "".join(["_" if not self._sat_latching(i) else "X" for i in range(_TOGGLE_COUNT)])
            arm_str = "ARM:CLR" if not self._sat_latching(_SW_ARM) else "ARM:ON!"
            self.core.display.update_status(f"RESET: {tog_str}", arm_str)

            if all_clear:
                self.core.synth.play_note(800.0, "SUCCESS", duration=0.1)
                return True

            await asyncio.sleep(0.08)

    # ------------------------------------------------------------------
    # Main game loop
    # ------------------------------------------------------------------

    async def run(self):
        """Main Orbital Strike game loop."""
        self.difficulty = self.core.data.get_setting("ORBITAL_STRIKE", "difficulty", "NORMAL")
        self.variant = self.difficulty

        params = _DIFF_PARAMS.get(self.difficulty, _DIFF_PARAMS["NORMAL"])
        self._code_len = params["code_len"]
        self._drift_enabled = params["drift"]

        # Satellite check
        if not self.sat or not self.sat.is_active:
            self.core.display.update_status("ORBITAL STRIKE", "SAT OFFLINE - ABORT")
            await asyncio.sleep(2)
            return "FAILURE"

        # Intro
        self.core.display.use_standard_layout()
        self.core.display.update_status("ORBITAL STRIKE", "WEAPONS ONLINE...")
        self.core.matrix.show_icon("ORBITAL_STRIKE", clear=True)
        asyncio.create_task(
            self.core.synth.play_sequence(tones.POWER_UP, patch="SCANNER")
        )
        await asyncio.sleep(2.0)

        # Reset encoders (value=0 means start position; index selects which encoder)
        self.core.hid.reset_encoder(value=0, index=_ENC_CORE)
        if self.sat:
            try:
                self.sat.hid.reset_encoder(value=0, index=_ENC_SAT)
            except Exception:
                pass

        self._time_remaining = _GLOBAL_TIME
        self._mission_count = 0
        self.score = 0
        self._last_tick_ms = ticks_ms()

        game_running = True

        while game_running:
            # --- Global timer tick ---
            now = ticks_ms()
            elapsed_ms = ticks_diff(now, self._last_tick_ms)
            if elapsed_ms >= 100:
                delta_s = elapsed_ms / 1000.0
                self._time_remaining -= delta_s
                self._last_tick_ms = now

            if self._time_remaining <= 0:
                break

            # --- New mission ---
            self._new_mission()
            mission_start_time = self._time_remaining

            # Phase 1: Target Grid
            self._phase = _PHASE_GRID
            done = await self._timed_phase(self._run_phase_grid)
            if not done:
                break

            # Update timer after phase completes
            now = ticks_ms()
            elapsed_ms = ticks_diff(now, self._last_tick_ms)
            self._time_remaining -= elapsed_ms / 1000.0
            self._last_tick_ms = now
            if self._time_remaining <= 0:
                break

            # Phase 2: Payload Configuration
            self._phase = _PHASE_PAYLOAD
            done = await self._timed_phase(self._run_phase_payload)
            if not done:
                break

            now = ticks_ms()
            elapsed_ms = ticks_diff(now, self._last_tick_ms)
            self._time_remaining -= elapsed_ms / 1000.0
            self._last_tick_ms = now
            if self._time_remaining <= 0:
                break

            # Phase 3: Fine Targeting
            self._phase = _PHASE_TARGET
            done = await self._timed_phase(self._run_phase_target)
            if not done:
                break

            now = ticks_ms()
            elapsed_ms = ticks_diff(now, self._last_tick_ms)
            self._time_remaining -= elapsed_ms / 1000.0
            self._last_tick_ms = now
            if self._time_remaining <= 0:
                break

            # Phase 4: Execute
            self._phase = _PHASE_EXECUTE
            done = await self._timed_phase(self._run_phase_execute)
            if not done:
                break

            now = ticks_ms()
            elapsed_ms = ticks_diff(now, self._last_tick_ms)
            self._time_remaining -= elapsed_ms / 1000.0
            self._last_tick_ms = now
            if self._time_remaining <= 0:
                break

            # --- Mission Complete! ---
            mission_time = mission_start_time - self._time_remaining
            speed_bonus = max(0, int(30 - mission_time) * 10)
            self.score += 100 + speed_bonus
            self._time_remaining = min(_GLOBAL_TIME, self._time_remaining + _BONUS_TIME)
            self._mission_count += 1

            self.core.display.update_status(
                f"STRIKE CONFIRMED!",
                f"+{100 + speed_bonus} PTS | T:{self._time_remaining:.0f}s"
            )
            self._send_segment("BOOM    ")

            # Explosion animation
            asyncio.create_task(
                self.core.synth.play_sequence(tones.FIREBALL, patch="ALARM")
            )
            await self._animate_explosion()

            # Phase 5: Reset
            self._phase = _PHASE_RESET
            await self._run_phase_reset()

            now = ticks_ms()
            elapsed_ms = ticks_diff(now, self._last_tick_ms)
            self._time_remaining -= elapsed_ms / 1000.0
            self._last_tick_ms = now

            # Brief pause before next mission
            self.core.display.update_status(
                f"MISSION {self._mission_count} COMPLETE",
                f"SCORE: {self.score} | T:{self._time_remaining:.0f}s"
            )
            await asyncio.sleep(1.0)

        # Time's up
        self._send_segment("T-O END ")
        return await self.game_over()

    async def _timed_phase(self, phase_coro):
        """Run a phase coroutine; returns False if global time runs out first."""
        task = asyncio.create_task(phase_coro())
        try:
            while not task.done():
                # Tick global timer while waiting
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
