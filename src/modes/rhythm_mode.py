"""Rhythm Game Mode - NEON BEATS time-synced rhythm game for the JEB framework.

Uses a master time anchor (ticks_ms) to synchronise falling-note visuals with
background audio streamed from the SD card.  All note positioning and hit
detection are calculated from elapsed wall-clock time so that display frame
rate jitter never drifts against the music.

Beatmap files are pre-compiled JSON arrays (one entry per note) and are loaded
from the SD card at startup.  A companion PC script (examples/extract_beatmap.py)
converts Clone Hero / MIDI charts into the required format.

Beatmap entry format::

    {"time": <ms_from_song_start>, "col": <0-7>, "state": "WAITING"}

Button → column mapping (4 physical buttons on CORE):
    Button 0 → col 0
    Button 1 → col 2
    Button 2 → col 5
    Button 3 → col 7
"""

import asyncio
import json
from adafruit_ticks import ticks_ms, ticks_diff

from utilities.palette import Palette
from .game_mode import GameMode


class RhythmMode(GameMode):
    """
    Rhythm Game Mode - NEON BEATS.

    Features:
    - Master time anchor: all rendering and hit detection are elapsed-time based
    - Falling notes mapped to 4 matrix columns driven by 4 hardware buttons
    - PERFECT / GOOD / MISS grade windows
    - Beatmap loaded from a pre-compiled JSON file on the SD card
    - Background WAV played via AudioManager CH_ATMO; synth hits via SynthManager
    - Configurable latency offset to calibrate SD card / DAC start-up delay
    """

    METADATA = {
        "id": "RHYTHM",
        "name": "NEON BEATS",
        "icon": "RHYTHM",
        "requires": ["CORE"],
        "settings": [
            {
                "key": "difficulty",
                "label": "DIFF",
                "options": ["EASY", "NORMAL", "HARD"],
                "default": "NORMAL"
            },
            {
                "key": "latency",
                "label": "LATENCY",
                "options": ["0", "20", "45", "70", "100"],
                "default": "45"
            }
        ]
    }

    # Button index → matrix column mapping (4 CORE buttons)
    BUTTON_COLUMNS = [0, 2, 5, 7]

    # Hit-zone row (bottom of the 8-row matrix)
    HIT_ZONE_ROW = 7

    # How long a note takes to travel from top (row 0) to hit zone (row 7)
    FALL_DURATION_MS = 1000

    # Hit detection windows in milliseconds
    PERFECT_WINDOW_MS = 50
    GOOD_WINDOW_MS = 150

    def __init__(self, core):
        super().__init__(core, "NEON BEATS", "Rhythm Game")

        self.fall_duration_ms = self.FALL_DURATION_MS
        self.hit_window_ms = self.GOOD_WINDOW_MS
        self.latency_offset_ms = 45

        self.start_anchor = 0
        self.beatmap = []
        self.combo = 0

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    async def run(self):
        """Load beatmap, start audio, and run the main game loop."""

        # Read settings
        self.difficulty = self.core.data.get_setting("RHYTHM", "difficulty", "NORMAL")
        latency_str = self.core.data.get_setting("RHYTHM", "latency", "45")
        self.latency_offset_ms = int(latency_str)

        if self.difficulty == "EASY":
            self.hit_window_ms = 200
            self.fall_duration_ms = 1400
        elif self.difficulty == "HARD":
            self.hit_window_ms = 100
            self.fall_duration_ms = 800

        # Load beatmap from SD card
        self.core.display.update_status("NEON BEATS", "LOADING...")
        beatmap_path = "/sd/data/rhythm/beatmap.json"
        try:
            with open(beatmap_path, "r") as f:
                self.beatmap = json.load(f)
        except OSError:
            # No beatmap found – use a built-in demo beatmap so the mode is
            # still playable without an SD card during development / testing.
            self.beatmap = self._demo_beatmap()

        if not self.beatmap:
            self.core.display.update_status("NEON BEATS", "NO BEATMAP")
            await asyncio.sleep(2)
            return "FAILURE"

        # Sort beatmap by time to ensure correct ordering
        self.beatmap.sort(key=lambda n: n["time"])

        # Reset per-run state
        self.score = 0
        self.combo = 0
        for note in self.beatmap:
            note["state"] = "WAITING"

        # Start background music, then immediately set the time anchor
        self.core.display.update_status("NEON BEATS", "GET READY")
        await asyncio.sleep(0.5)

        await self.core.audio.play(
            "audio/rhythm/track.wav",
            self.core.audio.CH_ATMO,
            level=0.8
        )

        # Master time anchor – set immediately after play() is called
        self.start_anchor = ticks_ms()

        self.core.hid.flush()
        self.core.display.update_status("NEON BEATS", f"SCORE: {self.score}")

        # Main game loop
        end_time_ms = self.beatmap[-1]["time"] + 3000
        while True:
            now = ticks_ms()
            elapsed = ticks_diff(now, self.start_anchor)
            current_song_time = elapsed - self.latency_offset_ms

            # --- Input handling ---
            pressed_cols = self._get_pressed_columns()
            for col in pressed_cols:
                self._process_hit(current_song_time, col)

            # --- Rendering ---
            self._render(current_song_time)

            # --- End condition ---
            if current_song_time > end_time_ms:
                return await self.victory()

            await asyncio.sleep(0.016)  # ~60 fps target

    # ------------------------------------------------------------------
    # Hit processing
    # ------------------------------------------------------------------

    def _get_pressed_columns(self):
        """Return a list of matrix columns for buttons that were just tapped."""
        pressed = []
        for btn_idx, col in enumerate(self.BUTTON_COLUMNS):
            if self.core.hid.is_button_pressed(btn_idx, action="tap"):
                pressed.append(col)
        return pressed

    def _process_hit(self, current_time, col):
        """Find the closest waiting note in *col* and grade the hit."""
        closest_note = None
        smallest_diff = float('inf')

        for note in self.beatmap:
            if note["col"] == col and note["state"] == "WAITING":
                diff = abs(current_time - note["time"])
                if diff < smallest_diff:
                    smallest_diff = diff
                    closest_note = note

        if closest_note is not None and smallest_diff <= self.hit_window_ms:
            closest_note["state"] = "HIT"
            self.combo += 1

            if smallest_diff <= self.PERFECT_WINDOW_MS:
                self.score += 100
                self.core.leds.set_pixel(col % 4, Palette.GREEN)
                self.core.synth.play_note(880.0, "UI_SELECT", duration=0.05)
            else:
                self.score += 50
                self.core.leds.set_pixel(col % 4, Palette.YELLOW)
                self.core.synth.play_note(660.0, "UI_SELECT", duration=0.05)

            self.core.display.update_status("NEON BEATS", f"SCORE: {self.score}")
        else:
            # Miss / stray press
            self.combo = 0
            self.core.leds.set_pixel(col % 4, Palette.RED)

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _render(self, current_time):
        """Draw notes and hit zone on the LED matrix."""
        self.core.matrix.clear()

        # Draw hit-zone markers at the bottom row
        for col in self.BUTTON_COLUMNS:
            self.core.matrix.draw_pixel(col, self.HIT_ZONE_ROW, Palette.WHITE)

        for note in self.beatmap:
            if note["state"] != "WAITING":
                continue

            spawn_time = note["time"] - self.fall_duration_ms

            if spawn_time <= current_time <= note["time"]:
                # Map elapsed fall time to a y position (0 → HIT_ZONE_ROW)
                progress = (current_time - spawn_time) / self.fall_duration_ms
                y_pos = int(progress * self.HIT_ZONE_ROW)
                self.core.matrix.draw_pixel(note["col"], y_pos, Palette.CYAN)

            elif current_time > note["time"] + self.hit_window_ms:
                # Note has passed without being hit
                note["state"] = "MISSED"
                self.combo = 0
                self.core.synth.play_note(150.0, "UI_ERROR", duration=0.1)

    # ------------------------------------------------------------------
    # Demo beatmap (used when no SD card beatmap is found)
    # ------------------------------------------------------------------

    @staticmethod
    def _demo_beatmap():
        """Return a small built-in beatmap for testing without an SD card."""
        return [
            {"time": 2000, "col": 0,  "state": "WAITING"},
            {"time": 2500, "col": 2,  "state": "WAITING"},
            {"time": 3000, "col": 5,  "state": "WAITING"},
            {"time": 3500, "col": 7,  "state": "WAITING"},
            {"time": 4000, "col": 0,  "state": "WAITING"},
            {"time": 4000, "col": 5,  "state": "WAITING"},
            {"time": 4500, "col": 2,  "state": "WAITING"},
            {"time": 4500, "col": 7,  "state": "WAITING"},
            {"time": 5000, "col": 0,  "state": "WAITING"},
            {"time": 5500, "col": 5,  "state": "WAITING"},
            {"time": 6000, "col": 2,  "state": "WAITING"},
            {"time": 6000, "col": 7,  "state": "WAITING"},
        ]
