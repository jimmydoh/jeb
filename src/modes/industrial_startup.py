#File: src/core/modes/industrial_startup.py
"""Industrial Satellite Startup Sequence Mode."""

import asyncio
import random
from adafruit_ticks import ticks_ms, ticks_diff

from utilities.palette import Palette

from .game_mode import GameMode

class IndustrialStartup(GameMode):
    """Industrial Satellite Startup Sequence Mode.
    A multi-phase startup sequence requiring various inputs
    from both the Core and Industrial Satellite box.

    The middle phases (Toggle Sequence, Auth Code, Bracket Align,
    Reactor Balance) are drawn randomly from a phase pool each run,
    so no two playthroughs follow the same order.
    """

    REACTOR_BALANCE_DURATION = 15.0
    _REACTOR_COL_COUNT = 4
    _REACTOR_SAFE_MIN = 5.0
    _REACTOR_SAFE_MAX = 11.0

    def __init__(self, core):
        super().__init__(
            core,
            "INDUSTRIAL STARTUP",
            "Industrial Satellite Startup Sequence",
            total_steps=5
        )
        self.sat = None
        # Iterate through self.core.satellites: Dict[slot_id: int, Satellite]
        # Each Satellite has properties: sat_type_name (str), is_active (bool), slot_id (int)
        for sat in self.core.satellites.values():
            if sat.sat_type_name == "INDUSTRIAL":
                self.sat = sat
                break

    async def game_over(self):
        """Industrial Startup Fail Sequence."""
        self.core.matrix.show_icon("FAILURE", anim_mode="PULSE", speed=2.0)
        self.core.audio.play("audio/ind/atmo/hum_alarm.wav",
                            self.core.audio.CH_ATMO,
                            level=1.0,
                            loop=True,
                            interrupt=True)
        self.core.audio.play("audio/ind/voice/narration_fail.wav",
                            self.core.audio.CH_VOICE,
                            level=0.8,
                            wait=True)
        self.core.display.update_status("SYSTEM FAILURE", "SHUTTING DOWN...")
        await asyncio.sleep(2)
        return "GAME_OVER"

    async def victory(self):
        """Industrial Startup Victory Sequence."""
        self.core.matrix.show_icon("SUCCESS", anim_mode="PULSE", speed=2.0)
        self.core.audio.play("audio/ind/atmo/hum_final.wav",
                            self.core.audio.CH_ATMO,
                            level=1.0,
                            loop=True,
                            interrupt=True)
        self.core.audio.play("audio/ind/voice/narration_success.wav",
                            self.core.audio.CH_VOICE,
                            level=0.8,
                            wait=True)
        return "VICTORY"

    # ------------------------------------------------------------------
    # Phase helpers
    # ------------------------------------------------------------------

    async def _phase_boot_splash(self):
        """Boot sweep animation on the 16x16 matrix (Phase 0 visual)."""
        w = self.core.matrix.width
        h = self.core.matrix.height
        # Sweep columns left-to-right, lighting cyan
        for x in range(w):
            for y in range(h):
                self.core.matrix.draw_pixel(x, y, Palette.CYAN, show=False)
            await asyncio.sleep(0.04)
        await asyncio.sleep(0.2)
        self.core.matrix.fill(Palette.OFF, show=True)

    async def _phase_toggles(self, narration_vol=0.8):
        """Toggle Sequence mini-game (formerly Step 2).

        Returns None on success or "GAME_OVER" on failure.
        """
        self.core.display.update_status("INIT SPLINE MODS", "CONFIRM STATES")
        self.core.audio.play("audio/ind/atmo/hum_2.wav",
                            self.core.audio.CH_ATMO,
                            level=0.4,
                            loop=True,
                            interrupt=True)
        self.core.audio.play("audio/ind/voice/narration_2.wav",
                            self.core.audio.CH_VOICE,
                            level=narration_vol,
                            wait=True)

        iteration = 0
        total_iterations = 10

        while iteration < total_iterations:
            # Set all toggle LEDs to blue
            for i in range(6):
                self.sat.send("LEDBREATH", f"{i},{Palette.BLUE.index},0.0,0.5,1,2.0")
            await asyncio.sleep(0.5)

            # Calculate dynamic blink speed (gets faster every round)
            # Starts at 0.4s, ends at 0.1s
            blink_speed = 0.4 - (iteration * 0.03)

            # Randomly select the 'Target' toggle (0-4)
            # Max is 4: latching toggles 0-3, one momentary at index 4 (m_idx=0)
            target_idx = random.randint(0, 4)

            # Determine the required action for this toggle
            required_state = None
            required_direction = None
            m_idx = None
            if target_idx <= 3: # LATCHING
                # Success = flipping it to the opposite of what it is now
                required_state = 0 if self.sat.is_latching_toggled(target_idx) else 1
                mode = "LATCH"
            else: # MOMENTARY (4 or 5)
                # Success = holding a random direction
                m_idx = target_idx - 4
                required_direction = random.choice(["U", "D"])
                mode = "MOMENT"

            # Snapshot current toggle state
            self.sat.snapshot_state()

            # Reaction Loop
            self.core.display.update_status(
                f"PHASE: {iteration+1}/10",
                "AWAITING SIGNAL..."
            )
            success = False
            wrong_input = False

            while not success and not wrong_input:
                # Pulse the target LED Amber
                self.sat.send(
                    "LEDFLASH",
                    f"{target_idx},{Palette.ORANGE.index},0.0,0.5,3,{blink_speed},{blink_speed}"
                )
                # --- CHECK FOR SUCCESS ---
                if mode == "LATCH":
                    self.core.audio.play(f"audio/ind/voice/latch_{target_idx}.wav",
                                        self.core.audio.CH_VOICE,
                                        level=narration_vol,
                                        wait=True)
                    if self.sat.is_latching_toggled(target_idx) == required_state:
                        success = True
                else: # MOMENTARY
                    # Require a 2s hold to ensure it's intentional
                    self.core.audio.play(
                        f"audio/ind/voice/momentary_{target_idx}_{required_direction}.wav",
                        self.core.audio.CH_VOICE,
                        level=narration_vol,
                        wait=True
                    )
                    if self.sat.is_momentary_toggled(
                        m_idx,
                        required_direction,
                        long=True,
                        duration=2000
                    ):
                        success = True

                # --- CHECK FOR WRONG INPUT ---
                # Check if any OTHER latching toggle changed OR any momentary was touched
                if self.sat.any_other_input_detected(target_idx):
                    wrong_input = True

            # Handle Result
            if success:
                iteration += 1
                self.core.audio.play("audio/ind/sfx/toggle_confirm.wav",
                                    self.core.audio.CH_SFX,
                                    level=0.8,
                                    interrupt=True)
                self.sat.send("LED", f"{target_idx},{Palette.GREEN.index},0.0,0.5,2")
                self.core.matrix.show_progress_grid(iteration, total_iterations, color=Palette.GREEN)
                await asyncio.sleep(0.5)
                self.sat.send("LED", f"{target_idx},{Palette.SKY.index},0.0,0.5,2")

            elif wrong_input:
                self.core.audio.play("audio/ind/sfx/toggle_error.wav",
                                    self.core.audio.CH_SFX,
                                    level=0.8,
                                    interrupt=True)
                # Flash ALL toggle LEDs Red
                for _ in range(6):
                    self.sat.send(
                        "LEDFLASH",
                        f"{_},{Palette.RED.index},1.5,0.5,1,0.25,0.25"
                    )
                await asyncio.sleep(0.3)
                # Loop continues, iterations do NOT increase

        # Completed all iterations
        self.core.display.update_status("PHASE COMPLETE", "CORE STABILIZED")
        self.core.audio.play("audio/ind/voice/toggle_done.wav",
                            self.core.audio.CH_VOICE,
                            level=narration_vol,
                            wait=True)
        self.core.matrix.show_icon("SUCCESS", anim_mode="PULSE", speed=2.0)
        await asyncio.sleep(1)
        return None

    async def _phase_auth_code(self, narration_vol=0.8):
        """Auth Code Entry mini-game (formerly Step 3).

        Returns None on success.
        """
        self.core.display.update_status("AWAIT AUTH CODE", "ADMIN ACCESS")
        self.core.audio.play("audio/ind/atmo/hum_2.wav",
                            self.core.audio.CH_ATMO,
                            level=0.6,
                            loop=True,
                            interrupt=False)
        self.core.audio.play("audio/ind/voice/narration_3.wav",
                            self.core.audio.CH_VOICE,
                            level=narration_vol,
                            wait=True)

        target_sequence = "".join([str(random.randint(0, 9)) for _ in range(8)])
        user_entry = ""
        await asyncio.sleep(1)
        while user_entry != target_sequence:

            # Display the code one digit at a time
            for digit in target_sequence:
                self.core.display.update_status("ENTRY CODE:", digit)
                self.core.audio.play(f"audio/ind/voice/v_{digit}.wav",
                                    self.core.audio.CH_VOICE,
                                    level=narration_vol,
                                    wait=True)
                await asyncio.sleep(0.9)
            self.core.audio.play("audio/ind/voice/keypad_go.wav",
                                self.core.audio.CH_VOICE,
                                level=narration_vol,
                                wait=True)

            # Clear the buffer NOW to drop any keys pressed during dictation
            self.sat.clear_key()

            # Wait for user to enter code via keypad
            start_time = ticks_ms()
            while len(user_entry) < 8 and ticks_diff(ticks_ms(), start_time) < 10000:
                if self.sat.keypad != "N":
                    user_entry += self.sat.keypad
                    self.sat.send("DSP", user_entry)
                    self.core.audio.play("audio/ind/sfx/keypad_click.wav",
                                        self.core.audio.CH_SFX,
                                        level=0.8)
                    self.sat.clear_key()
                await asyncio.sleep(0.01)

            # If it does not match, prompt retry
            if user_entry != target_sequence:
                self.core.display.update_status("AUTH FAILED", "RE-TRANSMITTING")
                self.core.audio.play("audio/ind/sfx/fail.wav",
                                    self.core.audio.CH_SFX,
                                    level=0.6,
                                    interrupt=True)
                self.core.audio.play("audio/ind/voice/keypad_retry.wav",
                                    self.core.audio.CH_VOICE,
                                    level=narration_vol,
                                    wait=True)
                user_entry = ""
                self.sat.send("DSP", "********")
                await asyncio.sleep(2)

        # Success
        self.core.display.update_status("AUTH CODE ACCEPTED", "ACCESS GRANTED")
        self.core.audio.play("audio/ind/sfx/success.wav",
                            self.core.audio.CH_SFX,
                            level=0.8,
                            interrupt=True)
        return None

    async def _phase_brackets(self, narration_vol=0.8):
        """Bracket Align mini-game (formerly Step 4).

        Returns None on success or "GAME_OVER" on bracket collision.
        """
        self.core.display.update_status("ALIGN BRACKETS", "DUAL ENCODER SYNC")
        self.core.audio.play("audio/ind/atmo/hum_3.wav",
                            self.core.audio.CH_ATMO,
                            level=0.8,
                            loop=True,
                            interrupt=True)
        self.core.audio.play("audio/ind/voice/narration_4.wav",
                            self.core.audio.CH_VOICE,
                            level=narration_vol,
                            wait=True)

        w = self.core.matrix.width
        h = self.core.matrix.height
        target_y_start = h // 4
        target_y_end = h * 3 // 4
        bracket_y_start = h // 8
        bracket_y_end = h - h // 8

        self.sat.reset_encoder(0)           # Left bracket starts at column 0
        self.core.hid.reset_encoder(w - 1)  # Right bracket starts at last column

        target_pos = random.randint(2, w - 3)  # Target position with bracket clearance
        last_target_move = ticks_ms()
        lock_start_time = None

        while True:
            current_time = ticks_ms()

            # Dynamic target movement every 3-5 seconds
            if ticks_diff(current_time, last_target_move) > random.randint(3000, 5000):
                move = random.choice([-1, 1])
                new_target = max(1, min(w - 2, target_pos + move))
                if new_target != target_pos:
                    target_pos = new_target
                    self.core.audio.play("audio/ind/sfx/target_shift.wav",
                                        self.core.audio.CH_SFX,
                                        level=0.5)
                last_target_move = current_time

            # Get Input Positions (0 to w-1)
            left_pos = self.sat.get_scaled_encoder_pos(multiplier=1.0, wrap=w)
            right_pos = self.core.hid.get_scaled_encoder_pos(multiplier=1.0, wrap=w)

            # Logic Checks
            # Collision (Critical Failure)
            if left_pos >= right_pos:
                self.core.matrix.fill(Palette.RED, show=True, anim_mode="BLINK", speed=2.0)
                self.core.display.update_status("CRITICAL ERROR", "BRACKET COLLISION")
                self.core.audio.play("audio/ind/sfx/crash.wav",
                                    self.core.audio.CH_SFX,
                                    level=1.0)
                await asyncio.sleep(2)
                return "GAME_OVER"

            # Check if brackets are correctly aligned around target
            is_aligned = (left_pos == (target_pos - 1)) and (right_pos == (target_pos + 1))

            # Render Matrix Visuals
            self.core.matrix.fill(Palette.OFF, show=False)

            # Draw Target
            if is_aligned:
                for y in range(target_y_start, target_y_end):
                    self.core.matrix.draw_pixel(
                        target_pos,
                        y,
                        Palette.GREEN,
                        show=False,
                        anim_mode="PULSE",
                        speed=3.0
                    )
            else:
                for y in range(target_y_start, target_y_end):
                    self.core.matrix.draw_pixel(
                        target_pos,
                        y,
                        Palette.YELLOW,
                        show=False
                    )

            # Draw Left Bracket
            if is_aligned:
                for y in range(bracket_y_start, bracket_y_end):
                    self.core.matrix.draw_pixel(
                        left_pos,
                        y,
                        Palette.GREEN,
                        show=False,
                        anim_mode="PULSE",
                        speed=3.0
                    )
            else:
                for y in range(bracket_y_start, bracket_y_end):
                    self.core.matrix.draw_pixel(
                        left_pos,
                        y,
                        Palette.CYAN,
                        show=False
                    )

            # Draw Right Bracket
            if is_aligned:
                for y in range(bracket_y_start, bracket_y_end):
                    self.core.matrix.draw_pixel(
                        right_pos,
                        y,
                        Palette.GREEN,
                        show=False,
                        anim_mode="PULSE",
                        speed=3.0
                    )
            else:
                for y in range(bracket_y_start, bracket_y_end):
                    self.core.matrix.draw_pixel(
                        right_pos,
                        y,
                        Palette.MAGENTA,
                        show=False
                    )

            # Note: Hardware write is now centralized in CoreManager.render_loop()

            if is_aligned:
                if lock_start_time is None:
                    lock_start_time = current_time
                elif ticks_diff(current_time, lock_start_time) >= 1000:
                    # Held alignment for 1 second - Success
                    break
            else:
                lock_start_time = None

            await asyncio.sleep(0.05)

        return None

    async def _phase_reactor_balance(self, narration_vol=0.8):
        """Reactor Balance mini-game.

        Four vertical coolant columns on the 16x16 matrix, each 4 pixels wide.
        The 4 latching toggles on the satellite control the pump for each column:
          - Toggle UP  → pump coolant in (level rises)
          - Toggle DOWN → halt pump (level falls)
        The satellite 14-segment display shows a ticking countdown.
        Players must keep all column levels inside the safe zone (green centre
        band) until the countdown reaches zero.

        Returns None on success or "GAME_OVER" if any column overflows/empties.
        """
        w = self.core.matrix.width
        h = self.core.matrix.height
        col_width = w // self._REACTOR_COL_COUNT

        # Coolant levels as floats: 0.0 = empty (stall), h = full (meltdown)
        levels = [h / 2.0] * self._REACTOR_COL_COUNT

        self.core.display.update_status("CORE TEMP: CRITICAL", "REACTOR BALANCE")
        self.core.audio.play("audio/ind/atmo/hum_3.wav",
                            self.core.audio.CH_ATMO,
                            level=1.0,
                            loop=True,
                            interrupt=True)
        self.core.audio.play("audio/ind/voice/narration_balance.wav",
                            self.core.audio.CH_VOICE,
                            level=narration_vol,
                            wait=True)

        start_time = ticks_ms()
        last_drift_time = start_time

        while True:
            now = ticks_ms()
            elapsed = ticks_diff(now, start_time) / 1000.0
            remaining = max(0.0, self.REACTOR_BALANCE_DURATION - elapsed)

            # Format countdown for satellite 14-segment: "T- 15.00"
            secs = int(remaining)
            centisecs = int((remaining - secs) * 100)
            self.sat.send("DSP", f"T-{secs:3d}.{centisecs:02d}")

            # Win condition: countdown reached zero
            if remaining <= 0.0:
                break

            # Apply toggle-based pump adjustment each tick (100 ms)
            for i in range(self._REACTOR_COL_COUNT):
                if self.sat.is_latching_toggled(i):
                    levels[i] = min(float(h), levels[i] + 0.3)
                else:
                    levels[i] = max(0.0, levels[i] - 0.3)

            # Apply random drift every 500 ms to keep things unpredictable
            if ticks_diff(now, last_drift_time) >= 500:
                for i in range(self._REACTOR_COL_COUNT):
                    levels[i] = max(0.0, min(float(h), levels[i] + random.uniform(-0.8, 0.8)))
                last_drift_time = now

            # Fail condition: any column at absolute top or absolute bottom
            for i in range(self._REACTOR_COL_COUNT):
                if levels[i] <= 0.0 or levels[i] >= float(h):
                    self.core.display.update_status("REACTOR CRITICAL", "MELTDOWN / STALL")
                    self.core.matrix.fill(Palette.RED, show=True, anim_mode="BLINK", speed=2.0)
                    self.core.audio.play("audio/ind/sfx/crash.wav",
                                        self.core.audio.CH_SFX,
                                        level=1.0,
                                        interrupt=True)
                    await asyncio.sleep(2)
                    return "GAME_OVER"

            # Render coolant columns on the matrix
            self.core.matrix.fill(Palette.OFF, show=False)
            for col in range(self._REACTOR_COL_COUNT):
                level = levels[col]
                # Fluid fills from the bottom: surface row = h - level
                surface_row = int(h - level)
                x_start = col * col_width
                for y in range(surface_row, h):
                    # Choose colour based on whether the level is in the safe zone
                    if self._REACTOR_SAFE_MIN <= level <= self._REACTOR_SAFE_MAX:
                        color = Palette.GREEN
                    elif level < self._REACTOR_SAFE_MIN:
                        color = Palette.RED
                    else:
                        color = Palette.YELLOW
                    for x in range(x_start, x_start + col_width):
                        self.core.matrix.draw_pixel(x, y, color, show=False)

            await asyncio.sleep(0.1)

        # Success
        self.core.display.update_status("REACTOR STABLE", "BALANCE ACHIEVED")
        self.core.audio.play("audio/ind/sfx/success.wav",
                            self.core.audio.CH_SFX,
                            level=0.8,
                            interrupt=True)
        await asyncio.sleep(1)
        return None

    # ------------------------------------------------------------------
    # Main run loop
    # ------------------------------------------------------------------

    async def run(self):
        """Industrial Satellite Startup Sequence.

        Phase 0 (Boot) and the dual-input gate are always run first.
        Three mini-games are then drawn at random from the phase pool and
        executed in a random order before the victory sequence.
        """

        # Initial check to confirm Satellite is connected
        if not self.sat or not self.sat.is_connected:
            self.core.display.update_status("ERROR", "SATELLITE OFFLINE")
            await asyncio.sleep(2)
            return "FAILURE"

        narration_vol = 0.8

        # --- PHASE 0: BOOT INITIALIZATION ---
        self.core.display.update_status("LINK ESTABLISHED", "INITIALIZING...")
        self.core.audio.play("audio/ind/atmo/hum_1.wav",
                            self.core.audio.CH_ATMO,
                            level=0.2,
                            loop=True,
                            interrupt=True)
        await self._phase_boot_splash()
        self.core.audio.play("audio/ind/voice/narration_0.wav",
                            self.core.audio.CH_VOICE,
                            level=narration_vol,
                            wait=True)

        # --- PHASE 1: DUAL INPUT GATE ---
        self.core.display.update_status(
            "INDUSTRIAL CONTROL ONLINE",
            "HOLD [A] + Prime Switch DOWN"
        )
        self.core.audio.play("audio/ind/atmo/hum_1.wav",
                            self.core.audio.CH_ATMO,
                            level=0.2,
                            loop=True,
                            interrupt=True)
        self.core.audio.play("audio/ind/voice/narration_1.wav",
                            self.core.audio.CH_VOICE,
                            level=narration_vol,
                            wait=True)
        while True:
            core_press = self.core.hid.is_pressed(0, Long=True, Duration=2000)
            sat_press = self.sat.is_momentary_toggled(0, "D", Long=True, Duration=2000)
            if core_press and sat_press:
                break
            await asyncio.sleep(0.1)

        self.core.display.update_status("SUCCESSFULLY PRIMED", "POWERING UP...")
        self.core.audio.play("audio/ind/sfx/power_up.wav",
                            self.core.audio.CH_SFX)

        # --- MIDDLE PHASES: random selection of 3 from the phase pool ---
        phase_pool = [
            self._phase_toggles,
            self._phase_auth_code,
            self._phase_brackets,
            self._phase_reactor_balance,
        ]
        random.shuffle(phase_pool)

        for phase_fn in phase_pool[:3]:
            result = await phase_fn(narration_vol)
            if result == "GAME_OVER":
                return await self.game_over()

        # --- PHASE 5: VICTORY ---
        return await self.victory()
