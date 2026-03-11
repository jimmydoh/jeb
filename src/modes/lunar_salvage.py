# File: src/modes/lunar_salvage.py
"""Lunar Salvage – Core-Only Momentum Physics Game.

A physics-based piloting game where the player fights gravity to land a
ship on shifting platforms and collect salvage using a tractor beam.

Hardware (Core Only):
    - 16x16 Matrix: Pixel-art ship under constant gravity with a 2-pixel
      landing pad on the bottom row.
    - Rotary Encoder: Rotates the ship a full 360 degrees.
    - Button 0 (hold): Main Thruster – pushes the ship in the direction
      it is currently facing.
    - Button 1 (hold): Tractor Beam – collect salvage when hovering
      slowly over the landing pad.

Gameplay:
    Gravity constantly pulls the ship downward.  The player must feather
    the thruster (Button 0) to counteract gravity, rotate the ship to aim
    with the encoder, and gently position the ship over the 2-pixel
    landing pad.  Holding Button 1 while hovering softly over the pad
    starts the tractor beam collection sequence.  Hitting any wall or the
    floor at too high a speed results in a crash.  Each successful salvage
    moves the pad and increases the level (and gravity).
"""

import asyncio
import math
import random

from adafruit_ticks import ticks_ms, ticks_diff

from utilities.palette import Palette
from utilities import tones
from .game_mode import GameMode


