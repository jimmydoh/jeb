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
        self._pad_x = 0
        self._tractor_hold = 0
        self._salvage_count = 0

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

        # Thrust in the current heading direction
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
                    freq = 100.0 + abs(self.vel_y) * 60.0
                    self.core.synth.play_note(freq, "ENGINE_HUM", duration=0.05)

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
                        await asyncio.sleep(0.6)

                        # Respawn ship and move the pad
                        self._reset_ship()
                        self._new_pad()
                        self._tractor_hold = 0
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
