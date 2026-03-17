"""Vanguard Override Game Mode - Hardware-Managed Vertical Shmup."""

import asyncio
import random
import math

from adafruit_ticks import ticks_ms, ticks_diff

from utilities.palette import Palette
from utilities import tones

from .game_mode import GameMode

# ---------------------------------------------------------------------------
# Weapon type constants
# ---------------------------------------------------------------------------
WEAPON_LASER   = "LASER"    # Rotary POS A: single fast forward laser
WEAPON_SPREAD  = "SPREAD"   # Rotary POS B: 3-way spread shot
WEAPON_MISSILE = "MISSILE"  # Rotary POS C: homing missiles

# ---------------------------------------------------------------------------
# Hardware indices (Industrial Satellite / SAT-01 layout)
# ---------------------------------------------------------------------------
_SHIELD_TOGGLE_START = 0    # Left 4 latching toggles → shield power (0-3)
_SHIELD_TOGGLE_END   = 3    # inclusive
_WEAPON_TOGGLE_START = 4    # Right 4 latching toggles → weapon power (4-7)
_WEAPON_TOGGLE_END   = 7    # inclusive
_SW_ROTARY_A = 10           # 3-position rotary switch POS A (Exp2 pin 4)
_SW_ROTARY_B = 11           # 3-position rotary switch POS B (Exp2 pin 5)
_MT_EMP      = 0            # Momentary toggle index – EMP smart bomb
_BTN_FIRE    = 0            # Core big-red-button index – primary fire
_ENC_SHIP    = 0            # Core encoder index – ship X-axis movement

# ---------------------------------------------------------------------------
# Gameplay / physics constants
# ---------------------------------------------------------------------------
_MATRIX_WIDTH  = 16
_MATRIX_HEIGHT = 16

_OVERLOAD_THRESHOLD  = 7     # Total toggles UP that triggers reactor overload

_EMP_CHARGE_MAX      = 100.0
_EMP_CHARGE_RATE     = 4.0   # Charge units per second (fills in ~25 s)

_FIRE_INTERVAL_BASE  = 0.35  # Seconds between shots at weapon power 0
_FIRE_INTERVAL_STEP  = 0.05  # Interval reduction per weapon power level

_PLAYER_BULLET_SPEED = 10.0  # Rows per second, upward
_ENEMY_SPEED_BASE    = 2.5   # Rows per second, downward
_ENEMY_BULLET_SPEED  = 5.0   # Rows per second, downward

_SPAWN_INTERVAL_BASE = 2.0   # Seconds between enemy spawns
_ENEMY_SHOOT_CHANCE  = 0.015 # Per-enemy probability to fire per frame (~60 fps)
_SHIELD_COOLDOWN     = 1.5   # Seconds shield inactive after absorbing a hit

_SCORE_KILL          = 10    # Points for destroying one enemy
_SCORE_EMP_KILL      = 15    # Points per enemy cleared by EMP
_SCORE_WAVE          = 50    # Bonus points every 10 enemies destroyed

# ---------------------------------------------------------------------------
# Difficulty parameter table
# ---------------------------------------------------------------------------
_DIFF_PARAMS = {
    "NORMAL": {"speed_scale": 1.0, "spawn_scale": 1.0, "lives": 3, "shoot_scale": 1.0},
    "HARD":   {"speed_scale": 1.4, "spawn_scale": 0.7, "lives": 2, "shoot_scale": 1.5},
    "INSANE": {"speed_scale": 1.8, "spawn_scale": 0.45, "lives": 1, "shoot_scale": 2.5},
}


