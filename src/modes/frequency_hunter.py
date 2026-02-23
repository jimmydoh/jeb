# File: src/modes/frequency_hunter.py
"""Frequency Hunter – Audio-Visual Deduction Game Mode.

The player uses the rotary encoder to "tune" a hidden radio frequency.
A target icon is concealed behind random static noise.  As the player's
frequency converges on the target the static clears and the icon resolves.
Lock the signal by pressing any arcade button while the image is in focus.

Hard mode adds slow target frequency drift, forcing the player to keep
chasing the signal even after finding it.

Encoder → frequency sweep (FREQ_STEP Hz per detent)
Buttons 0-3 → Lock action (any button)
"""

import asyncio
import random

from adafruit_ticks import ticks_ms, ticks_diff

from utilities import matrix_animations
from utilities.icons import Icons
from utilities.synth_registry import Patches
from .game_mode import GameMode


class FrequencyHunterMode(GameMode):
    """Frequency Hunter – tune the rotary encoder to lock a hidden signal.

    Gameplay
    --------
    1. A random icon is chosen and assigned a random hidden frequency.
    2. The OLED shows the current band and player frequency.
    3. The LED matrix renders static noise that gradually resolves into the
       icon as the player's frequency approaches the target (clarity rises).
    4. A sonar-style synth pulse plays faster and higher as proximity grows.
    5. Once clarity is high enough, any arcade button locks the signal
       and awards points.  Running out of time triggers game over.

    Hard mode: the target frequency drifts slowly, forcing constant tracking.
    """

    # Pool of icons that can be selected as targets (keys in Icons.ICON_LIBRARY)
    SIGNAL_POOL = [
        "SKULL", "GHOST", "SWORD", "SHIELD",
        "SIMON", "PONG", "SNAKE", "SAFE",
    ]

    # Frequency sweep parameters
    FREQ_MIN = 50.0
    FREQ_MAX = 150.0
    FREQ_STEP = 0.25          # Hz per encoder detent

    # Proximity model: delta >= MAX_DELTA → clarity 0.0
    MAX_DELTA = 20.0

    # Minimum clarity required to accept a lock press
    LOCK_THRESHOLD = 0.85

    # Hard mode: target drifts this many Hz per second
    DRIFT_SPEED = 0.3

    # Scoring
    BASE_SCORE = 1000
    TIME_BONUS_MAX = 500

    # Time limit per difficulty (seconds)
    TIME_LIMITS = {
        "NORMAL": 60,
        "HARD": 45,
    }

    # Dynamic sonar pulse parameters
    SONAR_BPM_FAR = 30
    SONAR_BPM_NEAR = 200
    SONAR_PITCH_FAR = 220.0   # Hz  (A3)
    SONAR_PITCH_NEAR = 880.0  # Hz  (A5)

    def __init__(self, core):
        super().__init__(core, "FREQ HUNTER", "Tune the signal")
        self._player_freq = 100.0
        self._target_freq = 100.0
        self._drift_dir = 1.0
        self._running = False

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    async def run(self):
        """Run the Frequency Hunter game."""
        self.difficulty = self.core.data.get_setting("FREQ_HUNTER", "difficulty", "NORMAL")
        time_limit = self.TIME_LIMITS.get(self.difficulty, 60)

        self.score = 0

        # Intro splash
        self.core.display.update_status("FREQ HUNTER", "FIND THE SIGNAL")
        self.core.matrix.show_icon("FREQ_HUNTER", anim_mode="PULSE", speed=2.0)
        await asyncio.sleep(1.5)

        result = await self._play_round(time_limit)

        if result == "LOCKED":
            return await self.victory()
        return await self.game_over()

    # ------------------------------------------------------------------
    # Single round
    # ------------------------------------------------------------------

    async def _play_round(self, time_limit):
        """Play one round.  Returns 'LOCKED' or 'TIMEOUT'."""
        # Pick a random icon and assign it a hidden frequency
        icon_key = random.choice(self.SIGNAL_POOL)
        icon_data = Icons.ICON_LIBRARY.get(icon_key, Icons.DEFAULT)

        self._target_freq = round(
            random.uniform(self.FREQ_MIN + 20.0, self.FREQ_MAX - 20.0), 2
        )
        # Start the player in the middle of the dial
        self._player_freq = (self.FREQ_MIN + self.FREQ_MAX) / 2.0
        self._running = True
        self._drift_dir = 1.0 if random.random() > 0.5 else -1.0

        # Zero the encoder so position changes map to frequency changes
        self.core.hid.reset_encoder(0)
        last_encoder = self.core.hid.encoder_position(0)

        sonar_task = asyncio.create_task(self._sonar_pulse_loop())
        start_time = ticks_ms()
        result = "TIMEOUT"

        try:
            while True:
                elapsed_sec = ticks_diff(ticks_ms(), start_time) / 1000.0
                remaining = time_limit - elapsed_sec

                if remaining <= 0:
                    break

                # --- Signal drift (HARD mode) ---
                if self.difficulty == "HARD":
                    self._target_freq += self._drift_dir * self.DRIFT_SPEED * 0.02
                    # Reverse direction at the soft boundaries to keep signal in range
                    if self._target_freq >= self.FREQ_MAX - 5.0:
                        self._target_freq = self.FREQ_MAX - 5.0
                        self._drift_dir = -1.0
                    elif self._target_freq <= self.FREQ_MIN + 5.0:
                        self._target_freq = self.FREQ_MIN + 5.0
                        self._drift_dir = 1.0

                # --- Encoder → frequency ---
                curr_encoder = self.core.hid.encoder_position(0)
                delta_enc = curr_encoder - last_encoder
                if delta_enc != 0:
                    self._player_freq += delta_enc * self.FREQ_STEP
                    self._player_freq = max(self.FREQ_MIN, min(self.FREQ_MAX, self._player_freq))
                    last_encoder = curr_encoder

                # --- Proximity / clarity ---
                freq_delta = abs(self._player_freq - self._target_freq)
                clarity = max(0.0, 1.0 - (freq_delta / self.MAX_DELTA))

                # --- OLED telemetry ---
                band = "ALPHA" if self._target_freq < 100.0 else "BETA"
                self.core.display.update_header(f"BAND:{band}  T:{remaining:.0f}s")
                self.core.display.update_status(
                    f"FREQ: {self._player_freq:06.2f}",
                    f"SIG:  {'#' * int(clarity * 8)}"
                )

                # --- Matrix: static resolving into icon ---
                matrix_animations.animate_static_resolve(
                    self.core.matrix,
                    icon_data,
                    clarity
                )

                # --- Lock check ---
                if clarity >= self.LOCK_THRESHOLD:
                    for btn in range(4):
                        if self.core.hid.is_button_pressed(btn):
                            time_bonus = int((remaining / time_limit) * self.TIME_BONUS_MAX)
                            self.score = self.BASE_SCORE + time_bonus
                            result = "LOCKED"
                            break

                if result == "LOCKED":
                    break

                await asyncio.sleep(0.02)

        finally:
            self._running = False
            sonar_task.cancel()
            try:
                await sonar_task
            except asyncio.CancelledError:
                pass

        return result

    # ------------------------------------------------------------------
    # Dynamic sonar audio task
    # ------------------------------------------------------------------

    async def _sonar_pulse_loop(self):
        """Background task: play a sonar ping whose rate and pitch track proximity."""
        try:
            while self._running:
                freq_delta = abs(self._player_freq - self._target_freq)
                proximity = max(0.0, 1.0 - (freq_delta / self.MAX_DELTA))

                bpm = self.SONAR_BPM_FAR + proximity * (self.SONAR_BPM_NEAR - self.SONAR_BPM_FAR)
                pitch = self.SONAR_PITCH_FAR + proximity * (self.SONAR_PITCH_NEAR - self.SONAR_PITCH_FAR)
                beat_duration = 60.0 / bpm

                self.core.synth.play_note(pitch, Patches.SONAR, duration=beat_duration * 0.3)

                await asyncio.sleep(beat_duration)
        except asyncio.CancelledError:
            self.core.synth.release_all()
            raise
