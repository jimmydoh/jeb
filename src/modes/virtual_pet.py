# File: src/modes/virtual_pet.py
"""Tamagotchi-Style Virtual Pet Mode."""

import asyncio
from adafruit_ticks import ticks_ms, ticks_diff

from .base import BaseMode


class VirtualPet(BaseMode):
    """
    Tamagotchi-Style Virtual Pet Mode.

    An interactive idle mode featuring an 8-bit animated cat with stat
    tracking (hunger and happiness), hardware input interaction, and
    retro audio feedback.

    States:
        IDLE     - Cat sitting normally, gentle pulse animation.
        EATING   - Cat eating animation, triggered by Button 0 (feed).
        SLEEPING - Cat sleeping when idle long enough and happiness is high.
        HUNGRY   - Alert state when hunger exceeds threshold.
        PLAYING  - Cat playing after Button 1 (play) is pressed.

    Controls:
        Button 0 (tap)  - Feed the cat (reduces hunger, triggers EATING).
        Button 1 (tap)  - Play with the cat (boosts happiness, triggers PLAYING).
        Button 2 (tap)  - Toggle between status message and live stats display.
        Button 3 (hold) - Exit mode (handled automatically by BaseMode).

    Audio Cues:
        Meow sequence    - Plays when the cat is fed or played with.
        Alert sequence   - Periodic chime when the cat is hungry.
        Sleep tone       - Soft low tone played when the cat falls asleep.
    """

    # --- State Constants ---
    STATE_IDLE = "IDLE"
    STATE_EATING = "EATING"
    STATE_SLEEPING = "SLEEPING"
    STATE_HUNGRY = "HUNGRY"
    STATE_PLAYING = "PLAYING"

    # --- Stat thresholds ---
    HUNGER_THRESHOLD = 70   # Above this = hungry alert state
    HAPPY_LOW = 30          # Below this = sad (display note)

    # --- Timing (milliseconds) ---
    HUNGER_TICK_MS = 20000  # Hunger increases every 20 seconds
    HAPPY_TICK_MS  = 30000  # Happiness decreases every 30 seconds
    ACTION_DUR_MS  = 3000   # How long EATING / PLAYING states last
    SLEEP_IDLE_MS  = 15000  # Fall asleep after 15 s of inactivity
    ALERT_BEEP_MS  = 8000   # Re-alert every 8 s when hungry

    # --- Retro audio sequences ---
    # Meow: a rising then falling chirp used on feeding / playing
    _MEOW = {
        "bpm": 60,
        "sequence": [
            (600, 0.06), (900, 0.10), (700, 0.06), ("-", 0.04),
        ],
    }
    # Alert chime: two short urgent beeps
    _ALERT = {
        "bpm": 60,
        "sequence": [
            (880, 0.07), ("-", 0.04), (880, 0.07), ("-", 0.04),
        ],
    }
    # Sleep tone: a single soft low note
    _SLEEP_TONE = {
        "bpm": 60,
        "sequence": [
            (220, 0.20), ("-", 0.10), (196, 0.30),
        ],
    }

    def __init__(self, core):
        super().__init__(core, "VIRTUAL PET", "Tamagotchi Cat")

        # --- Pet Stats ---
        self.hunger    = 20    # 0 = full, 100 = starving
        self.happiness = 80    # 0 = miserable, 100 = ecstatic

        # --- State Machine ---
        self.state = self.STATE_IDLE

        # --- Internal timers (set in run()) ---
        self._state_start_ms   = 0
        self._last_input_ms    = 0
        self._last_hunger_ms   = 0
        self._last_happy_ms    = 0
        self._last_alert_ms    = 0

        # --- Display toggle ---
        self._show_stats = False

    # ------------------------------------------------------------------
    # BaseMode entry-point
    # ------------------------------------------------------------------

    async def run(self):
        """Main virtual pet loop."""
        now = ticks_ms()
        self._state_start_ms = now
        self._last_input_ms  = now
        self._last_hunger_ms = now
        self._last_happy_ms  = now
        self._last_alert_ms  = now

        self.core.display.update_status("VIRTUAL PET", "MEOW!")
        self._draw_state()

        while True:
            now = ticks_ms()
            self._handle_input(now)
            self._update_stats(now)
            self._update_state(now)
            self._update_display()
            await self._check_audio(now)
            await asyncio.sleep(0.05)

    # ------------------------------------------------------------------
    # Input
    # ------------------------------------------------------------------

    def _handle_input(self, now):
        """Process button taps."""
        if self.core.hid.is_button_pressed(0, action="tap"):
            self._feed(now)
        elif self.core.hid.is_button_pressed(1, action="tap"):
            self._play(now)
        elif self.core.hid.is_button_pressed(2, action="tap"):
            self._show_stats = not self._show_stats
            self._last_input_ms = now

    def _feed(self, now):
        """Feed the cat – reduces hunger, triggers EATING state."""
        self.hunger    = max(0,   self.hunger - 30)
        self.happiness = min(100, self.happiness + 10)
        self.state     = self.STATE_EATING
        self._state_start_ms = now
        self._last_input_ms  = now
        self.core.display.update_status("VIRTUAL PET", "NOM NOM!")
        self.core.buzzer.play_sequence(self._MEOW)
        self._draw_state()

    def _play(self, now):
        """Play with the cat – boosts happiness, triggers PLAYING state."""
        self.happiness = min(100, self.happiness + 25)
        self.hunger    = min(100, self.hunger    +  5)
        self.state     = self.STATE_PLAYING
        self._state_start_ms = now
        self._last_input_ms  = now
        self.core.display.update_status("VIRTUAL PET", "PLAY TIME!")
        self.core.buzzer.play_sequence(self._MEOW)
        self._draw_state()

    # ------------------------------------------------------------------
    # Stat decay
    # ------------------------------------------------------------------

    def _update_stats(self, now):
        """Decay stats over time."""
        if ticks_diff(now, self._last_hunger_ms) >= self.HUNGER_TICK_MS:
            self.hunger = min(100, self.hunger + 5)
            self._last_hunger_ms = now

        if ticks_diff(now, self._last_happy_ms) >= self.HAPPY_TICK_MS:
            self.happiness = max(0, self.happiness - 3)
            self._last_happy_ms = now

    # ------------------------------------------------------------------
    # State machine
    # ------------------------------------------------------------------

    def _update_state(self, now):
        """Drive state transitions."""
        if self.state in (self.STATE_EATING, self.STATE_PLAYING):
            # Action states expire after ACTION_DUR_MS
            if ticks_diff(now, self._state_start_ms) >= self.ACTION_DUR_MS:
                self.state = self.STATE_IDLE
                self._state_start_ms = now
                self._draw_state()

        elif self.state == self.STATE_IDLE:
            if self.hunger >= self.HUNGER_THRESHOLD:
                self.state = self.STATE_HUNGRY
                self._state_start_ms = now
                self.core.display.update_status("VIRTUAL PET", "FEED ME!")
                self._draw_state()
            elif ticks_diff(now, self._last_input_ms) >= self.SLEEP_IDLE_MS:
                self.state = self.STATE_SLEEPING
                self._state_start_ms = now
                self.core.display.update_status("VIRTUAL PET", "ZZZ...")
                self.core.buzzer.play_sequence(self._SLEEP_TONE)
                self._draw_state()

        elif self.state == self.STATE_SLEEPING:
            # Wake up if very hungry
            if self.hunger >= self.HUNGER_THRESHOLD:
                self.state = self.STATE_HUNGRY
                self._state_start_ms = now
                self.core.display.update_status("VIRTUAL PET", "FEED ME!")
                self._draw_state()
            # Wake up on any interaction (handled by _handle_input resetting _last_input_ms)
            elif ticks_diff(now, self._last_input_ms) < self.SLEEP_IDLE_MS:
                self.state = self.STATE_IDLE
                self._state_start_ms = now
                self.core.display.update_status("VIRTUAL PET", "WAKE UP!")
                self._draw_state()

        elif self.state == self.STATE_HUNGRY:
            # Return to idle once hunger is satisfied
            if self.hunger < self.HUNGER_THRESHOLD:
                self.state = self.STATE_IDLE
                self._state_start_ms = now
                self.core.display.update_status("VIRTUAL PET", "THANKS!")
                self._draw_state()

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _draw_state(self):
        """Display the cat sprite for the current state."""
        if self.state == self.STATE_IDLE:
            self.core.matrix.show_icon("CAT_IDLE", anim_mode="PULSE", speed=0.5)
        elif self.state == self.STATE_EATING:
            self.core.matrix.show_icon("CAT_EAT", anim_mode="BLINK", speed=2.0)
        elif self.state == self.STATE_SLEEPING:
            self.core.matrix.show_icon("CAT_SLEEP", anim_mode="PULSE", speed=0.2)
        elif self.state == self.STATE_HUNGRY:
            self.core.matrix.show_icon("CAT_IDLE", anim_mode="BLINK", speed=1.0)
        elif self.state == self.STATE_PLAYING:
            self.core.matrix.show_icon("CAT_WALK", anim_mode="ANIMATED", speed=8)

    def _update_display(self):
        """Refresh OLED display when stats view is active."""
        if self._show_stats:
            self.core.display.update_status(
                f"HUNGER: {self.hunger}%",
                f"HAPPY:  {self.happiness}%",
            )

    # ------------------------------------------------------------------
    # Audio
    # ------------------------------------------------------------------

    async def _check_audio(self, now):
        """Fire periodic alert chimes when the cat is hungry."""
        if self.state == self.STATE_HUNGRY:
            if ticks_diff(now, self._last_alert_ms) >= self.ALERT_BEEP_MS:
                self._last_alert_ms = now
                self.core.buzzer.play_sequence(self._ALERT)
