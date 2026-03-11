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

    async def run_tutorial(self):
        """
        A guided, non-interactive demonstration of Frequency Hunter.

        The Voiceover Script (audio/tutes/freq_tute.wav) ~ 33 seconds:
            [0:00] "Welcome to Frequency Hunter. You must intercept and lock onto rogue transmissions."
            [0:06] "Turn the dial to sweep across the radio spectrum."
            [0:10] "Listen to the audio and watch the signal strength on the matrix."
            [0:16] "When the waveform peaks and the tone is pure, you've found the target."
            [0:22] "Press button one to lock in the frequency before the signal fades."
            [0:27] "Intercept as many transmissions as you can before time runs out. Good luck!"
            [0:33] (End of file)
        """
        await self.core.clean_slate()
        self.game_state = "TUTORIAL"

        # 1. Start the voiceover track
        self.core.audio.play("audio/tutes/freq_tute.wav", bus_id=self.core.audio.CH_VOICE)

        # [0:00 - 0:06] "Welcome to Frequency Hunter..."
        self.core.display.update_status("FREQ HUNTER", "INTERCEPT SIGNALS")

        # Draw a static "searching" pulse
        for _ in range(12):
            self.core.matrix.clear()
            h = 8 + int(4 * math.sin(ticks_ms() / 200))
            for x in range(16):
                self.core.matrix.draw_pixel(x, h, Palette.CYAN, show=False)
            self.core.matrix.show_frame()
            await asyncio.sleep(0.5)

        # [0:06 - 0:10] "Turn the dial to sweep across the radio spectrum."
        self.core.display.update_status("TUNING", "TURN DIAL TO SWEEP")
        await asyncio.sleep(4.0)

        # [0:10 - 0:16] "Listen to the audio and watch the signal strength..."
        self.core.display.update_status("TUNING", "WATCH & LISTEN")

        # Simulate sweeping toward a target frequency
        target_freq = 50
        current_freq = 10

        # We will puppeteer the current_freq moving towards the target
        while current_freq < target_freq:
            current_freq += 1
            distance = abs(target_freq - current_freq)

            # 1. Visual Feedback: Waveform gets taller and less "noisy" as distance decreases
            self.core.matrix.clear()
            amplitude = 7 - min(7, int(distance / 5)) # Peaks at 7 when distance is 0
            noise_level = min(4, int(distance / 8))

            for x in range(16):
                # Base sine wave
                y = 8 + int(amplitude * math.sin(x * 0.8 + (ticks_ms() / 100)))
                # Add static/noise based on distance
                if noise_level > 0:
                    y += random.randint(-noise_level, noise_level)

                # Keep within bounds
                y = max(0, min(15, y))

                # Color shifts from Red (far) to Yellow (close) to Green (locked)
                if distance == 0:
                    color = Palette.GREEN
                elif distance < 15:
                    color = Palette.YELLOW
                else:
                    color = Palette.RED

                self.core.matrix.draw_pixel(x, y, color, show=False)

            self.core.matrix.show_frame()

            # 2. Audio Feedback: Pitch gets closer to a target pitch (e.g., 880Hz)
            # You might use your SynthManager here if you have one, or just the buzzer
            if distance % 3 == 0: # Don't spam the I2C bus every frame
                pitch = 880 - (distance * 10)
                # Play a short blip that rises in pitch
                self.core.buzzer.play_sequence([(pitch, 0.05)])

            await asyncio.sleep(0.15) # Speed of the dial sweeping

        # [0:16 - 0:22] "When the waveform peaks and the tone is pure..."
        self.core.display.update_status("SIGNAL FOUND!", "HOLD POSITION")

        # Hold the "Perfect Lock" visual and audio for a few seconds
        for _ in range(30):
            self.core.matrix.clear()
            for x in range(16):
                y = 8 + int(7 * math.sin(x * 0.8 + (ticks_ms() / 100)))
                self.core.matrix.draw_pixel(x, max(0, min(15, y)), Palette.GREEN, show=False)
            self.core.matrix.show_frame()

            if _ % 10 == 0:
                self.core.buzzer.play_sequence([(880, 0.1)]) # Pure, steady target tone

            await asyncio.sleep(0.2)

        # [0:22 - 0:27] "Press button one to lock in the frequency..."
        self.core.display.update_status("LOCK SIGNAL", "PRESS B1 TO LOCK")

        # Flash B1 LED using your updated LED manager method
        self.core.leds.flash_led(0, Palette.GREEN, duration=3.0, speed=0.15)
        await asyncio.sleep(2.0)

        # Simulate button press and success state
        self.core.buzzer.play_sequence(tones.SAVE_OK)
        self.core.matrix.fill(Palette.GREEN, show=True)
        self.core.display.update_header("SIGNAL LOCKED!")
        self.core.display.update_status("SCORE +100", "")
        await asyncio.sleep(2.0)

        # [0:27 - 0:33] "Intercept as many transmissions... Good luck!"
        self.core.display.update_header("-FREQ HUNTER-")
        self.core.display.update_status("WATCH THE CLOCK", "GOOD LUCK!")
        self.core.matrix.show_icon("CLOCK", anim_mode="PULSE", speed=1.0)

        # Wait out the rest of the audio
        await asyncio.sleep(6.0)

        # Clean up and return to the menu
        await self.core.clean_slate()
        return "TUTORIAL_COMPLETE"

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
        icon_data = Icons.get(icon_key)

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
