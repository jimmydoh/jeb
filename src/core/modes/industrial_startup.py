""""""

import asyncio
import random
from adafruit_ticks import ticks_ms, ticks_diff

class IndustrialStartup:
    """Industrial Satellite Startup Sequence Mode.
    A multi-phase startup sequence requiring various inputs
    from both the Core and Industrial Satellite box.
    """
    def __init__(self, jeb, sat):
        self.jeb = jeb
        self.sat = sat

    async def run(self):
        """Industrial Satellite Startup Sequence.

            A multi-phase startup sequence requiring various inputs
            from both the Core and Industrial Satellite box.

            Parameters:
                sat (Satellite): Satellite object to use as expansion.

            TODO:
                - Add re-sync of satellite visuals at start of each phase
        """
        # Initial check to confirm Satellite is connected
        narration_vol = 0.8
        active_sat = self.sat
        if not active_sat:
            await self.jeb.display.update_status("ERROR", "SATELLITE OFFLINE")
            return

        if self.jeb.current_mode_step == 0: # Reset step counter on first run
            await self.jeb.display.update_status("LINK ESTABLISHED", "INITIALIZING...")
            self.jeb.audio.play_sfx("hum_industrial_1.wav", voice=0, vol=0.2, loop=True, skip=True)
            self.jeb.audio.play_sfx("voice_industrial_narration_0.wav", voice=2, vol=narration_vol, wait=True)
            self.jeb.current_mode_step += 1

        elif self.jeb.current_mode_step == 1: # STEP 1 - Dual Input
            await self.jeb.display.update_status("INDUSTRIAL CONTROL ONLINE", "HOLD [A] + [L1-DN]")
            self.jeb.audio.play_sfx("hum_industrial_1.wav", voice=0, vol=0.2, loop=True, skip=True)
            self.jeb.audio.play_sfx("voice_industrial_narration_1.wav", voice=2, vol=narration_vol, wait=True)
            while not self.jeb.hid.is_pressed(0,Long=True,Duration=2000) and not active_sat.is_momentary_toggled(0,"U",Long=True,Duration=2000):
                await asyncio.sleep(0.1)
            self.jeb.audio.play_sfx("power_up.wav", voice=1)
            self.jeb.current_mode_step += 1

        elif self.jeb.current_mode_step == 2: # STEP 2 - Toggles
            await self.jeb.display.update_status("INIT SPLINE MODS", "CONFIRM STATES")
            self.jeb.audio.play_sfx("hum_industrial_2.wav", voice=0, vol=0.4, loop=True, skip=False)
            self.jeb.audio.play_sfx("voice_industrial_narration_2.wav", voice=2, vol=narration_vol, wait=True)

            iteration = 0
            total_iterations = 10

            while iteration < total_iterations:
                # Set all toggle LEDs to blue
                for i in range(4):
                    active_sat.send_cmd("LED", f"{i},100,100,255")
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
                await self.jeb.display.update_status(f"PHASE: {iteration+1}/10", "AWAITING SIGNAL...")
                success = False
                wrong_input = False

                while not success and not wrong_input:
                    # Pulse the target LED Amber
                    active_sat.send_cmd("LED", f"{target_idx},255,100,0")
                    await asyncio.sleep(blink_speed)
                    active_sat.send_cmd("LED", f"{target_idx},0,0,0")
                    await asyncio.sleep(blink_speed)
                    # --- CHECK FOR SUCCESS ---
                    if mode == "LATCH":
                        self.jeb.audio.play_sfx(f"voice_industrial_latch_{target_idx}.wav", voice=2, vol=narration_vol, wait=False)
                        if self.sat.is_latching_toggled(target_idx) == required_state:
                            success = True
                    else: # MOMENTARY
                        # Require a 2s hold to ensure it's intentional
                        self.jeb.audio.play_sfx(f"voice_industrial_momentary_{target_idx}.wav", voice=2, vol=narration_vol, wait=False)
                        if self.sat.is_momentary_toggled(m_idx, required_direction, long=True, duration=2000):
                            success = True

                    # --- CHECK FOR WRONG INPUT ---
                    # Check if any OTHER latching toggle changed OR any momentary was touched
                    if self.sat.any_other_input_detected(target_idx):
                        wrong_input = True

                # Handle Result
                if success:
                    iteration += 1
                    self.jeb.audio.play_sfx("sfx_industrial_toggle_confirm.wav", voice=1)
                    self.sat.send_cmd("LED", f"{target_idx},0,255,0")
                    # TODO Add progress animation for matrix
                    await asyncio.sleep(0.5)
                    self.sat.send_cmd("LED", f"{target_idx},100,100,255")

                elif wrong_input:
                    self.jeb.audio.play_sfx("sfx_industrial_toggle_fail.wav", voice=1)
                    # Flash ALL toggle LEDs Red
                    for _ in range(4):
                        self.sat.send_cmd("LED", "ALL,255,0,0")
                        await asyncio.sleep(0.3)
                        self.sat.send_cmd("LED", "ALL,0,0,0")
                        await asyncio.sleep(0.3)
                    # Loop continues, iterations do NOT increase

            # Completed all iterations
            await self.jeb.display.update_status("PHASE COMPLETE", "CORE STABILIZED")
            self.jeb.audio.play_sfx("voice_industrial_toggle_done.wav", voice=2, vol=narration_vol, wait=False)
            # TODO Play Victory Animation
            self.jeb.current_mode_step += 1
            await asyncio.sleep(1)

        elif self.jeb.current_mode_step == 3: # STEP 3 - Keypad Entry
            await self.jeb.display.update_status("AWAIT AUTH CODE", "ADMIN ACCESS")
            self.jeb.audio.play_sfx("hum_industrial_2.wav", voice=0, vol=0.6, loop=True, skip=False)
            self.jeb.audio.play_sfx("voice_industrial_narration_3.wav", voice=2, vol=narration_vol, wait=True)
            target_sequence = "".join([str(random.randint(0,9)) for _ in range(8)])
            user_entry = ""
            active_sat.clear_key()
            await asyncio.sleep(1)
            while user_entry != target_sequence:
                # Display the code one by one
                for digit in target_sequence:
                    await self.jeb.display.update_status("ENTRY CODE:", digit)
                    self.jeb.audio.play_sfx(f"v_{digit}.wav", voice=2)
                    await asyncio.sleep(0.9)
                self.jeb.audio.play_sfx("voice_keypad_go.wav", voice=2)
                # Collect 8 digits
                start_time = ticks_ms()
                while len(user_entry) < 8 and ticks_diff(ticks_ms(), start_time) < 10000:
                    if active_sat.keypad != "N":
                        user_entry += active_sat.keypad
                        active_sat.send_cmd("DSP",user_entry)
                        self.jeb.audio.play_sfx("click.wav")
                        active_sat.clear_key()
                    await asyncio.sleep(0.01)
                if user_entry != target_sequence:
                    await self.jeb.display.update_status("AUTH FAILED", "RE-TRANSMITTING")
                    self.jeb.audio.play_sfx("fail.wav", voice=1)
                    self.jeb.audio.play_sfx("v_retry.wav", voice=2)
                    user_entry = ""
                    active_sat.send_cmd("DSP","********")
                    await asyncio.sleep(2)
            self.jeb.current_mode_step += 1

        elif self.jeb.current_mode_step == 4: # STEP 4 - Bracketing
            await self.jeb.display.update_status("ALIGN BRACKETS", "DUAL ENCODER SYNC")
            self.jeb.audio.play_sfx("hum_industrial_3.wav", voice=0, vol=0.8, loop=True, skip=False)
            self.jeb.audio.play_sfx("voice_industrial_narration_4.wav", voice=2, vol=narration_vol, wait=True)

            active_sat.reset_encoder(0) # Left bracket starts at LED 0
            self.jeb.hid.reset_encoder(7) # Right bracket starts at LED 7
            target_pos = random.randint(1, 6)
            last_move = ticks_ms()

            while not self.jeb.hid.is_pressed(4,Long=True,Duration=500) or active_sat.is_pressed(0,Long=True,Duration=500):
                # Dynamic Target Movement
                # Every 2-4 seconds, the target attempts to shift
                if ticks_diff(ticks_ms(), last_move) > random.randint(2000, 4000):
                    move = random.choice([-1, 1])
                    # Keep target within bounds [1, 6]
                    target_pos = max(1, min(6, target_pos + move))
                    last_move = ticks_ms()
                    self.jeb.audio.play_sfx("target_shift.wav", voice=1, vol=0.3)

                # Get positions from both hardware sources
                # Left Bracket (Sat) and Right Bracket (Core)
                left_pos = active_sat.get_scaled_encoder_pos(multiplier=1.0, wrap=8)
                right_pos = self.jeb.hid.get_scaled_encoder_pos(multiplier=1.0, wrap=8)

                # Update neobar visuals
                # TODO Replace neobar with matrix

                # Collision Detection (Critical Failure)
                if left_pos >= right_pos:
                    await self.jeb.display.update_status("CRITICAL ERROR", "BRACKET COLLISION")
                    self.jeb.audio.play_sfx("sounds/crash.wav", voice=1)
                    # Flash Red and exit
                    # TODO CRITICAL Fail Animation
                    await asyncio.sleep(2)
                    return "FAILURE"

                await asyncio.sleep(0.05)

            # Validation: Success if Target is bracketed by left and right
            # OR if both encoders are specifically set to a target value
            if left_pos == (target_pos - 1) and right_pos == (target_pos + 1):
                self.jeb.audio.play_sfx("hum_industrial_final.wav", voice=0, vol=0.5, loop=True, skip=False)
                self.jeb.audio.play_sfx("voice_industrial_narration_success.wav", voice=2, vol=narration_vol, wait=False)
                # TODO Play victory animation
                self.jeb.current_mode_step += 1
            else:
                await self.jeb.display.update_status("ALIGNMENT FAILED", "EMERGENCY SHUTDOWN")
                self.jeb.audio.play_sfx("hum_industrial_3.wav", voice=0, vol=1.0, loop=True, skip=True)
                self.jeb.audio.set_volume(0,1.0)
                self.jeb.audio.play_sfx("voice_industrial_narration_fail.wav", voice=2, vol=narration_vol, wait=False)
                self.jeb.audio.play_sfx("sfx_industrial_alarm.wav", voice=1, vol=1.0)
                await asyncio.sleep(3)
