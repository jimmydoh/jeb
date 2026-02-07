#File: src/core/modes/industrial_startup.py
"""Industrial Satellite Startup Sequence Mode."""

import asyncio
import random
from adafruit_ticks import ticks_ms, ticks_diff

from utilities import Palette

from .game_mode import GameMode

class IndustrialStartup(GameMode):
    """Industrial Satellite Startup Sequence Mode.
    A multi-phase startup sequence requiring various inputs
    from both the Core and Industrial Satellite box.
    """

    METADATA = {
        "id": "IND",
        "name": "INDUSTRIAL",
        "icon": "IND",
        "requires": ["INDUSTRIAL"], # Explicit dependency
        "settings": []
    }

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
                            Interrupt=True)
        self.core.audio.play("audio/ind/voice/narration_fail.wav",
                            self.core.audio.CH_VOICE,
                            level=0.8,
                            Wait=True)
        await self.core.display.update_status("SYSTEM FAILURE", "SHUTTING DOWN...")
        await asyncio.sleep(2)
        return "GAME_OVER"

    async def victory(self):
        """Industrial Startup Victory Sequence."""
        self.core.matrix.show_icon("SUCCESS", anim_mode="PULSE", speed=2.0)
        self.core.audio.play("audio/ind/atmo/hum_final.wav",
                            self.core.audio.CH_ATMO,
                            level=1.0,
                            loop=True,
                            Interrupt=True)
        self.core.audio.play("audio/ind/voice/narration_success.wav",
                            self.core.audio.CH_VOICE,
                            level=0.8,
                            Wait=True)
        return "VICTORY"

    async def run(self):
        """Industrial Satellite Startup Sequence."""

        # Initial check to confirm Satellite is connected
        if not self.sat or not self.sat.is_connected:
            await self.core.display.update_status("ERROR", "SATELLITE OFFLINE")
            await asyncio.sleep(2)
            return "FAILURE"

        narration_vol = 0.8

        # --- MAIN GAME LOOP ---
        while self.step <= self.total_steps:

            # --- STEP 0: INITIALIZATION ---
            if self.step == 0:
                await self.core.display.update_status("LINK ESTABLISHED", "INITIALIZING...")
                self.core.audio.play("audio/ind/atmo/hum_1.wav",
                                    self.core.audio.CH_ATMO,
                                    level=0.2,
                                    loop=True,
                                    interrupt=True)
                self.core.audio.play("audio/ind/voice/narration_0.wav",
                                    self.core.audio.CH_VOICE,
                                    level=narration_vol,
                                    wait=True)
                self.step += 1

            # --- STEP 1: DUAL INPUT ---
            elif self.step == 1:
                await self.core.display.update_status(
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
                # Await both inputs
                while True:
                    core_press = self.core.hid.is_pressed(0, Long=True, Duration=2000)
                    sat_press = self.sat.is_momentary_toggled(0, "D", Long=True, Duration=2000)
                    if core_press and sat_press:
                        break
                    await asyncio.sleep(0.1)

                await self.core.display.update_status("SUCCESSFULLY PRIMED", "POWERING UP...")
                self.core.audio.play("audio/ind/sfx/power_up.wav",
                                    self.core.audio.CH_SFX)
                self.step += 1

            # --- STEP 2: TOGGLE SEQUENCE ---
            elif self.step == 2:
                await self.core.display.update_status("INIT SPLINE MODS", "CONFIRM STATES")
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
                        self.sat.send_cmd("LEDBREATH", f"{i},0,0,200,0.0,0.5,1,2.0")
                    await asyncio.sleep(0.5)

                    # Calculate dynamic blink speed (gets faster every round)
                    # Starts at 0.4s, ends at 0.1s
                    blink_speed = 0.4 - (iteration * 0.03)

                    # Randomly select the 'Target' toggle (0-5)
                    target_idx = random.randint(0, 5)

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
                    await self.core.display.update_status(
                        f"PHASE: {iteration+1}/10",
                        "AWAITING SIGNAL..."
                    )
                    success = False
                    wrong_input = False

                    while not success and not wrong_input:
                        # Pulse the target LED Amber
                        self.sat.send_cmd(
                            "LEDFLASH",
                            f"{target_idx},255,165,0,0.0,0.5,3,{blink_speed},{blink_speed}"
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
                                            Interrupt=True)
                        self.sat.send_cmd("LED", f"{target_idx},0,255,0,0.0,0.5,2")
                        # TODO Add progress animation for matrix
                        await asyncio.sleep(0.5)
                        self.sat.send_cmd("LED", f"{target_idx},100,100,255,0.0,0.5,2")

                    elif wrong_input:
                        self.core.audio.play("audio/ind/sfx/toggle_error.wav",
                                            self.core.audio.CH_SFX,
                                            level=0.8,
                                            Interrupt=True)
                        # Flash ALL toggle LEDs Red
                        for _ in range(6):
                            self.sat.send_cmd("LEDFLASH", f"{_},255,0,0,1.5,0.5,1,0.25,0.25")
                        await asyncio.sleep(0.3)
                        # Loop continues, iterations do NOT increase

                # Completed all iterations
                await self.core.display.update_status("PHASE COMPLETE", "CORE STABILIZED")
                self.core.audio.play("audio/ind/voice/toggle_done.wav",
                                    self.core.audio.CH_VOICE,
                                    level=narration_vol,
                                    wait=True)
                # TODO Play Victory Animation
                self.step += 1
                await asyncio.sleep(1)

            # --- STEP 3: AUTH CODE ENTRY ---
            elif self.step == 3:
                await self.core.display.update_status("AWAIT AUTH CODE", "ADMIN ACCESS")
                self.core.audio.play("audio/ind/atmo/hum_2.wav",
                                    self.core.audio.CH_ATMO,
                                    level=0.6,
                                    loop=True,
                                    Interrupt=False)
                self.core.audio.play("audio/ind/voice/narration_3.wav",
                                    self.core.audio.CH_VOICE,
                                    level=narration_vol,
                                    wait=True)

                target_sequence = "".join([str(random.randint(0,9)) for _ in range(8)])
                user_entry = ""
                self.sat.clear_key()
                await asyncio.sleep(1)
                while user_entry != target_sequence:

                    # Display the code one by one
                    for digit in target_sequence:
                        await self.core.display.update_status("ENTRY CODE:", digit)
                        # TODO Display on matrix as well
                        self.core.audio.play(f"audio/ind/voice/v_{digit}.wav",
                                            self.core.audio.CH_VOICE,
                                            level=narration_vol,
                                            Wait=True)
                        await asyncio.sleep(0.9)
                    self.core.audio.play("audio/ind/voice/keypad_go.wav",
                                        self.core.audio.CH_VOICE,
                                        level=narration_vol,
                                        Wait=True)

                    # Wait for user to enter code via keypad
                    start_time = ticks_ms()
                    while len(user_entry) < 8 and ticks_diff(ticks_ms(), start_time) < 10000:
                        if self.sat.keypad != "N":
                            user_entry += self.sat.keypad
                            self.sat.send_cmd("DSP",user_entry)
                            self.core.audio.play("audio/ind/sfx/keypad_click.wav",
                                                self.core.audio.CH_SFX,
                                                level=0.8)
                            self.sat.clear_key()
                        await asyncio.sleep(0.01)

                    # If it does not match, prompt retry
                    if user_entry != target_sequence:
                        await self.core.display.update_status("AUTH FAILED", "RE-TRANSMITTING")
                        self.core.audio.play("audio/ind/sfx/fail.wav",
                                            self.core.audio.CH_SFX,
                                            level=0.6,
                                            Interrupt=True)
                        self.core.audio.play("audio/ind/voice/keypad_retry.wav",
                                            self.core.audio.CH_VOICE,
                                            level=narration_vol,
                                            Wait=True)
                        user_entry = ""
                        self.sat.send_cmd("DSP","********")
                        await asyncio.sleep(2)

                # Success
                await self.core.display.update_status("AUTH CODE ACCEPTED", "ACCESS GRANTED")
                self.core.audio.play("audio/ind/sfx/success.wav",
                                    self.core.audio.CH_SFX,
                                    level=0.8,
                                    Interrupt=True)
                self.core.current_mode_step += 1

            # --- STEP 4: ALIGN BRACKETS ---
            elif self.step == 4:
                await self.core.display.update_status("ALIGN BRACKETS", "DUAL ENCODER SYNC")
                self.core.audio.play("audio/ind/atmo/hum_3.wav",
                                    self.core.audio.CH_ATMO,
                                    level=0.8,
                                    loop=True,
                                    Interrupt=True)
                self.core.audio.play("audio/ind/voice/narration_4.wav",
                                    self.core.audio.CH_VOICE,
                                    level=narration_vol,
                                    Wait=True)

                self.sat.reset_encoder(0)       # Left bracket starts at LED 0
                self.core.hid.reset_encoder(7)   # Right bracket starts at LED 7

                target_pos = random.randint(2, 5)  # Target position between 2 and 5
                last_target_move = ticks_ms()
                lock_start_time = None

                while True:
                    current_time = ticks_ms()

                    # Dynamic target movement every 3-5 seconds
                    if ticks_diff(current_time, last_target_move) > random.randint(3000, 5000):
                        move = random.choice([-1, 1])
                        new_target = max(1, min(6, target_pos + move))
                        if new_target != target_pos:
                            target_pos = new_target
                            self.core.audio.play("audio/ind/sfx/target_shift.wav",
                                                self.core.audio.CH_SFX,
                                                level=0.5)
                        last_target_move = current_time

                    # Get Input Positions (0-7)
                    left_pos = self.sat.get_scaled_encoder_pos(multiplier=1.0, wrap=8)
                    right_pos = self.core.hid.get_scaled_encoder_pos(multiplier=1.0, wrap=8)

                    # Logic Checks
                    # Collision (Critical Failure)
                    if left_pos >= right_pos:
                        self.core.matrix.fill(Palette.RED, show=True, anim_mode="BLINK", speed=2.0)
                        await self.core.display.update_status("CRITICAL ERROR", "BRACKET COLLISION")
                        self.core.audio.play("audio/ind/sfx/crash.wav",
                                            self.core.audio.CH_SFX,
                                            level=1.0)
                        await asyncio.sleep(2)
                        return await self.game_over()

                    # Check if brackets are correctly aligned around target
                    is_aligned = (left_pos == (target_pos - 1)) and (right_pos == (target_pos + 1))

                    # Render Matrix Visuals
                    self.core.matrix.fill(Palette.OFF, show=True)

                    # Draw Target
                    if is_aligned:
                        for y in range(2, 6):
                            self.core.matrix.draw_pixel(
                                target_pos,
                                y,
                                Palette.GREEN,
                                show=False,
                                anim_mode="PULSE",
                                speed=3.0
                            )
                    else:
                        for y in range(2, 6):
                            self.core.matrix.draw_pixel(
                                target_pos,
                                y,
                                Palette.YELLOW,
                                show=False
                            )

                    # Draw Left Bracket
                    if is_aligned:
                        for y in range(1, 7):
                            self.core.matrix.draw_pixel(
                                left_pos,
                                y,
                                Palette.GREEN,
                                show=False,
                                anim_mode="PULSE",
                                speed=3.0
                            )
                    else:
                        for y in range(1, 7):
                            self.core.matrix.draw_pixel(
                                left_pos,
                                y,
                                Palette.CYAN,
                                show=False
                            )

                    # Draw Right Bracket
                    if is_aligned:
                        for y in range(1, 7):
                            self.core.matrix.draw_pixel(
                                right_pos,
                                y,
                                Palette.GREEN,
                                show=False,
                                anim_mode="PULSE",
                                speed=3.0
                            )
                    else:
                        for y in range(1, 7):
                            self.core.matrix.draw_pixel(
                                right_pos,
                                y,
                                Palette.MAGENTA,
                                show=False
                            )

                    self.core.matrix.pixels.show()

                    if is_aligned:
                        if lock_start_time is None:
                            lock_start_time = current_time
                        elif ticks_diff(current_time, lock_start_time) >= 1000:
                            # Held alignment for 1 second - Success
                            break
                    else:
                        lock_start_time = None

                    await asyncio.sleep(0.05)

                # --- VICTORY STATE ---
                return await self.victory()

            await asyncio.sleep(0.1)

        # --- Somehow we have more steps complete than total steps ---
        return "SUCCESS"