class VanguardOverride(GameMode):
    """Vanguard Override – Hardware-Managed Vertical Shmup.

    A top-down vertical scrolling shooter where the player must constantly
    manage ship subsystems via the Industrial Satellite while dodging and
    firing at incoming enemy formations.

    Hardware:
        Core:
            - 16×16 Matrix: scrolling game field; player ship locked to bottom row
            - OLED: score, HP, power-management status
            - Rotary Encoder (0): ship X-axis movement
            - Big Red Button (0): primary fire

        Industrial Satellite (SAT-01):
            - 14-Segment Display: EMP charge level
            - Latching Toggles 0-3 (left 4): shield power – absorb incoming hits
            - Latching Toggles 4-7 (right 4): weapon power – fire rate & spread
            - Total toggles ≥ 7 → reactor overload, weapons disabled
            - 3-Position Rotary Switch (indices 10-11):
                POS A = Forward Laser, POS B = Wide Spread, POS C = Homing Missiles
            - Momentary Toggle (0): EMP Smart Bomb (only when charge is full)
    """

    def __init__(self, core):
        super().__init__(core, "VANGUARD OVERRIDE", "Hardware-Managed Vertical Shmup")
        self.sat = None
        for sat in self.core.satellites.values():
            if sat.sat_type_name == "INDUSTRIAL":
                self.sat = sat
                break

        # Ship state
        self.ship_x = _MATRIX_WIDTH // 2
        self.ship_hp = 3

        # Active entity lists
        self.bullets = []        # player projectiles: {'x': float, 'y': float, 'dx': int, 'type': str}
        self.enemies = []        # enemy ships: {'x': float, 'y': float, 'hp': int}
        self.enemy_bullets = []  # enemy projectiles: {'x': float, 'y': float}

        # EMP system
        self.emp_charge = 0.0
        self._emp_triggered = False

        # Timing state
        self._last_fire_time = 0.0
        self._spawn_timer = 0.0
        self._shield_cooldown_timer = 0.0   # seconds remaining on shield cooldown
        self._invincible_timer = 0.0        # brief invincibility after taking a hit
        self._last_tick_ms = 0
        self._kill_count = 0
        self._last_wave_bonus_at = 0        # kill count at which last wave bonus was awarded

        # Power management state
        self._overloaded = False
        self._weapon_type = WEAPON_LASER
        self._last_led_shield = [None] * 4
        self._last_led_weapon = [None] * 4

        # Difficulty params (set in run())
        self._speed_scale = 1.0
        self._spawn_scale = 1.0
        self._shoot_scale = 1.0

        self._last_seg_text = ""

    # ------------------------------------------------------------------
    # Tutorial
    # ------------------------------------------------------------------

    async def run_tutorial(self):
        """Guided demo of Vanguard Override mechanics.

        The Voiceover Script (audio/tutes/vanguard_tute.wav) ~ 40 seconds:
            [0:00] "Pilot, welcome to Vanguard Override. Enemies approach from above."
            [0:05] "Turn the dial to fly your ship left and right. Press the big red button to fire."
            [0:11] "Your weapon type is set by the three-position rotary switch."
            [0:16] "Position A fires a forward laser. Position B fires a wide spread."
            [0:21] "Position C launches homing missiles that track the nearest enemy."
            [0:26] "The left four toggles route power to shields, absorbing hits. The right four boost weapons."
            [0:32] "Flip too many toggles at once and the reactor overloads, disabling your weapons."
            [0:37] "When the charge display is full, throw the momentary switch for an EMP smart bomb."
            [0:40] (End of file)
        """
        await self.core.clean_slate()

        if not self.sat or not self.sat.is_active:
            self.core.display.update_status("VANGUARD OVERRIDE", "SAT OFFLINE - ABORT")
            await asyncio.sleep(2)
            return "TUTORIAL_FAILED"

        self.game_state = "TUTORIAL"
        self.core.audio.play("audio/tutes/vanguard_tute.wav", bus_id=self.core.audio.CH_VOICE)

        # Reset state for demo
        self.ship_x = 8
        self.bullets.clear()
        self.enemies.clear()
        self.enemy_bullets.clear()
        self.emp_charge = 0.0
        self.ship_hp = 3
        self._overloaded = False

        # ── [0:00-0:05] Welcome ───────────────────────────────────────────────
        self.core.display.update_header("VANGUARD OVERRIDE")
        self.core.display.update_status("INCOMING ENEMIES", "STAND BY PILOT")
        self.core.matrix.show_icon("VANGUARD_OVERRIDE", clear=True)
        self.core.buzzer.play_sequence(tones.POWER_UP)
        await asyncio.sleep(5.0)

        # ── [0:05-0:11] Movement + firing demo ───────────────────────────────
        self.core.display.update_status("TURN DIAL TO MOVE", "BIG BTN = FIRE")
        self.core.matrix.clear()
        # Seed a single enemy
        self.enemies.append({'x': 8.0, 'y': 1.0, 'hp': 2})

        for step in range(60):
            delta_s = 0.05
            self.ship_x = 8 + int(4 * math.sin(step * 0.2))
            self._update_bullets(delta_s)
            self._update_enemies(delta_s)
            # Occasionally fire
            if step % 10 == 0:
                self.bullets.append({'x': float(self.ship_x), 'y': float(_MATRIX_HEIGHT - 2),
                                     'dx': 0, 'type': WEAPON_LASER})
            self._render()
            await asyncio.sleep(delta_s)

        self.bullets.clear()

        # ── [0:11-0:26] Weapon type demo ────────────────────────────────────
        self.core.display.update_status("ROTARY = WEAPON", "POS A: LASER")
        self.enemies.clear()
        self.enemies.append({'x': 8.0, 'y': 2.0, 'hp': 3})
        self.enemies.append({'x': 3.0, 'y': 3.0, 'hp': 2})
        self.enemies.append({'x': 13.0, 'y': 3.0, 'hp': 2})
        self._weapon_type = WEAPON_LASER

        for step in range(60):
            delta_s = 0.05
            if step == 20:
                self.core.display.update_status("ROTARY = WEAPON", "POS B: SPREAD")
                self._weapon_type = WEAPON_SPREAD
            elif step == 40:
                self.core.display.update_status("ROTARY = WEAPON", "POS C: MISSILES")
                self._weapon_type = WEAPON_MISSILE
            if step % 8 == 0:
                self._spawn_player_bullets()
            self._update_bullets(delta_s)
            self._update_enemies(delta_s)
            self._render()
            await asyncio.sleep(delta_s)

        self.bullets.clear()
        self.enemies.clear()

        # ── [0:26-0:37] Power management demo ───────────────────────────────
        self.core.display.update_status("TOGGLES=POWER", "LEFT=SHIELD R=WEAPON")
        self.enemies.append({'x': 8.0, 'y': 4.0, 'hp': 2})
        self.enemy_bullets.append({'x': 8.0, 'y': 8.0})

        for step in range(60):
            delta_s = 0.05
            if step == 30:
                self.core.display.update_status("OVERLOAD WARNING", "TOO MANY TOGGLES!")
            self._update_enemy_bullets(delta_s)
            self._render()
            await asyncio.sleep(delta_s)

        self.enemy_bullets.clear()

        # ── [0:37-0:40] EMP demo ─────────────────────────────────────────────
        self.core.display.update_status("EMP CHARGE FULL", "THROW SWITCH: BOMB!")
        self.emp_charge = _EMP_CHARGE_MAX
        self._update_segment_display()
        self.enemies.clear()
        for _ in range(6):
            self.enemies.append({'x': float(random.randint(0, 15)),
                                  'y': float(random.randint(1, 10)),
                                  'hp': 1})
        for _ in range(3):
            self.enemy_bullets.append({'x': float(random.randint(0, 15)),
                                        'y': float(random.randint(1, 12))})

        self._render()
        await asyncio.sleep(1.0)

        # Simulate EMP detonation
        self.core.matrix.fill(Palette.WHITE, show=True)
        asyncio.create_task(self.core.synth.play_sequence(tones.FIREBALL, patch="ALARM"))
        await asyncio.sleep(0.15)
        self.enemies.clear()
        self.enemy_bullets.clear()
        self.emp_charge = 0.0
        self._render()
        await asyncio.sleep(1.5)

        await self.core.clean_slate()
        return "TUTORIAL_COMPLETE"

    # ------------------------------------------------------------------
    # Main game loop
    # ------------------------------------------------------------------

    async def run(self):
        """Main Vanguard Override game loop."""
        self.difficulty = self.core.data.get_setting("VANGUARD_OVERRIDE", "difficulty", "NORMAL")
        self.variant = self.difficulty

        params = _DIFF_PARAMS.get(self.difficulty, _DIFF_PARAMS["NORMAL"])
        self._speed_scale = params["speed_scale"]
        self._spawn_scale = params["spawn_scale"]
        self._shoot_scale = params["shoot_scale"]
        self.ship_hp = params["lives"]

        if not self.sat or not self.sat.is_active:
            self.core.display.update_status("VANGUARD OVERRIDE", "SAT OFFLINE - ABORT")
            await asyncio.sleep(2)
            return "FAILURE"

        # Intro
        self.core.display.use_standard_layout()
        self.core.display.update_status("VANGUARD OVERRIDE", "POWER SYSTEMS ONLINE")
        self.core.matrix.show_icon("VANGUARD_OVERRIDE", clear=True)
        asyncio.create_task(self.core.synth.play_sequence(tones.POWER_UP, patch="SCANNER"))
        await asyncio.sleep(2.0)

        self.core.hid.reset_encoder(value=0, index=_ENC_SHIP)

        # Reset game state
        self.score = 0
        self.ship_hp = params["lives"]
        self.ship_x = _MATRIX_WIDTH // 2
        self.bullets.clear()
        self.enemies.clear()
        self.enemy_bullets.clear()
        self.emp_charge = 0.0
        self._emp_triggered = False
        self._spawn_timer = 1.0
        self._shield_cooldown_timer = 0.0
        self._invincible_timer = 0.0
        self._kill_count = 0
        self._last_wave_bonus_at = 0
        self._last_led_shield = [None] * 4
        self._last_led_weapon = [None] * 4
        self._last_tick_ms = ticks_ms()
        self._last_fire_time = 0.0

        game_running = True

        while game_running:
            now = ticks_ms()
            delta_ms = ticks_diff(now, self._last_tick_ms)

            if delta_ms >= 16:  # ~60 FPS target
                delta_s = delta_ms / 1000.0
                self._last_tick_ms = now

                # ── Read hardware ─────────────────────────────────────────────
                self._update_ship_position()
                shield_power, weapon_power = self._read_power_toggles()
                self._overloaded = (shield_power + weapon_power) >= _OVERLOAD_THRESHOLD
                self._weapon_type = self._read_weapon_type()

                # ── Timers ────────────────────────────────────────────────────
                self._shield_cooldown_timer = max(0.0, self._shield_cooldown_timer - delta_s)
                self._invincible_timer      = max(0.0, self._invincible_timer - delta_s)

                # ── EMP charge ────────────────────────────────────────────────
                if self.emp_charge < _EMP_CHARGE_MAX:
                    self.emp_charge = min(_EMP_CHARGE_MAX, self.emp_charge + _EMP_CHARGE_RATE * delta_s)

                # ── EMP trigger via momentary toggle ─────────────────────────
                if self._is_emp_triggered() and self.emp_charge >= _EMP_CHARGE_MAX:
                    self._fire_emp()

                # ── Primary fire via big red button ───────────────────────────
                if not self._overloaded:
                    if self.core.hid.is_button_pressed(_BTN_FIRE, action="held"):
                        fire_interval = max(
                            0.1,
                            _FIRE_INTERVAL_BASE - weapon_power * _FIRE_INTERVAL_STEP
                        )
                        elapsed = ticks_diff(now, int(self._last_fire_time * 1000.0)) / 1000.0
                        if elapsed >= fire_interval:
                            self._spawn_player_bullets()
                            self._last_fire_time = now / 1000.0

                # ── Spawn new enemies ─────────────────────────────────────────
                self._spawn_timer -= delta_s
                if self._spawn_timer <= 0.0:
                    self._spawn_enemy()
                    self._spawn_timer = (_SPAWN_INTERVAL_BASE / self._spawn_scale) * random.uniform(0.8, 1.2)

                # ── Enemy shooting ────────────────────────────────────────────
                shoot_prob = _ENEMY_SHOOT_CHANCE * self._shoot_scale
                for enemy in self.enemies:
                    if random.random() < shoot_prob:
                        self.enemy_bullets.append({'x': enemy['x'], 'y': enemy['y'] + 0.5})

                # ── Physics updates ───────────────────────────────────────────
                self._update_bullets(delta_s)
                self._update_enemies(delta_s)
                self._update_enemy_bullets(delta_s)

                # ── Collision: player bullets vs enemies ──────────────────────
                self._check_bullet_enemy_collisions()

                # ── Collision: enemy bullets vs ship ─────────────────────────
                hit = self._check_enemy_bullet_ship_collision()
                if hit and self._invincible_timer <= 0.0:
                    if self._shield_cooldown_timer <= 0.0 and shield_power > 0:
                        # Shields absorb the hit
                        self._shield_cooldown_timer = _SHIELD_COOLDOWN
                        asyncio.create_task(
                            self.core.synth.play_sequence(tones.UI_TICK, patch="CLICK")
                        )
                        self._invincible_timer = 0.3
                    else:
                        # No shields – lose a life
                        self.ship_hp -= 1
                        self._invincible_timer = 1.5
                        asyncio.create_task(
                            self.core.synth.play_sequence(tones.ERROR, patch="ERROR")
                        )
                        self.core.matrix.fill(Palette.RED, show=True)
                        await asyncio.sleep(0.05)
                        if self.ship_hp <= 0:
                            game_running = False
                            continue

                # ── Enemy reaches bottom row → lose a life ────────────────────
                breach = self._check_enemy_breach()
                if breach:
                    self.ship_hp -= 1
                    self._invincible_timer = 1.0
                    asyncio.create_task(
                        self.core.synth.play_sequence(tones.ERROR, patch="ERROR")
                    )
                    if self.ship_hp <= 0:
                        game_running = False
                        continue

                # ── Wave bonus ────────────────────────────────────────────────
                kills_since_last_bonus = self._kill_count - self._last_wave_bonus_at
                if kills_since_last_bonus >= 10:
                    self.score += _SCORE_WAVE
                    self._last_wave_bonus_at = self._kill_count

                # ── Update satellite displays & LEDs ──────────────────────────
                self._update_segment_display()
                self._update_sat_leds(shield_power, weapon_power)

                # ── Update OLED ───────────────────────────────────────────────
                overload_str = " OVLD!" if self._overloaded else ""
                shld_str = f"SH:{shield_power}{'*' if self._shield_cooldown_timer > 0 else ' '}"
                wpn_str  = f"WP:{weapon_power}"
                self.core.display.update_status(
                    f"SCORE:{self.score} HP:{self.ship_hp}",
                    f"{shld_str} {wpn_str}{overload_str}"
                )
                self.core.display.update_footer(f"WPN:{self._weapon_type[:3]} EMP:{int(self.emp_charge)}%")

                # ── Render matrix ─────────────────────────────────────────────
                self._render()

            await asyncio.sleep(0.01)

        # Game over
        self._send_segment("GAME OVR")
        return await self.game_over()

    # ------------------------------------------------------------------
    # Spawning helpers
    # ------------------------------------------------------------------

    def _spawn_enemy(self):
        """Spawn a new enemy at a random X position above the screen."""
        x = float(random.randint(0, _MATRIX_WIDTH - 1))
        # Harder difficulties occasionally spawn tougher enemies
        if self.difficulty == "INSANE" and random.random() < 0.3:
            hp = 3
        elif self.difficulty in ("HARD", "INSANE") and random.random() < 0.4:
            hp = 2
        else:
            hp = 1
        self.enemies.append({'x': x, 'y': -1.0, 'hp': hp})

    def _spawn_player_bullets(self):
        """Spawn player bullet(s) based on current weapon type."""
        sx = float(self.ship_x)
        sy = float(_MATRIX_HEIGHT - 2)

        if self._weapon_type == WEAPON_LASER:
            self.bullets.append({'x': sx, 'y': sy, 'dx': 0, 'type': WEAPON_LASER})

        elif self._weapon_type == WEAPON_SPREAD:
            for dx in (-1, 0, 1):
                self.bullets.append({'x': sx, 'y': sy, 'dx': dx, 'type': WEAPON_SPREAD})

        elif self._weapon_type == WEAPON_MISSILE:
            # Homing: find nearest enemy
            target_x = sx
            if self.enemies:
                nearest = min(self.enemies, key=lambda e: abs(e['x'] - sx) + abs(e['y'] - sy))
                target_x = nearest['x']
            dx_sign = 0
            if target_x < sx - 0.5:
                dx_sign = -1
            elif target_x > sx + 0.5:
                dx_sign = 1
            self.bullets.append({'x': sx, 'y': sy, 'dx': dx_sign, 'type': WEAPON_MISSILE})

        asyncio.create_task(
            self.core.synth.play_sequence([(880.0, 0.04)], patch="CLICK")
        )

    # ------------------------------------------------------------------
    # Physics updates
    # ------------------------------------------------------------------

    def _update_ship_position(self):
        """Read encoder and update ship X (clamped 0..MATRIX_WIDTH-1)."""
        enc = self.core.hid.encoder_positions[_ENC_SHIP]

        # Clamp the hardware tracking to prevent wind-up and screen-wrapping
        if enc < 0:
            self.core.hid.encoder_positions[_ENC_SHIP] = 0
            enc = 0
        elif enc >= _MATRIX_WIDTH:
            self.core.hid.encoder_positions[_ENC_SHIP] = _MATRIX_WIDTH - 1
            enc = _MATRIX_WIDTH - 1

        self.ship_x = enc

    def _update_bullets(self, delta_s):
        """Move all player bullets; remove off-screen ones."""
        keep = []
        speed = _PLAYER_BULLET_SPEED * delta_s
        for b in self.bullets:
            b['y'] -= speed
            if b['dx'] != 0:
                b['x'] += b['dx'] * delta_s * 3.0
                b['x'] = max(0.0, min(float(_MATRIX_WIDTH - 1), b['x']))
            if b['y'] >= -1.0:
                keep.append(b)
        self.bullets = keep

    def _update_enemies(self, delta_s):
        """Move all enemies downward; remove those that have breached."""
        keep = []
        speed = _ENEMY_SPEED_BASE * self._speed_scale * delta_s
        for e in self.enemies:
            e['y'] += speed
            if e['y'] < _MATRIX_HEIGHT - 1:  # breaching handled separately
                keep.append(e)
        self.enemies = keep

    def _update_enemy_bullets(self, delta_s):
        """Move enemy bullets downward; remove off-screen ones."""
        keep = []
        speed = _ENEMY_BULLET_SPEED * delta_s
        for eb in self.enemy_bullets:
            eb['y'] += speed
            if eb['y'] < _MATRIX_HEIGHT:
                keep.append(eb)
        self.enemy_bullets = keep

    # ------------------------------------------------------------------
    # Collision detection
    # ------------------------------------------------------------------

    def _check_bullet_enemy_collisions(self):
        """Check player bullets against enemies; remove both on hit."""
        bullets_to_remove = set()
        enemies_to_remove = []

        for bi, b in enumerate(self.bullets):
            bx = int(round(b['x']))
            by = int(round(b['y']))
            for e in self.enemies:
                ex = int(round(e['x']))
                ey = int(round(e['y']))
                if abs(bx - ex) <= 1 and abs(by - ey) <= 1:
                    e['hp'] -= 1
                    bullets_to_remove.add(bi)
                    if e['hp'] <= 0:
                        enemies_to_remove.append(e)
                        self.score += _SCORE_KILL
                        self._kill_count += 1
                        self.core.synth.play_note(1100.0, "UI_SELECT", duration=0.04)
                    break

        self.bullets = [b for i, b in enumerate(self.bullets) if i not in bullets_to_remove]
        for e in enemies_to_remove:
            if e in self.enemies:
                self.enemies.remove(e)

    def _check_enemy_bullet_ship_collision(self):
        """Return True (and consume the bullet) if any enemy bullet hits the ship."""
        sx = self.ship_x
        sy = _MATRIX_HEIGHT - 1
        hit = False
        keep = []
        for eb in self.enemy_bullets:
            ebx = int(round(eb['x']))
            eby = int(round(eb['y']))
            if abs(ebx - sx) <= 1 and abs(eby - sy) <= 1:
                hit = True
            else:
                keep.append(eb)
        self.enemy_bullets = keep
        return hit

    def _check_enemy_breach(self):
        """Return True and remove any enemy that has reached the bottom row."""
        breach = False
        keep = []
        for e in self.enemies:
            if e['y'] >= _MATRIX_HEIGHT - 1:
                breach = True
            else:
                keep.append(e)
        self.enemies = keep
        return breach

    # ------------------------------------------------------------------
    # EMP system
    # ------------------------------------------------------------------

    def _fire_emp(self):
        """Detonate the EMP smart bomb – clear all enemies and enemy bullets."""
        cleared = len(self.enemies) + len(self.enemy_bullets)
        self.score += cleared * _SCORE_EMP_KILL
        self.enemies.clear()
        self.enemy_bullets.clear()
        self.emp_charge = 0.0
        self._emp_triggered = False

        # Flash feedback
        self.core.matrix.fill(Palette.WHITE, show=True)
        asyncio.create_task(
            self.core.synth.play_sequence(tones.FIREBALL, patch="ALARM")
        )

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _render(self):
        """Draw the game field to the LED matrix."""
        self.core.matrix.clear()

        # --- Enemies (red, brighter = more HP) ---
        for e in self.enemies:
            ex = int(round(e['x']))
            ey = int(round(e['y']))
            if 0 <= ex < _MATRIX_WIDTH and 0 <= ey < _MATRIX_HEIGHT:
                color = Palette.RED if e['hp'] == 1 else (Palette.ORANGE if e['hp'] == 2 else Palette.WHITE)
                self.core.matrix.draw_pixel(ex, ey, color, show=False)

        # --- Enemy bullets (orange) ---
        for eb in self.enemy_bullets:
            ebx = int(round(eb['x']))
            eby = int(round(eb['y']))
            if 0 <= ebx < _MATRIX_WIDTH and 0 <= eby < _MATRIX_HEIGHT:
                self.core.matrix.draw_pixel(ebx, eby, Palette.ORANGE, show=False)

        # --- Player bullets ---
        for b in self.bullets:
            bx = int(round(b['x']))
            by = int(round(b['y']))
            if 0 <= bx < _MATRIX_WIDTH and 0 <= by < _MATRIX_HEIGHT:
                if b['type'] == WEAPON_LASER:
                    color = Palette.YELLOW
                elif b['type'] == WEAPON_SPREAD:
                    color = Palette.GREEN
                else:  # MISSILE
                    color = Palette.CYAN
                self.core.matrix.draw_pixel(bx, by, color, show=False)

        # --- Player ship (cyan; flash when invincible) ---
        if self._invincible_timer <= 0.0 or (int(self._invincible_timer * 10) % 2 == 0):
            sx = self.ship_x
            sy = _MATRIX_HEIGHT - 1
            # Ship pixel
            self.core.matrix.draw_pixel(sx, sy, Palette.CYAN, show=False)
            # Wing pixels
            if sx > 0:
                self.core.matrix.draw_pixel(sx - 1, sy, Palette.BLUE, show=False)
            if sx < _MATRIX_WIDTH - 1:
                self.core.matrix.draw_pixel(sx + 1, sy, Palette.BLUE, show=False)



    # ------------------------------------------------------------------
    # Satellite helpers
    # ------------------------------------------------------------------

    def _read_power_toggles(self):
        """Return (shield_power, weapon_power) – each 0-4."""
        shield = 0
        weapon = 0
        if not self.sat:
            return shield, weapon
        try:
            for i in range(_SHIELD_TOGGLE_START, _SHIELD_TOGGLE_END + 1):
                if self.sat.hid.latching_values[i]:
                    shield += 1
            for i in range(_WEAPON_TOGGLE_START, _WEAPON_TOGGLE_END + 1):
                if self.sat.hid.latching_values[i]:
                    weapon += 1
        except (IndexError, AttributeError):
            pass
        return shield, weapon

    def _read_weapon_type(self):
        """Read the 3-position rotary switch and return the weapon type string."""
        if not self.sat:
            return WEAPON_LASER
        try:
            rot_a = bool(self.sat.hid.latching_values[_SW_ROTARY_A])
            rot_b = bool(self.sat.hid.latching_values[_SW_ROTARY_B])
        except (IndexError, AttributeError):
            return WEAPON_LASER

        if not rot_a and not rot_b:
            return WEAPON_LASER    # centre / default
        if rot_a and not rot_b:
            return WEAPON_LASER    # POS A
        if not rot_a and rot_b:
            return WEAPON_SPREAD   # POS B
        # rot_a and rot_b
        return WEAPON_MISSILE      # POS C

    def _is_emp_triggered(self):
        """Return True if the momentary EMP toggle is held UP."""
        if not self.sat:
            return False
        try:
            return bool(self.sat.hid.is_momentary_toggled(_MT_EMP, direction="U"))
        except (IndexError, AttributeError):
            return False

    def _update_segment_display(self):
        """Update the satellite 14-segment display with EMP charge level."""
        pct = int(self.emp_charge)
        if self.emp_charge >= _EMP_CHARGE_MAX:
            self._send_segment("EMP RDY!")
        else:
            charge_str = f"CHRG:{pct:3d}%"
            self._send_segment(charge_str[:8])

    def _send_segment(self, text):
        """Send a string to the satellite 14-segment display."""
        safe = text[:8]
        if self.sat and self._last_seg_text != safe:
            try:
                self.sat.send("DSP", safe)
                self._last_seg_text = safe
            except Exception:
                pass

    def _update_sat_leds(self, shield_power, weapon_power):
        """Update satellite NeoPixel LEDs to reflect toggle power states."""
        if not self.sat:
            return

        shield_active = self._shield_cooldown_timer <= 0.0

        # Shield LEDs
        for i in range(4):
            try:
                toggle_up = bool(self.sat.hid.latching_values[_SHIELD_TOGGLE_START + i])
            except (IndexError, AttributeError):
                toggle_up = False

            if toggle_up and shield_active:
                color_name, color_idx = "GREEN", Palette.GREEN.index
            elif toggle_up and not shield_active:
                color_name, color_idx = "YELLOW", Palette.YELLOW.index
            else:
                color_name, color_idx = "OFF", Palette.OFF.index

            if self._last_led_shield[i] != color_name:
                try:
                    self.sat.send("LED", f"{_SHIELD_TOGGLE_START + i},{color_idx},0.0,1.0,2")
                    self._last_led_shield[i] = color_name
                except Exception:
                    pass

        # Weapon LEDs
        for i in range(4):
            try:
                toggle_up = bool(self.sat.hid.latching_values[_WEAPON_TOGGLE_START + i])
            except (IndexError, AttributeError):
                toggle_up = False

            if toggle_up and self._overloaded:
                color_name, color_idx = "RED", Palette.RED.index
            elif toggle_up:
                color_name, color_idx = "ORANGE", Palette.ORANGE.index
            else:
                color_name, color_idx = "OFF", Palette.OFF.index

            if self._last_led_weapon[i] != color_name:
                try:
                    self.sat.send("LED", f"{_WEAPON_TOGGLE_START + i},{color_idx},0.0,1.0,2")
                    self._last_led_weapon[i] = color_name
                except Exception:
                    pass