class LunarSalvage(GameMode):
    """Lunar Salvage – gravity/momentum piloting game (Core only)."""

    # --- Matrix dimensions ---
    MATRIX_WIDTH = 16
    MATRIX_HEIGHT = 16

    # --- Physics constants ---
    GRAVITY_BASE = 0.022          # pixels / frame² downward acceleration
    GRAVITY_PER_LEVEL = 0.004     # extra gravity per level gained
    THRUST_FORCE = 0.10           # pixels / frame² applied in heading direction
    MAX_VELOCITY = 1.5            # absolute velocity cap per axis
    BOUNCE_DAMPING = 0.45         # fraction of speed retained after a wall bounce
    CRASH_SPEED = 0.42            # landing speed (px/frame) above which = crash

    # --- Controls ---
    DEGREES_PER_TICK = 11.25      # 32 encoder ticks = full 360°

    # --- Tractor beam ---
    PAD_WIDTH = 2                 # landing pad width in pixels
    TRACTOR_HOVER_ROWS = 3        # vertical proximity required (rows from floor)
    TRACTOR_HOLD_FRAMES = 45      # consecutive frames of beam required (~1.5 s)

    # --- Difficulty modifiers ---
    _DIFFICULTY = {
        "EASY":   {"gravity_mult": 0.7,  "crash_mult": 1.3},
        "NORMAL": {"gravity_mult": 1.0,  "crash_mult": 1.0},
        "HARD":   {"gravity_mult": 1.4,  "crash_mult": 0.85},
        "INSANE": {"gravity_mult": 2.0,  "crash_mult": 0.7},
    }

    def __init__(self, core):
        super().__init__(core, "LUNAR SALVAGE", "Physics Pilot Game")
        self._gravity_mult = 1.0
        self._crash_speed = self.CRASH_SPEED
        self._reset_ship()
        self._new_pad()
        self._tractor_hold = 0
        self._salvage_count = 0

    async def run_tutorial(self):
        """
        A guided, non-interactive demonstration of Lunar Salvage.

        The Voiceover Script (audio/tutes/lunar_tute.wav) ~ 35 seconds:
            [0:00] "Welcome to Lunar Salvage. A physics-based test of momentum."
            [0:05] "Gravity will constantly pull your ship down."
            [0:09] "Use the dial to rotate your ship."
            [0:13] "Hold button one to fire your main thruster and fight gravity."
            [0:19] "Your goal is to hover gently over the cyan salvage pad."
            [0:24] "Once hovering safely over the pad, hold button two to activate the tractor beam."
            [0:30] "Collect the salvage, but don't hit the walls too hard. Good luck!"
            [0:35] (End of file)
        """
        await self.core.clean_slate()
        self.game_state = "TUTORIAL"

        # 1. Start the voiceover track
        self.core.audio.play("audio/tutes/lunar_tute.wav", bus_id=self.core.audio.CH_VOICE)

        # Setup safe initial state
        self.ship_x = 8.0
        self.ship_y = 2.0
        self.vel_x = 0.0
        self.vel_y = 0.0
        self.angle = 90.0  # Pointing right
        self._pad_x = 8
        self._tractor_time = 0.0
        self.crashed = False

        # Internal helper to step physics for the tutorial
        async def sim_frames(frames, thrust=False, tractor=False, angle_adj=0):
            for _ in range(frames):
                self.angle = (self.angle + angle_adj) % 360.0
                rad = math.radians(self.angle)

                # Apply Gravity
                self.vel_y += 0.8 * 0.03 # _GRAVITY * delta_s

                if thrust:
                    self.vel_x += math.sin(rad) * 1.5 * 0.03 # _THRUST * delta_s
                    self.vel_y -= math.cos(rad) * 1.5 * 0.03
                    # Thrust visuals
                    if random.random() < 0.5:
                        self.core.matrix.draw_pixel(
                            int(self.ship_x - math.sin(rad)*2),
                            int(self.ship_y + math.cos(rad)*2),
                            Palette.ORANGE, show=False
                        )

                self.ship_x += self.vel_x * 0.03
                self.ship_y += self.vel_y * 0.03

                # Floor collision logic
                if self.ship_y >= self.core.matrix.height - 1:
                    self.ship_y = self.core.matrix.height - 1
                    self.vel_y = 0.0
                    self.vel_x *= 0.8

                self._render(tractor_active=tractor, frame_count=int(ticks_ms()/33))
                self.core.matrix.show_frame()
                await asyncio.sleep(0.03)

        # [0:00 - 0:05] "Welcome to Lunar Salvage. A physics-based test of momentum."
        self.core.display.update_status("LUNAR SALVAGE", "MOMENTUM PHYSICS")

        # We assume you added LUNAR_SALVAGE to icons.py! If not, change to "DEFAULT"
        self.core.matrix.show_icon("LUNAR_SALVAGE", clear=True)
        await asyncio.sleep(5.0)

        # [0:05 - 0:09] "Gravity will constantly pull your ship down."
        self.core.display.update_status("GRAVITY", "PULLS YOU DOWN")
        self.angle = 0 # Point UP
        await sim_frames(110) # Let it fall gracefully

        # [0:09 - 0:13] "Use the dial to rotate your ship."
        self.core.display.update_status("NAVIGATION", "DIAL TO ROTATE")
        await sim_frames(40, angle_adj=3)  # Rotate Right
        await sim_frames(40, angle_adj=-3) # Rotate Left

        # [0:13 - 0:19] "Hold button one to fire your main thruster..."
        self.core.display.update_status("THRUST", "HOLD B1 TO FIRE")
        self.core.leds.solid_led(0, Palette.ORANGE) # Light up Button 0
        await sim_frames(120, thrust=True) # Fire thruster to arrest fall
        self.core.leds.off_led(0)

        # [0:19 - 0:24] "Your goal is to land gently on the cyan salvage pad."
        self.core.display.update_status("SALVAGE PAD", "LAND GENTLY")
        self.angle = 180 # Point DOWN
        await sim_frames(60, thrust=True) # Push down toward pad
        self.angle = 0   # Point UP
        await sim_frames(70, thrust=True) # Retro-burn to slow down
        await sim_frames(60) # Settle onto the pad

        # [0:24 - 0:30] "Once hovering safely over the pad, hold button two..."
        self.core.display.update_status("TRACTOR BEAM", "HOLD B2 TO COLLECT")
        self.core.leds.solid_led(1, Palette.CYAN) # Light up Button 1

        for _ in range(80):
            self._tractor_time += 0.03
            await sim_frames(1, thrust=True, tractor=True)

        # Collection Success
        self.core.display.update_status("SALVAGE SECURED!", "+100 PTS")
        self.core.matrix.fill(Palette.GREEN, show=True)
        self.core.synth.play_note(880.0, "SUCCESS", duration=0.1)
        await asyncio.sleep(1.0)
        self.core.leds.off_led(1)

        # [0:30 - 0:35] "Collect the salvage, but don't hit the walls too hard..."
        self.core.display.update_status("CAUTION", "WATCH YOUR SPEED")
        self.core.matrix.clear()
        self.core.matrix.show_frame()

        # Wait for the audio track to finish naturally
        if hasattr(self.core.audio, 'wait_for_bus'):
            await self.core.audio.wait_for_bus(self.core.audio.CH_VOICE)
        else:
            await asyncio.sleep(4.0)

        # Clean up and return to the menu
        await self.core.clean_slate()
        return "TUTORIAL_COMPLETE"

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _reset_ship(self):
        """Reset ship to the top-centre of the field."""
        self.ship_x = float(self.MATRIX_WIDTH // 2)
        self.ship_y = 2.0
        self.vel_x = 0.0
        self.vel_y = 0.0
        self.angle = 90.0  # Start pointing upward

    def _new_pad(self):
        """Spawn a landing pad at a random bottom position."""
        # Keep pad away from corners so it is always reachable
        self._pad_x = random.randint(2, self.MATRIX_WIDTH - self.PAD_WIDTH - 2)

    def _gravity(self):
        """Return the current gravity value adjusted for level and difficulty."""
        base = self.GRAVITY_BASE + self.level * self.GRAVITY_PER_LEVEL
        return base * self._gravity_mult

    def _speed(self):
        """Return the magnitude of the ship's current velocity."""
        return math.sqrt(self.vel_x ** 2 + self.vel_y ** 2)

    def _over_pad(self):
        """Return True when the ship is hovering over the landing pad."""
        sx = round(self.ship_x)
        sy = round(self.ship_y)
        # Must be in the bottom few rows
        if sy < self.MATRIX_HEIGHT - self.TRACTOR_HOVER_ROWS:
            return False
        # Must overlap the pad horizontally
        return self._pad_x <= sx <= self._pad_x + self.PAD_WIDTH - 1

    def _update_physics(self, thrust_on):
        """Apply gravity, optional thrust, and integrate position."""
        # Gravity (positive = downward in screen coords)
        self.vel_y += self._gravity()

        # Thrust in the current heading direction.
        # Angle is measured counter-clockwise from the positive X-axis, with
        # screen Y increasing downward – so thrust "up" (angle=90°) subtracts
        # from vel_y to move against gravity.
        if thrust_on:
            angle_rad = math.radians(self.angle)
            self.vel_x += math.cos(angle_rad) * self.THRUST_FORCE
            self.vel_y -= math.sin(angle_rad) * self.THRUST_FORCE

        # Velocity cap
        self.vel_x = max(-self.MAX_VELOCITY, min(self.MAX_VELOCITY, self.vel_x))
        self.vel_y = max(-self.MAX_VELOCITY, min(self.MAX_VELOCITY, self.vel_y))

        # Integrate
        self.ship_x += self.vel_x
        self.ship_y += self.vel_y

    def _check_wall_collision(self):
        """Bounce the ship off boundaries. Returns True if the impact was fatal."""
        crashed = False

        # Left wall
        if self.ship_x < 0:
            self.ship_x = 0.0
            if abs(self.vel_x) > self._crash_speed:
                crashed = True
            self.vel_x = abs(self.vel_x) * self.BOUNCE_DAMPING

        # Right wall
        if self.ship_x >= self.MATRIX_WIDTH:
            self.ship_x = float(self.MATRIX_WIDTH - 1)
            if abs(self.vel_x) > self._crash_speed:
                crashed = True
            self.vel_x = -abs(self.vel_x) * self.BOUNCE_DAMPING

        # Top wall
        if self.ship_y < 0:
            self.ship_y = 0.0
            if abs(self.vel_y) > self._crash_speed:
                crashed = True
            self.vel_y = abs(self.vel_y) * self.BOUNCE_DAMPING

        # Bottom wall / floor
        if self.ship_y >= self.MATRIX_HEIGHT:
            self.ship_y = float(self.MATRIX_HEIGHT - 1)
            if self.vel_y > self._crash_speed:
                crashed = True
            self.vel_y = -abs(self.vel_y) * self.BOUNCE_DAMPING

        return crashed

    def _render(self, tractor_active=False, frame_count=0):
        """Render the current game state onto the LED matrix."""
        self.core.matrix.clear()

        # Landing pad
        pad_color = Palette.GREEN
        if tractor_active and self._over_pad():
            # Blink pad to show the beam is active
            pad_color = Palette.YELLOW if (frame_count // 4) % 2 == 0 else Palette.GREEN
        for i in range(self.PAD_WIDTH):
            px = self._pad_x + i
            if 0 <= px < self.MATRIX_WIDTH:
                self.core.matrix.draw_pixel(px, self.MATRIX_HEIGHT - 1, pad_color)

        # Tractor beam (vertical line from ship to pad when active and overhead)
        if tractor_active and self._over_pad():
            beam_x = int(round(self.ship_x))
            sy_int = int(round(self.ship_y))
            for by in range(sy_int + 1, self.MATRIX_HEIGHT - 1):
                if 0 <= beam_x < self.MATRIX_WIDTH:
                    self.core.matrix.draw_pixel(beam_x, by, Palette.BLUE)

        # Ship body pixel
        sx = int(round(self.ship_x))
        sy = int(round(self.ship_y))
        ship_color = Palette.BLUE if tractor_active else Palette.CYAN
        if 0 <= sx < self.MATRIX_WIDTH and 0 <= sy < self.MATRIX_HEIGHT:
            self.core.matrix.draw_pixel(sx, sy, ship_color)

        # Ship nose / heading indicator
        angle_rad = math.radians(self.angle)
        nose_x = int(round(self.ship_x + math.cos(angle_rad)))
        nose_y = int(round(self.ship_y - math.sin(angle_rad)))
        if 0 <= nose_x < self.MATRIX_WIDTH and 0 <= nose_y < self.MATRIX_HEIGHT:
            if nose_x != sx or nose_y != sy:
                self.core.matrix.draw_pixel(nose_x, nose_y, Palette.YELLOW)

        # Draw velocity vector (dim pixel showing momentum direction)
        if abs(self.vel_x) > 0.5 or abs(self.vel_y) > 0.5:
            vec_x = sx + int(self.vel_x * 1.5)
            vec_y = sy + int(self.vel_y * 1.5)
            if 0 <= vec_x < self.MATRIX_WIDTH and 0 <= vec_y < self.MATRIX_HEIGHT:
                self.core.matrix.draw_pixel(vec_x, vec_y, Palette.GRAY, brightness=0.2)

        self.core.matrix.show_frame()

    # ------------------------------------------------------------------
    # Game loop
    # ------------------------------------------------------------------

    async def run(self):
        """Main game loop."""
        self.difficulty = self.core.data.get_setting("LUNAR_SALVAGE", "difficulty", "NORMAL")
        self.variant = self.difficulty

        diff_cfg = self._DIFFICULTY.get(self.difficulty, self._DIFFICULTY["NORMAL"])
        self._gravity_mult = diff_cfg["gravity_mult"]
        self._crash_speed = self.CRASH_SPEED * diff_cfg["crash_mult"]

        self.core.display.use_standard_layout()
        self.core.display.update_status("LUNAR SALVAGE", "HOLD B0: THRUST")
        self.core.display.update_footer("ENC:ROTATE  B1:BEAM")
        asyncio.create_task(self.core.synth.play_sequence(tones.POWER_UP, patch="SCANNER"))
        await asyncio.sleep(2.0)

        self.core.hid.reset_encoder(0)
        self.score = 0
        self.level = 0
        self._salvage_count = 0
        self._reset_ship()
        self._new_pad()
        self._tractor_hold = 0

        last_tick = ticks_ms()
        frame_count = 0
        game_running = True

        while game_running:
            now = ticks_ms()
            delta_ms = ticks_diff(now, last_tick)

            if delta_ms >= 33:  # ~30 FPS target
                last_tick = now
                frame_count += 1

                # --- Controls ---
                encoder_pos = self.core.hid.encoder_positions[0]
                self.angle = (encoder_pos * self.DEGREES_PER_TICK) % 360.0

                thrust_on = self.core.hid.is_button_pressed(0)
                tractor_on = self.core.hid.is_button_pressed(1)

                # --- Engine sound while thrusting ---
                if thrust_on:
                    # Throttle audio to ~10Hz to protect the I2C bus
                    if now - getattr(self, '_last_thrust_audio', 0) > 100:
                        freq = 100.0 + abs(self.vel_y) * 60.0
                        self.core.synth.play_note(freq, "ENGINE_HUM", duration=0.1) # matched duration to throttle
                        self._last_thrust_audio = now

                # --- Physics ---
                self._update_physics(thrust_on)

                # --- Boundary collision ---
                crashed = self._check_wall_collision()
                if crashed:
                    self.core.matrix.fill(Palette.RED)
                    self.core.matrix.show_frame()
                    asyncio.create_task(self.core.synth.play_sequence(tones.GAME_OVER))
                    await asyncio.sleep(0.3)
                    return await self.game_over()

                # --- Tractor beam / salvage collection ---
                if tractor_on and self._over_pad():
                    spd = self._speed()
                    if spd > self._crash_speed:
                        # Came in too hot while trying to tractor – crash
                        self.core.matrix.fill(Palette.RED)
                        self.core.matrix.show_frame()
                        asyncio.create_task(self.core.synth.play_sequence(tones.GAME_OVER))
                        await asyncio.sleep(0.3)
                        return await self.game_over()
                    # Slowly pulling in salvage
                    self._tractor_hold += 1
                    if self._tractor_hold >= self.TRACTOR_HOLD_FRAMES:
                        # Successful salvage!
                        self._salvage_count += 1
                        # Bonus points for how gently the player hovered
                        precision_bonus = max(0, int((self._crash_speed - spd) * 200))
                        self.score += 100 + precision_bonus
                        self.level = self._salvage_count

                        self.core.buzzer.play_sequence(tones.UI_CONFIRM)
                        self.core.display.update_status(
                            f"SCORE: {self.score}",
                            f"SALVAGE x{self._salvage_count}!"
                        )
                        await asyncio.sleep(1.0)

                        # Respawn ship and move the pad
                        self._reset_ship()
                        self._new_pad()
                        self._tractor_hold = 0

                        # Flush inputs so the ship doesn't immediately thrust on respawn
                        self.core.hid.flush()
                        last_tick = ticks_ms() # Reset tick so physics don't jump
                else:
                    # Reset beam counter whenever the beam is off or misaligned
                    self._tractor_hold = 0

                # --- HUD update ---
                spd_display = min(99, int(self._speed() * 10))
                beam_label = "BEAM!" if (tractor_on and self._over_pad()) else "FLY  "
                self.core.display.update_status(
                    f"SCORE: {self.score}",
                    f"LV{self.level + 1} SPD:{spd_display:02d} {beam_label}"
                )

                # --- Render ---
                self._render(tractor_on, frame_count)

            await asyncio.sleep(0.01)
